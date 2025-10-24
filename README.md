hotboat-etl (Railway) – Python APScheduler + Sheets + Booknetic

Worker de ETL para HotBoat. Importa Google Sheets y Booknetic a Postgres (Railway).

## Deploy rápido
1. Conecta el repo a Railway
2. Añade el plugin Postgres → copia `DATABASE_URL`
3. Variables de entorno: `DATABASE_URL`, `GOOGLE_SA_JSON_BASE64`, `SHEETS_SPREADSHEET_ID`, `SHEETS_WORKSHEET_NAME`, `BOOKNETIC_BASE_URL`, `BOOKNETIC_TOKEN`
4. Start Command: `python -m jobs.runner`
5. Ejecuta `sql/schema.sql` y `sql/job_meta.sql` una vez

## Cron
- Sheets: cada 30 min (minuto 5 y 35)
- Booknetic: cada 15 min

## Customización
- Ajusta columnas de Sheets en `jobs/job_import_sheets.py`
- Pega tu scraper en `jobs/job_scrape_booknetic.py`
- Usa ON CONFLICT para idempotencia (ya implementado en helpers de DB)

## Desarrollo local
1. Crea `.env` desde `.env.example`
2. Instala dependencias: `pip install -r requirements.txt`
3. Ejecuta: `python -m jobs.runner`

## Estructura
```
jobs/
  runner.py
  job_import_sheets.py
  job_scrape_booknetic.py
db/
  connection.py
  utils.py
sql/
  schema.sql
  job_meta.sql
requirements.txt
.env.example
README.md
```

## Notas
- El job de Sheets lee por encabezados; asegúrate que tu hoja tenga columnas compatibles con el mapeo definido.
- El job de Booknetic es un stub: agrega tu lógica de scraping/requests y mapea al esquema `booknetic_appointments`.
- Todos los jobs registran metadatos en `job_runs`.


