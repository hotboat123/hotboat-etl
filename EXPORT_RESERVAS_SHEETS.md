# Export Reservas_Con_Extras_Sheets a Google Sheets

## Descripción

Este módulo exporta automáticamente la tabla `Reservas_Con_Extras_Sheets` desde PostgreSQL a Google Sheets cada 15 minutos, permitiendo su análisis en tiempo real con Looker u otras herramientas de BI.

## Archivos

- `jobs/export_reservas_to_sheets.py`: Script principal de exportación
- `jobs/runner.py`: Runner actualizado que ejecuta la exportación cada 15 minutos

## Configuración

### Variables de Entorno

Las siguientes variables de entorno deben estar configuradas:

```bash
# Conexión a PostgreSQL (ya configuradas)
DATABASE_URL=postgresql://...

# Google Sheets (ya configuradas)
GOOGLE_SA_JSON_BASE64=<base64_encoded_service_account_json>
SHEETS_SPREADSHEET_ID=<tu_spreadsheet_id>

# Nueva variable opcional para el nombre de la hoja destino
SHEETS_EXPORT_WORKSHEET_NAME=Reservas_Con_Extras_Sheets  # Por defecto

# Intervalo de exportación (en segundos)
EXPORT_RESERVAS_INTERVAL=900  # 15 minutos por defecto
```

### Cómo Funciona

1. **Lectura de Datos**: El script lee toda la tabla `Reservas_Con_Extras_Sheets` desde PostgreSQL
2. **Transformación**: Aplana el campo JSON `raw` en columnas individuales
3. **Exportación**: Escribe los datos en Google Sheets, reemplazando el contenido anterior
4. **Formato**: Aplica formato a los headers (negrita, fondo gris) y congela la primera fila

### Estructura de Datos Exportados

La hoja de Google Sheets contendrá las siguientes columnas (ordenadas por prioridad):

**Campos Prioritarios:**
- `_db_id`: ID interno de la base de datos
- `id`: ID del registro
- `reservation_id`: ID único de la reserva
- `appointment_id`: ID del appointment
- `fecha`, `hora`: Fecha y hora de la reserva
- `nombre_cliente`, `email`, `telefono`: Datos del cliente
- `servicio`: Nombre del servicio
- `num_adultos`, `num_ninos`, `num_personas`: Cantidad de personas
- `ingreso_total`, `ingreso_reserva`, `ingreso_extras`: Ingresos
- `costo_operativo_total`, `costo_operativo_fijo`, `costo_operativo_variable`: Costos
- `status`, `ciudad_origen`, `como_supieron`, `tipo_clientes`, `categoria_clientes`
- `clima_del_dia`, `tiene_cruce`
- `extras_json`: JSON con los extras de la reserva
- `_source`, `_created_at`, `_updated_at`: Metadatos

**Campos adicionales:**
- Cualquier otro campo presente en el JSON se agregará alfabéticamente

### Ejecución Manual

Para ejecutar la exportación manualmente:

```bash
python jobs/export_reservas_to_sheets.py
```

### Ejecución Automática con Runner

El runner ejecuta automáticamente la exportación cada 15 minutos:

```bash
python jobs/runner.py
```

El runner mostrará en los logs:
```
⚙️ Configuración:
   - Booknetic: cada 30 minutos
   - Sheets: cada 10 minutos
   - Export Reservas: cada 15 minutos
```

## Integración con Looker

Una vez que los datos están en Google Sheets:

1. **Conectar Looker a Google Sheets**: 
   - En Looker, ve a Admin > Connections
   - Crea una nueva conexión de tipo "Google Sheets"
   - Autoriza con la cuenta que tiene acceso al spreadsheet

2. **Crear una Vista/Explore**:
   - Usa el spreadsheet ID: `1K8ndJSfQ_sxVwNyIio8GL9WwMtwIX2x9mCJdGGiAlsA`
   - Selecciona la hoja: `Reservas_Con_Extras_Sheets`

3. **Actualización Automática**:
   - Los datos se actualizan cada 15 minutos automáticamente
   - Looker puede configurarse para refrescar el cache en intervalos similares

## Troubleshooting

### Error: "No module named 'db'"
Asegúrate de ejecutar el script desde la raíz del proyecto o que el path esté correctamente configurado.

### Error: "GOOGLE_SA_JSON_BASE64 no está definido"
Verifica que las credenciales de Google estén configuradas en el archivo `.env`.

### Error: "Hoja no encontrada"
El script crea automáticamente la hoja si no existe. Si aparece este error repetidamente, verifica los permisos de la cuenta de servicio.

### Los datos no se actualizan
- Verifica que el runner esté ejecutándose
- Revisa los logs para ver errores
- Verifica la conexión a la base de datos

## Monitoreo

El sistema incluye tracking de fallos consecutivos:
- Si hay 3 o más fallos consecutivos, se envía una notificación
- Cuando se recupera después de fallos, se notifica también
- Los logs muestran el estado de salud de cada job

## Ejemplo de Uso en Looker

Una vez conectado a Looker, puedes crear dashboards con:

```lookml
view: reservas_con_extras {
  sql_table_name: `Reservas_Con_Extras_Sheets` ;;
  
  dimension: reservation_id {
    type: string
    sql: ${TABLE}.reservation_id ;;
    primary_key: yes
  }
  
  dimension_group: fecha {
    type: time
    timeframes: [date, week, month, year]
    sql: CAST(${TABLE}.fecha AS TIMESTAMP) ;;
  }
  
  measure: total_ingresos {
    type: sum
    sql: CAST(${TABLE}.ingreso_total AS FLOAT64) ;;
    value_format: "$#,##0.00"
  }
  
  measure: total_costos {
    type: sum
    sql: CAST(${TABLE}.costo_operativo_total AS FLOAT64) ;;
    value_format: "$#,##0.00"
  }
  
  measure: margen {
    type: number
    sql: ${total_ingresos} - ${total_costos} ;;
    value_format: "$#,##0.00"
  }
}
```

## Próximos Pasos

Posibles mejoras futuras:
1. Agregar filtros para exportar solo registros recientes
2. Implementar exportación incremental (solo cambios)
3. Agregar más formatos y estilos a la hoja
4. Crear dashboards pre-configurados en Looker
