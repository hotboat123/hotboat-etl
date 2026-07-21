hotboat-etl (Railway) – Python + Sheets + Meta/Google Ads

Worker de ETL para HotBoat. Importa "consolidad flujo caja" desde Google Sheets a Postgres (Railway) y sincroniza Meta Ads / Google Ads para análisis en Looker/DBeaver.

## Deploy rápido
1. Conecta el repo a Railway
2. Añade el plugin Postgres → copia `DATABASE_URL`
3. Variables de entorno: `DATABASE_URL`, `GOOGLE_SA_JSON_BASE64`, `LOOKER_SPREADSHEET_ID`. **Meta Ads → Postgres (DBeaver):** `META_ACCESS_TOKEN`, `META_AD_ACCOUNT_ID`; opcional `META_ADS_INTERVAL` (segundos, default 3600), `META_DATE_PRESET` (ej. `last_90d`, `maximum`; Meta no admite `last_365d` en insights), `META_TIME_RANGE_SINCE` + `META_TIME_RANGE_UNTIL` (`YYYY-MM-DD`, backfill), `META_API_VERSION` (ej. `v21.0`).
4. Start Command: `python -m jobs.runner`
5. Ejecuta `sql/schema.sql` una vez

## Cron
- **Meta Ads** (si configuras token + cuenta): cada 60 min por defecto; tablas `meta_campaigns`, `meta_adsets`, `meta_ads`, `meta_ads_insights`
- **Google Ads** (si configuras token + cuenta): cada 60 min por defecto; tablas `google_ads_campaigns`, `google_ads_adgroups`, `google_ads_performance`
- **Flujo Caja** (si configuras `LOOKER_SPREADSHEET_ID`): cada 30 min por defecto

## Customización
- Usa ON CONFLICT para idempotencia (ya implementado en helpers de DB)

## Desarrollo local
1. Crea `.env` desde `.env.example`
2. Instala dependencias: `pip install -r requirements.txt`
3. Ejecuta: `python -m jobs.runner`

## Estructura
```
jobs/
  runner.py                       # Runner principal
  job_meta_ads.py                 # Sync Meta Ads
  job_google_ads.py               # Sync Google Ads
  job_flujo_caja.py                # Import Flujo Caja desde Sheets
db/
  connection.py
  utils.py
sql/
  schema.sql
requirements.txt
.env.example
README.md
```
