import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .transcripcion import (
    MAX_UPLOAD_SIZE,
    InvalidAudioFileError,
    InvalidYouTubeUrlError,
    TranscriptionError,
    transcribir_archivo_subido,
    transcribir_video,
)


logger = logging.getLogger(__name__)


def saludo(request):
    """
    Vista para saludar al usuario.
    """
    return JsonResponse({"mensaje": "Hola desde Django"})


@csrf_exempt
@require_POST
def transcribir(request):
    """
    Vista para transcribir un video a partir de su URL.
    """
    try:
        datos = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "El cuerpo debe ser JSON válido."}, status=400)

    if not isinstance(datos, dict):
        return JsonResponse(
            {"error": "El cuerpo JSON debe ser un objeto."},
            status=400,
        )

    url = datos.get("url")
    if not isinstance(url, str) or not url.strip():
        return JsonResponse({"error": "Falta la URL del video."}, status=400)

    try:
        resultado = transcribir_video(url.strip())
    except InvalidYouTubeUrlError as error:
        return JsonResponse({"error": str(error)}, status=400)
    except TranscriptionError as error:
        logger.exception("Falló la descarga del video solicitado.")
        return JsonResponse({"error": str(error)}, status=502)
    except Exception:
        logger.exception("Falló la transcripción del video solicitado.")
        return JsonResponse(
            {"error": "No se pudo completar la transcripción."},
            status=500,
        )

    return JsonResponse(resultado)


@csrf_exempt
@require_POST
def transcribir_archivo(request):
    """Transcribe a short audio or video file uploaded by the user."""
    uploaded_file = request.FILES.get("archivo")
    if uploaded_file is None:
        return JsonResponse({"error": "Selecciona un archivo."}, status=400)
    if uploaded_file.size > MAX_UPLOAD_SIZE:
        return JsonResponse(
            {"error": "El archivo no puede superar los 25 MB."},
            status=413,
        )

    try:
        resultado = transcribir_archivo_subido(uploaded_file)
    except InvalidAudioFileError as error:
        return JsonResponse({"error": str(error)}, status=400)
    except TranscriptionError as error:
        logger.exception("Falló la transcripción del archivo subido.")
        return JsonResponse({"error": str(error)}, status=502)
    except Exception:
        logger.exception("Falló la transcripción del archivo subido.")
        return JsonResponse(
            {"error": "No se pudo completar la transcripción."},
            status=500,
        )

    return JsonResponse(resultado)