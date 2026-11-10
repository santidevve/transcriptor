from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.test import Client, SimpleTestCase
from django.urls import reverse

from .transcripcion import transcribir_video, validar_url_youtube


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


class TranscriptionServiceTests(SimpleTestCase):
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
