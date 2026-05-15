"""
Sync Google Ads → PostgreSQL.

Sincroniza campañas, grupos de anuncios y métricas diarias de rendimiento.
Usa la Google Ads REST API (GAQL) directamente con requests — sin librería google-ads.

Variables requeridas:
  GOOGLE_ADS_DEVELOPER_TOKEN   Token de desarrollador (Google Ads API Center)
  GOOGLE_ADS_CLIENT_ID         OAuth2 Client ID (Google Cloud Console)
  GOOGLE_ADS_CLIENT_SECRET     OAuth2 Client Secret
  GOOGLE_ADS_REFRESH_TOKEN     OAuth2 Refresh Token (obtener con scripts/get_google_ads_token.py)
  GOOGLE_ADS_CUSTOMER_ID       ID de cuenta Google Ads, sin guiones (ej: 1234567890)

Variables opcionales:
  GOOGLE_ADS_LOGIN_CUSTOMER_ID  ID de cuenta manager/MCC (si aplica)
  GOOGLE_ADS_API_VERSION        Default v17. Cambia si la versión está deprecada.
  GOOGLE_ADS_DATE_PRESET        last_30d | last_90d | last_year | maximum. Default: last_30d
  GOOGLE_ADS_TIME_RANGE_SINCE   YYYY-MM-DD  ─┐ Para backfill histórico.
  GOOGLE_ADS_TIME_RANGE_UNTIL   YYYY-MM-DD  ─┘ Úsalos juntos, luego bórralos.
  GOOGLE_ADS_REPORT_LEVELS      campaign,adgroup  (default: ambos)
  GOOGLE_ADS_CHUNK_DAYS         Días por ventana de consulta. Default: 90
  GOOGLE_ADS_INTERVAL           Segundos entre syncs. Default: 3600

Tablas que maneja:
  google_ads_campaigns     Estructura de campañas (upsert)
  google_ads_adgroups      Estructura de grupos de anuncios (upsert)
  google_ads_performance   Métricas diarias por campaña/adgroup (upsert)

Nota sobre unidades monetarias:
  cost_micros, average_cpc_micros, average_cpm_micros = valor × 1.000.000
  (ej: $25 CLP = 25000000 micros). Divide por 1e6 en tus queries para ver CLP reales.
  conversions_value y all_conversions_value ya están en la moneda de la cuenta.
"""
from __future__ import annotations

import datetime as dt
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from db.utils import now_utc, upsert_many

log = logging.getLogger(__name__)

OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
GADS_BASE = "https://googleads.googleapis.com"

_PRESET_DAYS: Dict[str, Optional[int]] = {
    "last_7d": 7,
    "last_14d": 14,
    "last_30d": 30,
    "last_60d": 60,
    "last_90d": 90,
    "last_180d": 180,
    "last_365d": 365,
    "last_year": 365,
    "this_year": None,
    "maximum": None,
}


# ---------------------------------------------------------------------------
# Helpers de entorno y fechas
# ---------------------------------------------------------------------------

def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return str(v).strip() if v and str(v).strip() else default


def _date_range(preset: str, today: dt.date) -> Tuple[dt.date, dt.date]:
    if preset == "this_year":
        return dt.date(today.year, 1, 1), today
    if preset in ("maximum", "data_maximum"):
        return dt.date(2015, 1, 1), today
    days = _PRESET_DAYS.get(preset, 30)
    return today - dt.timedelta(days=days or 30), today


def _chunks(since: dt.date, until: dt.date, chunk_days: int) -> List[Tuple[dt.date, dt.date]]:
    out = []
    cur = since
    while cur <= until:
        end = min(until, cur + dt.timedelta(days=chunk_days - 1))
        out.append((cur, end))
        cur = end + dt.timedelta(days=1)
    return out


# ---------------------------------------------------------------------------
# OAuth2 — refresh token → access token
# ---------------------------------------------------------------------------

def _get_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    resp = requests.post(
        OAUTH_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(
            f"OAuth2 error: {data['error']} — {data.get('error_description', '')}"
        )
    return data["access_token"]


# ---------------------------------------------------------------------------
# Cliente Google Ads REST / GAQL
# ---------------------------------------------------------------------------

class GoogleAdsClient:
    def __init__(
        self,
        access_token: str,
        developer_token: str,
        customer_id: str,
        login_customer_id: str,
        api_version: str,
    ) -> None:
        self.access_token = access_token
        self.developer_token = developer_token
        self.customer_id = customer_id.replace("-", "")
        self.login_customer_id = login_customer_id.replace("-", "")
        self.api_version = api_version

    def _headers(self) -> Dict[str, str]:
        h = {
            "Authorization": f"Bearer {self.access_token}",
            "developer-token": self.developer_token,
            "Content-Type": "application/json",
        }
        if self.login_customer_id != self.customer_id:
            h["login-customer-id"] = self.login_customer_id
        return h

    def search(self, query: str) -> List[Dict[str, Any]]:
        url = (
            f"{GADS_BASE}/{self.api_version}"
            f"/customers/{self.customer_id}/googleAds:search"
        )
        results: List[Dict] = []
        page_token: Optional[str] = None

        while True:
            body: Dict[str, Any] = {"query": query, "pageSize": 10000}
            if page_token:
                body["pageToken"] = page_token

            resp = requests.post(url, headers=self._headers(), json=body, timeout=120)

            if resp.status_code >= 400:
                try:
                    err = resp.json().get("error", {})
                    raise RuntimeError(
                        f"Google Ads API {err.get('code', resp.status_code)}: "
                        f"{err.get('message', resp.text[:300])}"
                    )
                except (ValueError, KeyError):
                    raise RuntimeError(
                        f"Google Ads API HTTP {resp.status_code}: {resp.text[:300]}"
                    )

            data = resp.json()
            results.extend(data.get("results") or [])
            page_token = data.get("nextPageToken")
            if not page_token:
                break
            time.sleep(0.2)

        return results


# ---------------------------------------------------------------------------
# Conversores de tipos
# ---------------------------------------------------------------------------

def _int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Mapeo de filas API → dicts para DB
# ---------------------------------------------------------------------------

def _map_campaign(customer_id: str, row: Dict) -> Optional[Dict]:
    c = row.get("campaign", {})
    if not c.get("id"):
        return None
    budget = row.get("campaignBudget", {})
    return {
        "id": str(c["id"]),
        "customer_id": customer_id,
        "name": c.get("name"),
        "status": c.get("status"),
        "channel_type": c.get("advertisingChannelType"),
        "budget_micros": _int(budget.get("amountMicros")),
        "raw": row,
    }


def _map_adgroup(customer_id: str, row: Dict) -> Optional[Dict]:
    ag = row.get("adGroup", {})
    if not ag.get("id"):
        return None
    return {
        "id": str(ag["id"]),
        "customer_id": customer_id,
        "campaign_id": str(row.get("campaign", {}).get("id", "")),
        "name": ag.get("name"),
        "status": ag.get("status"),
        "raw": row,
    }


def _map_performance(customer_id: str, level: str, row: Dict) -> Optional[Dict]:
    seg = row.get("segments", {})
    date_str = seg.get("date")
    if not date_str:
        return None
    try:
        date_start = dt.date.fromisoformat(date_str)
    except ValueError:
        return None

    if level == "campaign":
        entity = row.get("campaign", {})
        resource_id = str(entity.get("id", ""))
        resource_name = entity.get("name")
        campaign_id = resource_id
        adgroup_id = None
    elif level == "adgroup":
        entity = row.get("adGroup", {})
        resource_id = str(entity.get("id", ""))
        resource_name = entity.get("name")
        campaign_id = str(row.get("campaign", {}).get("id", ""))
        adgroup_id = resource_id
    else:
        return None

    if not resource_id:
        return None

    m = row.get("metrics", {})
    return {
        "customer_id": customer_id,
        "report_level": level,
        "resource_id": resource_id,
        "date_start": date_start,
        "resource_name": resource_name,
        "campaign_id": campaign_id,
        "adgroup_id": adgroup_id,
        # Métricas de volumen
        "impressions": _int(m.get("impressions")),
        "clicks": _int(m.get("clicks")),
        # Inversión (en micros — divide por 1.000.000 para obtener CLP/USD)
        "cost_micros": _int(m.get("costMicros")),
        "average_cpc_micros": _int(m.get("averageCpc")),
        "average_cpm_micros": _int(m.get("averageCpm")),
        # Conversiones
        "conversions": _float(m.get("conversions")),
        "conversions_value": _float(m.get("conversionsValue")),
        "all_conversions": _float(m.get("allConversions")),
        "all_conversions_value": _float(m.get("allConversionsValue")),
        "view_through_conversions": _int(m.get("viewThroughConversions")),
        # Ratios y cuotas
        "ctr": _float(m.get("ctr")),
        "search_impression_share": _float(m.get("searchImpressionShare")),
        "search_top_impression_share": _float(m.get("searchTopImpressionShare")),
        "search_abs_top_impression_share": _float(m.get("searchAbsoluteTopImpressionShare")),
        # Raw
        "raw": row,
        "fetched_at": now_utc(),
    }


# ---------------------------------------------------------------------------
# Queries GAQL
# ---------------------------------------------------------------------------

_CAMPAIGN_META_QUERY = """
    SELECT
      campaign.id,
      campaign.name,
      campaign.status,
      campaign.advertising_channel_type,
      campaign_budget.amount_micros
    FROM campaign
    WHERE campaign.status != 'REMOVED'
    ORDER BY campaign.name
"""

_ADGROUP_META_QUERY = """
    SELECT
      ad_group.id,
      ad_group.name,
      ad_group.status,
      campaign.id,
      campaign.name
    FROM ad_group
    WHERE ad_group.status != 'REMOVED'
    ORDER BY campaign.id, ad_group.name
"""

_CAMPAIGN_PERF_QUERY = """
    SELECT
      campaign.id, campaign.name, campaign.status,
      metrics.impressions, metrics.clicks, metrics.cost_micros,
      metrics.conversions, metrics.conversions_value,
      metrics.all_conversions, metrics.all_conversions_value,
      metrics.view_through_conversions,
      metrics.ctr, metrics.average_cpc, metrics.average_cpm,
      metrics.search_impression_share,
      metrics.search_top_impression_share,
      metrics.search_absolute_top_impression_share,
      segments.date
    FROM campaign
    WHERE segments.date BETWEEN '{since}' AND '{until}'
      AND metrics.impressions > 0
    ORDER BY segments.date DESC
"""

_ADGROUP_PERF_QUERY = """
    SELECT
      ad_group.id, ad_group.name, ad_group.status,
      campaign.id, campaign.name,
      metrics.impressions, metrics.clicks, metrics.cost_micros,
      metrics.conversions, metrics.conversions_value,
      metrics.all_conversions, metrics.all_conversions_value,
      metrics.view_through_conversions,
      metrics.ctr, metrics.average_cpc,
      segments.date
    FROM ad_group
    WHERE segments.date BETWEEN '{since}' AND '{until}'
      AND metrics.impressions > 0
    ORDER BY segments.date DESC
"""

_PERF_QUERIES = {
    "campaign": _CAMPAIGN_PERF_QUERY,
    "adgroup": _ADGROUP_PERF_QUERY,
}


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def run() -> int:
    required = {
        "GOOGLE_ADS_DEVELOPER_TOKEN": _env("GOOGLE_ADS_DEVELOPER_TOKEN"),
        "GOOGLE_ADS_CLIENT_ID": _env("GOOGLE_ADS_CLIENT_ID"),
        "GOOGLE_ADS_CLIENT_SECRET": _env("GOOGLE_ADS_CLIENT_SECRET"),
        "GOOGLE_ADS_REFRESH_TOKEN": _env("GOOGLE_ADS_REFRESH_TOKEN"),
        "GOOGLE_ADS_CUSTOMER_ID": _env("GOOGLE_ADS_CUSTOMER_ID"),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        log.info("[google_ads] Saltando: faltan variables → %s", ", ".join(missing))
        return 0

    customer_id = required["GOOGLE_ADS_CUSTOMER_ID"].replace("-", "")
    login_id = (_env("GOOGLE_ADS_LOGIN_CUSTOMER_ID") or customer_id).replace("-", "")
    api_version = _env("GOOGLE_ADS_API_VERSION", "v17") or "v17"
    chunk_days = max(1, int(_env("GOOGLE_ADS_CHUNK_DAYS", "90") or "90"))
    today = dt.date.today()

    report_levels = [
        lv.strip()
        for lv in (_env("GOOGLE_ADS_REPORT_LEVELS", "campaign,adgroup") or "campaign,adgroup").split(",")
        if lv.strip() in ("campaign", "adgroup")
    ]

    # Determinar rango de fechas
    time_since = _env("GOOGLE_ADS_TIME_RANGE_SINCE")
    time_until = _env("GOOGLE_ADS_TIME_RANGE_UNTIL")
    if time_since and time_until:
        since = dt.date.fromisoformat(time_since)
        until = dt.date.fromisoformat(time_until)
        log.info("[google_ads] Backfill: %s → %s", since, until)
    else:
        preset = _env("GOOGLE_ADS_DATE_PRESET", "last_30d") or "last_30d"
        since, until = _date_range(preset, today)
        log.info("[google_ads] Preset %s: %s → %s", preset, since, until)

    # Auth
    log.info("[google_ads] Obteniendo access token OAuth2...")
    access_token = _get_access_token(
        required["GOOGLE_ADS_CLIENT_ID"],
        required["GOOGLE_ADS_CLIENT_SECRET"],
        required["GOOGLE_ADS_REFRESH_TOKEN"],
    )

    client = GoogleAdsClient(
        access_token=access_token,
        developer_token=required["GOOGLE_ADS_DEVELOPER_TOKEN"],
        customer_id=customer_id,
        login_customer_id=login_id,
        api_version=api_version,
    )

    total = 0

    # 1. Metadata de campañas
    log.info("[google_ads] Sincronizando campañas...")
    camp_rows = [
        r for r in (_map_campaign(customer_id, x) for x in client.search(_CAMPAIGN_META_QUERY))
        if r
    ]
    if camp_rows:
        upsert_many(
            "google_ads_campaigns",
            camp_rows,
            conflict_columns=["id"],
            update_columns=["name", "status", "channel_type", "budget_micros", "raw"],
        )
        log.info("[google_ads] Campañas: %d", len(camp_rows))
        total += len(camp_rows)

    # 2. Metadata de ad groups
    log.info("[google_ads] Sincronizando grupos de anuncios...")
    ag_rows = [
        r for r in (_map_adgroup(customer_id, x) for x in client.search(_ADGROUP_META_QUERY))
        if r
    ]
    if ag_rows:
        upsert_many(
            "google_ads_adgroups",
            ag_rows,
            conflict_columns=["id"],
            update_columns=["campaign_id", "name", "status", "raw"],
        )
        log.info("[google_ads] Grupos de anuncios: %d", len(ag_rows))
        total += len(ag_rows)

    # 3. Performance diaria por nivel y chunk
    date_chunks = _chunks(since, until, chunk_days)

    for level in report_levels:
        perf_rows: List[Dict] = []
        query_template = _PERF_QUERIES[level]

        for i, (cs, ce) in enumerate(date_chunks):
            if i > 0:
                time.sleep(0.4)
            log.info(
                "[google_ads] Performance level=%s chunk %d/%d (%s→%s)",
                level, i + 1, len(date_chunks), cs, ce,
            )
            query = query_template.format(since=cs.isoformat(), until=ce.isoformat())
            for row in client.search(query):
                mapped = _map_performance(customer_id, level, row)
                if mapped:
                    perf_rows.append(mapped)

        if perf_rows:
            upsert_many(
                "google_ads_performance",
                perf_rows,
                conflict_columns=["customer_id", "report_level", "resource_id", "date_start"],
                update_columns=[
                    "resource_name", "campaign_id", "adgroup_id",
                    "impressions", "clicks", "cost_micros",
                    "average_cpc_micros", "average_cpm_micros",
                    "conversions", "conversions_value",
                    "all_conversions", "all_conversions_value",
                    "view_through_conversions",
                    "ctr", "search_impression_share",
                    "search_top_impression_share", "search_abs_top_impression_share",
                    "raw", "fetched_at",
                ],
            )
            log.info("[google_ads] Performance %s: %d filas", level, len(perf_rows))
            total += len(perf_rows)

    log.info("[google_ads] Total: %d filas", total)
    return total
