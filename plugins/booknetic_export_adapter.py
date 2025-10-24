import csv
import hashlib
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


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


def fetch() -> List[Dict[str, Any]]:
    # Directorio donde el export guarda CSVs
    export_dir = os.getenv("BOOKNETIC_EXPORT_DIR", os.path.join(os.getcwd(), "archivos_input", "Archivos input reservas"))
    run_script = os.getenv("BOOKNETIC_USE_EXPORT_SCRIPT", "").strip().lower() in {"1", "true", "yes", "y"}

    # Opcional: ejecutar el script de export si así se configura
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

    # Preferimos appointments_*.csv; si no, cualquier .csv reciente
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
    mapped = [_best_effort_map(r) for r in rows]
    return mapped


