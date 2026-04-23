"""
Booknetic → Postgres (export/scrape).

Deshabilitado por defecto: no descarga ni toca tablas salvo que definas
BOOKNETIC_SYNC_ENABLED=1 (true/yes/on). El runner (jobs.runner) ya no programa este job.
"""
import hashlib
import importlib
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Tuple

import requests

from db.utils import replace_all

# Si es "1"/"true"/"yes", el job falla cuando no hay filas de appointments (para no dar éxito en silencio).
def _env_truthy(name: str) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _try_plugin(module_path: str):
    """
    Try to load plugin and return data
    Returns: dict, tuple, or list depending on plugin
    """
    try:
        mod = importlib.import_module(module_path)
        data = mod.fetch()
        print(f"[booknetic] plugin used: {module_path}")
        return data
    except Exception as e:  # noqa: BLE001
        print(f"[booknetic] plugin '{module_path}' failed: {e}")
        import traceback
        traceback.print_exc()
    return None


def _fetch_booknetic():
    """
    Fetch Booknetic data using plugins
    Returns: dict, tuple, or list depending on plugin
    """
    # 1) Prefer explicit plugin via env
    plugin_module = os.getenv("BOOKNETIC_PLUGIN_MODULE")
    if plugin_module:
        data = _try_plugin(plugin_module)
        if data:
            return data
        # Si el usuario especificó un plugin explícito pero no hubo datos,
        # no forzamos la ruta API; devolvemos vacío para no romper por envs faltantes
        print(f"[booknetic] plugin '{plugin_module}' returned no data; skipping API fallback")
        return {"appointments": [], "customers": [], "payments": []}

    # 2) Autodetect common plugins if env not set
    for candidate in [
        "plugins.booknetic_full_export",  # Full export via Selenium (preferred)
        "plugins.booknetic_http_export",  # Fallback sin navegador (usa requests)
        "plugins.booknetic_export_adapter",
        "plugins.booknetic_selenium_export",
        "plugins.booknetic_adapter_example",
    ]:
        data = _try_plugin(candidate)
        if data:
            return data

    # 3) Fallback API: acepta alias de variables
    base_url = os.getenv("BOOKNETIC_BASE_URL") or os.getenv("BOOKNETIC_URL")
    token = os.getenv("BOOKNETIC_TOKEN")
    if not base_url or not token:
        raise RuntimeError("BOOKNETIC_BASE_URL/BOOKNETIC_TOKEN no definidos (o usa BOOKNETIC_PLUGIN_MODULE)")

    # EJEMPLO: ajusta al endpoint real de tu instancia Booknetic
    url = f"{base_url.rstrip('/')}/wp-json/booknetic/v1/appointments"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    payload = resp.json()

    # Esperamos lista de citas; adapta al formato real
    items = payload if isinstance(payload, list) else payload.get("data", [])
    appts = [
        {
            "id": str(it.get("id")),
            "customer_name": it.get("customer_name"),
            "customer_email": it.get("customer_email"),
            "service_name": it.get("service_name"),
            "starts_at": it.get("starts_at"),
            "status": it.get("status"),
            "raw": it,
        }
        for it in items
        if it.get("id") is not None
    ]
    return appts, []


def _dedup_rows(rows: List[Dict[str, Any]], key: str) -> Tuple[List[Dict[str, Any]], int]:
    """Remove duplicate rows preserving order, based on `key`."""
    seen = set()
    deduped: List[Dict[str, Any]] = []
    duplicates = 0
    for row in rows:
        value = row.get(key)
        if value is None:
            deduped.append(row)
            continue
        if value in seen:
            duplicates += 1
            continue
        seen.add(value)
        deduped.append(row)
    return deduped, duplicates


def _sanitize_payment_amounts(payments: List[Dict[str, Any]]) -> int:
    """Ensure payment amounts are numeric; replace invalid values with None."""
    cleaned = 0
    for payment in payments:
        raw_amount = payment.get("amount")
        if raw_amount in (None, "", "-", " "):
            payment["amount"] = None
            continue
        if isinstance(raw_amount, (int, float, Decimal)):
            continue
        try:
            normalized = str(raw_amount).replace(",", "").strip()
            if not normalized:
                payment["amount"] = None
                continue
            payment["amount"] = float(Decimal(normalized))
        except (InvalidOperation, ValueError):
            payment["amount"] = None
            cleaned += 1
    return cleaned


def _parse_datetime_flexible(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y %H:%M",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return None


def _sanitize_payment_dates(payments: List[Dict[str, Any]]) -> int:
    cleaned = 0
    for payment in payments:
        raw_date = payment.get("paid_at")
        if isinstance(raw_date, str) and any(token in raw_date for token in ("<", ">", "[", "]")):
            payment["paid_at"] = None
            cleaned += 1
            continue
        parsed = _parse_datetime_flexible(raw_date)
        if parsed:
            payment["paid_at"] = parsed
        else:
            if raw_date not in (None, "", "-"):
                cleaned += 1
            payment["paid_at"] = None
    return cleaned


def run() -> int:
    sync = (os.getenv("BOOKNETIC_SYNC_ENABLED") or "").strip().lower()
    if sync not in ("1", "true", "yes", "on"):
        print(
            "[booknetic] Omitido: scrape desactivado. Para ejecutarlo, define "
            "BOOKNETIC_SYNC_ENABLED=1 (este proyecto ya no lo corre en el runner)."
        )
        return 0

    data = _fetch_booknetic()
    
    # Handle different return formats
    if isinstance(data, tuple):
        # Old format: (appointments, customers)
        appts, customers = data
        payments = []
    elif isinstance(data, dict):
        # New format: {"appointments": [], "customers": [], "payments": []}
        appts = data.get("appointments", [])
        customers = data.get("customers", [])
        payments = data.get("payments", [])
    else:
        # List of appointments only
        appts = data if isinstance(data, list) else []
        customers = []
        payments = []

    print(
        f"[booknetic] Datos obtenidos del export: "
        f"appointments={len(appts)}, customers={len(customers)}, payments={len(payments)}"
    )
    if not appts:
        print(
            "[booknetic] ATENCION: lista de appointments VACIA. "
            "La tabla booknetic_appointments NO se actualiza en esta ejecucion "
            "(se conservan las filas anteriores). "
            "Revisa export CSV/plugin/login en WordPress/Booknetic."
        )
        if _env_truthy("BOOKNETIC_REQUIRE_APPOINTMENTS"):
            raise RuntimeError(
                "booknetic: appointments vacio (BOOKNETIC_REQUIRE_APPOINTMENTS activo)"
            )

    affected = 0

    # Replace appointments (TRUNCATE + INSERT)
    if appts:
        appts, dup_count = _dedup_rows(appts, "id")
        if dup_count:
            print(f"[booknetic] appointments duplicates removed: {dup_count}")
        # Asegura id estable si falta utilizando hash
        for it in appts:
            if not it.get("id"):
                raw = f"{it.get('customer_email','')}|{it.get('starts_at','')}|{it.get('service_name','')}"
                it["id"] = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        
        print(f"[booknetic] Replacing booknetic_appointments table...")
        affected += replace_all(
            table="booknetic_appointments",
            rows=appts
        )
        print(f"[booknetic] {affected} appointments replaced")

    # Replace customers if provided (TRUNCATE + INSERT)
    if customers:
        customers, dup_count = _dedup_rows(customers, "id")
        if dup_count:
            print(f"[booknetic] customers duplicates removed: {dup_count}")
        for c in customers:
            if not c.get("id"):
                raw = f"{c.get('email','')}|{c.get('name','')}|{c.get('phone','')}"
                c["id"] = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        
        print(f"[booknetic] Replacing booknetic_customers table...")
        customer_affected = replace_all(
            table="booknetic_customers",
            rows=customers
        )
        affected += customer_affected
        print(f"[booknetic] {customer_affected} customers replaced")

    # Replace payments if any (TRUNCATE + INSERT)
    if payments:
        payments, dup_count = _dedup_rows(payments, "id")
        if dup_count:
            print(f"[booknetic] payments duplicates removed: {dup_count}")
        cleaned_amounts = _sanitize_payment_amounts(payments)
        if cleaned_amounts:
            print(f"[booknetic] payments amounts cleaned: {cleaned_amounts}")
        cleaned_dates = _sanitize_payment_dates(payments)
        if cleaned_dates:
            print(f"[booknetic] payments dates cleaned: {cleaned_dates}")
        for p in payments:
            if not p.get("id"):
                raw = f"{p.get('appointment_id','')}|{p.get('amount','')}|{p.get('paid_at','')}"
                p["id"] = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        
        print(f"[booknetic] Replacing booknetic_payments table...")
        payment_affected = replace_all(
            table="booknetic_payments",
            rows=payments
        )
        affected += payment_affected
        print(f"[booknetic] {payment_affected} payments replaced")

    print(f"[booknetic] Total affected: {affected}")
    return affected


if __name__ == "__main__":
    # Permite ejecutar `python -m jobs.job_scrape_booknetic`
    try:
        run()
    except Exception as exc:
        print(f"[booknetic] Job failed: {exc}")
        raise

