import hashlib
import importlib
import os
from typing import Any, Dict, List, Tuple

import requests

from db.utils import replace_all


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
        "plugins.booknetic_full_export",  # NEW: Full export with customers, appointments, payments
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


def run() -> int:
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

    affected = 0

    # Replace appointments (TRUNCATE + INSERT)
    if appts:
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


