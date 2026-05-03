"""
Recolector de señales climáticas para Pucón.
Fuente: OpenWeather Current Weather API
Requiere: OPENWEATHER_API_KEY (free tier disponible en openweathermap.org)
"""
import datetime as dt
import logging
import os
import time

import requests
from psycopg.types.json import Json

from db.connection import get_connection

log = logging.getLogger(__name__)

PUCON_LAT = -39.2755
PUCON_LON = -71.9771
OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"


def _round_to_hour(ts: dt.datetime) -> dt.datetime:
    return ts.replace(minute=0, second=0, microsecond=0)


def _weather_score(temp: float, rain_1h: float, wind_ms: float, cloudiness: int) -> float:
    """
    Score orientado a HotBoat: clima frío/templado sin tormenta = bueno.
    Rango 0-100.
    """
    score = 50
    wind_kph = wind_ms * 3.6

    if 5 <= temp <= 18:
        score += 40
    elif temp < 5 or temp > 25:
        score -= 20

    if rain_1h >= 0.1 and rain_1h <= 5:
        score += 20
    elif rain_1h > 10:
        score -= 40

    if cloudiness >= 70:
        score += 10

    if wind_kph > 30:
        score -= 30

    return max(0.0, min(100.0, float(score)))


def _save_snapshot(conn, collected_at, target_date, metric_name, metric_value, metric_unit, raw):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO tourism_signal_snapshots
                (collected_at, target_date, source_type, source_name,
                 metric_name, metric_value, metric_unit, raw_payload, status)
            VALUES (%s, %s, 'weather', 'openweather', %s, %s, %s, %s, 'ok')
            ON CONFLICT (collected_at, source_type, metric_name, target_date)
            DO UPDATE SET
                metric_value  = EXCLUDED.metric_value,
                raw_payload   = EXCLUDED.raw_payload
            """,
            (collected_at, target_date, metric_name, metric_value, metric_unit, Json(raw)),
        )


def _save_query_log(conn, success, http_status, error_message, elapsed_ms):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO source_query_log
                (source_name, query_type, query_params, success,
                 http_status, error_message, response_time_ms)
            VALUES ('openweather', 'current_weather', %s, %s, %s, %s, %s)
            """,
            (Json({"lat": PUCON_LAT, "lon": PUCON_LON}),
             success, http_status, error_message, elapsed_ms),
        )


def collect_weather_signals() -> int:
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        log.warning("[weather] OPENWEATHER_API_KEY no configurada - saltando")
        return 0

    now = dt.datetime.now(dt.timezone.utc)
    collected_at = _round_to_hour(now)
    target_date = now.date()

    t0 = time.time()
    try:
        resp = requests.get(
            OPENWEATHER_URL,
            params={
                "lat": PUCON_LAT,
                "lon": PUCON_LON,
                "appid": api_key,
                "units": "metric",
                "lang": "es",
            },
            timeout=15,
        )
        elapsed_ms = int((time.time() - t0) * 1000)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        elapsed_ms = int((time.time() - t0) * 1000)
        log.error("[weather] Error API: %s", exc)
        with get_connection() as conn:
            _save_query_log(conn, False, None, str(exc), elapsed_ms)
            conn.commit()
        return 0

    main = data.get("main", {})
    wind = data.get("wind", {})
    clouds = data.get("clouds", {})
    rain = data.get("rain", {})

    temp = float(main.get("temp", 10.0))
    feels_like = main.get("feels_like")
    humidity = main.get("humidity")
    cloudiness = int(clouds.get("all", 0))
    wind_ms = float(wind.get("speed", 0.0))
    rain_1h = float(rain.get("1h", 0.0))
    score = _weather_score(temp, rain_1h, wind_ms, cloudiness)

    raw = {
        "location": "Pucón,Chile",
        "lat": PUCON_LAT,
        "lon": PUCON_LON,
        "payload": data,
    }

    metrics = [
        ("temperature_c",  temp,                    "°C"),
        ("feels_like_c",   feels_like,              "°C"),
        ("humidity_pct",   humidity,                "%"),
        ("cloudiness_pct", cloudiness,              "%"),
        ("wind_ms",        wind_ms,                 "m/s"),
        ("wind_kph",       round(wind_ms * 3.6, 2), "km/h"),
        ("rain_1h_mm",     rain_1h,                 "mm"),
        ("weather_score",  score,                   "score"),
    ]

    with get_connection() as conn:
        _save_query_log(conn, True, resp.status_code, None, elapsed_ms)
        for name, value, unit in metrics:
            _save_snapshot(conn, collected_at, target_date, name, value, unit, raw)
        conn.commit()

    log.info(
        "[weather] temp=%.1f°C rain=%.1fmm wind=%.1fkm/h score=%.0f",
        temp, rain_1h, wind_ms * 3.6, score,
    )
    return len(metrics)


def run() -> int:
    return collect_weather_signals()
