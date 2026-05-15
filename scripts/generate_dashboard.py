"""
Genera dashboard.html con la evolución del flujo turístico de Pucón.

Uso:
    python scripts/generate_dashboard.py            → genera dashboard.html
    python scripts/generate_dashboard.py -o /ruta   → ruta de salida personalizada

Requiere DATABASE_URL en el entorno (igual que el resto del ETL).
"""
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

SQL_FLOW_INDEX = """
SELECT
    target_date,
    final_flow_score,
    flow_level,
    COALESCE(traffic_score, 0)              AS traffic_score,
    COALESCE(weather_score, 0)              AS weather_score,
    COALESCE(lodging_availability_score, 0) AS lodging_avail_score,
    COALESCE(lodging_price_score, 0)        AS lodging_price_score
FROM pucon_flow_index
WHERE target_date >= CURRENT_DATE - 30
ORDER BY target_date;
"""

SQL_TRAFFIC_ROUTES = """
SELECT
    target_date,
    metric_name,
    AVG(metric_value) AS val
FROM tourism_signal_snapshots
WHERE source_type = 'traffic'
  AND status = 'ok'
  AND metric_name ~ '^traffic_(villarrica|temuco|aeropuerto|caburgua)_pucon_(travel_min|ratio)$'
  AND target_date >= CURRENT_DATE - 14
GROUP BY target_date, metric_name
ORDER BY target_date, metric_name;
"""

SQL_TRAFFIC_LATEST = """
SELECT metric_name, metric_value
FROM tourism_signal_snapshots
WHERE source_type = 'traffic'
  AND status = 'ok'
  AND collected_at = (
      SELECT MAX(collected_at)
      FROM tourism_signal_snapshots
      WHERE source_type = 'traffic' AND status = 'ok'
  );
"""

SQL_WEATHER_LATEST = """
SELECT metric_name, metric_value
FROM tourism_signal_snapshots
WHERE source_type = 'weather'
  AND status = 'ok'
  AND collected_at = (
      SELECT MAX(collected_at)
      FROM tourism_signal_snapshots
      WHERE source_type = 'weather' AND status = 'ok'
  );
"""

SQL_LODGING_LATEST = """
SELECT metric_name, metric_value
FROM tourism_signal_snapshots
WHERE source_type = 'lodging'
  AND status = 'ok'
  AND collected_at = (
      SELECT MAX(collected_at)
      FROM tourism_signal_snapshots
      WHERE source_type = 'lodging' AND status = 'ok'
  );
"""

SQL_SOURCE_RELIABILITY = """
SELECT
    source_name,
    COUNT(*)                                              AS total,
    SUM(CASE WHEN success THEN 1 ELSE 0 END)             AS ok,
    ROUND(100.0 * SUM(CASE WHEN success THEN 1 ELSE 0 END) / NULLIF(COUNT(*),0), 1) AS pct,
    ROUND(AVG(response_time_ms))                          AS avg_ms
FROM source_query_log
WHERE requested_at >= NOW() - INTERVAL '7 days'
GROUP BY source_name
ORDER BY source_name;
"""

SQL_CURRENT_FLOW = """
SELECT final_flow_score, flow_level, recommended_action, explanation, calculated_at
FROM pucon_flow_index
ORDER BY calculated_at DESC
LIMIT 1;
"""

SQL_WEATHER_HISTORY = """
SELECT
    target_date,
    metric_name,
    AVG(metric_value) AS val
FROM tourism_signal_snapshots
WHERE source_type = 'weather'
  AND status = 'ok'
  AND metric_name IN ('temperature_c', 'weather_score', 'rain_1h_mm', 'cloudiness_pct')
  AND target_date >= CURRENT_DATE - 14
GROUP BY target_date, metric_name
ORDER BY target_date, metric_name;
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _j(obj) -> str:
    def default(o):
        if isinstance(o, (date, datetime)):
            return o.isoformat()
        raise TypeError(f"Not serializable: {type(o)}")
    return json.dumps(obj, default=default, ensure_ascii=False)


def _row_to_dict(row, keys):
    return dict(zip(keys, row))


def _fetch(conn, sql) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(sql)
        cols = [d.name for d in cur.description]
        return [_row_to_dict(r, cols) for r in cur.fetchall()]


def _level_color(level: str) -> str:
    return {
        "bajo":     "#22c55e",
        "medio":    "#f59e0b",
        "alto":     "#f97316",
        "muy_alto": "#ef4444",
    }.get(level, "#6b7280")


def _level_label(level: str) -> str:
    return {
        "bajo":     "Bajo",
        "medio":    "Medio",
        "alto":     "Alto",
        "muy_alto": "Muy Alto",
    }.get(level, level.title())


# ---------------------------------------------------------------------------
# Data assembly
# ---------------------------------------------------------------------------

def _load_data(conn) -> dict:
    flow_rows       = _fetch(conn, SQL_FLOW_INDEX)
    traffic_rows    = _fetch(conn, SQL_TRAFFIC_ROUTES)
    traffic_latest  = _fetch(conn, SQL_TRAFFIC_LATEST)
    weather_latest  = _fetch(conn, SQL_WEATHER_LATEST)
    lodging_latest  = _fetch(conn, SQL_LODGING_LATEST)
    reliability     = _fetch(conn, SQL_SOURCE_RELIABILITY)
    current_flow    = _fetch(conn, SQL_CURRENT_FLOW)
    weather_history = _fetch(conn, SQL_WEATHER_HISTORY)

    # ---- Flow index chart ----
    flow_dates  = [r["target_date"].isoformat() for r in flow_rows]
    flow_scores = [float(r["final_flow_score"]) for r in flow_rows]
    traffic_scores  = [float(r["traffic_score"])      for r in flow_rows]
    weather_scores  = [float(r["weather_score"])      for r in flow_rows]
    lodging_a_scores = [float(r["lodging_avail_score"])  for r in flow_rows]
    lodging_p_scores = [float(r["lodging_price_score"])  for r in flow_rows]

    # ---- Traffic routes chart ----
    route_labels  = ["villarrica_pucon", "temuco_pucon", "aeropuerto_pucon", "caburgua_pucon"]
    route_display = {"villarrica_pucon": "Villarrica→Pucón",
                     "temuco_pucon": "Temuco→Pucón",
                     "aeropuerto_pucon": "Aeropuerto→Pucón",
                     "caburgua_pucon": "Caburgua→Pucón"}

    traffic_dates_set = sorted(set(r["target_date"].isoformat() for r in traffic_rows))

    def _series(suffix):
        pivot: dict[str, dict[str, float]] = {rl: {} for rl in route_labels}
        for r in traffic_rows:
            for rl in route_labels:
                if r["metric_name"] == f"traffic_{rl}_{suffix}":
                    pivot[rl][r["target_date"].isoformat()] = float(r["val"])
        return {rl: [pivot[rl].get(d) for d in traffic_dates_set] for rl in route_labels}

    travel_series = _series("travel_min")
    ratio_series  = _series("ratio")

    # ---- Weather history ----
    wx_dates_set = sorted(set(r["target_date"].isoformat() for r in weather_history))
    wx_pivot: dict[str, dict[str, float]] = {}
    for r in weather_history:
        wx_pivot.setdefault(r["metric_name"], {})[r["target_date"].isoformat()] = float(r["val"])

    # ---- Latest KPI values ----
    def _metric_map(rows):
        return {r["metric_name"]: (float(r["metric_value"]) if r["metric_value"] is not None else None)
                for r in rows}

    t_latest = _metric_map(traffic_latest)
    w_latest = _metric_map(weather_latest)
    l_latest = _metric_map(lodging_latest)

    cf = current_flow[0] if current_flow else {}

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
        "current_flow": {
            "score":  float(cf.get("final_flow_score", 0)) if cf else 0,
            "level":  cf.get("flow_level", "–"),
            "action": cf.get("recommended_action", ""),
            "explanation": cf.get("explanation", ""),
            "calculated_at": cf.get("calculated_at", ""),
        },
        "kpi": {
            "traffic_avg_ratio":  t_latest.get("traffic_avg_ratio"),
            "traffic_avg_score":  t_latest.get("traffic_avg_score"),
            "temperature_c":      w_latest.get("temperature_c"),
            "weather_score":      w_latest.get("weather_score"),
            "rain_1h_mm":         w_latest.get("rain_1h_mm"),
            "cloudiness_pct":     w_latest.get("cloudiness_pct"),
            "lodging_avail_score": l_latest.get("lodging_availability_score"),
            "lodging_price_score": l_latest.get("lodging_price_score"),
        },
        "flow_chart": {
            "dates":          flow_dates,
            "flow_scores":    flow_scores,
            "traffic_scores": traffic_scores,
            "weather_scores": weather_scores,
            "lodging_a":      lodging_a_scores,
            "lodging_p":      lodging_p_scores,
        },
        "traffic_chart": {
            "dates":          traffic_dates_set,
            "travel_series":  {route_display[k]: v for k, v in travel_series.items()},
            "ratio_series":   {route_display[k]: v for k, v in ratio_series.items()},
        },
        "weather_chart": {
            "dates":      wx_dates_set,
            "temp":       [wx_pivot.get("temperature_c", {}).get(d) for d in wx_dates_set],
            "rain":       [wx_pivot.get("rain_1h_mm", {}).get(d) for d in wx_dates_set],
            "cloudiness": [wx_pivot.get("cloudiness_pct", {}).get(d) for d in wx_dates_set],
            "score":      [wx_pivot.get("weather_score", {}).get(d) for d in wx_dates_set],
        },
        "reliability": [
            {"source": r["source_name"], "total": int(r["total"]),
             "ok": int(r["ok"]), "pct": float(r["pct"] or 0), "avg_ms": int(r["avg_ms"] or 0)}
            for r in reliability
        ],
    }


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Flujo Turístico Pucón · HotBoat</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3.0.1/dist/chartjs-plugin-annotation.min.js"></script>
<style>
  :root {
    --bg:      #0f172a;
    --surface: #1e293b;
    --card:    #273449;
    --border:  #334155;
    --text:    #e2e8f0;
    --muted:   #94a3b8;
    --accent:  #38bdf8;
    --green:   #22c55e;
    --yellow:  #f59e0b;
    --orange:  #f97316;
    --red:     #ef4444;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }
  /* ---- Layout ---- */
  .wrap   { max-width: 1280px; margin: 0 auto; padding: 0 24px; }
  header  {
    border-bottom: 1px solid var(--border);
    padding: 20px 0;
    background: var(--surface);
  }
  header .wrap {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
  }
  header h1 { font-size: 1.4rem; font-weight: 700; letter-spacing: -.02em; }
  header h1 span { color: var(--accent); }
  .badge-gen {
    font-size: .75rem;
    color: var(--muted);
    background: var(--card);
    border: 1px solid var(--border);
    padding: 4px 12px;
    border-radius: 999px;
  }
  main { padding: 32px 0 64px; }
  .section { margin-bottom: 40px; }
  .section-title {
    font-size: .78rem;
    font-weight: 600;
    letter-spacing: .1em;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 16px;
  }
  /* ---- Hero KPI ---- */
  .hero {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 28px 32px;
    display: flex;
    align-items: center;
    gap: 32px;
    flex-wrap: wrap;
    margin-bottom: 32px;
  }
  .hero-score {
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 120px;
  }
  .score-ring {
    width: 120px; height: 120px;
    position: relative;
    display: flex; align-items: center; justify-content: center;
  }
  .score-ring svg { position: absolute; top: 0; left: 0; transform: rotate(-90deg); }
  .score-ring .num {
    font-size: 2.2rem; font-weight: 800; position: relative; z-index: 1;
  }
  .score-label {
    margin-top: 8px;
    font-size: .85rem;
    font-weight: 700;
    letter-spacing: .05em;
    text-transform: uppercase;
  }
  .hero-info { flex: 1; min-width: 220px; }
  .hero-info .action {
    font-size: 1rem; font-weight: 600; color: var(--text); margin-bottom: 8px;
  }
  .hero-info .expl {
    font-size: .85rem; color: var(--muted); line-height: 1.5;
  }
  /* ---- KPI grid ---- */
  .kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 16px;
  }
  .kpi-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
  }
  .kpi-card .kpi-label {
    font-size: .72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .07em;
    color: var(--muted);
    margin-bottom: 10px;
  }
  .kpi-card .kpi-value {
    font-size: 1.9rem;
    font-weight: 800;
    line-height: 1;
  }
  .kpi-card .kpi-sub {
    font-size: .75rem;
    color: var(--muted);
    margin-top: 6px;
  }
  /* ---- Charts ---- */
  .chart-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
  }
  @media (max-width: 800px) { .chart-grid { grid-template-columns: 1fr; } }
  .chart-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
  }
  .chart-card.wide { grid-column: 1 / -1; }
  .chart-title {
    font-size: .8rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .07em;
    color: var(--muted);
    margin-bottom: 16px;
  }
  .chart-wrap { position: relative; height: 260px; }
  .chart-wrap.tall { height: 320px; }
  /* ---- Reliability table ---- */
  .rel-table { width: 100%; border-collapse: collapse; font-size: .85rem; }
  .rel-table th, .rel-table td {
    text-align: left;
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
  }
  .rel-table th { color: var(--muted); font-weight: 600; font-size: .75rem;
                  text-transform: uppercase; letter-spacing: .06em; }
  .rel-table tr:last-child td { border-bottom: none; }
  .rel-bar {
    height: 6px; border-radius: 3px;
    background: linear-gradient(90deg, var(--green), var(--accent));
    display: inline-block; vertical-align: middle;
  }
  /* ---- Footer ---- */
  footer {
    text-align: center;
    font-size: .75rem;
    color: var(--muted);
    padding: 24px;
    border-top: 1px solid var(--border);
  }
  footer strong { color: var(--accent); }
</style>
</head>
<body>

<header>
  <div class="wrap">
    <h1>Flujo Turístico <span>Pucón</span> · HotBoat</h1>
    <span class="badge-gen">Actualizado: %%GENERATED_AT%%</span>
  </div>
</header>

<main>
<div class="wrap">

  <!-- Hero -->
  <div class="hero">
    <div class="hero-score">
      <div class="score-ring">
        <svg width="120" height="120" viewBox="0 0 120 120">
          <circle cx="60" cy="60" r="50" fill="none" stroke="#1e293b" stroke-width="10"/>
          <circle cx="60" cy="60" r="50" fill="none"
            stroke="%%HERO_COLOR%%"
            stroke-width="10"
            stroke-dasharray="%%HERO_DASH%% 314.16"
            stroke-linecap="round"/>
        </svg>
        <span class="num" style="color:%%HERO_COLOR%%">%%HERO_SCORE%%</span>
      </div>
      <span class="score-label" style="color:%%HERO_COLOR%%">%%HERO_LEVEL%%</span>
    </div>
    <div class="hero-info">
      <div class="action">%%HERO_ACTION%%</div>
      <div class="expl">%%HERO_EXPL%%</div>
    </div>
  </div>

  <!-- KPIs -->
  <div class="section">
    <div class="section-title">Señales actuales</div>
    <div class="kpi-grid" id="kpi-grid"></div>
  </div>

  <!-- Charts: flow index evolution (wide) -->
  <div class="section">
    <div class="section-title">Evolución del índice de flujo · últimos 30 días</div>
    <div class="chart-card wide">
      <div class="chart-title">KPI Combinado + Fuentes</div>
      <div class="chart-wrap tall"><canvas id="flowChart"></canvas></div>
    </div>
  </div>

  <!-- Charts: traffic -->
  <div class="section">
    <div class="section-title">Tráfico vial hacia Pucón · últimos 14 días</div>
    <div class="chart-grid">
      <div class="chart-card">
        <div class="chart-title">Tiempo de viaje (minutos)</div>
        <div class="chart-wrap"><canvas id="travelChart"></canvas></div>
      </div>
      <div class="chart-card">
        <div class="chart-title">Ratio de congestión (1.0 = normal)</div>
        <div class="chart-wrap"><canvas id="ratioChart"></canvas></div>
      </div>
    </div>
  </div>

  <!-- Charts: weather -->
  <div class="section">
    <div class="section-title">Clima en Pucón · últimos 14 días</div>
    <div class="chart-grid">
      <div class="chart-card">
        <div class="chart-title">Temperatura (°C)</div>
        <div class="chart-wrap"><canvas id="tempChart"></canvas></div>
      </div>
      <div class="chart-card">
        <div class="chart-title">Lluvia (mm) y Nubosidad (%)</div>
        <div class="chart-wrap"><canvas id="rainChart"></canvas></div>
      </div>
    </div>
  </div>

  <!-- Reliability -->
  <div class="section">
    <div class="section-title">Fiabilidad de fuentes · últimos 7 días</div>
    <div class="chart-card wide">
      <table class="rel-table" id="relTable"></table>
    </div>
  </div>

</div>
</main>

<footer>
  Dashboard generado por <strong>HotBoat ETL</strong> · Datos de PostgreSQL en Railway
</footer>

<script>
// ── Embedded data ──────────────────────────────────────────────────────────
const DATA = %%DATA_JSON%%;

// ── Palette ───────────────────────────────────────────────────────────────
const C = {
  flow:     '#38bdf8',
  traffic:  '#f97316',
  weather:  '#22c55e',
  lodgingA: '#a78bfa',
  lodgingP: '#fb7185',
  routes: ['#38bdf8','#f97316','#22c55e','#a78bfa'],
  temp:   '#f97316',
  rain:   '#38bdf8',
  cloud:  '#94a3b8',
};

const commonOpts = (yLabel) => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: {
      labels: { color: '#94a3b8', font: { size: 11 }, boxWidth: 12, padding: 16 }
    }
  },
  scales: {
    x: {
      ticks: { color: '#64748b', font: { size: 10 }, maxRotation: 45 },
      grid: { color: '#1e293b' }
    },
    y: {
      title: { display: !!yLabel, text: yLabel, color: '#64748b', font: { size: 11 } },
      ticks: { color: '#64748b', font: { size: 11 } },
      grid: { color: '#1e293b' }
    }
  }
});

// ── KPI grid ──────────────────────────────────────────────────────────────
function kpiVal(v, decimals = 0, suffix = '') {
  if (v == null) return '<span style="color:#475569">–</span>';
  return (typeof v === 'number' ? v.toFixed(decimals) : v) + suffix;
}

const kpiItems = [
  { label: 'Score flujo', val: kpiVal(DATA.current_flow.score, 1), sub: 'Índice combinado /100', color: '%%HERO_COLOR%%' },
  { label: 'Ratio tráfico', val: kpiVal(DATA.kpi.traffic_avg_ratio, 2, 'x'), sub: '1.0 = sin congestión', color: DATA.kpi.traffic_avg_ratio > 1.3 ? '#ef4444' : '#22c55e' },
  { label: 'Score tráfico', val: kpiVal(DATA.kpi.traffic_avg_score, 0, '/100'), sub: 'Promedio 4 rutas', color: '#f97316' },
  { label: 'Temperatura', val: kpiVal(DATA.kpi.temperature_c, 1, '°C'), sub: 'Pucón ahora', color: '#22c55e' },
  { label: 'Lluvia', val: kpiVal(DATA.kpi.rain_1h_mm, 1, ' mm'), sub: 'Última hora', color: '#38bdf8' },
  { label: 'Nubosidad', val: kpiVal(DATA.kpi.cloudiness_pct, 0, '%'), sub: 'Cobertura de nubes', color: '#94a3b8' },
  { label: 'Score clima', val: kpiVal(DATA.kpi.weather_score, 0, '/100'), sub: 'Condición ambiental', color: '#22c55e' },
  { label: 'Disponib. alojam.', val: kpiVal(DATA.kpi.lodging_avail_score, 0, '/100'), sub: 'Rooms libres vs baseline', color: '#a78bfa' },
  { label: 'Precio alojam.', val: kpiVal(DATA.kpi.lodging_price_score, 0, '/100'), sub: 'Precio vs baseline', color: '#fb7185' },
];

const grid = document.getElementById('kpi-grid');
kpiItems.forEach(k => {
  grid.innerHTML += `
    <div class="kpi-card">
      <div class="kpi-label">${k.label}</div>
      <div class="kpi-value" style="color:${k.color}">${k.val}</div>
      <div class="kpi-sub">${k.sub}</div>
    </div>`;
});

// ── Flow Index chart (combined KPI) ──────────────────────────────────────
const fc = DATA.flow_chart;
new Chart(document.getElementById('flowChart'), {
  type: 'line',
  data: {
    labels: fc.dates,
    datasets: [
      {
        label: 'Índice Flujo (KPI)',
        data: fc.flow_scores,
        borderColor: C.flow,
        backgroundColor: C.flow + '22',
        borderWidth: 3,
        fill: true,
        tension: 0.35,
        pointRadius: 3,
        order: 0,
      },
      {
        label: 'Tráfico',
        data: fc.traffic_scores,
        borderColor: C.traffic,
        borderWidth: 2,
        fill: false,
        tension: 0.35,
        pointRadius: 2,
        borderDash: [4, 2],
        order: 1,
      },
      {
        label: 'Clima',
        data: fc.weather_scores,
        borderColor: C.weather,
        borderWidth: 2,
        fill: false,
        tension: 0.35,
        pointRadius: 2,
        borderDash: [4, 2],
        order: 2,
      },
      {
        label: 'Alojam. disponib.',
        data: fc.lodging_a,
        borderColor: C.lodgingA,
        borderWidth: 2,
        fill: false,
        tension: 0.35,
        pointRadius: 2,
        borderDash: [4, 2],
        order: 3,
      },
      {
        label: 'Precio alojam.',
        data: fc.lodging_p,
        borderColor: C.lodgingP,
        borderWidth: 2,
        fill: false,
        tension: 0.35,
        pointRadius: 2,
        borderDash: [4, 2],
        order: 4,
      },
    ]
  },
  options: {
    ...commonOpts('score /100'),
    plugins: {
      ...commonOpts().plugins,
      annotation: {
        annotations: {
          zoneBajo:    { type:'box', yMin:0,  yMax:30, backgroundColor:'#22c55e11', borderWidth:0 },
          zoneMedio:   { type:'box', yMin:30, yMax:55, backgroundColor:'#f59e0b11', borderWidth:0 },
          zoneAlto:    { type:'box', yMin:55, yMax:75, backgroundColor:'#f9731611', borderWidth:0 },
          zoneMuyAlto: { type:'box', yMin:75, yMax:100,backgroundColor:'#ef444411', borderWidth:0 },
        }
      }
    },
    scales: {
      ...commonOpts('score /100').scales,
      y: { ...commonOpts('score /100').scales.y, min: 0, max: 100 }
    }
  }
});

// ── Traffic: travel time ──────────────────────────────────────────────────
const tc = DATA.traffic_chart;
const routeNames = Object.keys(tc.travel_series);

new Chart(document.getElementById('travelChart'), {
  type: 'line',
  data: {
    labels: tc.dates,
    datasets: routeNames.map((name, i) => ({
      label: name,
      data: tc.travel_series[name],
      borderColor: C.routes[i],
      backgroundColor: 'transparent',
      borderWidth: 2,
      tension: 0.3,
      pointRadius: 3,
      spanGaps: true,
    }))
  },
  options: commonOpts('minutos')
});

// ── Traffic: ratio ────────────────────────────────────────────────────────
new Chart(document.getElementById('ratioChart'), {
  type: 'line',
  data: {
    labels: tc.dates,
    datasets: routeNames.map((name, i) => ({
      label: name,
      data: tc.ratio_series[name],
      borderColor: C.routes[i],
      backgroundColor: 'transparent',
      borderWidth: 2,
      tension: 0.3,
      pointRadius: 3,
      spanGaps: true,
    }))
  },
  options: {
    ...commonOpts('ratio'),
    plugins: {
      ...commonOpts().plugins,
      annotation: {
        annotations: {
          base: { type:'line', yMin:1, yMax:1, borderColor:'#94a3b844', borderWidth:1, borderDash:[4,4] }
        }
      }
    }
  }
});

// ── Weather: temperature ──────────────────────────────────────────────────
const wc = DATA.weather_chart;
new Chart(document.getElementById('tempChart'), {
  type: 'line',
  data: {
    labels: wc.dates,
    datasets: [{
      label: 'Temperatura (°C)',
      data: wc.temp,
      borderColor: C.temp,
      backgroundColor: C.temp + '22',
      fill: true,
      tension: 0.4,
      pointRadius: 3,
      spanGaps: true,
    }]
  },
  options: commonOpts('°C')
});

// ── Weather: rain + cloudiness ────────────────────────────────────────────
new Chart(document.getElementById('rainChart'), {
  type: 'bar',
  data: {
    labels: wc.dates,
    datasets: [
      {
        label: 'Lluvia (mm)',
        data: wc.rain,
        backgroundColor: C.rain + 'aa',
        borderColor: C.rain,
        borderWidth: 1,
        yAxisID: 'y',
      },
      {
        label: 'Nubosidad (%)',
        data: wc.cloudiness,
        type: 'line',
        borderColor: C.cloud,
        backgroundColor: 'transparent',
        borderWidth: 2,
        tension: 0.4,
        pointRadius: 2,
        spanGaps: true,
        yAxisID: 'y2',
      }
    ]
  },
  options: {
    ...commonOpts('mm'),
    scales: {
      x: commonOpts().scales.x,
      y:  { ...commonOpts('mm').scales.y,  position:'left',  title:{ display:true, text:'mm', color:'#64748b', font:{size:11} } },
      y2: { ...commonOpts().scales.y,      position:'right', min:0, max:100, title:{ display:true, text:'%', color:'#64748b', font:{size:11} }, grid:{ drawOnChartArea:false } },
    }
  }
});

// ── Reliability table ─────────────────────────────────────────────────────
const rt = document.getElementById('relTable');
rt.innerHTML = `
  <thead><tr>
    <th>Fuente</th><th>Consultas 7d</th><th>Exitosas</th><th>Tasa</th><th>Tiempo prom.</th>
  </tr></thead><tbody>` +
  DATA.reliability.map(r => {
    const barW = Math.round(r.pct);
    const col = r.pct >= 80 ? '#22c55e' : r.pct >= 50 ? '#f59e0b' : '#ef4444';
    return `<tr>
      <td style="font-weight:600">${r.source}</td>
      <td>${r.total}</td>
      <td>${r.ok}</td>
      <td>
        <span class="rel-bar" style="width:${barW}px;background:${col};margin-right:8px"></span>
        <span style="color:${col};font-weight:700">${r.pct}%</span>
      </td>
      <td style="color:#64748b">${r.avg_ms} ms</td>
    </tr>`;
  }).join('') + '</tbody>';
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

def _render(data: dict) -> str:
    cf    = data["current_flow"]
    score = cf["score"]
    level = cf["level"]
    color = _level_color(level)
    # SVG dash: circumference ≈ 314.16, fill proportional to score
    dash  = round(314.16 * score / 100, 2)

    html = HTML_TEMPLATE
    html = html.replace("%%GENERATED_AT%%",  data["generated_at"])
    html = html.replace("%%HERO_COLOR%%",    color)
    html = html.replace("%%HERO_DASH%%",     str(dash))
    html = html.replace("%%HERO_SCORE%%",    str(round(score, 1)))
    html = html.replace("%%HERO_LEVEL%%",    _level_label(level))
    html = html.replace("%%HERO_ACTION%%",   cf.get("action") or "–")
    html = html.replace("%%HERO_EXPL%%",     cf.get("explanation") or "")
    html = html.replace("%%DATA_JSON%%",     _j(data))
    return html


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    out_path = Path("/home/user/hotboat-etl/dashboard.html")
    for i, arg in enumerate(sys.argv[1:]):
        if arg in ("-o", "--output") and i + 1 < len(sys.argv) - 1:
            out_path = Path(sys.argv[i + 2])

    # Import here so the script fails clearly if DATABASE_URL is missing
    from db.connection import get_connection  # noqa: PLC0415

    print("Conectando a PostgreSQL…")
    with get_connection() as conn:
        data = _load_data(conn)

    html = _render(data)
    out_path.write_text(html, encoding="utf-8")
    print(f"Dashboard generado: {out_path}  ({len(html):,} bytes)")
    print(f"  Flujo actual: {data['current_flow']['score']:.1f} ({data['current_flow']['level']})")
    print(f"  Días con datos: {len(data['flow_chart']['dates'])}")
    print(f"  Rutas de tráfico con datos: "
          f"{sum(1 for v in data['traffic_chart']['travel_series'].values() if any(x is not None for x in v))}")


if __name__ == "__main__":
    main()
