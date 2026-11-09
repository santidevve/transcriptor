from django.http import JsonResponse
import json
from django.views.decorators.http import require_POST
from .transcripcion import transcribir_video  # Función a extraer del script


def saludo(request):
    """
    Vista para saludar al usuario.
    """
    return JsonResponse({"mensaje": "Hola desde Django"})


@require_POST
def transcribir(request):
    """
    Vista para transcribir un video a partir de su URL.
    """
    try:
        datos = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "El cuerpo debe ser JSON válido."}, status=400)

    url = datos.get("url")
    # Validate that the URL exists and is a non-empty string.
    if not isinstance(url, str) or not url.strip():
        return JsonResponse({"error": "Falta la URL del video."}, status=400)
    # Call the transcribir_video function with the provided URL if the URL is valid.
    resultado = transcribir_video(url.strip())
    return JsonResponse(resultado)