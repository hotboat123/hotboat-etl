hotboat-etl (Railway) – Python APScheduler + Sheets + Booknetic

Worker de ETL para HotBoat. Importa Google Sheets y Booknetic a Postgres (Railway) y exporta datos procesados de vuelta a Google Sheets para análisis en Looker.

## 🆕 NUEVO: Exportación Automática a Google Sheets

El sistema ahora **exporta automáticamente** la tabla `Reservas_Con_Extras_Sheets` a Google Sheets cada 15 minutos para análisis en tiempo real con Looker u otras herramientas de BI.

**📊 Ver Guía Rápida**: [GUIA_RAPIDA_EXPORT.md](./GUIA_RAPIDA_EXPORT.md)

**URL del Spreadsheet**: https://docs.google.com/spreadsheets/d/1K8ndJSfQ_sxVwNyIio8GL9WwMtwIX2x9mCJdGGiAlsA

### Características
✅ Exportación automática cada 15 minutos (configurable)
✅ Formato automático (headers en negrita, primera fila congelada)
✅ 50 filas × 30 columnas con datos completos de reservas
✅ Todas las columnas JSON aplanadas para fácil análisis
✅ Listo para conectar con Looker
✅ Metadatos de auditoría incluidos

### Ejecución Rápida
```bash
# Exportar una vez (prueba)
python demo_export.py

# Ejecutar continuamente (producción)
python jobs/runner.py
```

## Deploy rápido
1. Conecta el repo a Railway
2. Añade el plugin Postgres → copia `DATABASE_URL`
3. Variables de entorno: `DATABASE_URL`, `GOOGLE_SA_JSON_BASE64`, `SHEETS_SPREADSHEET_ID`, `SHEETS_WORKSHEET_NAME`, `BOOKNETIC_BASE_URL`, `BOOKNETIC_TOKEN`. Opcional: `BOOKNETIC_PLUGIN_MODULE` (p.ej. `plugins.booknetic_adapter_example`).
4. Start Command: `python -m jobs.runner`
5. Ejecuta `sql/schema.sql` y `sql/job_meta.sql` una vez

## Cron
- Booknetic: cada 30 min
- Sheets Import: cada 10 min
- **Export Reservas**: cada 15 min (NUEVO) ⭐

## Customización
- Ajusta columnas de Sheets en `jobs/job_import_sheets.py`
- Pega tu scraper en `plugins/` y exporta `fetch()`; configura `BOOKNETIC_PLUGIN_MODULE` para usarlo.
- Usa ON CONFLICT para idempotencia (ya implementado en helpers de DB)

## Desarrollo local
1. Crea `.env` desde `.env.example`
2. Instala dependencias: `pip install -r requirements.txt`
3. Ejecuta: `python -m jobs.runner`

## Estructura
```
jobs/
  runner.py                       # Runner principal con 3 jobs
  job_import_sheets.py           # Import desde Google Sheets
  job_scrape_booknetic.py        # Scraping de Booknetic
  export_reservas_to_sheets.py   # Export a Google Sheets (NUEVO)
db/
  connection.py
  utils.py
sql/
  schema.sql
  job_meta.sql
requirements.txt
.env.example
README.md
GUIA_RAPIDA_EXPORT.md            # Guía de exportación (NUEVO)
EXPORT_RESERVAS_SHEETS.md        # Docs técnicas completas (NUEVO)
demo_export.py                   # Demo de exportación (NUEVO)
```

## Notas
- El job de Sheets lee por encabezados; asegúrate que tu hoja tenga columnas compatibles con el mapeo definido.
- El job de Booknetic es un stub: agrega tu lógica de scraping/requests y mapea al esquema `booknetic_appointments`.
- Todos los jobs registran metadatos en `job_runs`.


