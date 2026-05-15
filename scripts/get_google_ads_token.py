"""
Script de una sola vez para obtener el GOOGLE_ADS_REFRESH_TOKEN.

Ejecutar LOCALMENTE (no en Railway):
  python scripts/get_google_ads_token.py

Pasos previos:
  1. Google Cloud Console → crear proyecto → habilitar "Google Ads API"
  2. APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID
     Tipo: Desktop app
     Copia client_id y client_secret
  3. Pega client_id y client_secret abajo (o como env vars)
  4. Ejecuta este script → abre el navegador → autoriza → imprime el refresh token
  5. Copia GOOGLE_ADS_REFRESH_TOKEN y ponlo en Railway como variable de entorno
"""
import http.server
import os
import threading
import urllib.parse
import webbrowser

import requests  # ya está en requirements.txt

# -------------------------------------------------
# EDITA ESTOS VALORES (o ponlos como variables de entorno)
# -------------------------------------------------
CLIENT_ID     = os.getenv("GOOGLE_ADS_CLIENT_ID", "TU_CLIENT_ID_AQUI")
CLIENT_SECRET = os.getenv("GOOGLE_ADS_CLIENT_SECRET", "TU_CLIENT_SECRET_AQUI")
# -------------------------------------------------

SCOPE        = "https://www.googleapis.com/auth/adwords"
PORT         = 8080
REDIRECT_URI = f"http://localhost:{PORT}"

code_holder: list = [None]


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if "code" in params:
            code_holder[0] = params["code"][0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Listo. Puedes cerrar esta ventana.")

    def log_message(self, *args):  # silenciar logs del servidor
        pass


def main():
    if "TU_CLIENT_ID" in CLIENT_ID:
        print("ERROR: edita CLIENT_ID y CLIENT_SECRET en este script (o ponlos como env vars)")
        return

    # Arrancar servidor local para capturar el código
    server = http.server.HTTPServer(("localhost", PORT), _CallbackHandler)
    t = threading.Thread(target=server.handle_request)
    t.start()

    auth_url = (
        "https://accounts.google.com/o/oauth2/auth"
        f"?client_id={urllib.parse.quote(CLIENT_ID)}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
        f"&response_type=code"
        f"&scope={urllib.parse.quote(SCOPE)}"
        f"&access_type=offline"
        f"&prompt=consent"
    )

    print(f"\nAbriendo navegador para autorización de Google Ads...")
    print(f"Si no se abre, copia esta URL:\n{auth_url}\n")
    webbrowser.open(auth_url)

    t.join(timeout=120)
    server.server_close()

    if not code_holder[0]:
        print("ERROR: no se recibió código. Inténtalo de nuevo.")
        return

    # Intercambiar código por tokens
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code_holder[0],
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    tokens = resp.json()

    if "refresh_token" not in tokens:
        print(f"ERROR obteniendo tokens: {tokens}")
        return

    print("\n" + "=" * 60)
    print("COPIA ESTAS VARIABLES EN RAILWAY:")
    print("=" * 60)
    print(f"GOOGLE_ADS_REFRESH_TOKEN={tokens['refresh_token']}")
    print(f"GOOGLE_ADS_CLIENT_ID={CLIENT_ID}")
    print(f"GOOGLE_ADS_CLIENT_SECRET={CLIENT_SECRET}")
    print("=" * 60)
    print("\nAccess token (expira en 1h, no lo guardes):", tokens.get("access_token", "")[:40] + "...")


if __name__ == "__main__":
    main()
