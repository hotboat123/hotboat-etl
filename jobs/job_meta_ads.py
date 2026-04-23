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
  META_SYNC_MARKETING_COSTS_TABLE  Default 1: tras insights, rellena tabla marketing_costs desde meta_ads_insights. 0 para desactivar.
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
        data = r.json()
        if r.status_code >= 400 or "error" in data:
            err = data.get("error", {})
            msg = err.get("message", r.text)
            code = err.get("code", r.status_code)
            raise RuntimeError(_meta_api_error_message(code, str(msg)))
        return data

    def paged(self, path: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        params = dict(params or {})
        params.setdefault("limit", 100)
        next_url: Optional[str] = None
        while True:
            if next_url:
                time.sleep(0.35)
                r = requests.get(next_url, timeout=120)
                chunk = r.json()
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
    account_id: str, o: Dict[str, Any], level: str
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
    return {
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

    insight_fields = (
        "date_start,date_stop,campaign_id,adset_id,ad_id,"
        "impressions,clicks,reach,spend,frequency,cpm,cpc,ctr,cpp,"
        "account_currency,"
        "actions,cost_per_action_type,"
        "video_thruplay_watched_actions,"
        "video_p25_watched_actions,video_p50_watched_actions,video_p75_watched_actions,"
        "video_p95_watched_actions,video_p100_watched_actions"
    )

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
        p_tr: Dict[str, Any] = {
            **base_insight,
            "time_range": json.dumps(
                {"since": time_since.strip(), "until": time_until.strip()}
            ),
        }
        insight_fetch_plans.append(
            (f"time_range {time_since}..{time_until}", p_tr)
        )
        print(
            "[meta_ads] ATENCION: META_TIME_RANGE_* activo — cada ejecución solo pide ese rango a la API. "
            "Para datos recientes sin quitar el backfill de 2025, define META_APPEND_ROLLING_PRESET=last_30d "
            "(o borra META_TIME_RANGE_SINCE/UNTIL tras el backfill y usa solo META_DATE_PRESET)."
        )
        if append_rolling_ok and append_rolling:
            p_roll = {**base_insight, "date_preset": append_rolling}
            insight_fetch_plans.append((f"date_preset {append_rolling} (rolling)", p_roll))
        else:
            print(
                "[meta_ads] Sugerencia: META_APPEND_ROLLING_PRESET=last_30d para también traer la ventana móvil."
            )
    else:
        insight_fetch_plans.append((f"date_preset {date_preset}", {**base_insight, "date_preset": date_preset}))

    insight_rows: List[Dict[str, Any]] = []
    for label, insight_params in insight_fetch_plans:
        print(f"[meta_ads] Fetching insights level={level} ({label})...")
        raw_insights = client.paged(f"{acct_path}/insights", insight_params)
        for x in raw_insights:
            row = _row_insight(account_id, x, level)
            if row:
                insight_rows.append(row)

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

    _sync_marketing_costs_from_meta()

    total = len(camp_rows) + len(adset_rows) + len(ad_rows) + len(insight_rows)
    print(
        f"[meta_ads] Upserted campaigns={len(camp_rows)} adsets={len(adset_rows)} "
        f"ads={len(ad_rows)} insights={len(insight_rows)}"
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
