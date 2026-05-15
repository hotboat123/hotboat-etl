"""
Recolector de tiempos de tráfico hacia Pucón.
Fuente: Google Maps Directions (scraping con Selenium).
No requiere API key.

Mide el tiempo de viaje real (con tráfico) desde 4 orígenes hacia Pucón.
El tiempo "normal" se calcula como el percentil 10 de los últimos 30 días
almacenados (= condición sin congestión). Las primeras semanas usa
estimaciones hardcodeadas como fallback hasta acumular baseline.

Estrategia de extracción (múltiples fallbacks por cambios de HTML):
  1. aria-label de elementos de ruta
  2. Texto visible del body, líneas cortas
Validación: cada ruta tiene un rango de minutos esperados para filtrar
falsos positivos.
"""
import datetime as dt
import logging
import os
import re
import time
from typing import Optional

from psycopg.types.json import Json

from db.connection import get_connection

log = logging.getLogger(__name__)

GMAPS_DIR_URL = (
    "https://www.google.com/maps/dir/{lat1},{lon1}/{lat2},{lon2}"
    "/?travelmode=driving&hl=es"
)

# (label, lat_orig, lon_orig, lat_dest, lon_dest, normal_min_fallback)
# normal_min_fallback = estimación de tiempo sin tráfico hasta tener baseline de 30 días
ROUTES = [
    ("villarrica_pucon",  -39.2817, -72.2269, -39.2755, -71.9771,  20),
    ("temuco_pucon",      -38.7359, -72.5904, -39.2755, -71.9771,  90),
    ("aeropuerto_pucon",  -38.9262, -72.6509, -39.2755, -71.9771,  80),
    ("caburgua_pucon",    -39.1667, -71.7833, -39.2755, -71.9771,  20),
]

# Rango de tiempo razonable por ruta (min, max) en minutos
# Filtra falsos positivos del scraping
ROUTE_TIME_RANGE = {
    "villarrica_pucon":  ( 8,  70),
    "temuco_pucon":      (55, 200),
    "aeropuerto_pucon":  (45, 200),
    "caburgua_pucon":    ( 8,  70),
}


# ---------------------------------------------------------------------------
# Parseo de tiempo
# ---------------------------------------------------------------------------

def _parse_minutes(text: str) -> Optional[float]:
    """Convierte texto de tiempo Google Maps a minutos. Soporta es/en."""
    text = text.lower().strip()
    # "1 h 30 min" / "1 hora 30 min" / "1 hour 30 min"
    m = re.search(r'(\d+)\s*h(?:ora\w*|our\w*)?\s+(\d+)\s*min', text)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    # "2 h" / "2 horas" — sin minutos adicionales (match al final o con espacio)
    m = re.search(r'\b(\d+)\s*h(?:ora\w*|our\w*)?(?:\s|$)(?!\d)', text)
    if m:
        return float(int(m.group(1)) * 60)
    # "45 min" / "45 minutos" / "45 minutes"
    m = re.search(r'\b(\d+)\s*min', text)
    if m:
        return float(m.group(1))
    return None


# ---------------------------------------------------------------------------
# Selenium
# ---------------------------------------------------------------------------

def _build_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-zygote")
    opts.add_argument("--single-process")
    opts.add_argument("--lang=es-CL,es")
    opts.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    opts.add_experimental_option("useAutomationExtension", False)

    for path in ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"]:
        if os.path.exists(path):
            opts.binary_location = path
            break

    try:
        service = Service(ChromeDriverManager().install())
    except Exception:
        service = Service()

    driver = webdriver.Chrome(service=service, options=opts)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    driver.set_page_load_timeout(30)
    return driver


def _dismiss_consent(driver) -> None:
    """Cierra diálogos de cookies/consentimiento de Google si aparecen."""
    from selenium.webdriver.common.by import By
    for xpath in [
        "//button[contains(., 'Rechazar')]",
        "//button[contains(., 'Aceptar todo')]",
        "//button[contains(., 'Accept all')]",
        "//button[contains(., 'Reject all')]",
        "//form[@action='https://consent.google.com/save']//button",
    ]:
        try:
            btns = driver.find_elements(By.XPATH, xpath)
            if btns:
                btns[0].click()
                time.sleep(1.5)
                return
        except Exception:
            continue


def _extract_travel_time(driver, label: str) -> Optional[float]:
    """
    Extrae el tiempo de viaje de la página actual de Google Maps Directions.
    Intenta primero con aria-labels, luego con texto visible del body.
    Aplica filtro de rango por ruta para descartar falsos positivos.
    """
    from selenium.webdriver.common.by import By

    min_t, max_t = ROUTE_TIME_RANGE.get(label, (2, 600))

    # Estrategia 1: aria-label de cualquier elemento que tenga un tiempo válido
    try:
        for el in driver.find_elements(By.CSS_SELECTOR, "[aria-label]"):
            label_text = el.get_attribute("aria-label") or ""
            t = _parse_minutes(label_text)
            if t and min_t <= t <= max_t:
                log.debug("[traffic] %s aria-label='%s' → %.0f min", label, label_text[:80], t)
                return t
    except Exception:
        pass

    # Estrategia 2: scan línea a línea del texto visible del body
    # Líneas cortas (3-25 chars) que contengan un patrón de tiempo
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        for line in body_text.split("\n"):
            line = line.strip()
            if 3 <= len(line) <= 25:
                t = _parse_minutes(line)
                if t and min_t <= t <= max_t:
                    log.debug("[traffic] %s body='%s' → %.0f min", label, line, t)
                    return t
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------

def _get_baseline_min(conn, metric_name: str, fallback: float) -> float:
    """
    Percentil 10 de los últimos 30 días = tiempo en condición sin congestión.
    Devuelve el fallback hardcodeado si no hay suficientes datos aún.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY metric_value)
            FROM tourism_signal_snapshots
            WHERE source_type = 'traffic'
              AND metric_name  = %s
              AND status       = 'ok'
              AND metric_value > 0
              AND collected_at >= now() - interval '30 days'
            HAVING COUNT(*) >= 10
            """,
            (metric_name,),
        )
        row = cur.fetchone()
    val = float(row[0]) if row and row[0] is not None else None
    return val if val else fallback


def _save_snapshot(conn, collected_at, target_date, metric_name, metric_value, metric_unit, raw):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO tourism_signal_snapshots
                (collected_at, target_date, source_type, source_name,
                 metric_name, metric_value, metric_unit, raw_payload, status)
            VALUES (%s, %s, 'traffic', 'google_maps_scraping', %s, %s, %s, %s, 'ok')
            ON CONFLICT (collected_at, source_type, metric_name, target_date)
            DO UPDATE SET
                metric_value = EXCLUDED.metric_value,
                raw_payload  = EXCLUDED.raw_payload
            """,
            (collected_at, target_date, metric_name, metric_value, metric_unit, Json(raw)),
        )


def _save_query_log(conn, label, success, elapsed_ms, error_message=None):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO source_query_log
                (source_name, query_type, query_params, success,
                 error_message, response_time_ms)
            VALUES ('google_maps_scraping', 'directions', %s, %s, %s, %s)
            """,
            (Json({"route": label}), success, error_message, elapsed_ms),
        )


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def collect_traffic_signals() -> int:
    now = dt.datetime.now(dt.timezone.utc)
    collected_at = now.replace(minute=0, second=0, microsecond=0)
    target_date = now.date()
    total_rows = 0
    ratios = []

    driver = None
    try:
        try:
            driver = _build_driver()
        except Exception as exc:
            log.error("[traffic] No se pudo iniciar Chrome: %s", exc)
            return 0

        # Visitar Google Maps home primero para establecer cookies/sesión
        try:
            driver.get("https://www.google.com/maps?hl=es")
            time.sleep(3)
            _dismiss_consent(driver)
        except Exception:
            pass

        for label, lat1, lon1, lat2, lon2, fallback_normal in ROUTES:
            url = GMAPS_DIR_URL.format(lat1=lat1, lon1=lon1, lat2=lat2, lon2=lon2)
            t0 = time.time()
            travel_min = None

            try:
                driver.get(url)
                time.sleep(2)
                _dismiss_consent(driver)
                time.sleep(3)  # esperar que carguen las rutas
                travel_min = _extract_travel_time(driver, label)
                elapsed_ms = int((time.time() - t0) * 1000)
            except Exception as exc:
                elapsed_ms = int((time.time() - t0) * 1000)
                log.error("[traffic] %s: error Selenium: %s", label, exc)
                with get_connection() as conn:
                    _save_query_log(conn, label, False, elapsed_ms, str(exc)[:300])
                    conn.commit()
                continue

            if travel_min is None:
                log.warning("[traffic] %s: tiempo de viaje no encontrado en la página", label)
                with get_connection() as conn:
                    _save_query_log(conn, label, False, elapsed_ms, "tiempo_no_encontrado")
                    conn.commit()
                time.sleep(2)
                continue

            raw = {
                "label": label,
                "url": url,
                "travel_min": travel_min,
                "page_title": driver.title,
            }

            with get_connection() as conn:
                baseline_min = _get_baseline_min(
                    conn, f"traffic_{label}_travel_min", fallback_normal
                )
                ratio = travel_min / baseline_min if baseline_min > 0 else 1.0
                score = min(100.0, max(0.0, (ratio - 1.0) * 100.0))
                ratios.append(ratio)

                metrics = [
                    (f"traffic_{label}_travel_min",   travel_min,    "min"),
                    (f"traffic_{label}_baseline_min",  baseline_min,  "min"),
                    (f"traffic_{label}_ratio",          ratio,         "ratio"),
                    (f"traffic_{label}_score",          score,         "score"),
                ]
                _save_query_log(conn, label, True, elapsed_ms)
                for name, value, unit in metrics:
                    _save_snapshot(conn, collected_at, target_date, name, value, unit, raw)
                conn.commit()

            log.info(
                "[traffic] %s: %.0f min (baseline=%.0f min) ratio=%.2f score=%.0f",
                label, travel_min, baseline_min, ratio, score,
            )
            total_rows += len(metrics)
            time.sleep(4)  # pausa entre rutas para no saturar

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    # Score promedio agregado (usado por el flow index)
    if ratios:
        avg_ratio = sum(ratios) / len(ratios)
        avg_score = min(100.0, max(0.0, (avg_ratio - 1.0) * 100.0))
        agg_raw = {"routes_measured": len(ratios), "ratios": ratios}
        with get_connection() as conn:
            _save_snapshot(conn, collected_at, target_date,
                           "traffic_avg_ratio", avg_ratio, "ratio", agg_raw)
            _save_snapshot(conn, collected_at, target_date,
                           "traffic_avg_score", avg_score, "score", agg_raw)
            conn.commit()
        total_rows += 2
        log.info(
            "[traffic] promedio: ratio=%.2f score=%.0f (%d/%d rutas exitosas)",
            avg_ratio, avg_score, len(ratios), len(ROUTES),
        )

    return total_rows


def run() -> int:
    return collect_traffic_signals()
