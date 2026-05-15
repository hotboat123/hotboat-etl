"""
Genera dashboard.html con la evolución del flujo turístico de Pucón.

Uso:
    python scripts/generate_dashboard.py            → genera dashboard.html en raíz del repo
    python scripts/generate_dashboard.py -o /ruta   → ruta de salida personalizada

Requiere DATABASE_URL en el entorno.
"""
import sys
from pathlib import Path

from app.tourism_dashboard import load_data, render
from db.connection import get_connection


def main() -> None:
    out_path = Path(__file__).resolve().parent.parent / "dashboard.html"
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg in ("-o", "--output") and i + 1 < len(args):
            out_path = Path(args[i + 1])

    print("Conectando a PostgreSQL…")
    with get_connection() as conn:
        data = load_data(conn)

    html = render(data)
    out_path.write_text(html, encoding="utf-8")
    print(f"Dashboard generado: {out_path}  ({len(html):,} bytes)")
    print(f"  Flujo actual : {data['current_flow']['score']:.1f} ({data['current_flow']['level']})")
    print(f"  Días con datos: {len(data['flow_chart']['dates'])}")


if __name__ == "__main__":
    main()
