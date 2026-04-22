"""
Intercambia un token de usuario de corta duración (Explorador Graph) por uno de larga duración (~60 días).

Requisitos en .env o entorno:
  META_APP_ID       ID de la app (Configuración de la app → Básico)
  META_APP_SECRET   Secreto de la app (mismo sitio; no lo subas a Git)
  META_ACCESS_TOKEN Token corto actual (el que acabas de generar en el Explorador)

Uso:
  python scripts/exchange_meta_long_lived_token.py

Salida: imprime access_token largo → cópialo a META_ACCESS_TOKEN en .env y Railway.

Doc Meta: https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived
"""
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
load_dotenv(_root / ".env")

API_VER = os.getenv("META_API_VERSION", "v21.0").lstrip("v")
APP_ID = os.getenv("META_APP_ID", "").strip()
APP_SECRET = os.getenv("META_APP_SECRET", "").strip()
SHORT_TOKEN = os.getenv("META_ACCESS_TOKEN", "").strip()


def main() -> None:
    if not (APP_ID and APP_SECRET and SHORT_TOKEN):
        print(
            "Faltan META_APP_ID, META_APP_SECRET o META_ACCESS_TOKEN en .env",
            file=sys.stderr,
        )
        sys.exit(1)
    url = f"https://graph.facebook.com/v{API_VER}/oauth/access_token"
    r = requests.get(
        url,
        params={
            "grant_type": "fb_exchange_token",
            "client_id": APP_ID,
            "client_secret": APP_SECRET,
            "fb_exchange_token": SHORT_TOKEN,
        },
        timeout=60,
    )
    data = r.json()
    if r.status_code >= 400 or "error" in data:
        err = data.get("error", {})
        print(
            f"Error {err.get('code')}: {err.get('message', data)}",
            file=sys.stderr,
        )
        sys.exit(1)
    long_token = data.get("access_token")
    expires = data.get("expires_in")  # segundos (~5184000 ≈ 60 días)
    print("--- Token de larga duración (guárdalo en META_ACCESS_TOKEN) ---")
    print(long_token)
    if expires:
        print(f"\n(expires_in segundos: {expires}, ~{expires // 86400} días)")
    print("\nNo compartas este token ni lo subas a repositorios públicos.")


if __name__ == "__main__":
    main()
