# Konwerter plików multimedialnych

Gotowa aplikacja webowa do bezpiecznej konwersji plików audio, obrazów i wideo. Interfejs jest w języku polskim, działa w przeglądarce i obsługuje całe zadanie od logowania kodem jednorazowym do pobrania wyniku.

## Zakres funkcji

- Logowanie hasłem jednorazowym: sześciocyfrowy kod ważny 10 minut, maksymalnie pięć prób, sesja `HttpOnly` ważna 30 dni i unieważniana przy wylogowaniu.
- Limit 10 aktywnych użytkowników w ciągu ostatnich 15 minut.
- Import metodą przeciągnij i upuść albo przyciskiem, od jednego do dwóch plików na zadanie, maksymalnie 250 MB na plik.
- Rozpoznawanie formatu na podstawie sygnatury pliku, nie samego rozszerzenia.
- Dziewięć formatów: FLAC, MP3, WAV, JPG, PNG, HEIC, GIF, MP4 i MOV; dozwolone są wyłącznie dwa formaty docelowe z tej samej kategorii (18 ścieżek).
- Ostrzeżenia przed konwersją stratną; stałe profile docelowe zgodne z wymaganiami.
- Kolejka z limitem równoległych konwersji, niezależne statusy plików, możliwość ponowienia błędnego pliku i pobieranie gotowego wyniku.
- Pliki oraz wyniki są automatycznie usuwane 60 minut po zakończeniu konwersji.
- SQLite w trybie WAL, identyfikatory UUID dla plików na dysku oraz dziennik plikowy dla administratora.

## Szybkie uruchomienie przez Docker

1. Skopiuj `.env.example` do `.env` i ustaw `SECRET_KEY`. Dla lokalnego testu pozostaw `APP_ENV=development`; kod logowania pokaże się w interfejsie, jeśli nie ustawisz SMTP.
2. Uruchom Docker Desktop.
3. W katalogu projektu wykonaj:

   ```powershell
   docker compose up --build
   ```

4. Otwórz [http://localhost:8000](http://localhost:8000).

Obraz zawiera FFmpeg oraz obsługę HEIC. Konwersje są uruchamiane jako osobne procesy bez powłoki, z limitem czasu; kontener ma ograniczenia CPU, pamięci i uprawnień. Przed wdrożeniem publicznym ustaw prawdziwe SMTP, `APP_ENV=production`, `COOKIE_SECURE=true`, losowy sekret oraz `ADMIN_EMAILS`.

## HTTPS z Caddy

Na serwerze ustaw w `.env` `DOMAIN=twoja-domena.example`, `APP_ENV=production` i `COOKIE_SECURE=true`, a następnie uruchom:

```powershell
docker compose --profile production up --build -d
```

Caddy automatycznie obsłuży certyfikat HTTPS. Skonfiguruj rekord DNS domeny przed uruchomieniem.

## Uruchomienie bez Dockera

Wymagany jest Python 3.12+, FFmpeg z `ffprobe` na `PATH`, a dla HEIC także biblioteka `pillow-heif`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Profile konwersji

| Kategoria | Format docelowy | Wbudowany profil |
| --- | --- | --- |
| Audio | FLAC | Kompresja bezstratna z zachowaniem parametrów źródła |
| Audio | MP3 | 320 kb/s CBR |
| Audio | WAV | PCM bez kompresji |
| Obraz | JPG | Jakość 95, próbkowanie 4:4:4, białe tło dla przezroczystości |
| Obraz | PNG | Zachowana przezroczystość |
| Obraz | HEIC | Jakość 90, zachowane EXIF i orientacja |
| Wideo | GIF | Paleta dla całego klipu, bez dźwięku |
| Wideo | MP4 | H.264 CRF 18, AAC 256 kb/s |
| Wideo | MOV | Kopiowanie strumieni z MP4, w pozostałych przypadkach H.264 CRF 18 i AAC 256 kb/s |

## Testy

Po zainstalowaniu zależności uruchom:

```powershell
python -m unittest discover -s tests -v
```

Testy pokrywają reguły formatów, ich sygnatury i mechanizmy bezpieczeństwa kodów jednorazowych.
