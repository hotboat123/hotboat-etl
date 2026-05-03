"""
Recolector de señales de alojamiento en Pucón.
Etapa 2 - pendiente de implementación.

Arquitectura preparada para conectar Booking.com u otra fuente pública.
Métricas objetivo:
  - lodging_availability_score  (100 * (1 - available / baseline))
  - lodging_price_score         (50 + 50 * (avg_price - baseline) / baseline)
  - lodging_available_count
  - lodging_avg_price_clp
  - lodging_median_price_clp

Cuando se implemente, usar collect_at redondeado a la hora y guardar en
tourism_signal_snapshots con source_type='lodging', source_name='booking' (u otro).
"""
import logging

log = logging.getLogger(__name__)


def collect_lodging_signals() -> int:
    log.info("[lodging] Recolección pendiente (etapa 2)")
    return 0


def run() -> int:
    return collect_lodging_signals()
