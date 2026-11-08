# Konwerter plików multimedialnych

Aplikacja webowa do konwersji plików audio, obrazów i wideo. Serwer działa na jednym komputerze, a użytkownicy korzystają z niej przez przeglądarkę na dowolnym urządzeniu w sieci, w tym z telefonu. Interfejs jest po polsku.

- Logowanie kodem jednorazowym wysyłanym e-mailem (6 cyfr, ważny 10 minut, maks. 5 prób). Sesja jest pamiętana przez 30 dni.
- 9 formatów, 18 ścieżek konwersji w obrębie kategorii:
  - audio: FLAC, MP3, WAV,
  - obrazy: JPG, PNG, HEIC,
  - wideo: GIF, MP4, MOV.
- 1–2 pliki na zadanie, do 250 MB każdy. Pliki dodaje się przeciągnięciem albo przyciskiem „Importuj pliki”.
- Format rozpoznawany po zawartości pliku. Przed konwersją stratną pojawia się ostrzeżenie.
- Kolejka konwersji z niezależnym statusem każdego pliku, ponawianiem błędnych konwersji i pobieraniem wyniku.
- Pliki są automatycznie usuwane 60 minut po zakończeniu konwersji.
- Jednocześnie może pracować najwyżej 10 aktywnych użytkowników. Kolejni widzą komunikat o zajętym serwerze.

Pełna instrukcja obsługi i wdrożenia (konfiguracja poczty, dostęp z internetu, administracja, rozwiązywanie problemów) jest w pliku **[INSTRUKCJA.md](INSTRUKCJA.md)**.

---

## Szybki start (Windows)

### 1. Na komputerze, który będzie serwerem

1. Zainstaluj i uruchom [Docker Desktop](https://www.docker.com/products/docker-desktop/). Poczekaj, aż ikona wieloryba pokaże stan „Engine running”.
2. Otwórz PowerShell (jako administrator) w katalogu projektu i uruchom:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\uruchom-serwer.ps1 -Mailpit

   New-NetFirewallRule -DisplayName "Konwerter plikow (TCP 8000)" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private,Domain
   ```

   Skrypt przy pierwszym uruchomieniu tworzy plik `.env` z losowym sekretem, buduje i uruchamia kontener, a na końcu wypisuje adresy aplikacji:

   ```text
    Konwerter dziala.
      Na tym komputerze:   http://localhost:8000
      Z innych komputerow: http://192.168.x.x:8000   (Ethernet)
      Z innych komputerow: http://192.168.x.x:8000   (Wi-Fi)
      Poczta:               smtp
      Skrzynka testowa:     http://localhost:8025
   ```
3. Dostęp przez internet: **[Cloudflare Tunnel](INSTRUKCJA.md#43-dostęp-z-internetu)**

   ```text
    +--------------------------------------------------------------------------------------------+
    |  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |
    |  https://x-x-x-x.trycloudflare.com                                    |
    +--------------------------------------------------------------------------------------------+
   ```

### 2. Na komputerze klienta

1. Komputery w tej samej sieci: Otwórz przeglądarkę i wpisz adres z linii „Z innych komputerow”, np. `http://192.168.x.x:8000`. Klient nie musi niczego instalować. 
2. Dostęp przez internet: Otwórz przeglądarkę i wpisz adres wygenerowany przez Cloudflare z domeny trycloudflare.com, np. `https://x-x-x-x.trycloudflare.com`.

---

## Jak przetestować wszystkie funkcje

### Pliki testowe

Jedno polecenie generuje komplet próbek do folderu `probki/`. Działa w kontenerze, więc nie trzeba instalować FFmpeg:

```powershell
Get-Content tests\make_samples.py | docker compose exec -T app python - /tmp/probki
docker compose cp app:/tmp/probki ./probki
```

Powstaną pliki:

| Plik | Do czego służy |
| --- | --- |
| `dzwiek.wav`, `dzwiek.flac`, `dzwiek.mp3` | konwersje audio (WAV ma 24 bity, co sprawdza zachowanie głębi bitowej) |
| `zdjecie.jpg`, `obraz.png`, `zdjecie.heic` | konwersje obrazów (PNG ma przezroczystość, HEIC ma obrót w EXIF) |
| `animacja.gif`, `film.mp4`, `film.mov` | konwersje wideo (GIF ma nieparzyste wymiary, MOV wymaga ponownego kodowania) |
| `uszkodzony.wav` | błąd konwersji i przycisk „Ponów” |
| `to-nie-obraz.png` | odrzucenie pliku, którego zawartość nie zgadza się z rozszerzeniem |

### Lista kontrolna (najlepiej z drugiego komputera)

| # | Czynność | Oczekiwany wynik |
| --- | --- | --- |
| 1 | Wejdź na `http://IP-SERWERA:8000`, podaj e-mail, kliknij „Wyślij kod” | Kod przychodzi e-mailem (albo widać go na ekranie w trybie testowym) |
| 2 | Wpisz błędny kod | „Nieprawidłowy kod. Pozostało prób: 4.” |
| 3 | Wpisz poprawny kod | Widok „Dodaj pliki do konwersji” i Twój adres w prawym górnym rogu |
| 4 | Odśwież stronę (F5) | Nadal zalogowany, bo sesja jest zapamiętana |
| 5 | Przeciągnij `obraz.png` na pole „Upuść pliki tutaj” | Plik na liście, do wyboru „Zamień na JPG” / „Zamień na HEIC” |
| 6 | Kliknij „Importuj pliki” i dodaj `animacja.gif` | Drugi plik na liście, do wyboru MP4 / MOV |
| 7 | Spróbuj dodać trzeci plik | „Jedno zadanie może zawierać najwyżej dwa pliki.” |
| 8 | Wybierz JPG dla PNG | Ostrzeżenie: JPG jest stratny, przezroczystość zastąpi białe tło |
| 9 | Kliknij „Konwertuj” | Statusy zmieniają się same: „oczekuje” → „w toku” → „gotowe” |
| 10 | Kliknij „Pobierz” | Pobiera się `obraz.jpg` / `animacja.mp4`, oba pliki się otwierają |
| 11 | Powtórz dla `film.mp4` → GIF i `film.mov` → MP4 | Status „gotowe”, wynik się odtwarza |
| 12 | Przekonwertuj `dzwiek.flac` → MP3 i `dzwiek.mp3` → WAV | Przy MP3 → WAV ostrzeżenie, że jakość nie wróci; oba wyniki grają |
| 13 | Przekonwertuj `zdjecie.heic` → JPG | Zdjęcie jest pionowe (300×400), czyli orientacja EXIF została uwzględniona |
| 14 | Dodaj `uszkodzony.wav` + `zdjecie.jpg` w jednym zadaniu | WAV ma status „błąd” i przycisk „Ponów”, a JPG mimo to kończy się „gotowe” |
| 15 | Kliknij „Ponów” | Plik wraca do kolejki (i znów kończy się błędem, bo jest uszkodzony) |
| 16 | Dodaj `to-nie-obraz.png` i kliknij „Konwertuj” | „Nie rozpoznano obsługiwanego formatu na podstawie zawartości pliku.” |
| 17 | Spójrz na „Usunięcie:” przy gotowym pliku | Godzina około 60 minut po zakończeniu konwersji |
| 18 | Kliknij „Wyloguj” | Powrót do ekranu logowania; ponowne wejście wymaga nowego kodu |
| 19 | Dopisz swój adres do `ADMIN_EMAILS` w `.env`, uruchom skrypt ponownie, zaloguj się | Przycisk „Dziennik administratora” pokazuje logi serwera |
| 20 | Zaloguj się z dwóch różnych komputerów na różne adresy | Każdy użytkownik widzi tylko własne zadania |

Limit 10 użytkowników najłatwiej sprawdzić, ustawiając w `.env` `MAX_ACTIVE_USERS=1`. Wtedy logowanie drugiej osoby kończy się komunikatem „Serwer jest obecnie zajęty”.

### Testy automatyczne

Testy wymagają Pythona 3.12 na komputerze deweloperskim:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Zakres testów:

- `tests/test_rules.py`: reguły formatów (18 ścieżek), sygnatury plików, ostrzeżenia i parametry poleceń FFmpeg.
- `tests/test_api.py`: cały przepływ przez API na tymczasowej bazie, czyli:
  - logowanie, wysyłka kodu przez SMTP (symulowany serwer), limity prób i zamawiania kodów,
  - sesja i wylogowanie, limit użytkowników,
  - rzeczywiste konwersje obrazów, błąd i ponowienie,
  - walidacja plików, izolacja użytkowników, dziennik administratora i usuwanie plików.

Konwersje audio i wideo wymagają FFmpeg, więc sprawdza się je w kontenerze, korzystając z listy kontrolnej powyżej.

---

## Przydatne polecenia

| Cel | Polecenie |
| --- | --- |
| Uruchomienie / restart po zmianie `.env` | `powershell -ExecutionPolicy Bypass -File .\uruchom-serwer.ps1` |
| Zatrzymanie | `powershell -ExecutionPolicy Bypass -File .\uruchom-serwer.ps1 -Stop` |
| Logi na żywo | `docker compose logs -f app` |
| Test poczty | `docker compose exec app python -m app.mailtest adres@example.pl` |
| Stan aplikacji | otwórz `http://localhost:8000/health` |
| Dokumentacja API | otwórz `http://localhost:8000/docs` |

## Profile konwersji

| Kategoria | Format docelowy | Wbudowany profil |
| --- | --- | --- |
| Audio | FLAC | Kompresja bezstratna z zachowaniem częstotliwości i głębi bitowej źródła |
| Audio | MP3 | 320 kb/s CBR |
| Audio | WAV | PCM bez kompresji, głębia bitowa źródła (16/24/32 bity) |
| Obraz | JPG | Jakość 95, próbkowanie 4:4:4, białe tło zamiast przezroczystości |
| Obraz | PNG | Zachowana przezroczystość |
| Obraz | HEIC | Jakość 90, zachowane EXIF i orientacja |
| Wideo | GIF | Paleta dla całego klipu, 12 klatek/s, bez dźwięku |
| Wideo | MP4 | H.264 CRF 18, AAC 256 kb/s |
| Wideo | MOV | Z MP4: przepakowanie bez rekodowania; w pozostałych przypadkach H.264 CRF 18 i AAC 256 kb/s |
