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
# GOOGLE_SA_JSON_BASE64=tu_base64_aqui
# SHEETS_SPREADSHEET_ID=tu_id_aqui
# SHEETS_WORKSHEET_NAME=Sheet1

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

