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
3. Variables de entorno: `DATABASE_URL`, `GOOGLE_SA_JSON_BASE64`, `SHEETS_SPREADSHEET_ID`, `SHEETS_WORKSHEET_NAME`, `BOOKNETIC_BASE_URL`, `BOOKNETIC_TOKEN`. Opcional: `BOOKNETIC_PLUGIN_MODULE` (p.ej. `plugins.booknetic_adapter_example`). **Meta Ads → Postgres (DBeaver):** `META_ACCESS_TOKEN`, `META_AD_ACCOUNT_ID`; opcional `META_ADS_INTERVAL` (segundos, default 3600), `META_DATE_PRESET` (ej. `last_90d`, `maximum`; Meta no admite `last_365d` en insights), `META_TIME_RANGE_SINCE` + `META_TIME_RANGE_UNTIL` (`YYYY-MM-DD`, backfill), `META_API_VERSION` (ej. `v21.0`).
4. Start Command: `python -m jobs.runner`
5. Ejecuta `sql/schema.sql` y `sql/job_meta.sql` una vez

## Cron
- Booknetic: cada 30 min
- Sheets Import: cada 10 min
- **Export Reservas**: cada 15 min (NUEVO) ⭐
- **Meta Ads** (si configuras token + cuenta): cada 60 min por defecto; tablas `meta_campaigns`, `meta_adsets`, `meta_ads`, `meta_ads_insights`

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

## Índice de Flujo Turístico Pucón

Sistema para estimar la demanda turística en Pucón y generar un "semáforo de marketing" accionable.

### Tablas nuevas

| Tabla | Descripción |
|---|---|
| `tourism_signal_snapshots` | Señales brutas por hora: clima, tráfico, alojamiento |
| `pucon_flow_index` | Índice final calculado (0-100) con nivel y acción recomendada |
| `source_query_log` | Log de cada llamada a API externa |

### Variables de entorno requeridas

```
# Clima (OpenWeather - free tier disponible en openweathermap.org)
OPENWEATHER_API_KEY=...

# Tráfico (Google Maps Platform - Distance Matrix API, requiere billing activado)
GOOGLE_MAPS_API_KEY=...
```

### Variables de entorno opcionales (intervalos)

```
WEATHER_INTERVAL=3600       # cada 1 h (default)
TRAFFIC_INTERVAL=10800      # cada 3 h (default)
FLOW_INDEX_INTERVAL=3600    # cada 1 h (default)
```

### Lógica del índice (MVP sin alojamiento)

```
final_score = 0.60 * traffic_score + 0.40 * weather_score

0-30   → bajo     → Promoción last minute, descuentos
31-55  → medio    → Campañas normales, destacar premium
56-75  → alto     → Subir presupuesto, urgencia
76-100 → muy_alto → Precio completo, remarketing
```

Cuando se agregue alojamiento (etapa 2):
```
final_score = 0.40 * lodging_avail + 0.25 * lodging_price + 0.25 * traffic + 0.10 * weather
```

### Score de clima para HotBoat

| Condición | Efecto |
|---|---|
| Temperatura 5-18°C | +40 |
| Lluvia suave (0.1-5mm/h) | +20 |
| Nubosidad ≥ 70% | +10 |
| Viento > 30 km/h | -30 |
| Lluvia extrema > 10mm/h | -40 |
| Base | 50 |

### Score de tráfico

```
ratio = duracion_con_trafico / duracion_normal
score = min(100, max(0, (ratio - 1) * 100))
# ratio 1.0 = score 0 (sin congestión)
# ratio 1.3 = score 30
# ratio 1.8 = score 80
```

Rutas medidas: Villarrica→Pucón, Temuco→Pucón, Aeropuerto La Araucanía→Pucón, Caburgua→Pucón.

### Etapa 2: Alojamiento

Ver `jobs/job_collect_lodging.py` — arquitectura lista para conectar Booking.com u otra fuente.

---

## Notas
- El job de Sheets lee por encabezados; asegúrate que tu hoja tenga columnas compatibles con el mapeo definido.
- El job de Booknetic es un stub: agrega tu lógica de scraping/requests y mapea al esquema `booknetic_appointments`.
- Todos los jobs registran metadatos en `job_runs`.


