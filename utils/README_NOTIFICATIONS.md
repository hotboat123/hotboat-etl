# 🔔 Sistema de Notificaciones

Sistema de alertas automáticas para errores críticos en el ETL de HotBoat.

## 📋 Características

- ✅ Notificaciones automáticas cuando fallan los jobs
- ✅ Alertas específicas para errores de Chrome/Selenium
- ✅ Tracking de fallos consecutivos
- ✅ Notificación de recuperación después de fallos
- ✅ Guardado de notificaciones en base de datos
- ✅ Soporte para webhooks (Discord, Slack, etc.)
- ✅ Soporte opcional para notificaciones vía email (SMTP)

## 🚀 Uso Básico

El sistema de notificaciones se ejecuta automáticamente. No requiere configuración adicional para logging en consola y base de datos.

## 🔧 Configuración de Webhooks (Opcional)

Para recibir notificaciones en Discord, Slack u otro servicio:

### Discord

1. Crea un Webhook en tu servidor de Discord:
   - Settings → Integrations → Webhooks → New Webhook
   - Copia la URL del webhook

2. Agrega la variable de entorno en Railway:
   ```
   NOTIFICATION_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_URL
   ```

### Slack

1. Crea un Incoming Webhook en Slack:
   - https://api.slack.com/messaging/webhooks
   - Copia la URL del webhook

2. Agrega la variable de entorno en Railway:
   ```
   NOTIFICATION_WEBHOOK_URL=https://hooks.slack.com/services/YOUR_WEBHOOK_URL
   ```

## ✉️ Configuración de Email (Opcional)

Para recibir alertas por correo configura las siguientes variables en Railway (o en tu `.env`):

```
NOTIFICATION_EMAIL_HOST=smtp.gmail.com
NOTIFICATION_EMAIL_PORT=587                # Opcional (por defecto 587)
NOTIFICATION_EMAIL_USERNAME=tu_usuario     # Opcional si el servidor no requiere auth
NOTIFICATION_EMAIL_PASSWORD=tu_password    # Opcional
NOTIFICATION_EMAIL_FROM=alertas@hotboat.com
NOTIFICATION_EMAIL_TO=admin@hotboat.com,soporte@hotboat.com
NOTIFICATION_EMAIL_USE_TLS=true            # true por defecto (usar false si el servidor no soporta TLS)
NOTIFICATION_EMAIL_USE_SSL=false           # true para SMTPS (por ejemplo puerto 465)
NOTIFICATION_EMAIL_SUBJECT_PREFIX=[HotBoat ETL]
```

Con que existan `NOTIFICATION_EMAIL_HOST`, `NOTIFICATION_EMAIL_FROM` y `NOTIFICATION_EMAIL_TO`, el sistema intentará enviar correos. El mensaje incluye todo el detalle del error (igual que en los logs/webhook).

## 📊 Tipos de Notificaciones

### 1. Error de Chrome/Selenium
Se envía cuando Chrome/Chromium falla al iniciarse:
```
🚨 ERROR DE CHROME/SELENIUM EN RAILWAY
- Incluye stack trace completo
- Sugerencias de solución
- Se guarda en la base de datos
```

### 2. Fallo de Job
Se envía cuando un job falla:
```
❌ FALLO EN JOB: booknetic_scrape
- Detalles del error
- Timestamp
- Se guarda en la base de datos
```

### 3. Recuperación
Se envía cuando un job se recupera después de 3+ fallos consecutivos:
```
✅ JOB RECUPERADO: booknetic_scrape
- Número de intentos que fallaron
- Confirmación de vuelta a la normalidad
```

## 🗄️ Base de Datos

Las notificaciones se guardan en la tabla `notifications`:

```sql
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    level TEXT NOT NULL,  -- info, warning, error, critical
    error_details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Consultar notificaciones recientes:

```sql
-- Ver últimas 10 notificaciones
SELECT * FROM notifications 
ORDER BY created_at DESC 
LIMIT 10;

-- Ver solo errores críticos
SELECT * FROM notifications 
WHERE level = 'critical'
ORDER BY created_at DESC;

-- Ver errores de las últimas 24 horas
SELECT * FROM notifications 
WHERE created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC;
```

## 📝 Ejemplos de Uso Programático

### Enviar notificación personalizada:

```python
from utils.notifications import send_notification

send_notification(
    title="Advertencia Personalizada",
    message="Algo importante sucedió",
    level="warning"
)
```

### Notificar error con excepción:

```python
from utils.notifications import send_notification

try:
    # tu código aquí
    risky_operation()
except Exception as e:
    send_notification(
        title="Error en operación riesgosa",
        message="Detalles adicionales aquí",
        error=e,
        level="error"
    )
```

## 🎯 Estado de Salud

El runner muestra el estado de salud en los logs:

```
💤 Esperando... Próxima ejecución de Booknetic: 18:45:00 ✅
💤 Esperando... Próxima ejecución de Booknetic: 18:50:00 ⚠️(2 fallos)
```

## 🔍 Troubleshooting

### No recibo notificaciones en Discord/Slack

1. Verifica que `NOTIFICATION_WEBHOOK_URL` esté configurado correctamente
2. Verifica que la URL del webhook sea válida
3. Revisa los logs para ver si hay errores al enviar

### Las notificaciones no se guardan en la base de datos

1. Verifica que la conexión a la base de datos funcione
2. La tabla `notifications` se crea automáticamente
3. Si falla, revisa los permisos de la base de datos

## 📚 Funciones Disponibles

```python
# notifications.py

send_notification(title, message, error=None, level="error")
# Envía notificación genérica

notify_chrome_error(error)
# Notificación específica para errores de Chrome

notify_job_failure(job_name, error)
# Notificación de fallo de job

notify_success_after_failure(job_name, attempts)
# Notificación de recuperación
```

## 🛠️ Mejoras Futuras

- [ ] Integración con Telegram
- [ ] Dashboard web para ver notificaciones
- [ ] Agregación de notificaciones (evitar spam)
- [ ] Configuración de umbrales personalizados

