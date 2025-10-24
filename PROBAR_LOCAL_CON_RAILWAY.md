# 🧪 Probar Localmente con Base de Datos de Railway

Esta guía te permite probar el ETL completo desde tu máquina local, pero usando la base de datos de Railway. Así pruebas exactamente lo mismo que correrá en producción.

---

## 📋 Paso 1: Obtener DATABASE_URL de Railway

1. Ve a tu proyecto en [Railway](https://railway.app/)
2. Click en el servicio **PostgreSQL** (el ícono de base de datos)
3. Ve a la pestaña **"Variables"** o **"Connect"**
4. Busca y **copia** el valor de `DATABASE_URL`

Debería verse así:
```
postgresql://postgres:XXXXXXXXXXXX@monorail.proxy.rlwy.net:12345/railway
```

---

## 📋 Paso 2: Verificar la Base de Datos

Edita el archivo `check_database.py` y pega tu `DATABASE_URL`:

```python
# Línea 8 del archivo check_database.py
DATABASE_URL = "postgresql://postgres:XXXX@monorail.proxy.rlwy.net:12345/railway"
```

Luego ejecuta:

```bash
python check_database.py
```

**Deberías ver:**
```
✅ Conectado a PostgreSQL
✅ booknetic_customers - 0 registros
✅ booknetic_appointments - 0 registros
✅ booknetic_payments - 0 registros
✅ job_runs - 0 registros
✅ TODAS LAS TABLAS ESTÁN CONFIGURADAS CORRECTAMENTE
```

### ⚠️ Si Faltan Tablas

Si el script dice que faltan tablas, necesitas ejecutar el schema SQL.

**Opción A: Desde Railway Web (Más fácil)**
1. Ve a Railway → PostgreSQL → **"Data"** o **"Query"**
2. Abre `sql/schema.sql` en tu editor
3. Copia TODO el contenido
4. Pégalo en el query editor de Railway
5. Ejecuta
6. Repite con `sql/job_meta.sql`

**Opción B: Desde Terminal (requiere psql instalado)**
```bash
psql "tu-database-url-aqui" -f sql/schema.sql
psql "tu-database-url-aqui" -f sql/job_meta.sql
```

---

## 📋 Paso 3: Configurar el Test

Edita el archivo `test_with_railway_db.py` y pega tu `DATABASE_URL`:

```python
# Línea 13 del archivo test_with_railway_db.py
DATABASE_URL = "postgresql://postgres:XXXX@monorail.proxy.rlwy.net:12345/railway"
```

---

## 📋 Paso 4: Ejecutar el Test Completo

```bash
python test_with_railway_db.py
```

**Esto hará:**
1. ✅ Login a WordPress con Selenium
2. ✅ Exportar customers → `downloads/customers_YYYY-MM-DD.csv`
3. ✅ Exportar appointments → `downloads/appointments_YYYY-MM-DD.csv`
4. ✅ Exportar payments → `downloads/payments_YYYY-MM-DD.csv`
5. ✅ Leer los CSV
6. ✅ Cargar datos a PostgreSQL de Railway
7. ✅ Mostrar resumen

**Resultado esperado:**
```
============================================================
📊 RESUMEN DE EXPORTACIÓN CSV
============================================================
✅ Exportaciones exitosas: 3/3
❌ Exportaciones fallidas: 0/3

============================================================
📤 Cargando datos a PostgreSQL...
============================================================
✅ Parsed 156 rows from customers_2025Oct24.csv
✅ 156 customers insertados/actualizados

✅ Parsed 423 rows from appointments_2025Oct24.csv
✅ 423 appointments insertados/actualizados

✅ Parsed 267 rows from payments_2025Oct24.csv
✅ 267 payments insertados/actualizados

============================================================
📊 RESUMEN FINAL
============================================================
📥 CSV Exportados: 3/3
💾 Customers en DB: 156
💾 Appointments en DB: 423
💾 Payments en DB: 267
💾 Total registros en DB: 846
============================================================

🎉 ¡Proceso completado exitosamente!
```

---

## 📋 Paso 5: Verificar los Datos en Railway

### Opción A: Desde Railway Web Console

1. Ve a Railway → PostgreSQL → **"Data"** o **"Query"**
2. Ejecuta estas consultas:

```sql
-- Ver conteo total
SELECT 'customers' as tabla, COUNT(*) as total FROM booknetic_customers
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

-- Ver últimos clientes
SELECT 
  name,
  email,
  phone,
  status
FROM booknetic_customers
ORDER BY created_at DESC
LIMIT 10;
```

### Opción B: Volver a ejecutar check_database.py

```bash
python check_database.py
```

Ahora debería mostrar los registros:
```
✅ booknetic_customers - 156 registros
✅ booknetic_appointments - 423 registros
✅ booknetic_payments - 267 registros
```

---

## 🎯 Resumen de Scripts

| Script | Para qué sirve |
|--------|----------------|
| `test_booknetic_local.py` | ✅ Test SIN DB (solo descarga CSV) |
| `check_database.py` | 🔍 Verifica conexión y tablas de Railway |
| `test_with_railway_db.py` | 🚀 Test COMPLETO con carga a Railway |

---

## ⚠️ Troubleshooting

### Error: "Could not connect to server"
**Solución:** Verifica que el DATABASE_URL sea correcto y que tengas internet

### Error: "relation does not exist"
**Solución:** Las tablas no están creadas. Ejecuta `sql/schema.sql` en Railway

### Error: "Login falló"
**Solución:** Verifica las credenciales de WordPress en el script

### Los datos se duplican
**Solución:** El sistema usa UPSERT, no debería duplicar. Verifica que los IDs sean consistentes.

---

## 🎉 ¡Todo Listo!

Si el test funcionó, significa que:
- ✅ Tu código funciona correctamente
- ✅ Se pueden exportar los CSV
- ✅ Se pueden cargar a PostgreSQL
- ✅ Railway ejecutará lo mismo automáticamente cada 15 minutos

Para ver los logs en Railway:
1. Ve a tu proyecto en Railway
2. Click en tu servicio web
3. Ve a la pestaña **"Logs"**
4. Deberías ver el mismo output cada 15 minutos

---

## 📚 Próximos Pasos

- **Monitorear Railway**: Revisa los logs para ver las ejecuciones automáticas
- **Consultar datos**: Usa las queries SQL para analizar los datos
- **Ajustar frecuencia**: Edita `jobs/runner.py` si quieres cambiar el intervalo

¡Tu ETL está funcionando perfectamente! 🚀

