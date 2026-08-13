"""
Sync Meta (Facebook) Marketing API data into PostgreSQL for analysis in DBeaver.

Requires env:
  META_ACCESS_TOKEN   Long-lived user or system token with ads_read (and business permissions as needed)
  META_AD_ACCOUNT_ID  Numeric ID or act_1234567890

Optional:
  META_API_VERSION    Default v21.0
  META_DATE_PRESET    Default last_30d. Valores válidos: last_7d, last_30d, last_90d, maximum, last_year, etc. (Meta no admite last_365d; se mapea a maximum).
  META_TIME_RANGE_SINCE / META_TIME_RANGE_UNTIL  YYYY-MM-DD (ambas obligatorias). Usa time_range en la API.
    Sin META_APPEND_ROLLING_PRESET, cada sync solo pide ese rango (ej. 2025) y no actualiza el mes actual.
  META_APPEND_ROLLING_PRESET  Ej. last_30d: si usas time_range, hace una 2ª petición con este date_preset para mezclar datos recientes.
  META_INSIGHTS_LEVEL Default ad  (campaign | adset | ad)
  META_INSIGHTS_INCLUDE_VIDEO  Default 0. Si 1, pide métricas de vídeo (más pesadas; pueden provocar error API #1).
  META_INSIGHTS_TIME_CHUNK_DAYS  Default 31. Parte time_range / presets largos en ventanas de a lo sumo N días (evita "reduce the amount of data").
  META_INSIGHTS_MAX_CHUNKS  Default 36. Con maximum/data_maximum, máximo de ventanas hacia atrás (~3 años si chunk=31).
  META_INSIGHTS_PAGE_LIMIT  Default 25. Límite por página en /insights (más bajo = menos carga por respuesta).
  META_SYNC_MARKETING_COSTS_TABLE  Default 1: tras insights, rellena tabla marketing_costs desde meta_ads_insights. 0 para desactivar.
  META_INSIGHTS_SYNC_REGION  Default 1: además de los insights normales, pide una 2ª pasada con
    breakdowns=region y la guarda en meta_ads_insights_region (una fila por anuncio x día x región,
    ver vista v_meta_ads_by_region). Duplica las llamadas a /insights; 0 para desactivar.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from db.connection import get_connection
from db.migrate import ensure_schema
from db.utils import now_utc, upsert_many


def _sync_marketing_costs_from_meta() -> None:
    """
    Tabla legado `marketing_costs`: el ETL solo escribe en meta_*; esta función
    alinea marketing_costs con meta_ads_insights tras cada sync.
    """
    flag = (_env("META_SYNC_MARKETING_COSTS_TABLE", "1") or "1").lower()
    if flag in ("0", "false", "no"):
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'marketing_costs'
                """
            )
            if cur.fetchone() is None:
                print("[meta_ads] marketing_costs: tabla no existe, omitiendo sync")
                return
            cur.execute("TRUNCATE TABLE marketing_costs RESTART IDENTITY")
            cur.execute(
                """
                INSERT INTO marketing_costs (
                    cost_date, ad_name, campaign_name, adset_name,
                    amount_spent, currency, reach, impressions, clicks, purchases,
                    raw, created_at, updated_at
                )
                SELECT
                    i.date_start,
                    COALESCE(a.name, ''),
                    COALESCE(c.name, ''),
                    COALESCE(s.name, ''),
                    COALESCE(i.spend, 0),
                    COALESCE(i.raw->>'account_currency', 'CLP'),
                    i.reach::integer,
                    i.impressions::integer,
                    i.clicks::integer,
                    LEAST(
                        2147483647,
                        GREATEST(
                            0,
                            ROUND(
                                COALESCE(
                                    meta_fn_action_types_sum(
                                        i.actions,
                                        ARRAY[
                                            'purchase',
                                            'omni_purchase',
                                            'offsite_conversion.fb_pixel_purchase',
                                            'onsite_conversion.purchase'
                                        ]
                                    ),
                                    0
                                )
                            )::bigint
                        )
                    )::integer,
                    i.raw,
                    now(), now()
                FROM meta_ads_insights i
                LEFT JOIN meta_ads a ON a.id = i.ad_id
                LEFT JOIN meta_campaigns c ON c.id = i.campaign_id
                LEFT JOIN meta_adsets s ON s.id = i.adset_id
                """
            )
            n = cur.rowcount if cur.rowcount >= 0 else 0
        conn.commit()
    print(f"[meta_ads] marketing_costs: sincronizada ({n} filas desde meta_ads_insights)")


def _meta_api_error_message(code: Any, msg: str) -> str:
    base = f"Meta API error {code}: {msg}"
    sm = str(msg).lower() if msg else ""
    if code == 190 and "parse" in sm:
        return (
            f"{base} — Revisa META_ACCESS_TOKEN: una sola línea, sin comillas extra ni espacios raros al inicio/fin; "
            f"regenera el token si hace falta."
        )
    if code == 190 or ("expired" in sm and "token" in sm):
        return (
            f"{base} — Token caducado o inválido. Genera uno nuevo en el Explorador Graph "
            f"(permiso ads_read) y actualiza META_ACCESS_TOKEN en .env / Railway. "
            f"Los tokens de corta duración caducan en ~1–2 h; en producción usa token de larga duración."
        )
    if code == 1 and "reduce" in sm and "data" in sm:
        return (
            f"{base} — La consulta de insights es demasiado grande. "
            f"Prueba: META_INSIGHTS_LEVEL=adset o campaign, "
            f"META_INSIGHTS_TIME_CHUNK_DAYS más bajo (p. ej. 14), "
            f"dejar META_INSIGHTS_INCLUDE_VIDEO=0, o un META_DATE_PRESET más corto."
        )
    return base


def _normalize_access_token(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    t = str(raw).strip()
    if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")):
        t = t[1:-1].strip()
    if "\n" in t or "\r" in t:
        print("[meta_ads] ADVERTENCIA: META_ACCESS_TOKEN contiene saltos de línea; debe ser una sola línea.")
    return t or None


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v is None or str(v).strip() == "":
        return default
    return str(v).strip()


# date_preset permitido por Meta en /insights (error #100 si falla)
_VALID_INSIGHT_DATE_PRESETS = frozenset(
    {
        "today",
        "yesterday",
        "this_month",
        "last_month",
        "this_quarter",
        "maximum",
        "data_maximum",
        "last_3d",
        "last_7d",
        "last_14d",
        "last_28d",
        "last_30d",
        "last_90d",
        "last_week_mon_sun",
        "last_week_sun_sat",
        "last_quarter",
        "last_year",
        "this_week_mon_today",
        "this_week_sun_today",
        "this_year",
    }
)

# Valores que la gente suele poner pero Meta no acepta en insights
_ALIAS_INSIGHT_DATE_PRESET = {
    "last_365d": "maximum",
    "last_60d": "last_90d",
    "last_180d": "last_90d",
}


def _normalize_insight_date_preset(value: str, env_name: str) -> str:
    v = (value or "last_30d").strip()
    key = v.lower()
    if key in _ALIAS_INSIGHT_DATE_PRESET:
        repl = _ALIAS_INSIGHT_DATE_PRESET[key]
        print(
            f"[meta_ads] AVISO: {env_name}={v!r} no es válido en Insights API; "
            f"usando {repl!r}. Para más histórico usa maximum/data_maximum o META_TIME_RANGE_*."
        )
        v = repl
    if v in _VALID_INSIGHT_DATE_PRESETS:
        return v
    raise RuntimeError(
        f"{env_name}={value!r} no es un date_preset válido para insights. "
        f"Ej.: last_7d, last_30d, last_90d, maximum, last_year. "
        f"(Lista oficial en error #100 de la API Meta.)"
    )


# Presets que suelen requerir varias ventanas time_range (error #1 si una sola petición)
_CHUNKED_DATE_PRESETS = frozenset(
    {
        "maximum",
        "data_maximum",
        "last_year",
        "last_90d",
        "last_quarter",
        "this_year",
        "this_quarter",
    }
)


def _chunk_inclusive_ranges(
    since: dt.date, until: dt.date, max_span_days: int
) -> List[tuple[dt.date, dt.date]]:
    """Parte [since, until] en ventanas disjuntas de a lo sumo max_span_days (inclusive)."""
    if since > until:
        return []
    max_span_days = max(1, max_span_days)
    out: List[tuple[dt.date, dt.date]] = []
    cur_start = since
    while cur_start <= until:
        cur_end = min(until, cur_start + dt.timedelta(days=max_span_days - 1))
        out.append((cur_start, cur_end))
        cur_start = cur_end + dt.timedelta(days=1)
    return out


def _backward_time_windows(
    total_days: int, chunk_days: int, end: dt.date
) -> List[tuple[dt.date, dt.date]]:
    """Ventanas desde end hacia atrás que cubren total_days días (inclusive), sin solapar."""
    chunks: List[tuple[dt.date, dt.date]] = []
    remaining = max(0, total_days)
    cur_end = end
    while remaining > 0:
        span = min(chunk_days, remaining)
        cur_start = cur_end - dt.timedelta(days=span - 1)
        chunks.append((cur_start, cur_end))
        remaining -= span
        cur_end = cur_start - dt.timedelta(days=1)
    return list(reversed(chunks))


def _backward_time_windows_unbounded(
    chunk_days: int, end: dt.date, n_chunks: int
) -> List[tuple[dt.date, dt.date]]:
    chunks: List[tuple[dt.date, dt.date]] = []
    cur_end = end
    for _ in range(max(1, n_chunks)):
        cur_start = cur_end - dt.timedelta(days=chunk_days - 1)
        chunks.append((cur_start, cur_end))
        cur_end = cur_start - dt.timedelta(days=1)
    return list(reversed(chunks))


def _approx_preset_span_days(preset: str, today: dt.date) -> Optional[int]:
    """Días aproximados del preset; None = histórico largo (maximum / data_maximum)."""
    if preset in ("maximum", "data_maximum"):
        return None
    if preset == "last_year":
        return 366
    if preset == "last_90d":
        return 90
    if preset == "last_quarter":
        return 93
    if preset == "this_year":
        return (today - dt.date(today.year, 1, 1)).days + 1
    if preset == "this_quarter":
        q0 = (today.month - 1) // 3
        start_m = q0 * 3 + 1
        start = dt.date(today.year, start_m, 1)
        return (today - start).days + 1
    raise ValueError(f"_approx_preset_span_days: preset inesperado {preset!r}")


def normalize_ad_account_id(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("act_"):
        return raw
    return f"act_{raw}"


def _num(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _int(v: Any) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, int):
        return v
    try:
        return int(float(str(v).replace(",", "")))
    except (TypeError, ValueError):
        return None


def _parse_date(s: Any) -> Optional[dt.date]:
    if s is None:
        return None
    if isinstance(s, dt.date) and not isinstance(s, dt.datetime):
        return s
    text = str(s).strip()[:10]
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        return None


class MetaMarketingClient:
    def __init__(self, access_token: str, api_version: str) -> None:
        self.access_token = access_token
        self.api_version = api_version.rstrip("/")
        self.base = f"https://graph.facebook.com/{self.api_version}"

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        p = dict(params or {})
        p["access_token"] = self.access_token
        url = f"{self.base}{path}" if path.startswith("/") else f"{self.base}/{path}"
        r = requests.get(url, params=p, timeout=120)
        try:
            data = r.json()
        except Exception:
            raise RuntimeError(
                f"Meta API devolvió respuesta no-JSON (status {r.status_code}): {r.text[:300]}"
            )
        if r.status_code >= 400 or "error" in data:
            err = data.get("error", {})
            msg = err.get("message", r.text)
            code = err.get("code", r.status_code)
            raise RuntimeError(_meta_api_error_message(code, str(msg)))
        return data

    def paged(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        page_limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        params = dict(params or {})
        if page_limit is not None:
            params["limit"] = page_limit
        else:
            params.setdefault("limit", 100)
        next_url: Optional[str] = None
        while True:
            if next_url:
                time.sleep(0.35)
                r = requests.get(next_url, timeout=120)
                try:
                    chunk = r.json()
                except Exception:
                    raise RuntimeError(
                        f"Meta API devolvió respuesta no-JSON en paginación (status {r.status_code}): {r.text[:300]}"
                    )
                if r.status_code >= 400 or "error" in chunk:
                    err = chunk.get("error", {})
                    raise RuntimeError(
                        _meta_api_error_message(
                            err.get("code"), str(err.get("message", r.text))
                        )
                    )
            else:
                chunk = self._get(path, params)
            out.extend(chunk.get("data") or [])
            paging = chunk.get("paging") or {}
            next_url = paging.get("next")
            if not next_url:
                break
        return out


def _row_campaign(account_id: str, o: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(o.get("id", "")),
        "ad_account_id": account_id,
        "name": o.get("name"),
        "status": o.get("status"),
        "objective": o.get("objective"),
        "raw": o,
    }


def _row_adset(account_id: str, o: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(o.get("id", "")),
        "ad_account_id": account_id,
        "campaign_id": str(o["campaign_id"]) if o.get("campaign_id") else None,
        "name": o.get("name"),
        "status": o.get("status"),
        "raw": o,
    }


def _row_ad(account_id: str, o: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(o.get("id", "")),
        "ad_account_id": account_id,
        "campaign_id": str(o["campaign_id"]) if o.get("campaign_id") else None,
        "adset_id": str(o["adset_id"]) if o.get("adset_id") else None,
        "name": o.get("name"),
        "status": o.get("status"),
        "raw": o,
    }


def _row_insight(
    account_id: str, o: Dict[str, Any], level: str, *, with_region: bool = False
) -> Optional[Dict[str, Any]]:
    date_start = _parse_date(o.get("date_start"))
    if date_start is None:
        return None
    if level == "ad":
        key = o.get("ad_id")
    elif level == "adset":
        key = o.get("adset_id")
    else:
        key = o.get("campaign_id")
    if not key:
        return None
    row = {
        "ad_id": str(key),
        "date_start": date_start,
        "date_stop": _parse_date(o.get("date_stop")),
        "ad_account_id": account_id,
        "campaign_id": str(o["campaign_id"]) if o.get("campaign_id") else None,
        "adset_id": str(o["adset_id"]) if o.get("adset_id") else None,
        "impressions": _int(o.get("impressions")),
        "clicks": _int(o.get("clicks")),
        "reach": _int(o.get("reach")),
        "spend": _num(o.get("spend")),
        "frequency": _num(o.get("frequency")),
        "cpm": _num(o.get("cpm")),
        "cpc": _num(o.get("cpc")),
        "ctr": _num(o.get("ctr")),
        "cpp": _num(o.get("cpp")),
        "actions": o.get("actions"),
        "cost_per_action_type": o.get("cost_per_action_type"),
        "raw": o,
        "fetched_at": now_utc(),
    }
    if with_region:
        # meta_ads_insights_region.region es parte de la llave primaria (no
        # puede ser NULL) — cuando Meta no logra atribuir región a una
        # porción del tráfico devuelve region="" en esa fila.
        row["region"] = (o.get("region") or "").strip() or "Desconocida"
    return row


def _sync_custom_conversions(
    client: "MetaMarketingClient", account_id: str, acct_path: str
) -> None:
    print("[meta_ads] Fetching custom conversions...")
    try:
        raw = client.paged(
            f"{acct_path}/customconversions",
            {"fields": "id,name,custom_event_type"},
        )
    except Exception as exc:
        print(f"[meta_ads] custom conversions: error ({exc}) — omitiendo")
        return
    rows = []
    for o in raw:
        if not o.get("id"):
            continue
        rows.append({
            "id": str(o["id"]),
            "ad_account_id": account_id,
            "name": o.get("name"),
            "action_type": f"offsite_conversion.custom.{o['id']}",
            "event_type": o.get("custom_event_type"),
            "raw": o,
        })
    if rows:
        upsert_many(
            "meta_custom_conversions",
            rows,
            conflict_columns=["id"],
            update_columns=["ad_account_id", "name", "action_type", "event_type", "raw"],
        )
    print(f"[meta_ads] Custom conversions sincronizadas: {len(rows)}")


# Conversiones personalizadas de Meta con su propia columna dedicada en
# meta_ads_insights (además de vivir, ya sin desglosar, dentro del JSONB
# crudo `actions` de cada fila) — para que tengan su propio nombre de
# columna fácil de consultar en vez de tener que buscar el action_type
# largo (offsite_conversion.custom.<id>) dentro del JSONB cada vez.
# Agregar una nueva conversión = agregar su columna en db/migrate.py +
# una entrada acá con el NOMBRE EXACTO tal cual aparece en Meta Ads
# Manager (el id numérico de Meta cambia si se recrea la conversión, el
# nombre es lo estable).
#
# Nombre EXACTO (match por LOWER(name) = LOWER(...), no ILIKE '%...%')
# — un patrón con wildcards como '%reserva app nueva%' también matchea
# "reserva app nueva 2", una conversión DISTINTA con el mismo prefijo, y
# sin ORDER BY el LIMIT 1 puede quedarse con cualquiera de las dos de
# forma no determinística. Encontrado 2026-08-12 corriendo esto en vivo:
# terminó backfillenado reserva_app_nueva con los valores de "reserva app
# nueva 2" (que no tiene datos), dejando la columna en 0 en vez de los
# valores reales.
_CUSTOM_CONVERSION_COLUMNS = {
    "reserva_app_nueva": "Reserva app nueva",
    "reserva_app_3": "Reserva app 3",
}


def _backfill_custom_conv_columns() -> None:
    """Extrae valores de conversiones personalizadas desde el JSONB actions
    hacia sus columnas dedicadas — ver _CUSTOM_CONVERSION_COLUMNS."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            for column, exact_name in _CUSTOM_CONVERSION_COLUMNS.items():
                cur.execute(
                    f"""
                    UPDATE meta_ads_insights i
                    SET {column} = (
                        SELECT COALESCE(SUM((elem->>'value')::numeric), 0)
                        FROM jsonb_array_elements(i.actions) elem
                        WHERE elem->>'action_type' = (
                            SELECT action_type
                            FROM meta_custom_conversions
                            WHERE LOWER(name) = LOWER(%s)
                            LIMIT 1
                        )
                    )
                    WHERE i.actions IS NOT NULL
                    """,
                    (exact_name,),
                )
                n = cur.rowcount if cur.rowcount >= 0 else 0
                print(f"[meta_ads] Backfill {column}: {n} filas actualizadas")
        conn.commit()


def run() -> int:
    token = _normalize_access_token(_env("META_ACCESS_TOKEN"))
    raw_acct = _env("META_AD_ACCOUNT_ID")
    if not token or not raw_acct:
        missing = [n for n, v in (("META_ACCESS_TOKEN", token), ("META_AD_ACCOUNT_ID", raw_acct)) if not v]
        _root = Path(__file__).resolve().parent.parent
        print(
            f"[meta_ads] Skip: define en .env (raíz del repo): {', '.join(missing)}. "
            f"Buscado: {_root / '.env'}"
        )
        return 0

    account_id = normalize_ad_account_id(raw_acct)
    ensure_schema()
    api_version = _env("META_API_VERSION", "v21.0") or "v21.0"
    date_preset = _normalize_insight_date_preset(
        _env("META_DATE_PRESET", "last_30d") or "last_30d", "META_DATE_PRESET"
    )
    time_since = _env("META_TIME_RANGE_SINCE")
    time_until = _env("META_TIME_RANGE_UNTIL")
    level = (_env("META_INSIGHTS_LEVEL", "ad") or "ad").lower()
    if level not in ("campaign", "adset", "ad"):
        level = "ad"

    client = MetaMarketingClient(token, api_version)
    acct_path = f"/{account_id}"

    fields_campaigns = "id,name,status,objective"
    fields_adsets = "id,campaign_id,name,status"
    fields_ads = "id,name,status,campaign_id,adset_id"

    include_video = (_env("META_INSIGHTS_INCLUDE_VIDEO", "0") or "0").lower() in (
        "1",
        "true",
        "yes",
    )
    insight_fields = (
        "date_start,date_stop,campaign_id,adset_id,ad_id,"
        "impressions,clicks,reach,spend,frequency,cpm,cpc,ctr,cpp,"
        "account_currency,actions,cost_per_action_type"
    )
    if include_video:
        insight_fields += (
            ",video_thruplay_watched_actions,"
            "video_p25_watched_actions,video_p50_watched_actions,video_p75_watched_actions,"
            "video_p95_watched_actions,video_p100_watched_actions"
        )

    chunk_days = max(1, int(_env("META_INSIGHTS_TIME_CHUNK_DAYS", "31") or "31"))
    max_ub = max(1, int(_env("META_INSIGHTS_MAX_CHUNKS", "36") or "36"))
    insights_page_limit = max(
        1, min(500, int(_env("META_INSIGHTS_PAGE_LIMIT", "25") or "25"))
    )
    today = dt.date.today()

    print(f"[meta_ads] Fetching campaigns for {account_id}...")
    raw_camps = client.paged(f"{acct_path}/campaigns", {"fields": fields_campaigns})
    camp_rows = [_row_campaign(account_id, x) for x in raw_camps if x.get("id")]
    upsert_many(
        "meta_campaigns",
        camp_rows,
        conflict_columns=["id"],
        update_columns=[
            "ad_account_id",
            "name",
            "status",
            "objective",
            "raw",
        ],
    )

    print(f"[meta_ads] Fetching ad sets...")
    raw_adsets = client.paged(f"{acct_path}/adsets", {"fields": fields_adsets})
    adset_rows = [_row_adset(account_id, x) for x in raw_adsets if x.get("id")]
    upsert_many(
        "meta_adsets",
        adset_rows,
        conflict_columns=["id"],
        update_columns=[
            "ad_account_id",
            "campaign_id",
            "name",
            "status",
            "raw",
        ],
    )

    print(f"[meta_ads] Fetching ads...")
    raw_ads = client.paged(f"{acct_path}/ads", {"fields": fields_ads})
    ad_rows = [_row_ad(account_id, x) for x in raw_ads if x.get("id")]
    upsert_many(
        "meta_ads",
        ad_rows,
        conflict_columns=["id"],
        update_columns=[
            "ad_account_id",
            "campaign_id",
            "adset_id",
            "name",
            "status",
            "raw",
        ],
    )

    base_insight: Dict[str, Any] = {
        "level": level,
        "time_increment": 1,
        "fields": insight_fields,
    }
    insight_fetch_plans: List[tuple[str, Dict[str, Any]]] = []
    append_rolling_raw = _env("META_APPEND_ROLLING_PRESET")
    append_rolling_ok = bool(
        append_rolling_raw
        and append_rolling_raw.lower() not in ("0", "false", "no", "")
    )
    append_rolling: Optional[str] = None
    if append_rolling_ok:
        append_rolling = _normalize_insight_date_preset(
            append_rolling_raw or "last_30d", "META_APPEND_ROLLING_PRESET"
        )

    if time_since and time_until:
        since_d = _parse_date(time_since.strip())
        until_d = _parse_date(time_until.strip())
        if since_d is None or until_d is None:
            raise RuntimeError(
                "META_TIME_RANGE_SINCE / META_TIME_RANGE_UNTIL deben ser fechas YYYY-MM-DD válidas."
            )
        tr_ranges = _chunk_inclusive_ranges(since_d, until_d, chunk_days)
        print(
            "[meta_ads] ATENCION: META_TIME_RANGE_* activo — cada ejecución solo pide ese rango a la API. "
            "Para datos recientes sin quitar el backfill de 2025, define META_APPEND_ROLLING_PRESET=last_30d "
            "(o borra META_TIME_RANGE_SINCE/UNTIL tras el backfill y usa solo META_DATE_PRESET)."
        )
        if len(tr_ranges) > 1:
            print(
                f"[meta_ads] Insights: partiendo time_range en {len(tr_ranges)} ventanas "
                f"(≤{chunk_days} días) para evitar error API #1."
            )
        for i, (a, b) in enumerate(tr_ranges):
            label = f"time_range {a.isoformat()}..{b.isoformat()}"
            if len(tr_ranges) > 1:
                label += f" ({i + 1}/{len(tr_ranges)})"
            insight_fetch_plans.append(
                (
                    label,
                    {
                        **base_insight,
                        "time_range": json.dumps(
                            {"since": a.isoformat(), "until": b.isoformat()}
                        ),
                    },
                )
            )
        if append_rolling_ok and append_rolling:
            p_roll = {**base_insight, "date_preset": append_rolling}
            insight_fetch_plans.append((f"date_preset {append_rolling} (rolling)", p_roll))
        else:
            print(
                "[meta_ads] Sugerencia: META_APPEND_ROLLING_PRESET=last_30d para también traer la ventana móvil."
            )
    else:
        if date_preset in _CHUNKED_DATE_PRESETS:
            span = _approx_preset_span_days(date_preset, today)
            if span is None:
                pranges = _backward_time_windows_unbounded(chunk_days, today, max_ub)
                print(
                    f"[meta_ads] Insights: preset {date_preset!r} en {len(pranges)} ventanas "
                    f"(≤{chunk_days} días, máx. {max_ub} ventanas). Ajusta META_INSIGHTS_MAX_CHUNKS si necesitas más histórico."
                )
            elif span > chunk_days:
                pranges = _backward_time_windows(span, chunk_days, today)
                print(
                    f"[meta_ads] Insights: preset {date_preset!r} en {len(pranges)} ventanas "
                    f"(≤{chunk_days} días)."
                )
            else:
                pranges = []
            if pranges:
                for i, (a, b) in enumerate(pranges):
                    insight_fetch_plans.append(
                        (
                            f"date_preset {date_preset} → {a.isoformat()}..{b.isoformat()} "
                            f"({i + 1}/{len(pranges)})",
                            {
                                **base_insight,
                                "time_range": json.dumps(
                                    {"since": a.isoformat(), "until": b.isoformat()}
                                ),
                            },
                        )
                    )
            else:
                insight_fetch_plans.append(
                    (f"date_preset {date_preset}", {**base_insight, "date_preset": date_preset})
                )
        else:
            insight_fetch_plans.append(
                (f"date_preset {date_preset}", {**base_insight, "date_preset": date_preset})
            )

    sync_region = (_env("META_INSIGHTS_SYNC_REGION", "1") or "1").lower() not in (
        "0",
        "false",
        "no",
    )

    insight_rows: List[Dict[str, Any]] = []
    insight_region_rows: List[Dict[str, Any]] = []
    for idx, (label, insight_params) in enumerate(insight_fetch_plans):
        if idx > 0:
            time.sleep(0.4)
        print(f"[meta_ads] Fetching insights level={level} ({label})...")
        raw_insights = client.paged(
            f"{acct_path}/insights", insight_params, page_limit=insights_page_limit
        )
        for x in raw_insights:
            row = _row_insight(account_id, x, level)
            if row:
                insight_rows.append(row)

        if sync_region:
            # Segunda pasada con breakdowns=region — no se puede mezclar con
            # la de arriba en una sola petición porque cambia la forma de
            # cada fila (una por anuncio × día × región en vez de una por
            # anuncio × día), y meta_ads_insights depende de esa unicidad.
            time.sleep(0.4)
            print(f"[meta_ads] Fetching insights BY REGION level={level} ({label})...")
            region_params = {**insight_params, "breakdowns": "region"}
            raw_region = client.paged(
                f"{acct_path}/insights", region_params, page_limit=insights_page_limit
            )
            for x in raw_region:
                row = _row_insight(account_id, x, level, with_region=True)
                if row:
                    insight_region_rows.append(row)

    upsert_many(
        "meta_ads_insights",
        insight_rows,
        conflict_columns=["ad_id", "date_start"],
        update_columns=[
            "date_stop",
            "ad_account_id",
            "campaign_id",
            "adset_id",
            "impressions",
            "clicks",
            "reach",
            "spend",
            "frequency",
            "cpm",
            "cpc",
            "ctr",
            "cpp",
            "actions",
            "cost_per_action_type",
            "raw",
            "fetched_at",
        ],
    )

    if insight_region_rows:
        upsert_many(
            "meta_ads_insights_region",
            insight_region_rows,
            conflict_columns=["ad_id", "date_start", "region"],
            update_columns=[
                "date_stop",
                "ad_account_id",
                "campaign_id",
                "adset_id",
                "impressions",
                "clicks",
                "reach",
                "spend",
                "frequency",
                "cpm",
                "cpc",
                "ctr",
                "cpp",
                "actions",
                "cost_per_action_type",
                "raw",
                "fetched_at",
            ],
        )

    _sync_custom_conversions(client, account_id, acct_path)
    _backfill_custom_conv_columns()
    _sync_marketing_costs_from_meta()

    total = len(camp_rows) + len(adset_rows) + len(ad_rows) + len(insight_rows) + len(insight_region_rows)
    print(
        f"[meta_ads] Upserted campaigns={len(camp_rows)} adsets={len(adset_rows)} "
        f"ads={len(ad_rows)} insights={len(insight_rows)} insights_region={len(insight_region_rows)}"
    )
    return total


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv

        _root = Path(__file__).resolve().parent.parent
        load_dotenv(_root / ".env")
    except ImportError:
        pass
    n = run()
    print(f"done rows_total={n}")
