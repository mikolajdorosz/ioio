"""Tworzy komplet plików do ręcznego testowania wszystkich funkcji aplikacji.

Uruchamiany wewnątrz kontenera (jest tam FFmpeg i pillow-heif):
    Get-Content tests\\make_samples.py | docker compose exec -T app python - /tmp/probki
    docker compose cp app:/tmp/probki ./probki
"""

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw
from pillow_heif import register_heif_opener

register_heif_opener()
target = Path(sys.argv[1] if len(sys.argv) > 1 else "probki")
target.mkdir(parents=True, exist_ok=True)


def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


# Audio: 24-bitowy WAV pozwala sprawdzić zachowanie głębi bitowej.
ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=5", "-ar", "48000", "-c:a", "pcm_s24le", str(target / "dzwiek.wav"))
ffmpeg("-i", str(target / "dzwiek.wav"), "-c:a", "flac", str(target / "dzwiek.flac"))
ffmpeg("-i", str(target / "dzwiek.wav"), "-c:a", "libmp3lame", "-b:a", "192k", str(target / "dzwiek.mp3"))

# Wideo: GIF ma nieparzyste wymiary, MOV ma kodek ProRes (wymusza ponowne kodowanie).
ffmpeg("-f", "lavfi", "-i", "testsrc=size=321x241:rate=10:duration=3", str(target / "animacja.gif"))
ffmpeg("-f", "lavfi", "-i", "testsrc=size=1280x720:rate=25:duration=5", "-f", "lavfi", "-i", "sine=duration=5",
       "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(target / "film.mp4"))
ffmpeg("-i", str(target / "film.mp4"), "-c:v", "prores_ks", "-c:a", "pcm_s16le", str(target / "film.mov"))

# Obrazy: PNG z przezroczystością (w JPG ma pojawić się białe tło), HEIC z orientacją EXIF.
image = Image.new("RGBA", (400, 300), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
draw.ellipse((50, 50, 350, 250), fill=(220, 40, 40, 255))
draw.text((150, 140), "KONWERTER", fill=(255, 255, 255, 255))
image.save(target / "obraz.png")
image.convert("RGB").save(target / "zdjecie.jpg", quality=90)
exif = Image.Exif()
exif[0x0112] = 6  # obrót o 90°: wynik ma być ustawiony pionowo
image.convert("RGB").save(target / "zdjecie.heic", quality=90, exif=exif.tobytes())

# Pliki do testów błędów.
(target / "uszkodzony.wav").write_bytes(b"RIFF" + (36).to_bytes(4, "little") + b"WAVE" + b"\x00" * 64)
(target / "to-nie-obraz.png").write_bytes(b"%PDF-1.7 to jest dokument, nie obraz")

for path in sorted(target.iterdir()):
    print(f"{path.name:<20} {path.stat().st_size:>10} B")
