import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase
from django.urls import reverse

from .transcripcion import (
    InvalidAudioFileError,
    obtener_modelo,
    transcribir_archivo_subido,
    transcribir_video,
    validar_url_youtube,
)


class YouTubeUrlTests(SimpleTestCase):
    def test_accepts_supported_video_urls(self):
        urls = (
            "https://www.youtube.com/watch?v=abcdefghijk",
            "https://youtu.be/abcdefghijk",
            "https://m.youtube.com/shorts/abcdefghijk",
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertTrue(validar_url_youtube(url))

    def test_rejects_non_youtube_and_non_video_urls(self):
        urls = (
            "https://youtube.com.evil.example/watch?v=abcdefghijk",
            "https://example.com/watch?v=abcdefghijk",
            "https://www.youtube.com/playlist?list=abcdefghijk",
            "file:///etc/passwd",
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertFalse(validar_url_youtube(url))


class TranscriptionApiTests(SimpleTestCase):
    def test_rejects_malformed_json_and_non_object_json(self):
        malformed = self.client.post(
            reverse("transcribir"),
            data="{",
            content_type="application/json",
        )
        array = self.client.post(
            reverse("transcribir"),
            data="[]",
            content_type="application/json",
        )
        self.assertEqual(malformed.status_code, 400)
        self.assertEqual(array.status_code, 400)

    def test_rejects_missing_or_invalid_video_url(self):
        missing = self.client.post(
            reverse("transcribir"),
            data="{}",
            content_type="application/json",
        )
        invalid = self.client.post(
            reverse("transcribir"),
            data='{"url":"https://example.com/video"}',
            content_type="application/json",
        )
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(invalid.status_code, 400)

    @patch("api.views.transcribir_video")
    def test_returns_transcription_json(self, transcribir):
        transcribir.return_value = {
            "titulo": "Prueba",
            "idioma": "es",
            "segmentos": [{"inicio": 0.0, "fin": 1.0, "texto": "Hola"}],
        }
        response = self.client.post(
            reverse("transcribir"),
            data='{"url":"https://youtu.be/abcdefghijk"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), transcribir.return_value)

    @patch("api.views.transcribir_video")
    def test_api_post_works_without_a_browser_csrf_cookie(self, transcribir):
        transcribir.return_value = {"titulo": "Prueba", "segmentos": []}
        client = Client(enforce_csrf_checks=True)
        response = client.post(
            reverse("transcribir"),
            data='{"url":"https://youtu.be/abcdefghijk"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_file_endpoint_requires_an_upload(self):
        response = self.client.post(reverse("transcribir_archivo"))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "Selecciona un archivo."})

    @patch("api.views.MAX_UPLOAD_SIZE", 1)
    def test_file_endpoint_rejects_oversized_upload(self):
        response = self.client.post(
            reverse("transcribir_archivo"),
            {"archivo": SimpleUploadedFile("audio.wav", b"audio")},
        )

        self.assertEqual(response.status_code, 413)

    @patch("api.views.transcribir_archivo_subido")
    def test_file_endpoint_returns_transcription(self, transcribir):
        transcribir.return_value = {
            "titulo": "audio",
            "idioma": "es",
            "segmentos": [{"inicio": 0.0, "fin": 1.0, "texto": "Hola"}],
        }
        response = self.client.post(
            reverse("transcribir_archivo"),
            {"archivo": SimpleUploadedFile("audio.wav", b"audio")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), transcribir.return_value)
        transcribir.assert_called_once()


class TranscriptionServiceTests(SimpleTestCase):
    @patch.dict(os.environ, {"WHISPER_MODEL": "tiny"})
    @patch("api.transcripcion.WhisperModel")
    def test_loads_configured_whisper_model(self, whisper_model):
        obtener_modelo.cache_clear()
        self.addCleanup(obtener_modelo.cache_clear)

        obtener_modelo()

        whisper_model.assert_called_once_with(
            "tiny",
            device="cpu",
            compute_type="int8",
        )

    @patch("api.transcripcion.obtener_modelo")
    @patch("api.transcripcion.yt_dlp.YoutubeDL")
    def test_downloads_transcribes_and_serializes_segments(
        self,
        youtube_dl,
        get_model,
    ):
        downloaded_paths = []

        class FakeDownloader:
            def __init__(self, options):
                self.options = options

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def extract_info(downloader, _url, download):
                self.assertTrue(download)
                audio_path = Path(
                    downloader.options["outtmpl"].replace("%(ext)s", "webm")
                )
                audio_path.write_bytes(b"audio")
                downloaded_paths.append(audio_path)
                return {"title": "Video de prueba", "filepath": str(audio_path)}

        youtube_dl.side_effect = FakeDownloader

        def fake_transcribe(audio_path, beam_size):
            self.assertTrue(Path(audio_path).is_file())
            self.assertEqual(beam_size, 5)
            return (
                iter([SimpleNamespace(start=0, end=1.25, text=" Hola ")]),
                SimpleNamespace(language="es"),
            )

        get_model.return_value.transcribe.side_effect = fake_transcribe
        result = transcribir_video("https://youtu.be/abcdefghijk")

        self.assertEqual(result["titulo"], "Video de prueba")
        self.assertEqual(result["idioma"], "es")
        self.assertEqual(
            result["segmentos"],
            [{"inicio": 0.0, "fin": 1.25, "texto": "Hola"}],
        )
        self.assertTrue(downloaded_paths)
        self.assertFalse(downloaded_paths[0].exists())

    def test_uploaded_audio_is_transcribed_and_removed_afterward(self):
        media = MagicMock()
        media.streams.audio = [object()]
        media.duration = 5_000_000
        open_media = MagicMock()
        open_media.return_value.__enter__.return_value = media
        open_media.return_value.__exit__.return_value = False
        transcribed_paths = []

        def fake_transcribe(audio_path, title):
            self.assertTrue(Path(audio_path).is_file())
            self.assertEqual(title, "audio de prueba")
            transcribed_paths.append(Path(audio_path))
            return {"titulo": title, "idioma": "es", "segmentos": []}

        with (
            patch("api.transcripcion.av.open", open_media),
            patch("api.transcripcion._transcribir_archivo", side_effect=fake_transcribe),
        ):
            result = transcribir_archivo_subido(
                SimpleUploadedFile("audio de prueba.wav", b"audio")
            )

        self.assertEqual(result["titulo"], "audio de prueba")
        self.assertEqual(open_media.call_count, 1)
        self.assertFalse(transcribed_paths[0].exists())

    def test_uploaded_audio_over_one_minute_is_rejected(self):
        media = MagicMock()
        media.streams.audio = [object()]
        media.duration = 61_000_000
        open_media = MagicMock()
        open_media.return_value.__enter__.return_value = media
        open_media.return_value.__exit__.return_value = False

        with patch("api.transcripcion.av.open", open_media):
            with self.assertRaisesRegex(InvalidAudioFileError, "60 segundos"):
                transcribir_archivo_subido(
                    SimpleUploadedFile("audio.wav", b"audio")
                )

    def test_uploaded_unsupported_file_is_rejected(self):
        with self.assertRaisesRegex(InvalidAudioFileError, "Formato no admitido"):
            transcribir_archivo_subido(SimpleUploadedFile("document.pdf", b"data"))

    def test_uploaded_audio_without_audio_track_is_rejected(self):
        media = MagicMock()
        media.streams.audio = []
        open_media = MagicMock()
        open_media.return_value.__enter__.return_value = media
        open_media.return_value.__exit__.return_value = False

        with patch("api.transcripcion.av.open", open_media):
            with self.assertRaisesRegex(InvalidAudioFileError, "pista de audio"):
                transcribir_archivo_subido(SimpleUploadedFile("video.mp4", b"data"))
