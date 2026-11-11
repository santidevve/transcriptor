from io import BytesIO
import json
import logging
import math

from django.http import HttpResponse, JsonResponse
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from docx import Document

from .transcripcion import (
    MAX_COOKIE_FILE_SIZE,
    MAX_UPLOAD_SIZE,
    InvalidAudioFileError,
    InvalidCookieFileError,
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
    Transcribe un video y, opcionalmente, usa cookies proporcionadas en la solicitud.
    """
    uploaded_cookie_file = None
    if request.content_type == "multipart/form-data":
        datos = request.POST
        uploaded_cookie_file = request.FILES.get("cookies")
        if (
            uploaded_cookie_file is not None
            and uploaded_cookie_file.size > MAX_COOKIE_FILE_SIZE
        ):
            return JsonResponse(
                {"error": "El archivo de cookies no puede superar 1 MB."},
                status=413,
            )
    else:
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
        resultado = transcribir_video(url.strip(), uploaded_cookie_file)
    except InvalidYouTubeUrlError as error:
        return JsonResponse({"error": str(error)}, status=400)
    except InvalidCookieFileError as error:
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
def descargar_transcripcion_docx(request):
    """Create a Word document from a validated transcription payload."""
    if len(request.body) > 2 * 1024 * 1024:
        return JsonResponse(
            {"error": "La transcripción es demasiado grande para exportarla."},
            status=413,
        )
    try:
        datos = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "El cuerpo debe ser JSON válido."}, status=400)

    if not isinstance(datos, dict):
        return JsonResponse({"error": "El cuerpo JSON debe ser un objeto."}, status=400)

    titulo = datos.get("titulo", "Transcripción")
    idioma = datos.get("idioma", "")
    segmentos = datos.get("segmentos")
    if (
        not isinstance(titulo, str)
        or not titulo.strip()
        or len(titulo) > 250
        or not isinstance(idioma, str)
        or len(idioma) > 50
        or not isinstance(segmentos, list)
        or len(segmentos) > 5000
    ):
        return JsonResponse(
            {"error": "El formato de la transcripción no es válido."},
            status=400,
        )

    for segmento in segmentos:
        if (
            not isinstance(segmento, dict)
            or isinstance(segmento.get("inicio"), bool)
            or not isinstance(segmento.get("inicio"), (int, float))
            or not math.isfinite(segmento["inicio"])
            or segmento["inicio"] < 0
            or not isinstance(segmento.get("texto"), str)
            or len(segmento["texto"]) > 10000
        ):
            return JsonResponse(
                {"error": "El formato de la transcripción no es válido."},
                status=400,
            )

    document = Document()
    document.add_heading(titulo.strip(), 0)
    if idioma:
        document.add_paragraph(f"Idioma: {idioma}")
    for segmento in segmentos:
        seconds = int(segmento["inicio"])
        timestamp = f"{seconds // 3600:02}:{seconds % 3600 // 60:02}:{seconds % 60:02}"
        paragraph = document.add_paragraph()
        paragraph.add_run(f"[{timestamp}] ").bold = True
        paragraph.add_run(segmento["texto"])

    output = BytesIO()
    document.save(output)
    filename = slugify(titulo) or "transcripcion"
    response = HttpResponse(
        output.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}.docx"'
    return response


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