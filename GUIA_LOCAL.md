# 🚀 Guía para Correr Booknetic ETL Localmente

## Paso 1: Instalar Dependencias

```bash
# Crear entorno virtual (recomendado)
python -m venv venv

# Activar entorno virtual
# En Windows PowerShell:
.\venv\Scripts\Activate.ps1
# En Windows CMD:
.\venv\Scripts\activate.bat

# Instalar dependencias
pip install -r requirements.txt
```

## Paso 2: Configurar Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto con este contenido:

```env
# Base de datos PostgreSQL (para el runner completo)
DATABASE_URL=postgresql://usuario:password@localhost:5432/hotboat_etl

# Configuración de Booknetic
BOOKNETIC_URL=https://hotboatchile.com/wp-login.php
BOOKNETIC_USERNAME=hotboatvillarrica@gmail.com
BOOKNETIC_PASSWORD=H0TBOAT123

# Plugin a usar (para el runner)
BOOKNETIC_PLUGIN_MODULE=plugins.booknetic_selenium_export

# Timezone
TZ=America/Santiago
```

## Paso 3: Opciones de Ejecución

### Opción A: Test Rápido SIN Base de Datos (Recomendado para empezar)

Este script usa Selenium para hacer login y exportar datos de Booknetic, **sin necesidad de PostgreSQL**:

```bash
python test_booknetic_local.py
```

O ejecutar directamente el script mejorado:

```bash
python -m jobs.booknetic_export_improved
```

**Ventajas:**
- ✅ No necesita base de datos
- ✅ Descarga los datos directamente
- ✅ Guarda en carpeta `downloads/`
- ✅ Perfecto para testing

### Opción B: Runner Completo CON Base de Datos

Este ejecuta el ETL completo con APScheduler y guarda en PostgreSQL:

1. **Instalar PostgreSQL localmente** o usar Railway

   Para instalar localmente en Windows:
   - Descargar de: https://www.postgresql.org/download/windows/
   - O usar Docker: `docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=mysecretpassword postgres`

2. **Crear la base de datos:**

   ```bash
   # Conectarse a PostgreSQL
   psql -U postgres
   
   # Crear base de datos
   CREATE DATABASE hotboat_etl;
   \q
   ```

3. **Ejecutar el schema SQL:**

   ```bash
   psql -U postgres -d hotboat_etl -f sql/schema.sql
   psql -U postgres -d hotboat_etl -f sql/job_meta.sql
   ```

4. **Ejecutar el runner:**

   ```bash
   python -m jobs.runner
   ```

**Ventajas:**
- ✅ ETL completo automático
- ✅ Guarda datos en PostgreSQL
- ✅ Ejecuta en intervalos programados
- ✅ Incluye metadata de jobs

## Paso 4: Verificar Instalación de Chrome

El proyecto usa Selenium con Chrome. Asegúrate de tener Chrome instalado:

- Windows: Chrome se detecta automáticamente si está instalado
- El paquete `chromedriver-autoinstaller` descarga el driver automáticamente

## Problemas Comunes

### Error: Chrome no encontrado
```bash
# Instalar Chrome desde: https://www.google.com/chrome/
```

### Error: ModuleNotFoundError
```bash
# Asegúrate de estar en el entorno virtual
pip install -r requirements.txt
```

### Error: DATABASE_URL no definido
```bash
# Para test rápido, usa: python test_booknetic_local.py
# Para runner completo, configura el .env con tu DATABASE_URL
```

## Próximo Paso: Deploy a Railway

Una vez que funcione localmente, continúa con la `GUIA_RAILWAY.md`

