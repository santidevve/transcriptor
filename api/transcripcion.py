import logging
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlparse
import yt_dlp
from faster_whisper import WhisperModel


logger = logging.getLogger(__name__)
YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
}
SHORT_HOSTS = {"youtu.be", "www.youtu.be"}


class TranscriptionError(Exception):
    """Raised when YouTube audio cannot be downloaded for transcription."""


class InvalidYouTubeUrlError(ValueError):
    """Raised when a request does not contain a supported YouTube video URL."""


def validar_url_youtube(url):
    """Accept only supported video URLs on YouTube's exact hostnames."""
    if not isinstance(url, str):
        return False

    try:
        parsed = urlparse(url.strip())
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError:
        return False

    if (
        parsed.scheme not in {"http", "https"}
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 80, 443}
    ):
        return False

    if host in SHORT_HOSTS:
        video_id = parsed.path.strip("/")
    elif host in YOUTUBE_HOSTS:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        else:
            parts = parsed.path.strip("/").split("/")
            video_id = parts[1] if len(parts) == 2 and parts[0] in {
                "embed",
                "live",
                "shorts",
                "v",
            } else ""
    else:
        return False

    return len(video_id) == 11 and all(
        character.isalnum() or character in "_-" for character in video_id
    )


@lru_cache(maxsize=1)
def obtener_modelo():
    """Load Whisper once per Django worker, on the first transcription."""
    return WhisperModel("small", device="cpu", compute_type="int8")


def _descargar_audio(url, output_dir):
    output_template = str(Path(output_dir) / "audio.%(ext)s")
    options = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
    }

    cookies_path = Path(__file__).resolve().parent.parent / "youtube_cookies.txt"
    if cookies_path.is_file():
        options["cookiefile"] = str(cookies_path)

    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            video = downloader.extract_info(url, download=True)
            audio_path = video.get("filepath")
            if not audio_path:
                audio_path = downloader.prepare_filename(video)
    except yt_dlp.utils.DownloadError as error:
        logger.exception("No se pudo descargar el video de YouTube.")
        raise TranscriptionError(
            "No se pudo descargar el video. Comprueba que sea accesible."
        ) from error

    audio_path = Path(audio_path)
    if not audio_path.is_file():
        raise TranscriptionError("YouTube no generó el archivo de audio esperado.")
    return video, audio_path


def transcribir_video(url):
    """Download a YouTube video temporarily and return JSON-ready segments."""
    if not validar_url_youtube(url):
        raise InvalidYouTubeUrlError(
            "La URL debe pertenecer a un video válido de YouTube."
        )

    with TemporaryDirectory(prefix="transcripcion-") as temp_dir:
        video, audio_path = _descargar_audio(url.strip(), temp_dir)
        segments, info = obtener_modelo().transcribe(str(audio_path), beam_size=5)
        serialized_segments = [
            {
                "inicio": float(segment.start),
                "fin": float(segment.end),
                "texto": segment.text.strip(),
            }
            for segment in segments
        ]

        return {
            "titulo": video.get("title") or "Video de YouTube",
            "idioma": info.language,
            "segmentos": serialized_segments,
        }
