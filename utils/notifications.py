"""
Sistema de notificaciones para errores críticos del ETL
"""
import os
import json
import traceback
from datetime import datetime
from typing import Optional
import smtplib
import ssl
from email.message import EmailMessage
import requests


def send_notification(
    title: str,
    message: str,
    error: Optional[Exception] = None,
    level: str = "error"
) -> None:
    """
    Envía notificación de error/alerta
    
    Args:
        title: Título del mensaje
        message: Mensaje descriptivo
        error: Excepción opcional para incluir detalles
        level: Nivel de severidad (info, warning, error, critical)
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Construir mensaje completo
    full_message = f"""
{'='*60}
🚨 {title.upper()}
{'='*60}
⏰ Timestamp: {timestamp}
📊 Nivel: {level.upper()}

📝 Descripción:
{message}
"""
    
    if error:
        full_message += f"""
❌ Error:
{type(error).__name__}: {str(error)}

📋 Stack Trace:
{traceback.format_exc()}
"""
    
    full_message += f"\n{'='*60}\n"
    
    # 1. Imprimir a consola/logs (siempre)
    print(full_message)
    
    # 2. Enviar a webhook si está configurado (Discord, Slack, etc.)
    webhook_url = os.getenv("NOTIFICATION_WEBHOOK_URL")
    if webhook_url:
        try:
            _send_to_webhook(webhook_url, title, full_message, level)
        except Exception as e:
            print(f"⚠️ No se pudo enviar notificación a webhook: {e}")
    
    # 3. Enviar correo si hay configuración
    try:
        _send_email_notification(title, full_message, level)
    except Exception as e:
        print(f"⚠️ No se pudo enviar notificación por email: {e}")
    
    # 4. Guardar en base de datos (si está disponible)
    try:
        _save_to_database(title, message, error, level)
    except Exception as e:
        print(f"⚠️ No se pudo guardar notificación en DB: {e}")


def _send_to_webhook(webhook_url: str, title: str, message: str, level: str) -> None:
    """Envía notificación a webhook (Discord/Slack compatible)"""
    
    # Color según nivel
    colors = {
        "info": 3447003,      # Azul
        "warning": 16776960,  # Amarillo
        "error": 15158332,    # Rojo
        "critical": 10038562  # Rojo oscuro
    }
    
    # Emoji según nivel
    emojis = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "❌",
        "critical": "🚨"
    }
    
    # Formato para Discord
    if "discord" in webhook_url.lower():
        payload = {
            "embeds": [{
                "title": f"{emojis.get(level, '❌')} {title}",
                "description": message[:2000],  # Discord limit
                "color": colors.get(level, 15158332),
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {
                    "text": "HotBoat ETL - Railway"
                }
            }]
        }
    # Formato para Slack
    elif "slack" in webhook_url.lower():
        payload = {
            "text": f"{emojis.get(level, '❌')} *{title}*",
            "attachments": [{
                "text": message[:3000],
                "color": "danger" if level in ["error", "critical"] else "warning",
                "ts": int(datetime.now().timestamp())
            }]
        }
    # Formato genérico
    else:
        payload = {
            "title": title,
            "message": message,
            "level": level,
            "timestamp": datetime.now().isoformat()
        }
    
    response = requests.post(
        webhook_url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=10
    )
    response.raise_for_status()
    print(f"✅ Notificación enviada a webhook")


def _send_email_notification(title: str, message: str, level: str) -> None:
    """Envía notificación por email si la configuración está disponible."""
    host = os.getenv("NOTIFICATION_EMAIL_HOST")
    sender = os.getenv("NOTIFICATION_EMAIL_FROM")
    recipients_raw = os.getenv("NOTIFICATION_EMAIL_TO")
    if not host or not sender or not recipients_raw:
        return

    recipients = [addr.strip() for addr in recipients_raw.replace(";", ",").split(",") if addr.strip()]
    if not recipients:
        return

    subject_prefix = os.getenv("NOTIFICATION_EMAIL_SUBJECT_PREFIX", "[HotBoat ETL]")
    subject = f"{subject_prefix} {title}".strip()
    port = int(os.getenv("NOTIFICATION_EMAIL_PORT", "587"))
    username = os.getenv("NOTIFICATION_EMAIL_USERNAME")
    password = os.getenv("NOTIFICATION_EMAIL_PASSWORD")
    use_ssl = os.getenv("NOTIFICATION_EMAIL_USE_SSL", "false").lower() in {"1", "true", "yes", "on"}
    use_tls = os.getenv("NOTIFICATION_EMAIL_USE_TLS", "true").lower() in {"1", "true", "yes", "on"}

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["X-Priority"] = "1" if level in {"critical", "error"} else "3"
    msg.set_content(message)

    context = ssl.create_default_context()
    if use_ssl:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=15) as server:
            if username and password:
                server.login(username, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=15) as server:
            if use_tls:
                server.starttls(context=context)
            if username and password:
                server.login(username, password)
            server.send_message(msg)
    print("✅ Notificación enviada por email")


def _save_to_database(
    title: str,
    message: str,
    error: Optional[Exception],
    level: str
) -> None:
    """Guarda notificación en la base de datos"""
    try:
        from db.utils import get_connection
        
        error_details = None
        if error:
            error_details = {
                "type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc()
            }
        
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS notifications (
                        id SERIAL PRIMARY KEY,
                        title TEXT NOT NULL,
                        message TEXT NOT NULL,
                        level TEXT NOT NULL,
                        error_details JSONB,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                
                cur.execute("""
                    INSERT INTO notifications (title, message, level, error_details)
                    VALUES (%s, %s, %s, %s)
                """, (title, message, level, json.dumps(error_details) if error_details else None))
            
            conn.commit()
    except Exception:
        # Si falla, no hacer nada para no interrumpir el flujo
        pass


def notify_chrome_error(error: Exception) -> None:
    """Notificación específica para errores de Chrome/Selenium"""
    send_notification(
        title="Error de Chrome/Selenium en Railway",
        message="""
El proceso de Booknetic falló al iniciar Chrome/Chromium.

🔍 Posibles causas:
- Chrome/Chromium no está instalado correctamente en Railway
- Faltan dependencias del sistema
- Problema con chromedriver
- Memoria insuficiente

🛠️ Acciones recomendadas:
1. Verificar que nixpacks.toml incluya chromium y chromedriver
2. Revisar logs de Railway para ver errores del sistema
3. Verificar memoria disponible en Railway
4. Considerar reiniciar el servicio

💡 El sistema reintentará en el próximo ciclo programado.
        """.strip(),
        error=error,
        level="critical"
    )


def notify_job_failure(job_name: str, error: Exception) -> None:
    """Notificación genérica para fallo de job"""
    send_notification(
        title=f"Fallo en Job: {job_name}",
        message=f"""
El job '{job_name}' ha fallado durante su ejecución.

El sistema continuará intentando en el próximo ciclo programado.
        """.strip(),
        error=error,
        level="error"
    )


def notify_success_after_failure(job_name: str, attempts: int) -> None:
    """Notificación cuando un job se recupera después de fallos"""
    send_notification(
        title=f"✅ Job Recuperado: {job_name}",
        message=f"""
El job '{job_name}' se ha ejecutado exitosamente después de {attempts} intentos fallidos.

El sistema ha vuelto a la normalidad.
        """.strip(),
        level="info"
    )

