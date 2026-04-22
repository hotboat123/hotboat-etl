-- Ejecuta esto en DBeaver (Postgres) para ver qué nombres usa Meta en TUS datos.
-- Las conversiones personalizadas suelen aparecer como:
--   offsite_conversion.custom.<ID_NUMERICO>
-- o como eventos del pixel: offsite_conversion.fb_pixel_<evento>

-- 1) Todas las métricas de "acciones" (conteos) que han llegado al menos una vez
SELECT DISTINCT elem->>'action_type' AS action_type
FROM meta_ads_insights,
     jsonb_array_elements(COALESCE(actions, '[]'::jsonb)) AS elem
WHERE elem->>'action_type' IS NOT NULL
ORDER BY 1;

-- 2) Costos por tipo que devuelve Meta (costo medio por resultado, en la divisa de la cuenta)
SELECT DISTINCT elem->>'action_type' AS action_type
FROM meta_ads_insights,
     jsonb_array_elements(COALESCE(cost_per_action_type, '[]'::jsonb)) AS elem
WHERE elem->>'action_type' IS NOT NULL
ORDER BY 1;

-- 3) Opcional: ver una fila de ejemplo con el JSON completo
-- SELECT date_start, ad_id, actions, cost_per_action_type
-- FROM meta_ads_insights
-- WHERE actions::text LIKE '%custom%'
-- LIMIT 5;
