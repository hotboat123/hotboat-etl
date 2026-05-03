-- Índice de Flujo Turístico Pucón
-- Referencia: las tablas son creadas y gestionadas via db/migrate.py

CREATE TABLE IF NOT EXISTS tourism_signal_snapshots (
    id          BIGSERIAL PRIMARY KEY,
    collected_at TIMESTAMPTZ NOT NULL,
    target_date  DATE        NOT NULL,
    source_type  TEXT        NOT NULL,  -- weather, traffic, lodging
    source_name  TEXT        NOT NULL,  -- openweather, google_maps, booking, etc.
    metric_name  TEXT        NOT NULL,
    metric_value NUMERIC,
    metric_unit  TEXT,
    raw_payload  JSONB,
    status       TEXT        NOT NULL DEFAULT 'ok',
    error_message TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (collected_at, source_type, metric_name, target_date)
);

CREATE INDEX IF NOT EXISTS idx_tourism_signals_date_type
    ON tourism_signal_snapshots (target_date DESC, source_type);

CREATE INDEX IF NOT EXISTS idx_tourism_signals_collected
    ON tourism_signal_snapshots (collected_at DESC);

-- -------------------------------------------------------

CREATE TABLE IF NOT EXISTS pucon_flow_index (
    id          BIGSERIAL PRIMARY KEY,
    calculated_at TIMESTAMPTZ NOT NULL,
    target_date   DATE        NOT NULL,
    lodging_availability_score NUMERIC,
    lodging_price_score        NUMERIC,
    traffic_score              NUMERIC,
    weather_score              NUMERIC,
    final_flow_score           NUMERIC NOT NULL,
    flow_level                 TEXT    NOT NULL,  -- bajo, medio, alto, muy_alto
    recommended_action         TEXT,
    explanation                TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (calculated_at, target_date)
);

CREATE INDEX IF NOT EXISTS idx_pucon_flow_index_date
    ON pucon_flow_index (target_date DESC);

-- -------------------------------------------------------

CREATE TABLE IF NOT EXISTS source_query_log (
    id               BIGSERIAL PRIMARY KEY,
    source_name      TEXT        NOT NULL,
    query_type       TEXT        NOT NULL,
    query_params     JSONB,
    requested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    success          BOOLEAN,
    http_status      INTEGER,
    error_message    TEXT,
    response_time_ms INTEGER
);

CREATE INDEX IF NOT EXISTS idx_source_query_log_source
    ON source_query_log (source_name, requested_at DESC);
