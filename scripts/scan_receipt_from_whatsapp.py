"""
Escanea la boleta más reciente enviada por WhatsApp y registra el gasto.

Uso:
    DATABASE_URL="postgresql://..." GEMINI_API_KEY="..." python scripts/scan_receipt_from_whatsapp.py

    O con .env en la raíz del repo:
    python scripts/scan_receipt_from_whatsapp.py
"""
from __future__ import annotations

import base64
import json
import os
import sys
from datetime import date
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

# ── Configuración ────────────────────────────────────────────────────────────
PHONE_NUMBER   = "56977577307"
WHATSAPP_BASE  = "https://hotboat-whatsapp-staging-tom.up.railway.app"
GASTOS_URL     = f"{WHATSAPP_BASE}/api/admin/gastos"
GEMINI_MODEL   = "gemini-3.1-flash-lite"
GEMINI_URL     = (
    f"https://generativelanguage.googleapis.com/v1beta/models"
    f"/{GEMINI_MODEL}:generateContent"
)
DATABASE_URL   = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# ─────────────────────────────────────────────────────────────────────────────


def get_latest_image() -> dict:
    """Devuelve la fila más reciente de imagen entrante del número configurado."""
    if not DATABASE_URL:
        sys.exit("ERROR: DATABASE_URL no definido")

    import psycopg

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                SELECT phone_number, message_text, response_text,
                       message_type, direction, created_at
                FROM whatsapp_conversations
                WHERE phone_number  = %s
                  AND message_type  = 'image'
                  AND direction     = 'incoming'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (PHONE_NUMBER,),
            )
            row = cur.fetchone()

    if not row:
        sys.exit(f"No se encontraron imágenes entrantes de {PHONE_NUMBER}")

    print(f"[db] Imagen encontrada — created_at: {row['created_at']}")
    print(f"[db] response_text: {row['response_text']}")
    return dict(row)


def download_image(relative_url: str) -> tuple[bytes, str]:
    """Descarga la imagen y devuelve (bytes, mime_type)."""
    url = f"{WHATSAPP_BASE}{relative_url}"
    print(f"[img] Descargando: {url}")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    mime = r.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
    print(f"[img] Descargada — {len(r.content)} bytes, mime: {mime}")
    return r.content, mime


def analyze_with_gemini(image_bytes: bytes, mime_type: str) -> dict:
    """Envía la imagen a Gemini y devuelve {monto, comercio, fecha}."""
    if not GEMINI_API_KEY:
        sys.exit("ERROR: GEMINI_API_KEY no definido")

    b64 = base64.b64encode(image_bytes).decode()
    payload = {
        "contents": [{
            "parts": [
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": b64,
                    }
                },
                {
                    "text": (
                        "Analiza esta boleta de Chile. "
                        "Extrae: 1) monto total en CLP (entero), "
                        "2) nombre del comercio, "
                        "3) fecha en formato YYYY-MM-DD (null si no se ve). "
                        'Responde SOLO con JSON: {"monto": 12500, "comercio": "Copec", "fecha": "2024-01-15"}'
                    )
                },
            ]
        }],
        "generationConfig": {"maxOutputTokens": 300, "temperature": 0},
    }

    print("[gemini] Enviando imagen para análisis…")
    r = requests.post(
        GEMINI_URL,
        params={"key": GEMINI_API_KEY},
        json=payload,
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()

    raw_text = (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    )
    print(f"[gemini] Respuesta raw: {raw_text!r}")

    # Limpiar markdown si Gemini envuelve la respuesta en ```json ... ```
    clean = raw_text.strip()
    if clean.startswith("```"):
        clean = clean.split("```")[1]
        if clean.startswith("json"):
            clean = clean[4:]
    clean = clean.strip()

    try:
        extracted = json.loads(clean)
    except json.JSONDecodeError as exc:
        sys.exit(f"ERROR: Gemini no devolvió JSON válido — {exc}\nRespuesta: {raw_text}")

    print(f"[gemini] Extraído: {extracted}")
    return extracted


def register_gasto(monto: int, comercio: str, fecha: str | None) -> dict:
    """Registra el gasto vía API."""
    if not fecha:
        fecha = date.today().isoformat()

    body = {
        "fecha": fecha,
        "monto": int(monto),
        "comercio": comercio or "Desconocido",
        "descripcion": "",
        "notas": "Auto-escaneado desde WhatsApp",
    }
    print(f"[gastos] POST {GASTOS_URL} — {body}")
    r = requests.post(GASTOS_URL, json=body, timeout=30)
    r.raise_for_status()
    result = r.json()
    print(f"[gastos] Respuesta: {result}")
    return result


def main() -> None:
    row = get_latest_image()
    image_bytes, mime_type = download_image(row["response_text"])
    extracted = analyze_with_gemini(image_bytes, mime_type)

    monto    = extracted.get("monto")
    comercio = extracted.get("comercio", "")
    fecha    = extracted.get("fecha")

    if not monto:
        sys.exit(f"ERROR: Gemini no pudo extraer el monto — {extracted}")

    result = register_gasto(monto, comercio, fecha)

    print("\n" + "=" * 50)
    print("GASTO REGISTRADO:")
    print(f"  Comercio : {comercio}")
    print(f"  Monto    : ${monto:,} CLP")
    print(f"  Fecha    : {fecha or date.today().isoformat()}")
    print(f"  Resultado: {result}")
    print("=" * 50)


if __name__ == "__main__":
    main()
