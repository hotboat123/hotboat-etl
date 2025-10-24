# 🚂 Deploy Rápido en Railway

## ✅ Resumen de lo que Hace el Sistema

El ETL exporta automáticamente datos de Booknetic y los guarda en PostgreSQL:

1. **Login automático** a WordPress con Selenium
2. **Exporta 3 tipos de datos**: Customers, Appointments, Payments
3. **Descarga CSV** de cada módulo
4. **Carga a PostgreSQL** automáticamente
5. **Se ejecuta cada 15 minutos** en Railway

---

## 📋 Paso 1: Preparar el Repositorio Git

Asegúrate de tener estos archivos en tu repo:

```bash
git add .
git commit -m "Booknetic ETL completo con export y carga a DB"
git push origin main
```

**Archivos importantes:**
- ✅ `Procfile` → `worker: python -m jobs.runner`
- ✅ `requirements.txt` → Dependencias Python
- ✅ `nixpacks.toml` → Configuración de Chromium para Railway
- ✅ `runtime.txt` → Python 3.11
- ✅ `sql/schema.sql` → Schema de base de datos

---

## 📋 Paso 2: Crear Proyecto en Railway

1. Ve a [railway.app](https://railway.app/)
2. Click en **"New Project"**
3. Selecciona **"Deploy from GitHub repo"**
4. Selecciona tu repositorio: `HotBoat-etl`

---

## 📋 Paso 3: Agregar PostgreSQL

1. En tu proyecto Railway, click en **"+ New"**
2. Selecciona **"Database" → "PostgreSQL"**
3. Railway crea automáticamente `DATABASE_URL`

---

## 📋 Paso 4: Ejecutar el Schema SQL

### Opción A: Desde Railway Console

1. Ve al servicio **PostgreSQL**
2. Click en **"Connect"** → Copia **"Postgres Connection URL"**
3. Desde tu terminal local:

```bash
# Reemplaza con tu URL de Railway
psql "postgresql://..." -f sql/schema.sql
psql "postgresql://..." -f sql/job_meta.sql
```

### Opción B: Automático

El archivo `db/migrate.py` ejecuta el schema automáticamente al iniciar.

---

## 📋 Paso 5: Configurar Variables de Entorno

En Railway, ve a tu servicio web → **"Variables"** y agrega:

```env
# Booknetic - IMPORTANTE: Cambia estas credenciales
BOOKNETIC_URL=https://hotboatchile.com/wp-login.php
BOOKNETIC_USERNAME=hotboatvillarrica@gmail.com
BOOKNETIC_PASSWORD=Hotboat777

# Plugin a usar (el nuevo plugin completo)
BOOKNETIC_PLUGIN_MODULE=plugins.booknetic_full_export

# Habilitar carga a base de datos
USE_DATABASE=true

# Timezone
TZ=America/Santiago
```

**IMPORTANTE:**
- `DATABASE_URL` se configura automáticamente por Railway ✅
- `CHROME_BIN` se configura automáticamente por nixpacks ✅

---

## 📋 Paso 6: Deploy Automático

Railway detectará el push a main y deployará automáticamente:

1. Construye la imagen con Nixpacks
2. Instala Chrome/Chromium
3. Instala dependencias Python
4. Ejecuta `python -m jobs.runner`

---

## 📋 Paso 7: Monitorear Logs

1. Ve a tu servicio en Railway
2. Click en **"Logs"**
3. Deberías ver algo como:

```
[runner] Scheduler started
[booknetic] plugin used: plugins.booknetic_full_export
🎉 ¡LOGIN EXITOSO!
✅ Customers exportado exitosamente
✅ Appointments exportado exitosamente
✅ Payments exportado exitosamente
📤 Cargando datos a PostgreSQL...
✅ 156 customers insertados/actualizados
✅ 423 appointments insertados/actualizados
✅ 267 payments insertados/actualizados
🎉 ¡Proceso completado exitosamente!
```

---

## 📋 Paso 8: Verificar la Base de Datos

Conéctate a tu base de datos de Railway:

```bash
psql "tu-railway-connection-url"

-- Ver tablas
\dt

-- Contar registros
SELECT 'customers' as tabla, COUNT(*) FROM booknetic_customers
UNION ALL
SELECT 'appointments', COUNT(*) FROM booknetic_appointments  
UNION ALL
SELECT 'payments', COUNT(*) FROM booknetic_payments;

-- Ver últimos appointments
SELECT 
  customer_name,
  customer_email,
  service_name,
  starts_at,
  status,
  created_at
FROM booknetic_appointments 
ORDER BY created_at DESC 
LIMIT 10;

-- Ver últimas ejecuciones del job
SELECT * FROM job_runs ORDER BY started_at DESC LIMIT 10;
```

---

## 📋 Configuración del Scheduler

Por defecto, el runner ejecuta:

- **Booknetic**: cada 15 minutos
- **Boot run**: Al iniciar, ejecuta inmediatamente

Para cambiar el intervalo, edita `jobs/runner.py`:

```python
scheduler.add_job(
    lambda: run_with_job_meta("booknetic_scrape", run_booknetic),
    trigger="cron",
    minute="*/30",  # <-- Cambiar a cada 30 minutos
    id="booknetic_cron",
    replace_existing=True,
)
```

---

## 🔧 Troubleshooting

### Error: Chrome no encontrado
**Solución:** Verifica que `nixpacks.toml` incluya:
```toml
nixPkgs = ["chromium", "chromedriver", ...]
```

### Error: DATABASE_URL no definido
**Solución:** Asegúrate de haber agregado el plugin PostgreSQL en Railway

### Selenium falla o timeout
**Solución:** 
- Verifica las credenciales en variables de entorno
- Revisa que `--headless=new` esté habilitado (ya configurado)
- Aumenta los timeouts en `booknetic_export_improved.py` si es necesario

### No se cargan datos a la DB
**Solución:**
- Verifica que `USE_DATABASE=true` esté configurado
- Revisa los logs para ver errores específicos
- Asegúrate de que el schema SQL se ejecutó correctamente

---

## 🎯 Redeployar Cambios

Cuando hagas cambios al código:

```bash
git add .
git commit -m "Descripción de cambios"
git push origin main
```

Railway detectará automáticamente y redeployará.

---

## 📊 Estructura de Datos

### Tabla: `booknetic_customers`
- `id` (text, PK)
- `name` (text)
- `email` (text)
- `phone` (text)
- `status` (text)
- `raw` (jsonb) - Datos completos del CSV
- `created_at`, `updated_at`

### Tabla: `booknetic_appointments`
- `id` (text, PK)
- `customer_name` (text)
- `customer_email` (text)
- `service_name` (text)
- `starts_at` (timestamptz)
- `status` (text)
- `raw` (jsonb) - Datos completos del CSV
- `created_at`, `updated_at`

### Tabla: `booknetic_payments`
- `id` (text, PK)
- `appointment_id` (text)
- `amount` (numeric)
- `currency` (text)
- `status` (text)
- `method` (text)
- `paid_at` (timestamptz)
- `raw` (jsonb) - Datos completos del CSV
- `created_at`, `updated_at`

---

## 🎉 ¡Listo!

Tu ETL de Booknetic está corriendo en Railway automáticamente cada 15 minutos 🚀

