# 🔧 Fix: Error de Login en Railway

## ❌ Error Original

```
RuntimeError: Login failed
```

## 🔍 Diagnóstico

El login puede fallar por varias razones en Railway:

### 1. **Credenciales NO configuradas** (más común)

**Verifica en Railway:**
```bash
railway variables
```

Debes tener:
- ✅ `BOOKNETIC_USERNAME` = `hotboatvillarrica@gmail.com`
- ✅ `BOOKNETIC_PASSWORD` = `Hotboat777`

### 2. **El sitio bloquea IPs de Railway**

WordPress/Jetpack puede bloquear IPs desconocidas. Verifica:
- Logs de seguridad de WordPress
- Jetpack Protect puede estar bloqueando

### 3. **CAPTCHA o verificación adicional**

El sitio puede requerir:
- CAPTCHA
- Verificación 2FA
- Email de confirmación

### 4. **Timeout demasiado corto**

En Railway puede ser más lento, ahora el código espera 15 segundos (antes 10).

## ✅ Solución Implementada

### Mejoras en el código:

1. ✅ **Verificación de credenciales** antes de intentar login
2. ✅ **Tiempo de espera aumentado** a 15 segundos
3. ✅ **Múltiples intentos** de verificación (3 intentos)
4. ✅ **Mejor logging** para debug
5. ✅ **Screenshots automáticos** cuando falla (en `/app/downloads/login_failed.png`)

### Código actualizado:

```python
# Verificar credenciales ANTES de login
if not username:
    raise RuntimeError("BOOKNETIC_USERNAME not set")
if not password:
    raise RuntimeError("BOOKNETIC_PASSWORD not set")

# Login con múltiples intentos
for attempt in range(3):
    if 'wp-admin' in current_url:
        return True
    time.sleep(5)
```

## 🚀 Verificación en Railway

### Paso 1: Verificar Variables de Entorno

```bash
railway variables
```

O en Railway Dashboard:
1. Ve a tu proyecto
2. Click en "Variables"
3. Verifica que existan:
   - `BOOKNETIC_USERNAME`
   - `BOOKNETIC_PASSWORD`

### Paso 2: Ver Logs Completos

```bash
railway logs | grep -A 20 "login"
```

Deberías ver:
```
[booknetic_full_export] Usuario configurado: hotboatvillarrica@gmail.com
🚀 Iniciando proceso de login en WordPress...
🌐 Visitando página principal para establecer cookies...
📂 Navegando a la página de login de WordPress...
✍️ Rellenando formulario de WordPress...
✅ Usuario completado
✅ Contraseña completada
🔐 Haciendo login...
⏳ Esperando resultado...
🔍 Intento 1/3 - URL actual: https://hotboatchile.com/wp-login.php
```

### Paso 3: Ver Screenshot de Error

Si el login falla, se guarda un screenshot:
```bash
railway run ls -la /app/downloads/login_failed.png
```

Para descargarlo:
```bash
railway run cat /app/downloads/login_failed.png > login_failed.png
```

## 🔧 Soluciones por Problema

### Problema: Credenciales no configuradas

**Solución:**
```bash
railway variables set BOOKNETIC_USERNAME=hotboatvillarrica@gmail.com
railway variables set BOOKNETIC_PASSWORD=Hotboat777
```

### Problema: IP bloqueada

**Solución:**
1. Ve a WordPress Admin → Jetpack → Seguridad
2. Agrega la IP de Railway a la lista blanca
3. O desactiva temporalmente Jetpack Protect

### Problema: CAPTCHA

**Solución:**
- El código intenta resolver Jetpack Protect automáticamente (9 + 8 = 17)
- Si hay otro CAPTCHA, necesitarás desactivarlo temporalmente

### Problema: Timeout

**Solución:**
- Ya aumentado a 15 segundos
- Si aún falla, puedes aumentar más en la línea 230 de `booknetic_export_improved.py`

## 📊 Logs Esperados (Éxito)

```
[booknetic_full_export] Iniciando exportación completa...
⚙️ Inicializando Chrome driver...
🐳 Detectado entorno Railway/Docker - usando Chromium
✅ Usando chromedriver en: /nix/store/.../bin/chromedriver
✅ Chrome driver inicializado correctamente
[booknetic_full_export] Usuario configurado: hotboatvillarrica@gmail.com
[booknetic_full_export] Intentando login...
🚀 Iniciando proceso de login en WordPress...
🌐 Visitando página principal para establecer cookies...
📂 Navegando a la página de login de WordPress...
✍️ Rellenando formulario de WordPress...
✅ Usuario completado
✅ Contraseña completada
✅ Jetpack Protect está desactivado
🔐 Haciendo login...
⏳ Esperando resultado...
🔍 Intento 1/3 - URL actual: https://hotboatchile.com/wp-admin/
🎉 ¡LOGIN EXITOSO!
✅ Redirigido a: https://hotboatchile.com/wp-admin/
```

## 📊 Logs Esperados (Fallo)

```
[booknetic_full_export] Usuario configurado: hotboatvillarrica@gmail.com
🚀 Iniciando proceso de login en WordPress...
...
❌ Login falló o requiere verificación adicional
📄 URL final: https://hotboatchile.com/wp-login.php?loggedout=true
📄 Título de página: Log In
📸 Captura guardada en: /app/downloads/login_failed.png
⚠️ Mensaje de error: [mensaje del sitio]
```

## ✅ Checklist de Verificación

- [ ] Variables de entorno configuradas en Railway:
  - [ ] `BOOKNETIC_USERNAME`
  - [ ] `BOOKNETIC_PASSWORD`
- [ ] Credenciales son correctas
- [ ] El sitio web está accesible desde Railway
- [ ] No hay bloqueos de IP
- [ ] No hay CAPTCHA adicional
- [ ] Los logs muestran información detallada del error

## 🎯 Próximos Pasos

1. **Hacer commit y push:**
   ```bash
   git add .
   git commit -m "Fix: Mejorar manejo de errores de login en Railway"
   git push
   ```

2. **Monitorear logs:**
   ```bash
   railway logs | grep -i "login\|booknetic"
   ```

3. **Si el error persiste**, revisa:
   - Screenshot guardado en `/app/downloads/login_failed.png`
   - Mensajes de error en los logs
   - Variables de entorno en Railway

## 💡 Debug Avanzado

Si necesitas más información, puedes ejecutar:

```bash
railway run python -c "
import os
print('BOOKNETIC_USERNAME:', os.getenv('BOOKNETIC_USERNAME', 'NOT SET'))
print('BOOKNETIC_PASSWORD:', 'SET' if os.getenv('BOOKNETIC_PASSWORD') else 'NOT SET')
"
```

Esto te dirá si las variables están configuradas correctamente en Railway.

