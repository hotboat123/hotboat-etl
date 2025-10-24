import os
from typing import Any, Dict, List

import requests

from db.utils import upsert_many


def _fetch_booknetic() -> List[Dict[str, Any]]:
    base_url = os.getenv("BOOKNETIC_BASE_URL")
    token = os.getenv("BOOKNETIC_TOKEN")
    if not base_url or not token:
        raise RuntimeError("BOOKNETIC_BASE_URL/BOOKNETIC_TOKEN no definidos")

    # EJEMPLO: ajusta al endpoint real de tu instancia Booknetic
    url = f"{base_url.rstrip('/')}/wp-json/booknetic/v1/appointments"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    payload = resp.json()

    # Esperamos lista de citas; adapta al formato real
    items = payload if isinstance(payload, list) else payload.get("data", [])
    return [
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


def run() -> int:
    items = _fetch_booknetic()
    affected = upsert_many(
        table="booknetic_appointments",
        rows=items,
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
    return affected


