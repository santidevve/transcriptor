from django.urls import path
from .views import (
    descargar_transcripcion_docx,
    saludo,
    transcribir,
    transcribir_archivo,
)

urlpatterns = [
    path("saludo/", saludo, name="saludo"),
    path("transcribir/", transcribir, name="transcribir"),
    path("transcribir-archivo/", transcribir_archivo, name="transcribir_archivo"),
    path(
        "descargar-transcripcion-docx/",
        descargar_transcripcion_docx,
        name="descargar_transcripcion_docx",
    ),
]