"""
Calcula el índice de flujo turístico de Pucón y lo guarda en pucon_flow_index.

Pesos cuando hay datos de alojamiento:
  40% lodging_availability + 25% lodging_price + 25% traffic + 10% weather

Pesos sin datos de alojamiento (MVP):
  60% traffic + 40% weather  (normalizado a los que estén disponibles)

Clasificación:
  0-30   → bajo
  31-55  → medio
  56-75  → alto
  76-100 → muy_alto
"""
import datetime as dt
import logging

from db.connection import get_connection

log = logging.getLogger(__name__)

_LEVELS = [
    (30,  "bajo",     "Activar promoción last minute, subir campañas con descuento, enfocar en parejas locales o turistas ya instalados."),
    (55,  "medio",    "Mantener campañas normales, destacar experiencia premium y horarios disponibles."),
    (75,  "alto",     "Subir presupuesto, reducir descuentos, usar urgencia: últimos horarios disponibles."),
    (100, "muy_alto", "Priorizar precio completo, campañas de alta intención, remarketing y disponibilidad limitada."),
]


def _classify(score: float) -> tuple:
    for threshold, level, action in _LEVELS:
        if score <= threshold:
            return level, action
    return _LEVELS[-1][1], _LEVELS[-1][2]


def _latest_metric(conn, target_date: dt.date, source_type: str, metric_name: str):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT metric_value FROM tourism_signal_snapshots
            WHERE target_date = %s
              AND source_type = %s
              AND metric_name = %s
              AND status = 'ok'
            ORDER BY collected_at DESC
            LIMIT 1
            """,
            (target_date, source_type, metric_name),
        )
        row = cur.fetchone()
    return float(row[0]) if row and row[0] is not None else None


def calculate_pucon_flow_index() -> int:
    now = dt.datetime.now(dt.timezone.utc)
    calculated_at = now.replace(minute=0, second=0, microsecond=0)
    target_date = now.date()

    with get_connection() as conn:
        weather_score  = _latest_metric(conn, target_date, "weather",  "weather_score")
        traffic_score  = _latest_metric(conn, target_date, "traffic",  "traffic_avg_score")
        lodging_avail  = _latest_metric(conn, target_date, "lodging",  "lodging_availability_score")
        lodging_price  = _latest_metric(conn, target_date, "lodging",  "lodging_price_score")

    if weather_score is None and traffic_score is None:
        log.warning("[flow_index] Sin señales disponibles para %s - omitiendo", target_date)
        return 0

    # Construir lista (score, weight) según datos disponibles
    parts = []
    explanation_parts = []
    has_lodging = lodging_avail is not None and lodging_price is not None

    if has_lodging:
        parts.append((lodging_avail, 0.40))
        parts.append((lodging_price, 0.25))
        explanation_parts += [f"aloj_disp={lodging_avail:.0f}", f"aloj_precio={lodging_price:.0f}"]
        if traffic_score is not None:
            parts.append((traffic_score, 0.25))
            explanation_parts.append(f"trafico={traffic_score:.0f}")
        if weather_score is not None:
            parts.append((weather_score, 0.10))
            explanation_parts.append(f"clima={weather_score:.0f}")
    else:
        if traffic_score is not None:
            parts.append((traffic_score, 0.60))
            explanation_parts.append(f"trafico={traffic_score:.0f}")
        if weather_score is not None:
            parts.append((weather_score, 0.40))
            explanation_parts.append(f"clima={weather_score:.0f}")

    total_w = sum(w for _, w in parts)
    final_score = round(sum(s * (w / total_w) for s, w in parts), 2)
    final_score = max(0.0, min(100.0, final_score))

    flow_level, recommended_action = _classify(final_score)
    explanation = "Scores: " + ", ".join(explanation_parts) + f" → final={final_score:.1f}"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pucon_flow_index
                    (calculated_at, target_date,
                     lodging_availability_score, lodging_price_score,
                     traffic_score, weather_score,
                     final_flow_score, flow_level,
                     recommended_action, explanation)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (calculated_at, target_date) DO UPDATE SET
                    lodging_availability_score = EXCLUDED.lodging_availability_score,
                    lodging_price_score        = EXCLUDED.lodging_price_score,
                    traffic_score              = EXCLUDED.traffic_score,
                    weather_score              = EXCLUDED.weather_score,
                    final_flow_score           = EXCLUDED.final_flow_score,
                    flow_level                 = EXCLUDED.flow_level,
                    recommended_action         = EXCLUDED.recommended_action,
                    explanation                = EXCLUDED.explanation
                """,
                (
                    calculated_at, target_date,
                    lodging_avail, lodging_price,
                    traffic_score, weather_score,
                    final_score, flow_level,
                    recommended_action, explanation,
                ),
            )
        conn.commit()

    log.info(
        "[flow_index] %s → score=%.1f level=%s | %s",
        target_date, final_score, flow_level, explanation,
    )
    return 1


def run() -> int:
    return calculate_pucon_flow_index()
