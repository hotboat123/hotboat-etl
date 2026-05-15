"""
Recolector de disponibilidad y precios de alojamiento en Pucón.
Fuente: Booking.com (scraping público)
No requiere API key.

Estrategia:
  1. Intento rápido con requests (sin JS)
  2. Fallback a Selenium si requests no trae precios

Consulta 3 fechas: hoy, mañana, próximo sábado.
Guarda conteo, precios y scores vs baseline de 30 días.
"""
import datetime as dt
import json
import logging
import re
import statistics
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup
from psycopg.types.json import Json

from db.connection import get_connection

log = logging.getLogger(__name__)

BOOKING_SEARCH = "https://www.booking.com/searchresults.html"

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.booking.com/",
}


# ---------------------------------------------------------------------------
# Helpers de fecha y URL
# ---------------------------------------------------------------------------

def _round_to_hour(ts: dt.datetime) -> dt.datetime:
    return ts.replace(minute=0, second=0, microsecond=0)


def _next_saturday(today: dt.date) -> dt.date:
    days = (5 - today.weekday()) % 7
    return today + dt.timedelta(days=days or 7)


def _search_url(checkin: dt.date) -> str:
    checkout = checkin + dt.timedelta(days=1)
    return (
        f"{BOOKING_SEARCH}"
        f"?ss=Puc%C3%B3n%2C+Chile&dest_type=city"
        f"&checkin={checkin.isoformat()}&checkout={checkout.isoformat()}"
        f"&group_adults=2&no_rooms=1&order=popularity&lang=es&currency=CLP"
    )


# ---------------------------------------------------------------------------
# Parsing de HTML
# ---------------------------------------------------------------------------

def _parse_price(text: str) -> Optional[float]:
    """Extrae precio CLP de texto como '$45.000' o 'CLP 45,000'."""
    cleaned = re.sub(r"[^\d.,]", "", text.strip())
    if not cleaned:
        return None
    try:
        # Formato chileno: punto como miles (45.000 → 45000)
        if re.search(r"\.\d{3}", cleaned):
            cleaned = cleaned.replace(".", "").replace(",", "")
        else:
            cleaned = cleaned.replace(",", "")
        val = float(cleaned)
        if 5_000 <= val <= 10_000_000:
            return val
    except ValueError:
        pass
    return None


def _extract_from_html(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    prices = []

    # Intento 1: data-testid actual de Booking.com React
    for el in soup.select('[data-testid="price-and-discounted-price"]'):
        p = _parse_price(el.get_text())
        if p:
            prices.append(p)

    # Intento 2: cualquier data-testid con "price"
    if not prices:
        for el in soup.find_all(attrs={"data-testid": re.compile(r"price", re.I)}):
            p = _parse_price(el.get_text())
            if p:
                prices.append(p)

    # Intento 3: JSON-LD estructurado embebido
    if not prices:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                for item in (data if isinstance(data, list) else [data]):
                    raw_price = (
                        item.get("offers", {}).get("price")
                        or item.get("priceRange", "")
                    )
                    p = _parse_price(str(raw_price))
                    if p:
                        prices.append(p)
            except Exception:
                pass

    # Conteo de propiedades en el texto de resultado
    count = len(prices)
    count_el = soup.find(string=re.compile(
        r"\d[\d.]*\s+(?:alojamiento|propiedad|resultado|hotel)", re.I
    ))
    if count_el:
        m = re.search(r"([\d.]+)", count_el)
        if m:
            stripped = m.group(1).replace(".", "")
            if stripped:
                parsed = int(stripped)
                if parsed > 0:
                    count = parsed

    return {
        "available_count": count,
        "prices": prices,
        "min_price": min(prices) if prices else None,
        "avg_price": round(statistics.mean(prices)) if prices else None,
        "median_price": round(statistics.median(prices)) if prices else None,
    }


# ---------------------------------------------------------------------------
# Estrategia de fetch: requests → Selenium
# ---------------------------------------------------------------------------

def _fetch_with_requests(url: str) -> Optional[dict]:
    try:
        session = requests.Session()
        session.get("https://www.booking.com/", headers=HTTP_HEADERS, timeout=15)
        time.sleep(1.5)
        resp = session.get(url, headers=HTTP_HEADERS, timeout=20, allow_redirects=True)
        resp.raise_for_status()
        result = _extract_from_html(resp.text)
        if result["prices"]:
            result["method"] = "requests"
            result["http_status"] = resp.status_code
            return result
    except Exception as exc:
        log.debug("[lodging] requests falló: %s", exc)
    return None


def _fetch_with_selenium(url: str) -> Optional[dict]:
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
        from utils.chrome import build_driver
    except ImportError:
        log.warning("[lodging] Selenium no disponible")
        return None

    driver = None
    try:
        driver = build_driver()
        driver.get(url)

        # Esperar tarjetas de propiedades o precios
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    '[data-testid="price-and-discounted-price"], '
                    '[data-testid="property-card"]',
                ))
            )
        except Exception:
            time.sleep(6)  # si no aparecen en 20s, intentar igual

        result = _extract_from_html(driver.page_source)
        result["method"] = "selenium"
        result["http_status"] = 200
        return result
    except Exception as exc:
        log.error("[lodging] Selenium falló: %s", exc)
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------

def _save_snapshot(conn, collected_at, target_date, metric_name, metric_value, metric_unit, raw):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO tourism_signal_snapshots
                (collected_at, target_date, source_type, source_name,
                 metric_name, metric_value, metric_unit, raw_payload, status)
            VALUES (%s, %s, 'lodging', 'booking', %s, %s, %s, %s, 'ok')
            ON CONFLICT (collected_at, source_type, metric_name, target_date)
            DO UPDATE SET
                metric_value = EXCLUDED.metric_value,
                raw_payload  = EXCLUDED.raw_payload
            """,
            (collected_at, target_date, metric_name, metric_value, metric_unit, Json(raw)),
        )


def _save_query_log(conn, query_params, success, http_status, error_message, elapsed_ms):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO source_query_log
                (source_name, query_type, query_params, success,
                 http_status, error_message, response_time_ms)
            VALUES ('booking', 'search', %s, %s, %s, %s, %s)
            """,
            (Json(query_params), success, http_status, error_message, elapsed_ms),
        )


def _get_baseline_30d(conn, metric_name: str) -> Optional[float]:
    """Promedio del metric en los últimos 30 días (excluye hoy para no sesgar)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT AVG(metric_value)
            FROM tourism_signal_snapshots
            WHERE source_type = 'lodging'
              AND metric_name  = %s
              AND status       = 'ok'
              AND collected_at >= now() - interval '30 days'
              AND collected_at <  date_trunc('day', now())
            """,
            (metric_name,),
        )
        row = cur.fetchone()
    return float(row[0]) if row and row[0] is not None else None


# ---------------------------------------------------------------------------
# Scores
# ---------------------------------------------------------------------------

def _availability_score(count: int, baseline: Optional[float]) -> float:
    """Muchos disponibles = demanda baja → score bajo."""
    if not baseline:
        return 50.0
    return max(0.0, min(100.0, 100.0 * (1.0 - count / baseline)))


def _price_score(avg_price: float, baseline: Optional[float]) -> float:
    """Precios sobre el promedio histórico → demanda alta → score alto."""
    if not baseline:
        return 50.0
    return max(0.0, min(100.0, 50.0 + 50.0 * ((avg_price - baseline) / baseline)))


# ---------------------------------------------------------------------------
# Scrape por fecha individual
# ---------------------------------------------------------------------------

def _label_for_date(checkin: dt.date, today: dt.date) -> str:
    delta = (checkin - today).days
    if delta == 0:
        return "hoy"
    if delta == 1:
        return "manana"
    if checkin.weekday() == 5:
        return "sabado"
    return f"d{delta}"


def _scrape_one_date(
    collected_at: dt.datetime,
    checkin: dt.date,
    today: dt.date,
) -> bool:
    label = _label_for_date(checkin, today)
    url = _search_url(checkin)
    t0 = time.time()

    result = _fetch_with_requests(url)
    if result is None:
        log.info("[lodging] %s (%s): usando Selenium...", checkin, label)
        result = _fetch_with_selenium(url)

    elapsed_ms = int((time.time() - t0) * 1000)

    if result is None:
        log.warning("[lodging] %s (%s): sin datos", checkin, label)
        with get_connection() as conn:
            _save_query_log(
                conn, {"checkin": str(checkin), "label": label, "url": url},
                False, None, "sin_datos", elapsed_ms,
            )
            conn.commit()
        return False

    raw = {
        "checkin": str(checkin),
        "checkout": str(checkin + dt.timedelta(days=1)),
        "label": label,
        "url": url,
        "method": result.get("method"),
        "prices_sample": result["prices"][:10],
    }

    # El target_date es el día de la medición (hoy), no el checkin.
    # El label diferencia las métricas por fecha consultada.
    target_date = today

    with get_connection() as conn:
        # Baselines para esta misma ventana de fecha
        baseline_count = _get_baseline_30d(conn, f"lodging_{label}_count")
        baseline_price = _get_baseline_30d(conn, f"lodging_{label}_avg_price")

        avail_score = _availability_score(result["available_count"], baseline_count)
        price_score = (
            _price_score(result["avg_price"], baseline_price)
            if result["avg_price"]
            else 50.0
        )

        metrics = [
            (f"lodging_{label}_count",         result["available_count"],  "unidades"),
            (f"lodging_{label}_min_price",      result["min_price"],        "CLP"),
            (f"lodging_{label}_avg_price",      result["avg_price"],        "CLP"),
            (f"lodging_{label}_median_price",   result["median_price"],     "CLP"),
            (f"lodging_{label}_avail_score",    avail_score,                "score"),
            (f"lodging_{label}_price_score",    price_score,                "score"),
        ]

        # También guardamos los scores principales (sin label) para que el
        # flow index los encuentre fácilmente. Usamos hoy como referencia base.
        if label == "hoy":
            metrics += [
                ("lodging_availability_score", avail_score, "score"),
                ("lodging_price_score",        price_score, "score"),
            ]

        _save_query_log(
            conn,
            {"checkin": str(checkin), "label": label, "url": url, "method": result.get("method")},
            True, result.get("http_status", 200), None, elapsed_ms,
        )
        for name, value, unit in metrics:
            if value is not None:
                _save_snapshot(conn, collected_at, target_date, name, value, unit, raw)
        conn.commit()

    log.info(
        "[lodging] %s (%s): count=%d min=%s avg=%s avail_score=%.0f price_score=%.0f [%s]",
        checkin, label,
        result["available_count"],
        result["min_price"], result["avg_price"],
        avail_score, price_score, result.get("method"),
    )
    return True


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def collect_lodging_signals() -> int:
    now = dt.datetime.now(dt.timezone.utc)
    collected_at = _round_to_hour(now)
    today = now.date()

    dates = [
        today,
        today + dt.timedelta(days=1),
        _next_saturday(today),
    ]

    total = 0
    for checkin in dates:
        ok = _scrape_one_date(collected_at, checkin, today)
        if ok:
            total += 1
        time.sleep(4)  # pausa entre búsquedas para no saturar

    return total


def run() -> int:
    return collect_lodging_signals()
