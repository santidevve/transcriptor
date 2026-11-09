from django.urls import path
from .views import saludo, transcribir

urlpatterns = [
    path("saludo/", saludo, name="saludo"),
    path("transcribir/", transcribir, name="transcribir"),
]