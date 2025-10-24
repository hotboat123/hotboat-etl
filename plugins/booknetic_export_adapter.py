import csv
import hashlib
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import requests
import io


def _normalize_key(key: str) -> str:
    return (key or "").strip().lower().replace(" ", "_")


def _detect_field(row: Dict[str, Any], contains: List[str]) -> Optional[str]:
    for k in row.keys():
        nk = _normalize_key(k)
        if any(token in nk for token in contains):
            return k
    return None


def _parse_csv(path: Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            items.append(dict(r))
    return items


def _parse_csv_text(text: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    # Handle potential BOM and different newlines
    text_stream = io.StringIO(text)
    reader = csv.DictReader(text_stream)
    for r in reader:
        items.append(dict(r))
    return items


def _best_effort_map(row: Dict[str, Any]) -> Dict[str, Any]:
    # Heurística para extraer campos comunes
    email_k = _detect_field(row, ["email"])
    name_k = _detect_field(row, ["name", "customer", "cliente"])
    service_k = _detect_field(row, ["service", "servicio"])
    start_k = _detect_field(row, ["start", "fecha", "date", "hora"])  # flexible
    status_k = _detect_field(row, ["status", "estado"])
    id_k = _detect_field(row, ["id"])  # si viene un id real

    mapped: Dict[str, Any] = {
        "id": row.get(id_k) if id_k else None,
        "customer_name": row.get(name_k) if name_k else None,
        "customer_email": row.get(email_k) if email_k else None,
        "service_name": row.get(service_k) if service_k else None,
        "starts_at": row.get(start_k) if start_k else None,
        "status": row.get(status_k) if status_k else None,
        "raw": { _normalize_key(k): v for k, v in row.items() },
    }

    # Genera id estable si falta
    if not mapped["id"]:
        raw = f"{mapped.get('customer_email','')}|{mapped.get('starts_at','')}|{mapped.get('service_name','')}"
        mapped["id"] = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    return mapped


def fetch() -> Dict[str, List[Dict[str, Any]]]:
    # 1) Prefer URLs si están definidas
    url_appts = os.getenv("BOOKNETIC_EXPORT_URL_APPOINTMENTS") or os.getenv("BOOKNETIC_EXPORT_URL")
    if url_appts:
        try:
            resp = requests.get(url_appts, timeout=60)
            resp.raise_for_status()
            text = resp.content.decode("utf-8-sig", errors="replace")
            rows = _parse_csv_text(text)
            mapped_appts = [_best_effort_map(r) for r in rows]
            print(f"[booknetic-export] loaded {len(mapped_appts)} appointment rows from URL")
            # Optional secondary URL for payments
            pays_url = os.getenv("BOOKNETIC_EXPORT_URL_PAYMENTS")
            mapped_pays: List[Dict[str, Any]] = []
            if pays_url:
                try:
                    resp2 = requests.get(pays_url, timeout=60)
                    resp2.raise_for_status()
                    text2 = resp2.content.decode("utf-8-sig", errors="replace")
                    rows2 = _parse_csv_text(text2)
                    # Map payments minimal fields
                    for r in rows2:
                        mapped_pays.append({
                            "id": r.get("id") or r.get("payment_id") or r.get("ID"),
                            "appointment_id": r.get("appointment_id") or r.get("appointmentID"),
                            "amount": r.get("amount") or r.get("total"),
                            "currency": r.get("currency"),
                            "status": r.get("status"),
                            "method": r.get("method"),
                            "paid_at": r.get("paid_at") or r.get("date"),
                            "raw": { _normalize_key(k): v for k, v in r.items() },
                        })
                    print(f"[booknetic-export] loaded {len(mapped_pays)} payment rows from URL")
                except Exception as e:  # noqa: BLE001
                    print(f"[booknetic-export] failed to load payments URL: {e}")
            return {"appointments": mapped_appts, "payments": mapped_pays}
        except Exception as e:  # noqa: BLE001
            print(f"[booknetic-export] failed to load URL: {e}")

    # 2) Ejecutar script (opcional) y leer desde directorio
    export_dir = os.getenv("BOOKNETIC_EXPORT_DIR", os.path.join(os.getcwd(), "archivos_input", "Archivos input reservas"))
    run_script = os.getenv("BOOKNETIC_USE_EXPORT_SCRIPT", "").strip().lower() in {"1", "true", "yes", "y"}

    if run_script:
        try:
            from jobs.booknetic_export import main as export_main
            export_main()
        except Exception as e:  # noqa: BLE001
            print(f"[booknetic-export] run failed: {e}")

    folder = Path(export_dir)
    if not folder.exists():
        print(f"[booknetic-export] export_dir not found: {folder}")
        return []

    csvs = sorted(
        [p for p in folder.glob("appointments_*.csv")] or [p for p in folder.glob("*.csv")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not csvs:
        print(f"[booknetic-export] no CSV files found in {folder}")
        return []

    latest = csvs[0]
    rows = _parse_csv(latest)
    mapped_appts = [_best_effort_map(r) for r in rows]
    return {"appointments": mapped_appts}


