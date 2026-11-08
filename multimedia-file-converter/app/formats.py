from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MediaFormat:
    code: str
    category: str
    label: str
    is_lossy: bool
    profile: str


FORMATS: dict[str, MediaFormat] = {
    "flac": MediaFormat("flac", "audio", "FLAC", False, "Kompresja bezstratna; zachowane parametry źródła"),
    "mp3": MediaFormat("mp3", "audio", "MP3", True, "320 kb/s CBR"),
    "wav": MediaFormat("wav", "audio", "WAV", False, "PCM bez kompresji; parametry źródła"),
    "jpg": MediaFormat("jpg", "obraz", "JPG", True, "Jakość 95, 4:4:4, białe tło zamiast przezroczystości"),
    "png": MediaFormat("png", "obraz", "PNG", False, "Zachowana przezroczystość"),
    "heic": MediaFormat("heic", "obraz", "HEIC", True, "Jakość co najmniej 90, EXIF i orientacja"),
    "gif": MediaFormat("gif", "wideo", "GIF", True, "Paleta dla całego klipu, bez dźwięku"),
    "mp4": MediaFormat("mp4", "wideo", "MP4", True, "H.264 CRF 18, AAC 256 kb/s"),
    "mov": MediaFormat("mov", "wideo", "MOV", True, "Przepakowanie bez rekodowania lub H.264 CRF 18, AAC 256 kb/s"),
}


def target_options(source: str) -> list[MediaFormat]:
    if source not in FORMATS:
        return []
    source_format = FORMATS[source]
    return [
        item for item in FORMATS.values()
        if item.category == source_format.category and item.code != source
    ]


def allowed_target(source: str, target: str) -> bool:
    return target in {item.code for item in target_options(source)}


def conversion_warning(source: str, target: str) -> str | None:
    if not allowed_target(source, target):
        return "Format docelowy musi należeć do tej samej kategorii co plik źródłowy."
    origin, destination = FORMATS[source], FORMATS[target]
    if destination.is_lossy:
        return f"{destination.label} jest formatem stratnym. Wynik może mieć niższą jakość niż plik źródłowy."
    if source == "mp3" and target in {"flac", "wav"}:
        return "Konwersja nie odzyska jakości utraconej wcześniej w pliku MP3."
    return None
