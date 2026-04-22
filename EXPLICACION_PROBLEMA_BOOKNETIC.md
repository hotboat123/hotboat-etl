# 🔍 Explicación del Problema con Booknetic

## 📋 Resumen del Problema

Los CSVs de Booknetic **SÍ se están descargando correctamente** con Selenium, pero **PostgreSQL no se actualiza** porque las variables de entorno no están configuradas en tu entorno local.

## ✅ Lo que está funcionando:

1. ✅ **Selenium funciona perfectamente**
   - Se están descargando los CSVs de customers, appointments y payments
   - Los archivos están en la carpeta `downloads/`
   - Última descarga: `2025-10-24 23:16:40`

2. ✅ **Los CSVs contienen datos reales**
   - **293 customers**
   - **181 appointments**
   - **181 payments**

3. ✅ **El parsing de CSVs funciona**
   - Los archivos CSV se leen correctamente
   - Los datos se mapean correctamente a la estructura de la base de datos

## ❌ El Problema:

**Las variables de entorno NO están configuradas en tu máquina local**, especialmente:
- `DATABASE_URL` ❌ NO configurado
- `BOOKNETIC_USERNAME` ❌ NO configurado
- `BOOKNETIC_PASSWORD` ❌ NO configurado

Esto significa que:
- Cuando ejecutas el script localmente, no puede conectarse a PostgreSQL
- Los datos se descargan pero NO se cargan a la base de datos
- El proceso se detiene silenciosamente sin errores visibles

## 🔧 Soluciones:

### Opción 1: Ver los CSVs descargados (YA LOS TIENES)

Los CSVs están en `downloads/` y puedes abrirlos con Excel para ver los datos:
```
downloads/
├── customers_2025Oct24.csv      (293 registros)
├── appointments_2025Oct24.csv   (181 registros)
└── payments_2025Oct24.csv       (181 registros)
```

### Opción 2: Cargar manualmente a PostgreSQL

He creado un script `test_with_railway.py` que:
1. Lee los CSVs locales que ya descargaste
2. Se conecta a tu base de datos de Railway
3. Carga los datos (TRUNCATE + INSERT)

**Para ejecutarlo:**
```bash
python test_with_railway.py
```

⚠️ **IMPORTANTE**: Este script reemplazará completamente los datos en Railway con los datos de tus CSVs locales.

### Opción 3: Configurar variables de entorno localmente

Si quieres que el ETL completo funcione localmente, necesitas crear un archivo `.env`:

```bash
# Booknetic
BOOKNETIC_URL=https://hotboatchile.com/wp-login.php
BOOKNETIC_USERNAME=hotboatvillarrica@gmail.com
BOOKNETIC_PASSWORD=Hotboat777
BOOKNETIC_PLUGIN_MODULE=plugins.booknetic_full_export

# Railway Database
DATABASE_URL=postgresql://postgres:CxNTjRZqVQnUTzHUUeOYUITfqGWBXKVv@autorack.proxy.rlwy.net:31093/railway
```

Y luego ejecutar:
```bash
python -c "from jobs.job_scrape_booknetic import run; run()"
```

## 🚂 ¿Qué pasa en Railway?

En Railway, el proceso **SÍ debería estar funcionando** si:
1. Las variables de entorno están configuradas en Railway ✅
2. El job se ejecuta cada 15 minutos ✅
3. Selenium puede ejecutarse en el contenedor ⚠️

**POSIBLE PROBLEMA EN RAILWAY**: Selenium necesita Chrome/Chromium instalado. Si Railway no tiene Chrome instalado, Selenium fallará silenciosamente.

## 🔎 Verificar en Railway:

Para ver si el problema está en Railway, revisa los logs:

```bash
# Ver los logs más recientes
railway logs

# Buscar errores de Selenium
railway logs | grep -i "selenium\|chrome\|driver"

# Ver si los jobs se están ejecutando
railway logs | grep -i "booknetic"
```

Si ves errores como:
- `ChromeDriver not found`
- `Chrome binary not found`
- `WebDriverException`

Entonces el problema es que **Selenium no puede ejecutarse en Railway**.

## 💡 Solución Recomendada:

### Para Railway (producción):

El `Dockerfile` ya incluye Chrome:
```dockerfile
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    chromium \
    chromium-driver
```

Pero necesitas verificar que:
1. El build se complete correctamente
2. Chrome esté disponible en el PATH
3. Los permisos sean correctos

### Para Local (desarrollo):

Usa el script `test_with_railway.py` que creé, que:
1. Usa los CSVs que YA descargaste
2. Los carga directamente a Railway
3. No necesita Selenium

## 📊 Estructura de los Datos:

### Customers CSV:
```csv
"First name","Last name",Email,PHONE,"LAST APPOINTMENT","Date of birth",Note
sacha,damjanic,sachadamjanic@hotmail.com,+56977577313,-,-,-
```

Se mapea a:
```python
{
    "id": "hash_del_email",
    "name": "sacha damjanic",
    "email": "sachadamjanic@hotmail.com",
    "phone": "+56977577313",
    "status": "active",
    "created_at": "2025-10-24 23:16:40"
}
```

### Appointments CSV:
```csv
ID,"START DATE",Customer,Service,"Customer Email",...
56,"31/08/2024 13:00","Camila Rivas",,"camirivasc137@gmail.com",...
```

Se mapea a:
```python
{
    "id": 56,
    "customer_name": "Camila Rivas",
    "customer_email": "camirivasc137@gmail.com",
    "service_name": "HotBoat Trip 2 people (69.990 pp)",
    "starts_at": "2024-08-31 13:00:00",
    ...
}
```

## 🎯 Siguiente Paso:

1. **Ejecuta el diagnóstico en Railway** para ver si Selenium funciona allí:
   ```bash
   railway run python diagnose_booknetic.py
   ```

2. **O carga los datos manualmente** usando los CSVs que ya tienes:
   ```bash
   python test_with_railway.py
   ```

## ❓ Preguntas Frecuentes:

### ¿Por qué los datos no se actualizan en PostgreSQL?

Porque `DATABASE_URL` no está configurado localmente. Sin esta variable, el código no puede conectarse a PostgreSQL.

### ¿Los CSVs se están descargando?

SÍ, perfectamente. Tienes 19 archivos CSV en `downloads/` con datos reales.

### ¿El problema está en Selenium?

NO, Selenium funciona bien localmente. El problema es que los datos descargados no se cargan a PostgreSQL.

### ¿Cómo verifico que funcionó?

Después de cargar los datos, ejecuta:
```bash
python check_database.py
```

Deberías ver:
```
✅ booknetic_customers - 293 registros
✅ booknetic_appointments - 181 registros
✅ booknetic_payments - 181 registros
```

## 🚀 Resumen de Acciones:

1. ✅ Ya tienes los CSVs descargados
2. ⏭️ Ejecuta `python test_with_railway.py` para cargarlos a PostgreSQL
3. ⏭️ Verifica con `python check_database.py`
4. ⏭️ Si funciona, configura Railway para que funcione automáticamente

¿Quieres que te ayude con alguno de estos pasos?


