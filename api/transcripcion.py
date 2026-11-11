import logging
import os
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlparse

import av
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
MAX_UPLOAD_SIZE = 25 * 1024 * 1024
MAX_COOKIE_FILE_SIZE = 1024 * 1024
MAX_AUDIO_DURATION_SECONDS = 60
SUPPORTED_AUDIO_EXTENSIONS = {
    ".flac",
    ".m4a",
    ".mp3",
    ".mp4",
    ".mov",
    ".ogg",
    ".wav",
    ".webm",
}


class TranscriptionError(Exception):
    """Raised when YouTube audio cannot be downloaded for transcription."""


class InvalidYouTubeUrlError(ValueError):
    """Raised when a request does not contain a supported YouTube video URL."""


class InvalidCookieFileError(ValueError):
    """Raised when an uploaded YouTube cookie file is invalid or too large."""


class InvalidAudioFileError(ValueError):
    """Raised when an uploaded file is unsupported or exceeds its limits."""


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
    model_name = os.environ.get("WHISPER_MODEL", "small")
    return WhisperModel(model_name, device="cpu", compute_type="int8")


def _descargar_audio(url, output_dir, cookies_path=None):
    output_template = str(Path(output_dir) / "audio.%(ext)s")
    options = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
    }

    if cookies_path is not None:
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
            "YouTube rechazó la descarga o el video no está accesible desde "
            "el servidor. Inténtalo más tarde con un video público."
        ) from error

    audio_path = Path(audio_path)
    if not audio_path.is_file():
        raise TranscriptionError("YouTube no generó el archivo de audio esperado.")
    return video, audio_path


def transcribir_video(url, uploaded_cookie_file=None):
    """Download a YouTube video temporarily and return JSON-ready segments."""
    if not validar_url_youtube(url):
        raise InvalidYouTubeUrlError(
            "La URL debe pertenecer a un video válido de YouTube."
        )

    with TemporaryDirectory(prefix="transcripcion-") as temp_dir:
        cookies_path = None
        if uploaded_cookie_file is not None:
            cookies_path = _guardar_cookies_subidas(uploaded_cookie_file, temp_dir)
        video, audio_path = _descargar_audio(url.strip(), temp_dir, cookies_path)
        return _transcribir_archivo(str(audio_path), video.get("title"))


def _guardar_cookies_subidas(uploaded_cookie_file, output_dir):
    suffix = Path(uploaded_cookie_file.name).suffix.lower()
    if suffix != ".txt":
        raise InvalidCookieFileError("El archivo de cookies debe tener extensión .txt.")
    if uploaded_cookie_file.size == 0:
        raise InvalidCookieFileError("El archivo de cookies está vacío.")
    if uploaded_cookie_file.size > MAX_COOKIE_FILE_SIZE:
        raise InvalidCookieFileError("El archivo de cookies no puede superar 1 MB.")

    cookies_path = Path(output_dir) / "youtube-cookies.txt"
    with cookies_path.open("wb") as destination:
        for chunk in uploaded_cookie_file.chunks():
            destination.write(chunk)

    with cookies_path.open("rb") as source:
        first_line = source.readline().lstrip(b"\xef\xbb\xbf").strip()
    if first_line not in {b"# HTTP Cookie File", b"# Netscape HTTP Cookie File"}:
        raise InvalidCookieFileError(
            "El archivo no parece estar en formato Netscape cookies.txt."
        )

    return cookies_path


def _transcribir_archivo(audio_path, title):
    segments, info = obtener_modelo().transcribe(audio_path, beam_size=5)
    return {
        "titulo": title or "Archivo de audio",
        "idioma": info.language,
        "segmentos": [
            {
                "inicio": float(segment.start),
                "fin": float(segment.end),
                "texto": segment.text.strip(),
            }
            for segment in segments
        ],
    }


def transcribir_archivo_subido(uploaded_file):
    """Validate and transcribe a short uploaded audio/video file."""
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix not in SUPPORTED_AUDIO_EXTENSIONS:
        raise InvalidAudioFileError(
            "Formato no admitido. Usa MP3, WAV, M4A, MP4, OGG, FLAC o WebM."
        )
    if uploaded_file.size == 0:
        raise InvalidAudioFileError("El archivo está vacío.")
    if uploaded_file.size > MAX_UPLOAD_SIZE:
        raise InvalidAudioFileError("El archivo no puede superar los 25 MB.")

    with TemporaryDirectory(prefix="transcripcion-") as temp_dir:
        audio_path = Path(temp_dir) / f"archivo{suffix}"
        with audio_path.open("wb") as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        try:
            with av.open(str(audio_path)) as media:
                audio_streams = media.streams.audio
                if not audio_streams:
                    raise InvalidAudioFileError(
                        "El archivo no contiene una pista de audio."
                    )

                duration = media.duration
                if duration is None:
                    stream = audio_streams[0]
                    if stream.duration is None or stream.time_base is None:
                        raise InvalidAudioFileError(
                            "No se pudo determinar la duración del archivo."
                        )
                    duration = float(stream.duration * stream.time_base)
                else:
                    duration = duration / av.time_base

                if duration > MAX_AUDIO_DURATION_SECONDS:
                    raise InvalidAudioFileError(
                        "El audio no puede durar más de 60 segundos."
                    )
        except InvalidAudioFileError:
            raise
        except (av.error.FFmpegError, OSError, ValueError) as error:
            raise InvalidAudioFileError(
                "El archivo no es un audio o video válido."
            ) from error

        return _transcribir_archivo(
            str(audio_path),
            Path(uploaded_file.name).stem or "Archivo de audio",
        )
