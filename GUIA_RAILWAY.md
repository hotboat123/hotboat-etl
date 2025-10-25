# 🚂 Guía para Deploy en Railway

## Prerequisitos

1. ✅ El código funciona localmente (verifica con `test_booknetic_local.py`)
2. ✅ Tienes cuenta en [Railway](https://railway.app/)
3. ✅ Tienes tu código en un repositorio Git (GitHub, GitLab, etc.)

## Paso 1: Preparar el Repositorio

Asegúrate de que estos archivos estén en tu repo:

- ✅ `requirements.txt` - Dependencias de Python
- ✅ `Procfile` - Comando de inicio
- ✅ `nixpacks.toml` - Configuración de Chrome/Chromium para Selenium
- ✅ `runtime.txt` - Versión de Python
- ✅ `sql/schema.sql` - Schema de base de datos
- ✅ `sql/job_meta.sql` - Metadata de jobs

**IMPORTANTE:** NO subas archivos `.env` al repositorio (ya están en `.gitignore`)

## Paso 2: Crear Proyecto en Railway

1. Ve a [railway.app](https://railway.app/) e inicia sesión
2. Click en "New Project"
3. Selecciona "Deploy from GitHub repo"
4. Autoriza Railway a acceder a tu GitHub
5. Selecciona tu repositorio `HotBoat-etl`

## Paso 3: Agregar Base de Datos PostgreSQL

1. En tu proyecto de Railway, click en "+ New"
2. Selecciona "Database" → "PostgreSQL"
3. Railway creará automáticamente una base de datos
4. La variable `DATABASE_URL` se inyectará automáticamente

## Paso 4: Ejecutar el Schema SQL

Hay dos formas de ejecutar el schema:

### Opción A: Desde la consola de Railway

1. Ve a tu servicio de PostgreSQL en Railway
2. Click en "Connect" → "Postgres Connection URL"
3. Copia la URL de conexión
4. Desde tu terminal local:

```bash
# Reemplaza <RAILWAY_DATABASE_URL> con la URL que copiaste
psql "<RAILWAY_DATABASE_URL>" -f sql/schema.sql
psql "<RAILWAY_DATABASE_URL>" -f sql/job_meta.sql
```

### Opción B: Crear un script de migración

Ya tienes `db/migrate.py` que ejecuta automáticamente el schema al iniciar.

## Paso 5: Configurar Variables de Entorno

En Railway, ve a tu servicio → "Variables":

```env
# Booknetic
BOOKNETIC_URL=https://hotboatchile.com/wp-login.php
BOOKNETIC_USERNAME=hotboatvillarrica@gmail.com
BOOKNETIC_PASSWORD=Hotboat777
BOOKNETIC_PLUGIN_MODULE=plugins.booknetic_full_export

# Database (se habilita automáticamente en Railway)
USE_DATABASE=true

# Timezone
TZ=America/Santiago

# Google Sheets (si lo usas)
# GOOGLE_SA_JSON_BASE64=ewogICJ0eXBlIjogInNlcnZpY2VfYWNjb3VudCIsCiAgInByb2plY3RfaWQiOiAiaG90Ym9hdC1ldGwiLAogICJwcml2YXRlX2tleV9pZCI6ICJlOWI4MWQzYWYzMzRlZTQ5ODk4MzIyNTI5NjY0MWY4NTM5YTliYzk3IiwKICAicHJpdmF0ZV9rZXkiOiAiLS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tXG5NSUlFdlFJQkFEQU5CZ2txaGtpRzl3MEJBUUVGQUFTQ0JLY3dnZ1NqQWdFQUFvSUJBUUN3NTJtOXhKNklwcU9XXG5GYk1iaUt4TXlPczMyQVp3T01RY2xGcnROYjd2RHVzeDRUZHRxaG1PUDF5a1FuN3lBcVBKQ3JROXdXSnBtaTZXXG50N0pDdzVEd1V4OVZ0czRFWjJxMU9wKzhWdVVSakp1bnV1VUNaSWpGdTdhQi9KZHQ0OCtUSVM3WURuRWhzQnpXXG5SQmdNLzdUcWZOcXQzNXZYc1pBUmxTdXJVb2xrSnJnRG81cFc1ZVEvOXZGVzZSMitIQVprT0R1UUttUmQwODFwXG5FSkxDT1F6c2NuelRXbWg3bk1tbXdMOU4rWXZDWmRUaXFhUGduVVpuUDRhT0phamJwelhOT284d0NNNkllV0YyXG4wWUVtK0tEeFEwZmNEQjY0RXJFSDFpbkFvSFhrbjVRc2hUaUNMdTh3cWdZa3NTb2hKWVFPUXNwQ2VhbmRhZGJkXG5ZYlBXMWJBakFnTUJBQUVDZ2dFQUQwZkFpYUhtVGJNVElKVE82K1hDSXVuSFE0TnNpWnlsb3BCVlN2VzFxeXcwXG5qWkpBdVpTK20xdXhhQVlrWC9RY0ZmS2s2ZmFwRzZwZWlYODVneGNsdWFuUnVaTjQ0bkYvdFVLOTV4bnh0RjB3XG5XV3h2em8vdmc4dU4zVmJROVFRcCt3YWI1MmFyOHFIUWc5ak5qbHMzVXlVbUN4Y1cvTlVRdHRiQWpHT3NqQksvXG4rRXUyclZzSXN3Z2xUU3JhTFJ4RU56dmI1YUtaNlAxTkQ5emhjVndZVHJTbzN4MU80WkNYdzRhWWYxUmpuYklCXG4wT3YzL0tud0R3WnJCUFZRSmVkT2IyaW5MYWx6bE5OM0hiNGhYMkphZjZKMzc0d3pHN2pLRHJrL1lYSFVLVEJvXG4xOHRvazd2K2VuL3BwRVJwUGswSndjTytqS0N1b2wzUzF5MW5KTjhUYVFLQmdRRGVPUWFwUmxwdHNjblZ5WU1mXG5YUUpnRmVoMmJSUTVHdlRod0I2c0lNcXN2VE56dUV4OWRuTlFyV2IyNFdlOUhweFlmQlJLRTZGQzNHQmxBSGU0XG5oL3U3QWdHVkxGMEJWNE1RNkVGcHlYdE9hK2lsMCtqU1dhRStqQ1Bka1M2Wi9SN2J2YTZHd05OK1I5TTM3c29qXG5iWHFOZGtHdG1WY2pWUE5hMi9Tb1U1dnArd0tCZ1FETHl2bGRHV3ZxNVdzZHJjR09CRkFMdEJVbnRWeE00V1A2XG52QUpQZ2NuVTYvYWhTS2xFVVpyc0dWUnFWMG9yT1ByUzRMMlN3TXpiMklzUE9KbVRlV05Oc0hCaXpmQzEzY0haXG4zZ0JEQXlWMWxaa2UxTjhZVGtJSWhtcGxWQU5mMTNmVE84TlFodUZ2VGV6TTFLWGYySDAvYVdqVTgwWnJ0cTdEXG5PMWFOK2VWaCtRS0JnUURZMU5YZUY4cW1uRUt2dXRlWm83eHNteFBmY2lHNGNzZ2Mrc1F5K2pBb2l0aUlnbjBJXG5NcXJrUHI1b0NKcWJteUc4NlIwM0JwNWtTZm80czFNZUdIbVZDS2tZc0ZmenRqc3FKU1dtbmpVVjJROEJ0NXJHXG5uVFJMZnB5RVZtUWRWekZrQWxvb0hFQ0JTSDRkWm4rUVFBUER3bTdsZitqWmpjdUNqWHJWUC9lelB3S0JnQURDXG5QTE53Q01yVEY5Y0FjcHdJd0JPTEZCa1Z2OFk1Z0puS1lXZlNYK0gvRHVnQzBUNkQzMFBKeEZxeEFJR3dzSjVnXG5YOVJRQzNNMkZ5NXpVMzhORUtXVlpwVzNscEhXeFlYK0lab2VST0Z2TVNiQVBDUm5CaS9wOERONFlKcld2b2QyXG56WDliUVRPYzRxalFrZDJIZk0vam9KUktZNVM3RldOOHNSSE9RR0JoQW9HQVhJdUtNeFBrZFJSY3ZET0ZVZkpjXG51YjFCaXBGQUxQMnhrQmttQlUwUW1GbXpIYURXc1NuMFgwRUFNaDhiaUFHMHBYdmRUNy9Eb2RjbkhzRXVkb1FzXG5XY3JrNW96NGlRYUEvSEE2dGhwN1U1QXNNVTBNTTBRa01wQ00vQmR1ZjVkRXVPbWRESXQ2anhHd2QyMHFCOHhiXG5hOHdVUWtTajd4M2s2dDkzZzdIUVRCST1cbi0tLS0tRU5EIFBSSVZBVEUgS0VZLS0tLS1cbiIsCiAgImNsaWVudF9lbWFpbCI6ICJob3Rib2F0LWV0bC1zZXJ2aWNlQGhvdGJvYXQtZXRsLmlhbS5nc2VydmljZWFjY291bnQuY29tIiwKICAiY2xpZW50X2lkIjogIjExMjQxNTI3MzY2Njg0MDMyODYyOCIsCiAgImF1dGhfdXJpIjogImh0dHBzOi8vYWNjb3VudHMuZ29vZ2xlLmNvbS9vL29hdXRoMi9hdXRoIiwKICAidG9rZW5fdXJpIjogImh0dHBzOi8vb2F1dGgyLmdvb2dsZWFwaXMuY29tL3Rva2VuIiwKICAiYXV0aF9wcm92aWRlcl94NTA5X2NlcnRfdXJsIjogImh0dHBzOi8vd3d3Lmdvb2dsZWFwaXMuY29tL29hdXRoMi92MS9jZXJ0cyIsCiAgImNsaWVudF94NTA5X2NlcnRfdXJsIjogImh0dHBzOi8vd3d3Lmdvb2dsZWFwaXMuY29tL3JvYm90L3YxL21ldGFkYXRhL3g1MDkvaG90Ym9hdC1ldGwtc2VydmljZSU0MGhvdGJvYXQtZXRsLmlhbS5nc2VydmljZWFjY291bnQuY29tIiwKICAidW5pdmVyc2VfZG9tYWluIjogImdvb2dsZWFwaXMuY29tIgp9Cg==
# SHEETS_SPREADSHEET_ID=1K8ndJSfQ_sxVwNyIio8GL9WwMtwIX2x9mCJdGGiAlsA
# SHEETS_WORKSHEET_NAME=Informacion Reserva

# Chrome/Chromium (Railway lo detecta automáticamente con nixpacks.toml)
# CHROME_BIN=/nix/store/.../chromium
```

**NOTA:** `DATABASE_URL` ya está configurada automáticamente por Railway.

## Paso 6: Verificar Configuración de Deploy

Revisa que estos archivos estén correctos:

### `Procfile` (debe decir):
```
worker: python -m jobs.runner
```

### `nixpacks.toml` (debe incluir Chrome):
```toml
[phases.setup]
nixPkgs = [
  "python311",
  "chromium",
  "chromedriver",
  # ... otros paquetes
]
```

### `runtime.txt` (versión de Python):
```
python-3.11.x
```

## Paso 7: Deploy!

1. Railway detectará automáticamente los cambios en tu repo
2. Construirá la imagen con Nixpacks
3. Instalará las dependencias de `requirements.txt`
4. Ejecutará el comando del `Procfile`: `python -m jobs.runner`

## Paso 8: Monitorear

1. Ve a tu servicio en Railway
2. Click en "Logs" para ver la salida
3. Deberías ver algo como:

```
[runner] Scheduler started. Cron: sheets @ *; booknetic @ */15 (boot run enabled)
[booknetic] plugin used: plugins.booknetic_selenium_export
✅ Navegación a Booknetic exitosa
```

## Paso 9: Verificar Base de Datos

Conecta a tu base de datos de Railway y verifica que los datos se estén guardando:

```bash
psql "<RAILWAY_DATABASE_URL>"

-- Ver tablas
\dt

-- Ver datos de appointments
SELECT * FROM booknetic_appointments ORDER BY created_at DESC LIMIT 5;

-- Ver datos de customers
SELECT * FROM booknetic_customers ORDER BY created_at DESC LIMIT 5;

-- Ver logs de jobs
SELECT * FROM job_runs ORDER BY started_at DESC LIMIT 10;
```

## Configuración de Cron Jobs

Por defecto, el runner ejecuta:

- **Booknetic**: cada 15 minutos (`*/15`)
- **Google Sheets**: cada 10 minutos (`*/10`)
- **Boot run**: Al iniciar, ejecuta Booknetic inmediatamente

Puedes ajustar estos intervalos en `jobs/runner.py`:

```python
# Cambiar a cada 30 minutos:
scheduler.add_job(
    lambda: run_with_job_meta("booknetic_scrape", run_booknetic),
    trigger="cron",
    minute="*/30",  # <-- cambiar aquí
    id="booknetic_cron",
    replace_existing=True,
)
```

## Troubleshooting en Railway

### El worker no inicia
- Verifica que el `Procfile` esté correcto
- Revisa los logs en Railway para ver errores

### Error: Chrome no encontrado
- Verifica que `nixpacks.toml` incluya `chromium` y `chromedriver`
- Railway debería setear `CHROME_BIN` automáticamente

### Error: DATABASE_URL no definido
- Railway lo inyecta automáticamente si agregaste el plugin PostgreSQL
- Verifica en "Variables" que existe

### Selenium falla
- En Railway, usa modo headless: `--headless=new`
- El plugin `booknetic_selenium_export.py` ya lo tiene configurado

## Modo Desarrollo vs Producción

### Local (Desarrollo):
```bash
python test_booknetic_local.py  # Test rápido
python -m jobs.runner  # Full runner
```

### Railway (Producción):
- Se ejecuta automáticamente con `Procfile`
- Logs disponibles en la consola de Railway
- Reinicia automáticamente si falla

## Redeployar Cambios

Cuando hagas cambios al código:

```bash
git add .
git commit -m "Descripción de cambios"
git push origin main
```

Railway detectará el push y redeployará automáticamente.

## Recursos

- [Railway Docs](https://docs.railway.app/)
- [Nixpacks](https://nixpacks.com/docs)
- [APScheduler](https://apscheduler.readthedocs.io/)

---

¡Listo! Tu ETL de Booknetic debería estar corriendo en Railway 🎉

