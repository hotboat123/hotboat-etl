# Configurar Railway para usar otra rama

## Método 1: Dashboard Web (Más Fácil)

1. Ve a https://railway.app
2. Selecciona tu proyecto
3. Click en tu servicio (aplicación web)
4. Settings → Source → Branch
5. Cambia a: `selenium_working_local_but_not_on_railway`
6. Guarda y espera el redeploy automático

## Método 2: Railway CLI (Si tienes CLI instalado)

```bash
# Instalar Railway CLI (si no lo tienes)
npm install -g @railway/cli

# Login
railway login

# Link al proyecto
railway link

# Cambiar la rama de producción
railway environment production
railway service set-branch selenium_working_local_but_not_on_railway
```

## Método 3: Push forzado (Si quieres deploy inmediato)

```bash
# Hacer push de esta rama
git push origin selenium_working_local_but_not_on_railway

# Luego en Railway Dashboard, selecciona esta rama
```

## Verificar que funcionó

1. Ve a Railway Dashboard → Deployments
2. El último deployment debe mostrar: `Branch: selenium_working_local_but_not_on_railway`
3. Revisa los logs para ver que todo corra bien

## Importante

- Railway redesplegará automáticamente cada vez que hagas push a esta rama
- La base de datos PostgreSQL no se ve afectada por el cambio de rama
- Las variables de entorno se mantienen iguales

