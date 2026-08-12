-- Helpers: Meta devuelve actions / cost_per_action_type como arrays de {action_type, value}
-- Ejecutar después de meta_ads_insights (migrate / ensure_schema).

CREATE OR REPLACE FUNCTION meta_fn_action_type_sum(p_jsonb jsonb, p_type text)
RETURNS numeric
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $f$
  SELECT COALESCE(SUM((elem->>'value')::numeric), 0)
  FROM jsonb_array_elements(COALESCE(p_jsonb, '[]'::jsonb)) AS elem
  WHERE elem->>'action_type' = p_type;
$f$;

CREATE OR REPLACE FUNCTION meta_fn_action_array_sum(p_arr jsonb)
RETURNS numeric
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $f$
  SELECT COALESCE(SUM((elem->>'value')::numeric), 0)
  FROM jsonb_array_elements(COALESCE(p_arr, '[]'::jsonb)) AS elem
  WHERE elem ? 'value';
$f$;

-- Suma varios action_type (compras / conversiones duplicadas en distintos nombres)
CREATE OR REPLACE FUNCTION meta_fn_action_types_sum(p_jsonb jsonb, p_types text[])
RETURNS numeric
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $f$
  SELECT COALESCE(SUM((elem->>'value')::numeric), 0)
  FROM jsonb_array_elements(COALESCE(p_jsonb, '[]'::jsonb)) AS elem
  WHERE elem->>'action_type' = ANY (p_types);
$f$;

CREATE OR REPLACE VIEW v_meta_ads_analytics AS
SELECT
  a.name AS "Nombre del anuncio",
  i.date_start AS "Día",
  c.name AS "Nombre de la campaña",
  s.name AS "Nombre del conjunto de anuncios",
  i.reach AS "Alcance",
  i.impressions AS "Impresiones",
  i.frequency AS "Frecuencia",
  -- "Compras" = reserva_app_3 (conversión personalizada real de HotBoat —
  -- ver meta_ads_insights.reserva_app_3, extraída por nombre exacto en
  -- job_meta_ads.py::_backfill_custom_conv_columns, más robusta que repetir
  -- el id numérico de Meta acá). Antes usaba los action_types genéricos de
  -- Meta Pixel (purchase/omni_purchase/...) que nunca se disparan para
  -- HotBoat (no es una tienda online con checkout de Meta Pixel) y siempre
  -- daban 0 — cambiado 2026-08-12 a pedido del dueño. Se mantiene el
  -- nombre de columna "Compras" (no "Compra") a propósito: hotboat-automations/
  -- scripts/analyze_meta_ads_performance.py hace SUM("Compras") y se
  -- rompería con un rename.
  i.reserva_app_3 AS "Compras",
  COALESCE(i.raw->>'account_currency', 'CLP') AS "Divisa",
  i.spend AS "Importe gastado (CLP)",
  meta_fn_action_type_sum(i.actions, 'link_click') AS "Clics en el enlace",
  i.ctr AS "CTR (todos)",
  i.cpc AS "CPC (todos)",
  i.cpm AS "CPM (costo por mil impresiones)",
  COALESCE(
    meta_fn_action_type_sum(i.actions, 'video_view'),
    meta_fn_action_array_sum(i.raw->'video_thruplay_watched_actions')
  ) AS "Reproducciones de video de 3 segundos",
  meta_fn_action_array_sum(i.raw->'video_p25_watched_actions') AS "Reproducciones de video hasta el 25%",
  meta_fn_action_array_sum(i.raw->'video_p50_watched_actions') AS "Reproducciones de video hasta el 50%",
  meta_fn_action_array_sum(i.raw->'video_p75_watched_actions') AS "Reproducciones de video hasta el 75%",
  meta_fn_action_array_sum(i.raw->'video_p95_watched_actions') AS "Reproducciones de video hasta el 95%",
  meta_fn_action_array_sum(i.raw->'video_p100_watched_actions') AS "Reproducciones de video hasta el 100%",
  CASE
    WHEN i.reserva_app_3 > 0
    THEN i.spend / NULLIF(i.reserva_app_3, 0)
  END AS "Costo por compra",
  i.date_start AS "Inicio del informe",
  i.date_stop AS "Fin del informe",
  -- Conversiones personalizadas (IDs en Events Manager; renombra alias si quieres otro título)
  meta_fn_action_type_sum(i.actions, 'offsite_conversion.custom.920264533622915') AS "agrego al carrito tom (compro)",
  CASE
    WHEN meta_fn_action_type_sum(i.actions, 'offsite_conversion.custom.920264533622915') > 0
    THEN i.spend / NULLIF(meta_fn_action_type_sum(i.actions, 'offsite_conversion.custom.920264533622915'), 0)
  END AS "Costo por agrego al carrito tom (compro)",
  meta_fn_action_type_sum(i.actions, 'offsite_conversion.custom.1755907938288280') AS "Conversión personalizada 1755907938288280",
  CASE
    WHEN meta_fn_action_type_sum(i.actions, 'offsite_conversion.custom.1755907938288280') > 0
    THEN i.spend / NULLIF(meta_fn_action_type_sum(i.actions, 'offsite_conversion.custom.1755907938288280'), 0)
  END AS "Costo por conversión personalizada 1755907938288280",
  meta_fn_action_types_sum(
    i.actions,
    ARRAY['page_engagement', 'post_engagement', 'post_reaction']
  ) AS "Interacción con la página",
  meta_fn_action_types_sum(
    i.actions,
    ARRAY[
      'onsite_conversion.messaging_conversation_started_7d',
      'onsite_conversion.messaging_conversation_started',
      'messaging_conversation_started'
    ]
  ) AS "Conversaciones con mensajes iniciadas",
  CASE
    WHEN meta_fn_action_types_sum(
      i.actions,
      ARRAY[
        'onsite_conversion.messaging_conversation_started_7d',
        'onsite_conversion.messaging_conversation_started',
        'messaging_conversation_started'
      ]
    ) > 0
    THEN i.spend / NULLIF(
      meta_fn_action_types_sum(
        i.actions,
        ARRAY[
          'onsite_conversion.messaging_conversation_started_7d',
          'onsite_conversion.messaging_conversation_started',
          'messaging_conversation_started'
        ]
      ),
      0
    )
  END AS "Costo por conversación con mensajes iniciada"
FROM meta_ads_insights i
LEFT JOIN meta_ads a ON a.id = i.ad_id
LEFT JOIN meta_campaigns c ON c.id = i.campaign_id
LEFT JOIN meta_adsets s ON s.id = i.adset_id;

COMMENT ON VIEW v_meta_ads_analytics IS
  'Vista analítica Meta: columnas NULL personalizables según action_type en JSON (ver raw/actions). '
  'Re-sincroniza job_meta_ads tras ampliar campos en la API.';
