# 🚀 HotBoat ETL - Sistema Completo de Exportación Booknetic → PostgreSQL

## ✨ ¿Qué Hace Este Sistema?

1. **Login automático** a WordPress usando Selenium
2. **Exporta 3 tipos de datos** de Booknetic:
   - 👥 **Customers** (clientes)
   - 📅 **Appointments** (reservas/citas)
   - 💰 **Payments** (pagos)
3. **Descarga CSVs** automáticamente
4. **Carga a PostgreSQL** con upsert (no duplica datos)
5. **Se ejecuta automáticamente** cada 15 minutos en Railway

---

## 📁 Estructura del Proyecto

```
HotBoat-etl/
├── jobs/
│   ├── runner.py                       # Scheduler principal (APScheduler)
│   ├── job_scrape_booknetic.py        # Job que ejecuta el export
│   └── booknetic_export_improved.py   # ⭐ Script mejorado con Selenium + DB
│
├── plugins/
│   ├── booknetic_full_export.py       # ⭐ Plugin completo (customers + appointments + payments)
│   ├── booknetic_export_adapter.py    # Plugin alternativo (CSV directo)
│   └── booknetic_selenium_export.py   # Plugin legacy (solo appointments)
│
├── db/
│   ├── connection.py                  # Pool de conexiones PostgreSQL
│   ├── utils.py                       # Funciones de upsert
│   └── migrate.py                     # Ejecución automática de schema
│
├── sql/
│   ├── schema.sql                     # Schema de las tablas
│   └── job_meta.sql                   # Metadata de jobs
│
├── test_booknetic_local.py            # Test SIN base de datos (solo CSV)
├── test_booknetic_with_db.py          # Test CON base de datos
├── run_booknetic_interactive.py       # Test interactivo (pide credenciales)
│
├── GUIA_LOCAL.md                      # Guía para correr localmente
├── GUIA_RAILWAY.md                    # Guía para deploy en Railway
├── DEPLOY_RAILWAY.md                  # ⭐ Guía rápida de deploy
│
├── Procfile                           # Comando de inicio para Railway
├── nixpacks.toml                      # Configuración de Chrome/Chromium
├── requirements.txt                   # Dependencias Python
└── runtime.txt                        # Python 3.11
```

---

## 🎯 Scripts Disponibles

### 1. Test Rápido SIN Base de Datos
```bash
python test_booknetic_local.py
```
- ✅ Solo exporta CSV
- ✅ No requiere PostgreSQL
- ✅ Perfecto para testing rápido

### 2. Test CON Base de Datos
```bash
# Configura DATABASE_URL primero
export DATABASE_URL="postgresql://user:pass@localhost:5432/hotboat_etl"
python test_booknetic_with_db.py
```
- ✅ Exporta CSV Y carga a PostgreSQL
- ✅ Requiere PostgreSQL corriendo

### 3. Test Interactivo
```bash
python run_booknetic_interactive.py
```
- ✅ Te pide usuario y contraseña
- ✅ No hardcodea credenciales

---

## ⚙️ Configuración de Variables de Entorno

### Para Test Local (archivo `.env` o variables)

```env
# Booknetic
BOOKNETIC_URL=https://hotboatchile.com/wp-login.php
BOOKNETIC_USERNAME=hotboatvillarrica@gmail.com
BOOKNETIC_PASSWORD=Hotboat777

# Plugin (el nuevo plugin completo)
BOOKNETIC_PLUGIN_MODULE=plugins.booknetic_full_export

# Base de datos (para test con DB)
DATABASE_URL=postgresql://user:pass@localhost:5432/hotboat_etl
USE_DATABASE=true

# Timezone
TZ=America/Santiago
```

### Para Railway (Variables del servicio)

```env
BOOKNETIC_URL=https://hotboatchile.com/wp-login.php
BOOKNETIC_USERNAME=hotboatvillarrica@gmail.com
BOOKNETIC_PASSWORD=Hotboat777
BOOKNETIC_PLUGIN_MODULE=plugins.booknetic_full_export
USE_DATABASE=true
TZ=America/Santiago
```

**NOTA:** `DATABASE_URL` y `CHROME_BIN` se configuran automáticamente en Railway ✅

---

## 🗄️ Estructura de la Base de Datos

### Tabla: `booknetic_customers`
```sql
CREATE TABLE booknetic_customers (
    id TEXT PRIMARY KEY,
    name TEXT,
    email TEXT,
    phone TEXT,
    status TEXT,
    raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Tabla: `booknetic_appointments`
```sql
CREATE TABLE booknetic_appointments (
    id TEXT PRIMARY KEY,
    customer_name TEXT,
    customer_email TEXT,
    service_name TEXT,
    starts_at TIMESTAMPTZ,
    status TEXT,
    raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Tabla: `booknetic_payments`
```sql
CREATE TABLE booknetic_payments (
    id TEXT PRIMARY KEY,
    appointment_id TEXT,
    amount NUMERIC,
    currency TEXT,
    status TEXT,
    method TEXT,
    paid_at TIMESTAMPTZ,
    raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 🔄 Flujo de Datos

```
1. Scheduler (cada 15 min)
   ↓
2. jobs/runner.py ejecuta job_scrape_booknetic
   ↓
3. job_scrape_booknetic.py carga plugin booknetic_full_export
   ↓
4. booknetic_full_export.py ejecuta booknetic_export_improved.py
   ↓
5. booknetic_export_improved.py:
   - Login con Selenium
   - Exporta customers → customers_YYYY-MM-DD.csv
   - Exporta appointments → appointments_YYYY-MM-DD.csv
   - Exporta payments → payments_YYYY-MM-DD.csv
   ↓
6. Lee los CSV y los mapea a formato de DB
   ↓
7. Ejecuta UPSERT en PostgreSQL (no duplica datos)
   ↓
8. ✅ Listo!
```

---

## 🚂 Deploy en Railway - Guía Rápida

### 1. Push a GitHub
```bash
git add .
git commit -m "ETL completo con export y carga a DB"
git push origin main
```

### 2. Crear Proyecto en Railway
- Ve a [railway.app](https://railway.app/)
- New Project → Deploy from GitHub
- Selecciona tu repo

### 3. Agregar PostgreSQL
- Click "+ New" → Database → PostgreSQL
- Railway configura `DATABASE_URL` automáticamente

### 4. Configurar Variables
En Railway → Variables:
```env
BOOKNETIC_URL=https://hotboatchile.com/wp-login.php
BOOKNETIC_USERNAME=hotboatvillarrica@gmail.com
BOOKNETIC_PASSWORD=Hotboat777
BOOKNETIC_PLUGIN_MODULE=plugins.booknetic_full_export
USE_DATABASE=true
TZ=America/Santiago
```

### 5. Deploy Automático
Railway detecta el push y deploya automáticamente ✅

### 6. Ver Logs
Railway → Logs
```
[runner] Scheduler started
[booknetic] plugin used: plugins.booknetic_full_export
🎉 ¡LOGIN EXITOSO!
✅ Customers exportado exitosamente
✅ Appointments exportado exitosamente
✅ Payments exportado exitosamente
💾 156 customers en DB
💾 423 appointments en DB
💾 267 payments en DB
```

---

## 📊 Consultas Útiles

### Ver todos los datos
```sql
-- Contar registros
SELECT 'customers' as tabla, COUNT(*) FROM booknetic_customers
UNION ALL
SELECT 'appointments', COUNT(*) FROM booknetic_appointments
UNION ALL
SELECT 'payments', COUNT(*) FROM booknetic_payments;

-- Ver últimas reservas
SELECT 
  customer_name,
  customer_email,
  service_name,
  starts_at,
  status
FROM booknetic_appointments 
ORDER BY created_at DESC 
LIMIT 10;

-- Ver últimos pagos
SELECT 
  appointment_id,
  amount,
  currency,
  status,
  method,
  paid_at
FROM booknetic_payments 
ORDER BY created_at DESC 
LIMIT 10;
```

---

## 🛠️ Troubleshooting

### Error: Chrome no encontrado
**Solución:** Instala Chrome desde https://www.google.com/chrome/

### Error: DATABASE_URL no definido
**Solución:** Configura la variable o usa `test_booknetic_local.py` (sin DB)

### Error: Login falló
**Solución:** Verifica las credenciales `BOOKNETIC_USERNAME` y `BOOKNETIC_PASSWORD`

### No se cargan datos a DB
**Solución:** Verifica que `USE_DATABASE=true` esté configurado

---

## 📚 Documentación Completa

- **`GUIA_LOCAL.md`** - Instrucciones detalladas para local
- **`GUIA_RAILWAY.md`** - Instrucciones detalladas para Railway
- **`DEPLOY_RAILWAY.md`** - Guía rápida de deploy

---

## ✨ Características

✅ **Idempotente**: No duplica datos (usa UPSERT)  
✅ **Automático**: Se ejecuta cada 15 minutos  
✅ **Completo**: Exporta customers, appointments y payments  
✅ **Robusto**: Maneja errores y reintentos  
✅ **Monitoreable**: Logs detallados y metadata de jobs  
✅ **Flexible**: Funciona local y en Railway  

---

## 🎉 ¡Listo para Usar!

Tu ETL de Booknetic está listo para correr localmente o en Railway 🚀

