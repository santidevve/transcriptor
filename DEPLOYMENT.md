# Despliegue gratuito (con límites)

El frontend React/Vite está en Vercel y la API Django/Whisper en una instancia gratuita de Render. Esta opción no tiene costo dentro de los límites gratuitos de ambos proveedores, pero no es adecuada para producción crítica: Render suspende el servicio tras 15 minutos sin tráfico, el arranque en frío puede tardar alrededor de un minuto, el sistema de archivos no es persistente y la transcripción CPU con el modelo `tiny` será más lenta y menos precisa.

## API en Render

1. En Render, crea un **Blueprint** desde este repositorio y selecciona la rama `feature/transcription-and-document-download`.
2. Render leerá [`render.yaml`](./render.yaml) para crear solo el servicio web gratuito: no se crean PostgreSQL ni discos persistentes. Si Render muestra un recurso con costo al revisar el Blueprint, no lo confirmes.
3. Espera a que termine el despliegue y verifica `https://<servicio>.onrender.com/api/saludo/`.

El Blueprint selecciona `WHISPER_MODEL=tiny` para reducir memoria y configura CORS para el dominio de Vercel. El primer uso descarga el modelo y puede tardar; al suspenderse o reiniciarse la instancia, se pierde la caché y podría descargarse de nuevo. La transcripción de videos largos puede exceder los recursos o el tiempo disponible en el plan gratuito.

**Limitación comprobada:** YouTube puede bloquear las descargas desde las IPs de centros de datos con una verificación anti-bot. En ese caso, la API devuelve un error aunque el video sea público. No se garantiza que la transcripción desde YouTube funcione consistentemente en alojamiento gratuito. El formulario permite adjuntar opcionalmente un `cookies.txt` de YouTube; las cookies se copian al directorio temporal de la solicitud y se eliminan al terminar, pero no evitan bloqueos de IP ni garantizan acceso.

Las cookies son credenciales de sesión. El frontend advierte al usuario antes de enviarlas: solo debe exportar cookies de YouTube y no compartir el archivo. La API solo acepta el formato Netscape `.txt` de hasta 1 MB y no las escribe en almacenamiento permanente ni en los logs de aplicación. YouTube puede invalidarlas o limitar la cuenta.

Para transcribir sin depender de YouTube, el sitio permite subir un archivo local de audio o video (MP3, WAV, M4A, MP4, MOV, OGG, FLAC o WebM) de hasta 25 MB y 60 segundos. El archivo se guarda temporalmente y se elimina al terminar. El límite corto evita agotar el tiempo y la memoria del servicio gratuito.

Tras una transcripción, el usuario puede descargar un documento Word `.docx` con el título, idioma, marcas de tiempo y segmentos.

## Sitio web en Vercel

El frontend ya está publicado en Vercel como `https://transcriptor-movil.vercel.app`, conectado al repositorio, y `VITE_API_URL` apunta a `https://transcriptor-api.onrender.com`. Si el Blueprint crea otra URL de Render, actualiza `VITE_API_URL` en Production y Preview y vuelve a desplegar Vercel.

La URL de la API se lee durante el build del frontend. Para desarrollo local, déjala sin definir: Vite usa el proxy de `frontend/vite.config.js`.
