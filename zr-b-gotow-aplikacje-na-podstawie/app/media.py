from __future__ import annotations

import asyncio
import os
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageOps

from .config import settings
from .formats import FORMATS

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIC_READY = True
except ImportError:  # surfaced as a clear conversion error if HEIC is requested
    HEIC_READY = False


class MediaValidationError(ValueError):
    pass


class ConversionError(RuntimeError):
    pass


def detect_format(header: bytes) -> str | None:
    """Rozpoznaje format po sygnaturze, nie po rozszerzeniu nazwy."""
    if header.startswith(b"fLaC"):
        return "flac"
    if header.startswith(b"ID3") or (len(header) >= 2 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0):
        return "mp3"
    if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
        return "wav"
    if header.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if header.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if len(header) >= 12 and header[4:8] == b"ftyp":
        brand = header[8:12].lower()
        compatible = header[16:128].lower()
        brands = brand + compatible
        if b"qt  " in brands:
            return "mov"
        if any(item in brands for item in (b"heic", b"heix", b"hevc", b"heim", b"heis", b"mif1", b"msf1")):
            return "heic"
        return "mp4"
    return None


def safe_original_name(value: str | None) -> str:
    candidate = Path(value or "plik").name
    candidate = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", candidate).strip(". ")
    return (candidate or "plik")[:180]


async def save_and_detect(upload, temporary_path: Path, max_bytes: int) -> tuple[int, str]:
    """Zapisuje upload strumieniowo i zwraca rozmiar oraz format z magic bytes."""
    total = 0
    header = b""
    try:
        with temporary_path.open("xb") as handle:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    raise MediaValidationError(f"Plik przekracza limit {max(1, max_bytes // (1024 * 1024))} MB.")
                if len(header) < 128:
                    header += chunk[: 128 - len(header)]
                handle.write(chunk)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    fmt = detect_format(header)
    if fmt is None or fmt not in FORMATS:
        temporary_path.unlink(missing_ok=True)
        raise MediaValidationError("Nie rozpoznano obsługiwanego formatu na podstawie zawartości pliku.")
    return total, fmt


def source_path(file_id: str, source_format: str) -> Path:
    return settings.storage_dir / f"{file_id}.{source_format}"


def result_path(file_id: str, target_format: str) -> Path:
    return settings.storage_dir / f"{file_id}.wynik.{target_format}"


def _image_convert(source: Path, destination: Path, target: str) -> None:
    if (source.suffix.lower() == ".heic" or target == "heic") and not HEIC_READY:
        raise ConversionError("Obsługa HEIC wymaga pillow-heif. Zainstaluj zależności aplikacji.")
    try:
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image)
            exif = image.getexif()
            if target == "jpg":
                if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
                    background = Image.new("RGB", image.size, "white")
                    background.paste(image.convert("RGBA"), mask=image.convert("RGBA").getchannel("A"))
                    image = background
                else:
                    image = image.convert("RGB")
                image.save(destination, "JPEG", quality=95, subsampling=0, optimize=True, exif=exif.tobytes())
            elif target == "png":
                image.save(destination, "PNG", optimize=True)
            elif target == "heic":
                image.save(destination, "HEIF", quality=90, exif=exif.tobytes())
            else:
                raise ConversionError("Nieobsługiwany format docelowy obrazu.")
    except ConversionError:
        raise
    except Exception as exc:
        raise ConversionError(f"Nie udało się odczytać obrazu: {exc}") from exc


def _run(command: list[str]) -> None:
    process_options: dict = {}
    if os.name == "posix":
        # A worker receives its own CPU, virtual-memory and output-file limits in addition
        # to the cgroup limits defined for the Docker service.
        def restrict_resources() -> None:
            import resource

            memory = settings.converter_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_CPU, (settings.conversion_cpu_seconds, settings.conversion_cpu_seconds))
            resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
            resource.setrlimit(resource.RLIMIT_FSIZE, (settings.max_file_bytes * 2, settings.max_file_bytes * 2))

        process_options["preexec_fn"] = restrict_resources
    try:
        completed = subprocess.run(
            command,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=settings.conversion_timeout_seconds,
            check=False,
            **process_options,
        )
    except FileNotFoundError as exc:
        raise ConversionError("Nie znaleziono FFmpeg. Użyj obrazu Docker lub ustaw FFMPEG_BIN.") from exc
    except subprocess.TimeoutExpired as exc:
        raise ConversionError("Przekroczono limit czasu konwersji.") from exc
    if completed.returncode != 0:
        details = completed.stderr.decode("utf-8", errors="replace").strip().splitlines()
        message = details[-1] if details else "nieznany błąd FFmpeg"
        raise ConversionError(f"FFmpeg zakończył pracę błędem: {message[:400]}")


def probe_bit_depth(source: Path) -> int | None:
    """Odczytuje głębię bitową pierwszego strumienia audio; None, gdy nie da się ustalić."""
    command = [
        settings.ffprobe_bin, "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=bits_per_raw_sample,bits_per_sample",
        "-of", "default=noprint_wrappers=1", str(source),
    ]
    try:
        completed = subprocess.run(command, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    values: dict[str, str] = {}
    for line in completed.stdout.decode("utf-8", errors="replace").splitlines():
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    for key in ("bits_per_raw_sample", "bits_per_sample"):
        raw = values.get(key, "")
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
    return None


def pcm_codec(bit_depth: int | None) -> str:
    """WAV ma zachować parametry źródła: 24-bitowe i 32-bitowe źródła nie są spłaszczane do 16 bitów."""
    if bit_depth is None or bit_depth <= 16:
        return "pcm_s16le"
    if bit_depth <= 24:
        return "pcm_s24le"
    return "pcm_s32le"


# Even dimensions and yuv420p are required by libx264 and by typical players; GIF sources
# often have odd sizes and a palette pixel format, so both are normalised here.
_H264_PROFILE = [
    "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-pix_fmt", "yuv420p",
    "-c:v", "libx264", "-crf", "18", "-preset", "medium",
    "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart",
]


def ffmpeg_command(source: Path, destination: Path, source_format: str, target: str, bit_depth: int | None = None) -> list[str]:
    # Only local file and pipe protocols are enabled, so an uploaded file cannot make
    # FFmpeg fetch a network resource during conversion.
    command = [
        settings.ffmpeg_bin, "-hide_banner", "-nostdin", "-loglevel", "error", "-protocol_whitelist", "file,pipe", "-y", "-i", str(source)
    ]
    if target == "flac":
        command += ["-c:a", "flac"]
    elif target == "mp3":
        command += ["-c:a", "libmp3lame", "-b:a", "320k"]
    elif target == "wav":
        command += ["-c:a", pcm_codec(bit_depth)]
    elif target == "gif":
        command += ["-filter_complex", "[0:v]fps=12,split[a][b];[a]palettegen=stats_mode=full[p];[b][p]paletteuse", "-an"]
    elif target == "mp4":
        command += _H264_PROFILE
    elif target == "mov":
        if source_format == "mp4":
            command += ["-c", "copy", "-movflags", "+faststart"]
        else:
            command += _H264_PROFILE
    else:
        raise ConversionError("Nieobsługiwany format docelowy audio lub wideo.")
    return command + [str(destination)]


def _ffmpeg_convert(source: Path, destination: Path, source_format: str, target: str) -> None:
    bit_depth = probe_bit_depth(source) if target == "wav" else None
    _run(ffmpeg_command(source, destination, source_format, target, bit_depth))


def convert(source: Path, destination: Path, source_format: str, target_format: str) -> None:
    destination.unlink(missing_ok=True)
    category = FORMATS[source_format].category
    if category == "obraz":
        _image_convert(source, destination, target_format)
    else:
        _ffmpeg_convert(source, destination, source_format, target_format)
    if not destination.exists() or destination.stat().st_size == 0:
        raise ConversionError("Konwersja nie utworzyła pliku wynikowego.")


async def convert_async(source: Path, destination: Path, source_format: str, target_format: str) -> None:
    await asyncio.to_thread(convert, source, destination, source_format, target_format)
