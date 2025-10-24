import hashlib
import importlib
import os
from typing import Any, Dict, List, Tuple

import requests

from db.utils import upsert_many


def _try_plugin(module_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    try:
        mod = importlib.import_module(module_path)
        data = mod.fetch()
        print(f"[booknetic] plugin used: {module_path}")
        if isinstance(data, dict):
            return data.get("appointments", []), data.get("customers", [])
        if isinstance(data, list):
            return data, []
    except Exception as e:  # noqa: BLE001
        print(f"[booknetic] plugin '{module_path}' failed: {e}")
    return [], []


def _fetch_booknetic() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    # 1) Prefer explicit plugin via env
    plugin_module = os.getenv("BOOKNETIC_PLUGIN_MODULE")
    if plugin_module:
        appts, custs = _try_plugin(plugin_module)
        if appts or custs:
            return appts, custs
        # Si el usuario especificó un plugin explícito pero no hubo datos,
        # no forzamos la ruta API; devolvemos vacío para no romper por envs faltantes
        print(f"[booknetic] plugin '{plugin_module}' returned no data; skipping API fallback")
        return [], []

    # 2) Autodetect common plugins if env not set
    for candidate in [
        "plugins.booknetic_export_adapter",
        "plugins.booknetic_adapter_example",
    ]:
        appts, custs = _try_plugin(candidate)
        if appts or custs:
            return appts, custs

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
    appts, customers = _fetch_booknetic()

    # Asegura id estable si falta utilizando hash
    for it in appts:
        if not it.get("id"):
            raw = f"{it.get('customer_email','')}|{it.get('starts_at','')}|{it.get('service_name','')}"
            it["id"] = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    affected = upsert_many(
        table="booknetic_appointments",
        rows=appts,
        conflict_columns=["id"],
        update_columns=[
            "customer_name",
            "customer_email",
            "service_name",
            "starts_at",
            "status",
            "raw",
        ],
    )

    # Upsert customers if provided
    if customers:
        for c in customers:
            if not c.get("id"):
                raw = f"{c.get('email','')}|{c.get('name','')}|{c.get('phone','')}"
                c["id"] = hashlib.sha1(raw.encode("utf-8")).hexdigest()
        affected += upsert_many(
            table="booknetic_customers",
            rows=customers,
            conflict_columns=["id"],
            update_columns=["name", "email", "phone", "status", "raw"],
        )

    return affected


