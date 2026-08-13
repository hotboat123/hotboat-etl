-- Igual que v_meta_ads_analytics pero desde meta_ads_insights_region
-- (breakdowns=region) — depende de meta_fn_action_type_sum, creada por
-- v_meta_ads_analytics.sql (ejecutar ese primero; db/migrate.py ya respeta
-- ese orden). No confundir "Compras" acá con la de v_meta_ads_analytics: si
-- Meta no logra atribuir región a parte del tráfico, esas filas caen en
-- region='Unknown' en vez de perderse, pero la suma por región de esta
-- vista puede no calzar 1:1 con el total sin desglosar si Meta agrupa de
-- forma distinta entre ambas consultas.

CREATE OR REPLACE VIEW v_meta_ads_by_region AS
SELECT
  i.region AS "Región",
  i.date_start AS "Día",
  c.name AS "Nombre de la campaña",
  s.name AS "Nombre del conjunto de anuncios",
  a.name AS "Nombre del anuncio",
  i.reach AS "Alcance",
  i.impressions AS "Impresiones",
  i.clicks AS "Clics",
  COALESCE(i.raw->>'account_currency', 'CLP') AS "Divisa",
  i.spend AS "Importe gastado (CLP)",
  i.ctr AS "CTR (todos)",
  i.cpc AS "CPC (todos)",
  i.cpm AS "CPM (costo por mil impresiones)",
  -- Misma conversión personalizada "Reserva app 3" que usa v_meta_ads_analytics
  -- como "Compras" — ver ese archivo para el porqué del nombre exacto (no ILIKE).
  meta_fn_action_type_sum(
    i.actions,
    (SELECT action_type FROM meta_custom_conversions WHERE LOWER(name) = LOWER('Reserva app 3') LIMIT 1)
  ) AS "Compras",
  CASE
    WHEN meta_fn_action_type_sum(
      i.actions,
      (SELECT action_type FROM meta_custom_conversions WHERE LOWER(name) = LOWER('Reserva app 3') LIMIT 1)
    ) > 0
    THEN i.spend / NULLIF(
      meta_fn_action_type_sum(
        i.actions,
        (SELECT action_type FROM meta_custom_conversions WHERE LOWER(name) = LOWER('Reserva app 3') LIMIT 1)
      ),
      0
    )
  END AS "Costo por compra"
FROM meta_ads_insights_region i
LEFT JOIN meta_ads a ON a.id = i.ad_id
LEFT JOIN meta_campaigns c ON c.id = i.campaign_id
LEFT JOIN meta_adsets s ON s.id = i.adset_id;

COMMENT ON VIEW v_meta_ads_by_region IS
  'Vista analítica Meta desglosada por región (Región Metropolitana, Región de la Araucanía, etc.), desde meta_ads_insights_region (breakdowns=region). '
  'Re-sincroniza job_meta_ads tras ampliar campos en la API.';
