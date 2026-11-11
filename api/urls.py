from django.urls import path
from .views import saludo, transcribir, transcribir_archivo

urlpatterns = [
    path("saludo/", saludo, name="saludo"),
    path("transcribir/", transcribir, name="transcribir"),
    path("transcribir-archivo/", transcribir_archivo, name="transcribir_archivo"),
]