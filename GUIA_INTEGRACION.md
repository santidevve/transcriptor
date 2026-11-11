# Ejecutar Transcriptor

El proyecto tiene un frontend web React con Vite y una API Django. Para usarlo
en desarrollo, deja abiertos dos terminales desde la carpeta raíz.

## 1. Inicia Django

En la primera terminal, desde PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python manage.py check
python manage.py test api
python manage.py runserver 127.0.0.1:8000
```

La API debe responder en `http://127.0.0.1:8000/api/saludo/`.

## 2. Inicia React

En una segunda terminal:

```powershell
cd frontend
npm install
npm run dev
```

Abre la URL que Vite muestra en la terminal, normalmente
`http://localhost:5173`. Pega un enlace de video de YouTube y pulsa
**Transcribir**. El proxy de Vite reenvía `/api/` a Django en el puerto 8000.

Para recibir un aviso del sistema operativo cuando termine mientras estás en
otra pestaña, pulsa **Activar avisos del navegador** y permite las
notificaciones cuando el navegador lo solicite. Mantén abierta la página que
envió la transcripción; el resultado aparecerá también en ella. Si se cierra
esa página o el navegador, no habrá aviso: para ese caso se necesitaría una
integración de notificaciones push en segundo plano.

## Requisitos para transcribir

FFmpeg debe estar instalado y accesible desde `PATH`. El modelo Whisper
`small` se descarga y carga en CPU la primera vez que se solicita una
transcripción; por eso la primera ejecución puede tardar. Para un video de
YouTube que requiera autenticación, el formulario admite opcionalmente un
archivo Netscape `cookies.txt` de hasta 1 MB. El archivo se usa solo durante
esa solicitud y se elimina junto con el audio temporal. Las cookies son
credenciales sensibles: exporta solo las de YouTube y no las compartas. Su uso
no garantiza que YouTube permita la descarga desde una IP de centro de datos.

El resultado se puede exportar desde la interfaz como un documento Word
`.docx`, con el título, idioma, marcas de tiempo y texto de cada segmento.

## Compilar para publicar

Desde `frontend`:

```powershell
npm run build
```

Esto genera los archivos estáticos en `frontend/dist`. Para servir la versión
compilada en producción, despliega esos archivos con un servidor web y configura
`/api/` para que apunte al backend Django. `npm run dev` es solo para desarrollo;
no expongas el servidor de desarrollo de Django a Internet.
