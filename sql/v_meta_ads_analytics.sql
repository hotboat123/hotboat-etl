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
  meta_fn_action_types_sum(
    i.actions,
    ARRAY[
      'purchase',
      'omni_purchase',
      'offsite_conversion.fb_pixel_purchase',
      'onsite_conversion.purchase'
    ]
  ) AS "Compras",
  COALESCE(i.raw->>'account_currency', 'CLP') AS "Divisa",
  i.spend AS "Importe gastado (CLP)",
  meta_fn_action_type_sum(i.actions, 'link_click') AS "Clics en el enlace",
  i.ctr AS "CTR (todos)",
  i.cpc AS "CPC (todos)",
  i.cpm AS "CPM (costo por mil impresiones)",
  meta_fn_action_types_sum(
    i.actions,
    ARRAY[
      'add_to_cart',
      'offsite_conversion.fb_pixel_add_to_cart',
      'omni_add_to_cart',
      'onsite_web_add_to_cart',
      'onsite_web_app_add_to_cart'
    ]
  ) AS "Artículos agregados al carrito",
  CASE
    WHEN meta_fn_action_types_sum(
      i.actions,
      ARRAY[
        'add_to_cart',
        'offsite_conversion.fb_pixel_add_to_cart',
        'omni_add_to_cart',
        'onsite_web_add_to_cart',
        'onsite_web_app_add_to_cart'
      ]
    ) > 0
    THEN i.spend / NULLIF(
      meta_fn_action_types_sum(
        i.actions,
        ARRAY[
          'add_to_cart',
          'offsite_conversion.fb_pixel_add_to_cart',
          'omni_add_to_cart',
          'onsite_web_add_to_cart',
          'onsite_web_app_add_to_cart'
        ]
      ),
      0
    )
  END AS "Costo por artículo agregado al carrito",
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
    WHEN meta_fn_action_types_sum(
      i.actions,
      ARRAY['purchase', 'omni_purchase', 'offsite_conversion.fb_pixel_purchase', 'onsite_conversion.purchase']
    ) > 0
    THEN i.spend / NULLIF(
      meta_fn_action_types_sum(
        i.actions,
        ARRAY['purchase', 'omni_purchase', 'offsite_conversion.fb_pixel_purchase', 'onsite_conversion.purchase']
      ),
      0
    )
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
    ARRAY['add_payment_info', 'offsite_conversion.fb_pixel_add_payment_info']
  ) AS "Hizo el pago",
  CASE
    WHEN meta_fn_action_types_sum(
      i.actions,
      ARRAY['add_payment_info', 'offsite_conversion.fb_pixel_add_payment_info']
    ) > 0
    THEN i.spend / NULLIF(
      meta_fn_action_types_sum(
        i.actions,
        ARRAY['add_payment_info', 'offsite_conversion.fb_pixel_add_payment_info']
      ),
      0
    )
  END AS "Costo por Hizo el pago",
  meta_fn_action_types_sum(
    i.actions,
    ARRAY['page_engagement', 'post_engagement', 'post_reaction']
  ) AS "Interacción con la página",
  meta_fn_action_types_sum(
    i.actions,
    ARRAY[
      'initiate_checkout',
      'offsite_conversion.fb_pixel_initiate_checkout',
      'omni_initiated_checkout',
      'onsite_web_initiate_checkout'
    ]
  ) AS "Intento pagar",
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
