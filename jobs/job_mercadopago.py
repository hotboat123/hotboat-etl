"""
Sync MercadoPago → PostgreSQL.

Guarda en `mercadopago_pagos` cada cobro (Point, links de pago, etc.) con monto cobrado, comisión y monto
neto recibido, para cuadrarlos contra la app y el banco. Solo lectura sobre MercadoPago
(GET /v1/payments/search). No se guardan datos del pagador.

Variables requeridas:
  MERCADOPAGO_ACCESS_TOKEN       Access Token de producción de la aplicación (developers → Credenciales)

Variables opcionales:
  MERCADOPAGO_DAYS               Días hacia atrás en cada sync. Default: 30 (re-sincroniza reembolsos recientes)
  MERCADOPAGO_TIME_RANGE_SINCE   YYYY-MM-DD ─┐ Backfill histórico; úsalos juntos y luego bórralos.
  MERCADOPAGO_TIME_RANGE_UNTIL   YYYY-MM-DD ─┘
  MERCADOPAGO_INTERVAL           Segundos entre syncs. Default: 3600

Tabla: mercadopago_pagos (upsert por id de pago).
`fecha` y `hora` están en hora de Chile (America/Santiago).
"""
from __future__ import annotations

import datetime as dt
import logging
import os
import time
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests

from db.utils import now_utc, upsert_many

log = logging.getLogger(__name__)

API_URL = "https://api.mercadopago.com/v1/payments/search"
TZ = ZoneInfo("America/Santiago")
PAGE = 100


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return str(v).strip() if v and str(v).strip() else default


def _num(v: Any) -> Optional[float]:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _fetch(token: str, since: dt.date, until: dt.date) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    offset = 0
    while True:
        params = {
            "sort": "date_approved", "criteria": "asc", "range": "date_approved", "limit": PAGE, "offset": offset,
            # -04:00 por delante y -03:00 por detrás cubren el horario de verano y el de invierno de Chile.
            "begin_date": f"{since.isoformat()}T00:00:00.000-04:00",
            "end_date": f"{until.isoformat()}T23:59:59.000-03:00",
        }
        resp = requests.get(API_URL, params=params, headers={"Authorization": f"Bearer {token}"}, timeout=60)
        if resp.status_code >= 400:
            # No incluir headers/URL en el error: llevan el token.
            raise RuntimeError(f"MercadoPago API HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        rows.extend(data.get("results") or [])
        offset += PAGE
        if offset >= (data.get("paging") or {}).get("total", 0):
            return rows
        time.sleep(0.2)


def _map(p: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not p.get("id") or not p.get("date_approved"):
        return None
    when = dt.datetime.fromisoformat(p["date_approved"]).astimezone(TZ)
    details = p.get("transaction_details") or {}
    fee = sum(_num(f.get("amount")) or 0 for f in (p.get("fee_details") or []))
    point = (p.get("point_of_interaction") or {}).get("type")
    return {
        "id": int(p["id"]),
        "fecha": when.date(),
        "hora": when.time().replace(microsecond=0),
        "date_approved": when,
        "status": p.get("status"),
        "status_detail": p.get("status_detail"),
        "origen": "POINT" if point == "POINT" else (point or "CHECKOUT"),
        "payment_type_id": p.get("payment_type_id"),
        "payment_method_id": p.get("payment_method_id"),
        "installments": p.get("installments"),
        "monto": _num(p.get("transaction_amount")),
        "comision": fee,
        "neto_recibido": _num(details.get("net_received_amount")),
        "monto_reembolsado": _num(p.get("transaction_amount_refunded")) or 0,
        "descripcion": p.get("description"),
        "referencia_externa": p.get("external_reference"),
        "fecha_liberacion": p.get("money_release_date"),
        "fetched_at": now_utc(),
    }


def run() -> int:
    token = _env("MERCADOPAGO_ACCESS_TOKEN")
    if not token:
        log.info("[mercadopago] Saltando: falta MERCADOPAGO_ACCESS_TOKEN")
        return 0

    since_s, until_s = _env("MERCADOPAGO_TIME_RANGE_SINCE"), _env("MERCADOPAGO_TIME_RANGE_UNTIL")
    today = dt.datetime.now(TZ).date()
    if since_s and until_s:
        since, until = dt.date.fromisoformat(since_s), dt.date.fromisoformat(until_s)
        log.info("[mercadopago] Backfill: %s → %s", since, until)
    else:
        days = max(1, int(_env("MERCADOPAGO_DAYS", "30") or "30"))
        since, until = today - dt.timedelta(days=days), today
        log.info("[mercadopago] Últimos %d días: %s → %s", days, since, until)

    rows = [r for r in (_map(p) for p in _fetch(token, since, until)) if r]
    if not rows:
        log.info("[mercadopago] Sin pagos en el rango")
        return 0

    upsert_many(
        "mercadopago_pagos",
        rows,
        conflict_columns=["id"],
        update_columns=[
            "fecha", "hora", "date_approved", "status", "status_detail", "origen", "payment_type_id",
            "payment_method_id", "installments", "monto", "comision", "neto_recibido", "monto_reembolsado",
            "descripcion", "referencia_externa", "fecha_liberacion", "fetched_at",
        ],
    )
    log.info("[mercadopago] Pagos: %d", len(rows))
    return len(rows)
