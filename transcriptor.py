import os
import re
import subprocess
import shutil
import yt_dlp
import librosa
from faster_whisper import WhisperModel
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from transformers import pipeline

class Transcriptor:


    def validar_url_youtube(self, url):
        patron = r'^(https?://)?(www\.|m\.|music\.)?(youtube\.com/(watch\?v=|shorts/|playlist\?)|youtu\.be/)[a-zA-Z0-9_-]+'
        return bool(re.search(patron, url))


    


    def obtener_titulo_youtube(self, url):
        """
        Funcion para obtener el titulo del video de Youtube.
        """
        ydl_opts = {
            'quiet': True,  # No mostrar logs innecesarios en la consola
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # Extraemos la información del video sin descargar el archivo (.mp3/.mp4)
                info = ydl.extract_info(url, download=False)
                titulo = info.get('title', 'Título no encontrado')
                return titulo
            except Exception as e:
                print(f"❌ Error al obtener el título: {e}")
                return None

    def formatear_tiempo(self, segundos):
        """Convierte segundos a formato MM:SS"""
        minutos = int(segundos) // 60
        secs = int(segundos) % 60
        return f"{minutos:02d}:{secs:02d}"

    # Almacenar el modelo
    model = WhisperModel("small", device="cpu", compute_type="int8")

    # 1. Solicitar URL de Youtube
    while True:
        url_ingresada = input('Ingrese la URL del video de YouTube: ').strip()
        # 2. URL Válida?
        if validar_url_youtube(url_ingresada):
            # 3. Sí. Descarga el audio
            download_audio_ytdlp(url_ingresada)
            break
        else:
        # URL no es válida, vuelve a pedir la URL.
            print("❌ URL no válida. Intente nuevamente con un enlace válido (ej. https://www.youtube.com/watch?v=...).")

    # 4. Carga el audio con librosa
    audio_array, _ = librosa.load("audio.mp3", sr=16000)

    # 5. Transcribe el audio con WhisperModel.
    segments, info = model.transcribe(audio_array, beam_size=5)

    document = Document()

    texto_acumulado = ""
    inicio_bloque = 0.0
    fin_bloque = 0.0
    limite_caracteres = 450

    # 6. Procesar la inclusión de cada segmento en el documento.
    for segment in segments:

        if not texto_acumulado:
            inicio_bloque = segment.start

        texto_acumulado += " " + segment.text.strip()
        fin_bloque = segment.end

        if len(texto_acumulado) >= limite_caracteres:

            marca_tiempo = (
                f"[{formatear_tiempo(inicio_bloque)} - "
                f"{formatear_tiempo(fin_bloque)}]"
            )

            # Crear párrafo de marca de tiempo
            p_tiempo = document.add_paragraph()
            run_tiempo = p_tiempo.add_run(marca_tiempo)

            run_tiempo.font.name = 'Arial'
            run_tiempo.font.size = Pt(10)
            run_tiempo.font.bold = True
            run_tiempo.font.color.rgb = RGBColor(128, 128, 128)

            p_tiempo.paragraph_format.space_before = Pt(12)
            p_tiempo.paragraph_format.space_after = Pt(2)

            # Crear párrafo de transcripción
            p_texto = document.add_paragraph()
            run_texto = p_texto.add_run(texto_acumulado.strip())

            run_texto.font.name = 'Arial'
            run_texto.font.size = Pt(11)

            p_texto.paragraph_format.line_spacing = 1.15
            p_texto.paragraph_format.space_after = Pt(10)

            # Reiniciar acumulador
            texto_acumulado = ""

    # Guardar cualquier texto restante
    if texto_acumulado:

        marca_tiempo = (
            f"[{formatear_tiempo(inicio_bloque)} - "
            f"{formatear_tiempo(fin_bloque)}]"
        )

        p_tiempo = document.add_paragraph()
        run_tiempo = p_tiempo.add_run(marca_tiempo)

        run_tiempo.font.name = 'Arial'
        run_tiempo.font.size = Pt(10)
        run_tiempo.font.bold = True
        run_tiempo.font.color.rgb = RGBColor(128, 128, 128)

        p_texto = document.add_paragraph()
        run_texto = p_texto.add_run(texto_acumulado.strip())

        run_texto.font.name = 'Arial'
        run_texto.font.size = Pt(11)

        p_texto.paragraph_format.line_spacing = 1.15
        p_texto.paragraph_format.space_after = Pt(10)
    
    document.add_heading(f"{obtener_titulo_youtube(url_ingresada)} - Transcripción")
    document.save(f"{obtener_titulo_youtube(url_ingresada)} - Transcripción")


