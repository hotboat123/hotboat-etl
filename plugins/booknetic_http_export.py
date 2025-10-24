import csv
import hashlib
import io
import re
from typing import Any, Dict, List

import requests
import json
from urllib.parse import urljoin


def _normalize_key(key: str) -> str:
    return (key or "").strip().lower().replace(" ", "_")


def _has_login_cookie(session: requests.Session) -> bool:
    # WordPress sets cookies named like 'wordpress_logged_in_<hash>'
    return any(k.startswith("wordpress_logged_in_") for k in session.cookies.keys())


def _login_wp(session: requests.Session, base_url: str, username: str, password: str) -> None:
    login_url = base_url.rstrip("/") + "/wp-login.php"
    # Prime cookies and get any hidden fields if needed
    session.get(login_url, timeout=30)

    data = {
        "log": username,
        "pwd": password,
        "wp-submit": "Log In",
        "redirect_to": base_url.rstrip("/") + "/wp-admin/",
        "testcookie": "1",
    }
    resp = session.post(login_url, data=data, allow_redirects=True, timeout=60)
    resp.raise_for_status()
    if not _has_login_cookie(session):
        raise RuntimeError("WordPress login failed - no login cookie present")


def _download_csv(session: requests.Session, url: str) -> List[Dict[str, Any]]:
    resp = session.get(url, timeout=120)
    resp.raise_for_status()
    # Decode handling BOM
    text = resp.content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return [dict(r) for r in reader]


def _discover_export_url(session: requests.Session, base_url: str, module: str) -> str:
    """Try to discover a real export URL from the module admin page HTML."""
    admin_url = base_url.rstrip("/") + f"/wp-admin/admin.php?page=booknetic&module={module}"
    try:
        html = session.get(admin_url, timeout=60).text
        # Look for any href containing module and export
        m = re.search(r'href=["\']([^"\']*module=' + re.escape(module) + r'[^"\']*export[^"\']*)["\']', html, re.IGNORECASE)
        if m:
            href = m.group(1)
            if href.startswith('http'):
                return href
            return urljoin(base_url, href)
        # Look for admin-ajax endpoints with action export
        m = re.search(r'(admin-ajax\.php[^"\']*action[^"\']*export[^"\']*)', html, re.IGNORECASE)
        if m:
            return urljoin(base_url, '/wp-admin/' + m.group(1))
    except Exception:
        pass
    # Fallback to the generic pattern (may return HTML)
    return base_url.rstrip('/') + f"/wp-admin/admin.php?page=booknetic&module={module}&action=export"


def _best_map_appointment(row: Dict[str, Any]) -> Dict[str, Any]:
    def find_key(tokens):
        for k in row.keys():
            nk = _normalize_key(k)
            if any(t in nk for t in tokens):
                return k
        return None

    email_k = find_key(["email"]) or find_key(["correo"])  # es/pt support
    name_k = find_key(["name", "customer", "cliente"]) 
    service_k = find_key(["service", "servicio"]) 
    start_k = find_key(["start", "fecha", "date", "hora", "start_time"]) 
    status_k = find_key(["status", "estado"]) 
    id_k = find_key(["appointment_id", "appointmentid", "booking_id", "bookingid", "id", "ID"]) 

    mapped = {
        "id": row.get(id_k) if id_k else None,
        "customer_name": row.get(name_k) if name_k else None,
        "customer_email": row.get(email_k) if email_k else None,
        "service_name": row.get(service_k) if service_k else None,
        "starts_at": row.get(start_k) if start_k else None,
        "status": row.get(status_k) if status_k else None,
        "raw": { _normalize_key(k): v for k, v in row.items() },
    }
    if not mapped["id"]:
        pieces = [f"{_normalize_key(k)}={str(v).strip()}" for k, v in sorted(row.items(), key=lambda kv: _normalize_key(kv[0]))]
        fallback_raw = "|".join(pieces)
        mapped["id"] = hashlib.sha1(fallback_raw.encode("utf-8")).hexdigest()
    return mapped


def _best_map_customer(row: Dict[str, Any]) -> Dict[str, Any]:
    def fk(tokens):
        for k in row.keys():
            nk = _normalize_key(k)
            if any(t in nk for t in tokens):
                return k
        return None

    id_k = fk(["customer_id", "id", "ID"]) 
    name_k = fk(["name", "customer", "cliente"]) 
    email_k = fk(["email", "correo"]) 
    phone_k = fk(["phone", "telefono", "tel"])

    mapped = {
        "id": row.get(id_k) if id_k else None,
        "name": row.get(name_k) if name_k else None,
        "email": row.get(email_k) if email_k else None,
        "phone": row.get(phone_k) if phone_k else None,
        "status": row.get(fk(["status", "estado"])) if fk(["status", "estado"]) else None,
        "raw": { _normalize_key(k): v for k, v in row.items() },
    }
    if not mapped["id"]:
        pieces = [f"{_normalize_key(k)}={str(v).strip()}" for k, v in sorted(row.items(), key=lambda kv: _normalize_key(kv[0]))]
        fallback_raw = "|".join(pieces)
        mapped["id"] = hashlib.sha1(fallback_raw.encode("utf-8")).hexdigest()
    return mapped


def _best_map_payment(row: Dict[str, Any]) -> Dict[str, Any]:
    def fk(tokens):
        for k in row.keys():
            nk = _normalize_key(k)
            if any(t in nk for t in tokens):
                return k
        return None

    def norm_val(v):
        if v is None:
            return None
        if isinstance(v, (list, dict)):
            return json.dumps(v, ensure_ascii=False, sort_keys=True)
        return str(v)

    mapped = {
        "id": norm_val(row.get(fk(["payment_id", "id", "ID"]))),
        "appointment_id": norm_val(row.get(fk(["appointment_id", "appointmentid", "booking_id", "bookingid"]))),
        "amount": norm_val(row.get(fk(["amount", "total", "monto"]))),
        "currency": norm_val(row.get(fk(["currency", "moneda"]))),
        "status": norm_val(row.get(fk(["status", "estado"]))),
        "method": norm_val(row.get(fk(["method", "metodo"]))),
        "paid_at": norm_val(row.get(fk(["date", "paid_at", "fecha"]))),
        "raw": { _normalize_key(k): v for k, v in row.items() },
    }
    if not mapped["id"]:
        pieces = [f"{_normalize_key(k)}={str(v).strip()}" for k, v in sorted(row.items(), key=lambda kv: _normalize_key(kv[0]))]
        fallback_raw = "|".join(pieces)
        mapped["id"] = hashlib.sha1(fallback_raw.encode("utf-8")).hexdigest()
    return mapped


def fetch() -> Dict[str, List[Dict[str, Any]]]:
    """Login to WordPress and download Booknetic CSVs via HTTP (no browser)."""
    import os

    base_url = os.getenv("BOOKNETIC_URL") or os.getenv("BOOKNETIC_BASE_URL")
    username = os.getenv("BOOKNETIC_USERNAME")
    password = os.getenv("BOOKNETIC_PASSWORD")
    if not base_url or not username or not password:
        raise RuntimeError("BOOKNETIC_URL/USERNAME/PASSWORD not set")

    s = requests.Session()
    _login_wp(s, base_url, username, password)

    urls = {
        "appointments": _discover_export_url(s, base_url, "appointments"),
        "customers": _discover_export_url(s, base_url, "customers"),
        "payments": _discover_export_url(s, base_url, "payments"),
    }

    results: Dict[str, List[Dict[str, Any]]] = {"appointments": [], "customers": [], "payments": []}
    try:
        rows = _download_csv(s, urls["appointments"]) or []
        mapped = [_best_map_appointment(r) for r in rows]
        results["appointments"] = mapped
        print(f"[booknetic-http] appointments rows={len(mapped)} distinct_ids={len({m.get('id') for m in mapped})}")
    except Exception as e:
        print(f"[booknetic-http] appointments export failed: {e}")

    try:
        rows = _download_csv(s, urls["customers"]) or []
        mapped = [_best_map_customer(r) for r in rows]
        results["customers"] = mapped
        print(f"[booknetic-http] customers rows={len(mapped)} distinct_ids={len({m.get('id') for m in mapped})}")
    except Exception as e:
        print(f"[booknetic-http] customers export failed: {e}")

    try:
        rows = _download_csv(s, urls["payments"]) or []
        mapped = [_best_map_payment(r) for r in rows]
        results["payments"] = mapped
        print(f"[booknetic-http] payments rows={len(mapped)} distinct_ids={len({str(m.get('id')) for m in mapped})}")
    except Exception as e:
        print(f"[booknetic-http] payments export failed: {e}")

    return results


