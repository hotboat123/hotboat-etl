# Guía Rápida: Exportación Automática de Reservas a Google Sheets

## ✅ ¿Qué se ha implementado?

Se ha creado un sistema que **automáticamente exporta la tabla `Reservas_Con_Extras_Sheets` de PostgreSQL a Google Sheets cada 15 minutos**, permitiendo su análisis en tiempo real con Looker.

## 📊 Resultado

- **Google Sheets URL**: https://docs.google.com/spreadsheets/d/1K8ndJSfQ_sxVwNyIio8GL9WwMtwIX2x9mCJdGGiAlsA
- **Hoja**: `Reservas_Con_Extras_Sheets`
- **Datos**: 50 filas con 30 columnas
- **Actualización**: Cada 15 minutos (configurable)

## 🚀 Cómo Ejecutar

### Opción 1: Ejecución Manual (Una vez)

```bash
python demo_export.py
```

Esto ejecutará la exportación una sola vez para verificar que todo funciona.

### Opción 2: Ejecución Automática Continua (Recomendado)

```bash
python jobs/runner.py
```

Esto iniciará el runner que ejecutará automáticamente:
- **Booknetic scraping**: cada 30 minutos
- **Import desde Google Sheets**: cada 10 minutos
- **Export Reservas a Sheets**: cada 15 minutos ⭐ (NUEVO)

## ⚙️ Configuración

### Variables de Entorno

Ya están configuradas en tu archivo `.env`. Las relevantes son:

```bash
# PostgreSQL (ya configurado)
DATABASE_URL=postgresql://...

# Google Sheets (ya configurado)
GOOGLE_SA_JSON_BASE64=<base64_encoded_service_account_json>
SHEETS_SPREADSHEET_ID=1K8ndJSfQ_sxVwNyIio8GL9WwMtwIX2x9mCJdGGiAlsA

# Intervalo de exportación (OPCIONAL - por defecto 15 minutos)
EXPORT_RESERVAS_INTERVAL=900  # en segundos
```

### Cambiar el Intervalo de Actualización

Si quieres cambiar la frecuencia de actualización:

1. Edita el archivo `.env`
2. Agrega o modifica la variable:
   ```bash
   EXPORT_RESERVAS_INTERVAL=1800  # 30 minutos
   # o
   EXPORT_RESERVAS_INTERVAL=600   # 10 minutos
   ```
3. Reinicia el runner

## 📈 Integración con Looker

### Paso 1: Conectar Google Sheets a Looker

1. En Looker, ve a **Admin > Connections**
2. Crea una nueva conexión de tipo **"Google Sheets"**
3. Autoriza con la cuenta que tiene acceso al spreadsheet
4. Ingresa el Spreadsheet ID: `1K8ndJSfQ_sxVwNyIio8GL9WwMtwIX2x9mCJdGGiAlsA`

### Paso 2: Crear un Explore o Dashboard

1. Selecciona la hoja: **`Reservas_Con_Extras_Sheets`**
2. Looker detectará automáticamente las columnas
3. Crea tus métricas y dimensiones

### Columnas Disponibles

**Información Principal:**
- `reservation_id`, `appointment_id`: IDs únicos
- `fecha`, `hora`: Fecha y hora de la reserva
- `nombre_cliente`, `email`, `telefono`: Datos del cliente
- `servicio`: Nombre del servicio contratado

**Métricas Financieras:**
- `ingreso_total`: Ingreso total de la reserva
- `ingreso_reserva`: Ingreso por el servicio base
- `ingreso_extras`: Ingreso por extras
- `costo_operativo_total`: Costo operativo total
- `costo_operativo_fijo`: Costo fijo
- `costo_operativo_variable`: Costo variable

**Dimensiones de Análisis:**
- `num_adultos`, `num_ninos`, `num_personas`: Composición del grupo
- `tipo_clientes`: Tipo de cliente (Trabajador, Estudiante, etc.)
- `categoria_clientes`: Categoría (Pareja, Familia, etc.)
- `ciudad_origen`: Ciudad de origen del cliente
- `como_supieron`: Canal de adquisición
- `clima_del_dia`: Condición climática
- `tiene_cruce`: Boolean indicando si tiene cruce
- `extras_json`: JSON con detalles de extras contratados

**Metadatos:**
- `_db_id`: ID interno de la base de datos
- `_source`: Origen del registro
- `_created_at`, `_updated_at`: Timestamps de auditoría

## 🔍 Verificación

Para verificar que todo está funcionando:

```bash
# 1. Verificar que los jobs se importan correctamente
python verify_jobs.py

# 2. Ejecutar una exportación de prueba
python demo_export.py

# 3. Verificar en Google Sheets que los datos aparecen
# Abre: https://docs.google.com/spreadsheets/d/1K8ndJSfQ_sxVwNyIio8GL9WwMtwIX2x9mCJdGGiAlsA
```

## 📝 Archivos Creados

1. **`jobs/export_reservas_to_sheets.py`**: Script principal de exportación
2. **`jobs/runner.py`**: Actualizado para incluir el nuevo job
3. **`EXPORT_RESERVAS_SHEETS.md`**: Documentación técnica completa
4. **`GUIA_RAPIDA_EXPORT.md`**: Esta guía (referencia rápida)
5. **`demo_export.py`**: Script de demostración
6. **`verify_jobs.py`**: Script de verificación

## 🛠️ Troubleshooting

### "No hay datos para exportar"
- Verifica que la tabla `Reservas_Con_Extras_Sheets` tenga datos en PostgreSQL
- Ejecuta: `python check_reservas_estructura.py`

### "Error de conexión a Google Sheets"
- Verifica que `GOOGLE_SA_JSON_BASE64` esté correctamente configurado
- Verifica que la cuenta de servicio tenga permisos en el spreadsheet

### "Los datos no se actualizan automáticamente"
- Verifica que el runner esté ejecutándose: `python jobs/runner.py`
- Revisa los logs para detectar errores
- Verifica el intervalo configurado en `EXPORT_RESERVAS_INTERVAL`

### Cambiar el nombre de la hoja destino

Si quieres exportar a una hoja con otro nombre:

```bash
# Agrega a .env
SHEETS_EXPORT_WORKSHEET_NAME=Mi_Hoja_Personalizada
```

## 🎯 Siguiente Paso Recomendado

1. **Ejecutar el runner en modo continuo**:
   ```bash
   python jobs/runner.py
   ```

2. **Configurar Railway** (para producción):
   - El runner ya está configurado para ejecutarse en Railway
   - Solo necesitas hacer deploy y se ejecutará automáticamente

3. **Conectar a Looker** y crear tus dashboards

## 📚 Documentación Adicional

- Ver `EXPORT_RESERVAS_SHEETS.md` para documentación técnica completa
- Ver `README.md` para información general del proyecto

## ✨ Características

✅ Exportación automática cada 15 minutos
✅ Formato automático de headers (negrita, fondo gris)
✅ Primera fila congelada para mejor navegación
✅ Todas las columnas del JSON aplanadas
✅ Metadatos de auditoría incluidos
✅ Compatible con Looker y otras herramientas de BI
✅ Logging detallado para debugging
✅ Manejo de errores robusto
✅ Notificaciones en caso de fallos (configurables)

---

**¿Preguntas?** Revisa la documentación técnica en `EXPORT_RESERVAS_SHEETS.md`
