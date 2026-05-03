"""
Recolector de señales de tráfico hacia Pucón.
Fuente: Google Maps Distance Matrix API
Requiere: GOOGLE_MAPS_API_KEY con acceso a Distance Matrix + tráfico en tiempo real
(departure_time=now requiere plan pagado de Google Maps Platform)
"""
import datetime as dt
import logging
import os
import time

import requests
from psycopg.types.json import Json

from db.connection import get_connection

log = logging.getLogger(__name__)

GMAPS_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"

# (label, origin, destination)
ROUTES = [
    ("villarrica_pucon",    "Villarrica, Chile",                       "Pucón, Chile"),
    ("temuco_pucon",        "Temuco, Chile",                           "Pucón, Chile"),
    ("aeropuerto_pucon",    "Aeropuerto La Araucanía, Freire, Chile",  "Pucón, Chile"),
    ("caburgua_pucon",      "Caburgua, Pucón, Chile",                  "Pucón, Chile"),
]


def _round_to_hour(ts: dt.datetime) -> dt.datetime:
    return ts.replace(minute=0, second=0, microsecond=0)


def _save_snapshot(conn, collected_at, target_date, metric_name, metric_value, metric_unit, raw):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO tourism_signal_snapshots
                (collected_at, target_date, source_type, source_name,
                 metric_name, metric_value, metric_unit, raw_payload, status)
            VALUES (%s, %s, 'traffic', 'google_maps', %s, %s, %s, %s, 'ok')
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
            VALUES ('google_maps', 'distance_matrix', %s, %s, %s, %s, %s)
            """,
            (Json(query_params), success, http_status, error_message, elapsed_ms),
        )


def _fetch_route(api_key: str, origin: str, destination: str) -> tuple:
    params = {
        "origins": origin,
        "destinations": destination,
        "departure_time": "now",
        "traffic_model": "best_guess",
        "key": api_key,
    }
    t0 = time.time()
    resp = requests.get(GMAPS_URL, params=params, timeout=15)
    elapsed_ms = int((time.time() - t0) * 1000)
    resp.raise_for_status()
    return resp.json(), elapsed_ms, resp.status_code


def _parse_durations(api_data: dict) -> tuple:
    """Returns (normal_min, traffic_min). Both None if response is invalid."""
    try:
        elem = api_data["rows"][0]["elements"][0]
        if elem.get("status") != "OK":
            return None, None
        normal_s = elem["duration"]["value"]
        traffic_s = elem.get("duration_in_traffic", {}).get("value")
        return normal_s / 60.0, (traffic_s / 60.0 if traffic_s else None)
    except (KeyError, IndexError):
        return None, None


def collect_traffic_signals() -> int:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        log.warning("[traffic] GOOGLE_MAPS_API_KEY no configurada - saltando")
        return 0

    now = dt.datetime.now(dt.timezone.utc)
    collected_at = _round_to_hour(now)
    target_date = now.date()
    total_rows = 0
    ratios = []

    for label, origin, destination in ROUTES:
        try:
            api_data, elapsed_ms, http_status = _fetch_route(api_key, origin, destination)
        except Exception as exc:
            log.error("[traffic] %s: %s", label, exc)
            with get_connection() as conn:
                _save_query_log(
                    conn, {"origin": origin, "destination": destination},
                    False, None, str(exc), None,
                )
                conn.commit()
            continue

        normal_min, traffic_min = _parse_durations(api_data)
        if normal_min is None:
            log.warning("[traffic] %s: respuesta inesperada de API", label)
            continue

        if traffic_min is None:
            # API sin datos de tráfico en tiempo real: asumir sin congestión
            traffic_min = normal_min

        diff_min = traffic_min - normal_min
        ratio = traffic_min / normal_min if normal_min > 0 else 1.0
        score = min(100.0, max(0.0, (ratio - 1.0) * 100.0))
        ratios.append(ratio)

        raw = {"origin": origin, "destination": destination, "api_response": api_data}

        route_metrics = [
            (f"traffic_{label}_normal_min",  normal_min,  "min"),
            (f"traffic_{label}_traffic_min", traffic_min, "min"),
            (f"traffic_{label}_diff_min",    diff_min,    "min"),
            (f"traffic_{label}_ratio",       ratio,       "ratio"),
            (f"traffic_{label}_score",       score,       "score"),
        ]

        with get_connection() as conn:
            _save_query_log(
                conn, {"origin": origin, "destination": destination},
                True, http_status, None, elapsed_ms,
            )
            for name, value, unit in route_metrics:
                _save_snapshot(conn, collected_at, target_date, name, value, unit, raw)
            conn.commit()

        total_rows += len(route_metrics)
        log.info(
            "[traffic] %s: normal=%.0fmin traffic=%.0fmin ratio=%.2f score=%.0f",
            label, normal_min, traffic_min, ratio, score,
        )
        time.sleep(0.5)  # cortesía de rate limit entre rutas

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
        log.info("[traffic] avg ratio=%.2f avg score=%.0f", avg_ratio, avg_score)

    return total_rows


def run() -> int:
    return collect_traffic_signals()
