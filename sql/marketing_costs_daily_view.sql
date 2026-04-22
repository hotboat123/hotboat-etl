-- Vista diaria agregada desde meta_ads_insights (datos del job job_meta_ads).
-- Sustituye la definición antigua que leía de la tabla marketing_costs (ya no actualizada por el ETL).

CREATE OR REPLACE VIEW marketing_costs_daily AS
WITH daily AS (
  SELECT
    i.date_start,
    count(*)::bigint AS num_ads,
    sum(i.spend) AS total_spent,
    sum(i.reach) AS total_reach,
    sum(i.impressions) AS total_impressions,
    sum(i.clicks) AS total_clicks,
    sum(
      meta_fn_action_types_sum(
        i.actions,
        ARRAY[
          'purchase',
          'omni_purchase',
          'offsite_conversion.fb_pixel_purchase',
          'onsite_conversion.purchase'
        ]
      )
    ) AS total_purchases
  FROM meta_ads_insights i
  GROUP BY i.date_start
)
SELECT
  date_start AS cost_date,
  num_ads,
  total_spent,
  total_reach,
  total_impressions,
  total_clicks,
  total_purchases,
  CASE
    WHEN total_clicks > 0 THEN round(total_spent / total_clicks::numeric, 2)
    ELSE 0::numeric
  END AS avg_cpc,
  CASE
    WHEN total_purchases > 0 THEN round(total_spent / total_purchases::numeric, 2)
    ELSE 0::numeric
  END AS avg_cost_per_purchase
FROM daily;
