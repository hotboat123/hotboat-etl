# 🚂 Cambios Realizados para Railway

## ✅ **Resumen de Cambios**

Se actualizó el código para que funcione correctamente en Railway y descargue + cargue los datos a PostgreSQL automáticamente.

## 🔧 **Archivos Modificados**

### 1. **`jobs/booknetic_export_improved.py`**
   - ✅ **Verificación de descargas**: Ahora verifica que los archivos realmente se descarguen antes de continuar
   - ✅ **Selector correcto del botón**: Usa `button.export_csv` que es el selector real
   - ✅ **Modo headless para Railway**: Detecta automáticamente si está en Railway y activa headless
   - ✅ **Tiempos de espera aumentados**: 20 segundos para esperar descargas (especialmente importante en headless)

### 2. **`plugins/booknetic_full_export.py`**
   - ✅ **Mensajes mejorados**: Ahora muestra qué archivo está usando de cada tipo
   - ✅ **Verificación de éxito**: Muestra si cada descarga fue exitosa
   - ✅ **Espera aumentada**: 5 segundos adicionales para que terminen todas las descargas
   - ✅ **Mejor logging**: Muestra la ruta exacta donde busca los archivos

## 🚀 **Cómo Funciona en Railway**

### Flujo Completo:

```
1. Railway ejecuta jobs/runner.py cada 15 minutos
   ↓
2. runner.py llama a jobs/job_scrape_booknetic.py
   ↓
3. job_scrape_booknetic.py usa el plugin: plugins.booknetic_full_export
   ↓
4. booknetic_full_export.py:
   - Configura Chrome en modo headless
   - Hace login en WordPress
   - Descarga 3 CSVs (customers, appointments, payments)
   - Verifica que cada descarga fue exitosa
   - Parsea los CSVs más recientes
   - Retorna los datos parseados
   ↓
5. job_scrape_booknetic.py:
   - Recibe los datos parseados
   - Usa db.utils.replace_all() para cargar a PostgreSQL
   - Reemplaza completamente las tablas (TRUNCATE + INSERT)
```

## 📋 **Variables de Entorno Necesarias en Railway**

Asegúrate de tener estas variables configuradas en Railway:

```bash
# Booknetic
BOOKNETIC_USERNAME=hotboatvillarrica@gmail.com
BOOKNETIC_PASSWORD=Hotboat777
BOOKNETIC_PLUGIN_MODULE=plugins.booknetic_full_export

# PostgreSQL (de Railway)
DATABASE_URL=<tu_database_url_de_railway>

# Railway automáticamente establece:
RAILWAY_ENVIRONMENT=true  # Esto activa modo headless
```

## 🔍 **Verificación de Descargas**

El código ahora **verifica activamente** que los archivos se descarguen:

```python
# Después de hacer click en el botón:
- Monitorea la carpeta downloads/ durante 20 segundos
- Busca archivos nuevos que coincidan con el patrón (customers*.csv, etc.)
- Verifica que el archivo sea realmente nuevo (tiempo de creación)
- Retorna True/False dependiendo si encontró el archivo
```

Si la descarga falla:
- ⚠️ Muestra advertencia pero continúa
- 🔍 Busca el archivo más reciente disponible
- ✅ Usa el archivo más reciente encontrado

## ⚙️ **Modo Headless en Railway**

El código detecta automáticamente Railway:

```python
is_railway = os.getenv("RAILWAY_ENVIRONMENT") or os.path.exists("/usr/bin/chromium")
```

Si detecta Railway:
- ✅ Activa modo headless automáticamente
- ✅ Usa Chromium instalado en el sistema
- ✅ Configura descargas correctamente

## 📊 **Logs en Railway**

Cuando funciona correctamente, deberías ver en los logs:

```
[booknetic_full_export] Iniciando exportación completa...
⚙️ Inicializando Chrome driver...
🐳 Detectado entorno Railway/Docker - usando Chromium
✅ Chrome driver inicializado correctamente
🔐 Haciendo login...
✅ Navegación a Booknetic exitosa
[booknetic_full_export] Exportando customers...
✅ Botón encontrado con selector: button.export_csv
✅ Archivo descargado: customers_2025Nov02.csv
   Ruta: /app/downloads/customers_2025Nov02.csv
[booknetic_full_export] ✅ Customers descargado correctamente
... (mismo proceso para appointments y payments)
[booknetic_full_export] Total exportado: 293 customers, 181 appointments, 181 payments
[booknetic] Replacing booknetic_customers table...
[booknetic] 293 customers replaced
[booknetic] Replacing booknetic_appointments table...
[booknetic] 181 appointments replaced
[booknetic] Replacing booknetic_payments table...
[booknetic] 181 payments replaced
```

## 🐛 **Solución de Problemas**

### Problema: No se descargan archivos

**Síntoma**: Los logs dicen que se hizo click pero no hay archivos nuevos

**Posibles causas**:
1. Chrome en headless no permite descargas (poco probable con la configuración actual)
2. Los archivos se descargan muy lento (>20 segundos)
3. Los archivos tienen un nombre diferente al esperado

**Solución**:
- Revisa los logs para ver qué archivo encuentra
- Aumenta el timeout en la línea 324 de `booknetic_export_improved.py` si es necesario
- Verifica que el directorio `downloads/` tenga permisos de escritura

### Problema: PostgreSQL no se actualiza

**Síntoma**: Los CSVs se descargan pero la base de datos no cambia

**Causa**: `DATABASE_URL` no está configurado o es incorrecto

**Solución**:
- Verifica que `DATABASE_URL` esté en Railway
- Ejecuta `python check_database.py` localmente para probar la conexión
- Revisa los logs de Railway para ver errores de conexión

### Problema: Chrome no inicia en Railway

**Síntoma**: Error "ChromeDriver not found" o "Chrome binary not found"

**Causa**: Chromium no está instalado correctamente

**Solución**:
- Verifica que el `Dockerfile` instale Chromium correctamente
- Revisa los logs del build en Railway
- Asegúrate de que el PATH incluya `/usr/bin/chromium`

## ✅ **Checklist para Railway**

Antes de hacer deploy, verifica:

- [ ] Variables de entorno configuradas:
  - [ ] `BOOKNETIC_USERNAME`
  - [ ] `BOOKNETIC_PASSWORD`
  - [ ] `BOOKNETIC_PLUGIN_MODULE=plugins.booknetic_full_export`
  - [ ] `DATABASE_URL` (Railway lo configura automáticamente)
- [ ] Dockerfile incluye Chromium (ya debería estar)
- [ ] El job está configurado para ejecutarse cada 15 minutos (en `jobs/runner.py`)
- [ ] Los logs muestran que se ejecuta correctamente

## 🎯 **Próximos Pasos**

1. **Hacer deploy a Railway**
   ```bash
   git add .
   git commit -m "Fix: Mejora descarga y carga de Booknetic para Railway"
   git push
   ```

2. **Monitorear logs en Railway**
   ```bash
   railway logs
   ```

3. **Verificar que funciona**
   ```bash
   # Ver los logs más recientes
   railway logs | grep booknetic | tail -20
   
   # Verificar la base de datos
   railway run python check_database.py
   ```

4. **Esperar el próximo ciclo** (15 minutos) y verificar que se actualizó

## 📝 **Resumen Técnico**

**Mejoras principales**:
1. ✅ Verificación activa de descargas (no solo espera pasiva)
2. ✅ Selector correcto del botón (`button.export_csv`)
3. ✅ Detección automática de Railway para modo headless
4. ✅ Mejor logging y mensajes de error
5. ✅ Uso de archivos más recientes si hay múltiples versiones

**Compatible con**:
- ✅ Railway (modo headless)
- ✅ Local (modo visible para debugging)
- ✅ Docker
- ✅ Windows/Mac/Linux

¡El sistema ahora debería funcionar correctamente en Railway! 🎉

