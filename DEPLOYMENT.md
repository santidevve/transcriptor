# Despliegue de producción

La aplicación tiene dos servicios: React/Vite en Vercel y Django/Whisper en Render. El servicio de transcripción necesita memoria y procesamiento persistente, por lo que no se ejecuta en funciones serverless de Vercel.

## API en Render

1. En Render, crea un **Blueprint** desde este repositorio y selecciona la rama `feature/transcription-and-document-download`.
2. Render leerá [`render.yaml`](./render.yaml) para crear el servicio Django, PostgreSQL y el disco persistente para la caché del modelo Whisper.
3. En el servicio web, añade `CORS_ALLOWED_ORIGINS` con el origen exacto del sitio de Vercel (por ejemplo, `https://transcriptor-movil.vercel.app`, sin barra final).
4. Espera a que termine el despliegue y verifica `https://<servicio>.onrender.com/api/saludo/`.

El plan `standard`, el disco persistente y PostgreSQL son recursos de pago de Render; revisa el costo mostrado por Render antes de confirmar la creación. El tamaño de la instancia permite mantener el modelo Whisper en memoria y el disco lo conserva entre reinicios. PostgreSQL almacena los datos y sesiones de Django.

## Sitio web en Vercel

1. Importa `santidevve/transcriptor` en Vercel.
2. Configura **Root Directory** como `frontend`, Framework Preset `Vite`, Build Command `npm run build` y Output Directory `dist`.
3. Define la variable de entorno `VITE_API_URL` para Production y Preview con el origen Render, por ejemplo `https://<servicio>.onrender.com` (sin barra final).
4. Despliega y prueba una transcripción real desde el sitio publicado.

La URL de la API se lee durante el build del frontend. Si cambia, actualiza `VITE_API_URL` y vuelve a desplegar. Para desarrollo local, déjala sin definir: Vite usa el proxy de `frontend/vite.config.js`.

## Variables de entorno de Render

El Blueprint genera `DJANGO_SECRET_KEY`, define `DJANGO_DEBUG=False`, conecta `DATABASE_URL` y almacena la caché de Hugging Face en el disco persistente. `RENDER_EXTERNAL_HOSTNAME` se incluye automáticamente en los hosts permitidos. Configura manualmente `CORS_ALLOWED_ORIGINS` después de conocer el dominio final de Vercel.
