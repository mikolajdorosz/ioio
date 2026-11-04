# Konwerter plików multimedialnych – instrukcja obsługi i wdrożenia

Spis treści:

1. [Jak działa system](#1-jak-działa-system)
2. [Uruchomienie serwera krok po kroku](#2-uruchomienie-serwera-krok-po-kroku)
3. [Konfiguracja poczty (kody logowania)](#3-konfiguracja-poczty-kody-logowania)
4. [Dostęp z innych komputerów](#4-dostęp-z-innych-komputerów)
5. [Instrukcja dla użytkownika](#5-instrukcja-dla-użytkownika)
6. [Administracja](#6-administracja)
7. [Rozwiązywanie problemów](#7-rozwiązywanie-problemów)
8. [Uruchomienie bez Dockera](#8-uruchomienie-bez-dockera)

---

## 1. Jak działa system

```text
 Komputer klienta (przeglądarka)            Komputer-serwer (Docker)
 ┌────────────────────────────┐   HTTP    ┌──────────────────────────────────────┐
 │ http://IP-SERWERA:8000     │ ────────▶ │ Aplikacja (FastAPI) ─ kolejka konwersji│
 │ logowanie, wysyłanie,      │ ◀──────── │   ├─ FFmpeg (audio, wideo)            │
 │ pobieranie wyników         │           │   ├─ Pillow + pillow-heif (obrazy)    │
 └────────────────────────────┘           │   └─ SQLite + pliki (wolumen Docker)  │
                                           └──────────────┬───────────────────────┘
                                                          │ SMTP
                                                          ▼
                                               Serwer poczty (np. Gmail)
```

- **Serwer** to jeden komputer z Dockerem. Na nim działa aplikacja, wykonują się konwersje i są przechowywane pliki.
- **Klienci** potrzebują tylko przeglądarki. Mogą to być inne komputery, telefony albo tablety w tej samej sieci, a po dodatkowej konfiguracji także w internecie (rozdział 4).
- **Poczta** służy wyłącznie do wysyłania jednorazowych kodów logowania.

## 2. Uruchomienie serwera krok po kroku

### 2.1. Wymagania

| Element | Wymaganie |
| --- | --- |
| System | Windows 10/11 (64-bit); Linux i macOS też działają, opis poniżej dotyczy Windows |
| Pamięć RAM | min. 4 GB, kontener używa do 1,5 GB |
| Dysk | ok. 2 GB na obraz oraz miejsce na pliki (do 500 MB na zadanie, usuwane po 60 minutach) |
| Oprogramowanie | [Docker Desktop](https://www.docker.com/products/docker-desktop/) |
| Sieć | serwer i klienci w tej samej sieci (dostęp z internetu: rozdział 4.3) |

### 2.2. Instalacja Dockera (jednorazowo)

1. Pobierz Docker Desktop ze strony [docker.com](https://www.docker.com/products/docker-desktop/) i zainstaluj z ustawieniami domyślnymi (backend WSL 2).
2. Uruchom ponownie komputer, jeśli instalator o to poprosi.
3. Uruchom Docker Desktop i poczekaj, aż w lewym dolnym rogu pojawi się „Engine running”.
4. Opcjonalnie w ustawieniach Docker Desktop zaznacz „Start Docker Desktop when you sign in”, żeby serwer wstawał po restarcie komputera. Kontener ma ustawione `restart: unless-stopped`, więc wtedy uruchomi się sam.

### 2.3. Pierwsze uruchomienie

1. Skopiuj lub rozpakuj katalog projektu na serwer, np. do `C:\Konwerter`.
2. Otwórz PowerShell w tym katalogu: w Eksploratorze kliknij prawym przyciskiem w pustym miejscu folderu i wybierz „Otwórz w terminalu”.
3. Uruchom:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\uruchom-serwer.ps1
   ```

   Skrypt:
   - sprawdza, czy Docker działa,
   - przy pierwszym uruchomieniu tworzy `.env` z pliku `.env.example` i wpisuje losowy `SECRET_KEY`,
   - buduje obraz (pierwszy raz trwa 2–5 minut) i uruchamia kontener w tle,
   - czeka, aż aplikacja odpowie,
   - wypisuje adresy, pod którymi aplikacja jest dostępna, oraz stan poczty.

4. Otwórz na serwerze http://localhost:8000. Powinien pojawić się ekran „Zaloguj się”.

### 2.4. Odblokowanie zapory (jednorazowo)

Bez tego kroku aplikacja działa tylko na serwerze. Otwórz PowerShell **jako administrator** (menu Start → wpisz „PowerShell” → „Uruchom jako administrator”) i wykonaj:

```powershell
New-NetFirewallRule -DisplayName "Konwerter plikow (TCP 8000)" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private,Domain
```

Jeśli skrypt `uruchom-serwer.ps1` zostanie uruchomiony jako administrator, doda tę regułę sam.

Sieć serwera musi mieć profil **Prywatna**: Ustawienia → Sieć i Internet → (Wi-Fi albo Ethernet) → nazwa sieci → Typ profilu sieci → Prywatna. W profilu „Publiczna” Windows blokuje połączenia przychodzące.

### 2.5. Plik konfiguracyjny `.env`

Wszystkie ustawienia są w pliku `.env` w katalogu projektu. Po każdej zmianie uruchom ponownie `uruchom-serwer.ps1`.

| Ustawienie | Domyślnie | Znaczenie |
| --- | --- | --- |
| `APP_ENV` | `development` | `development`: bez SMTP kod pokazuje się na ekranie. `production`: kod tylko e-mailem |
| `SECRET_KEY` | losowy | Klucz do skrótów kodów i sesji. Jego zmiana wylogowuje wszystkich |
| `BIND_ADDRESS` | `0.0.0.0` | `0.0.0.0`: dostęp z sieci; `127.0.0.1`: tylko z serwera |
| `APP_PORT` | `8000` | Port aplikacji |
| `COOKIE_SECURE` | `false` | `true` tylko, gdy klienci łączą się przez HTTPS |
| `SMTP_*` | puste | Konfiguracja poczty (rozdział 3) |
| `ADMIN_EMAILS` | puste | Adresy z dostępem do dziennika, rozdzielone przecinkami |
| `MAX_CONVERSIONS` | `2` | Liczba równoczesnych konwersji; reszta czeka w kolejce |
| `CONVERSION_TIMEOUT_SECONDS` | `1800` | Maksymalny czas jednej konwersji |
| `APP_MEMORY_LIMIT`, `APP_CPUS` | `1536m`, `2.0` | Limity zasobów kontenera |
| `MAX_ACTIVE_USERS` | `10` | Limit jednoczesnych użytkowników (aktywność w ostatnich 15 minutach) |

## 3. Konfiguracja poczty (kody logowania)

Dopóki poczta nie jest skonfigurowana, a `APP_ENV=development`, kod logowania pojawia się na ekranie pod polem „Kod jednorazowy”. Tak można przetestować aplikację, ale **każdy, kto ma dostęp do serwera, może wtedy zalogować się na dowolny adres**. Przed udostępnieniem aplikacji innym osobom skonfiguruj pocztę i ustaw `APP_ENV=production`.

W trybie `production` bez SMTP aplikacja nie udaje wysyłki. Pokazuje komunikat „Wysyłka e-maili nie jest skonfigurowana”.

### 3.1. Gmail (najprostsza opcja)

1. Zaloguj się na konto Google, z którego mają wychodzić kody. Najlepiej załóż do tego osobne konto, np. `konwerter.zespol@gmail.com`.
2. Włącz weryfikację dwuetapową: [myaccount.google.com/security](https://myaccount.google.com/security) → „Weryfikacja dwuetapowa”.
3. Wygeneruj hasło aplikacji: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) → nazwa „Konwerter” → „Utwórz”. Skopiuj 16 liter i pomiń spacje.
4. Wpisz do `.env`:

   ```ini
   APP_ENV=production
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=konwerter.zespol@gmail.com
   SMTP_PASSWORD=abcdefghijklmnop
   SMTP_FROM=konwerter.zespol@gmail.com
   SMTP_STARTTLS=true
   SMTP_SSL=false
   ```

5. Uruchom ponownie serwer i wyślij wiadomość testową:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\uruchom-serwer.ps1
   docker compose exec app python -m app.mailtest twoj.prywatny@adres.pl
   ```

   Wynik `OK – wiadomość wysłana` oznacza, że poczta działa. Przy błędzie program podaje przyczynę i sposób naprawy.

Gmail pozwala wysłać około 500 wiadomości dziennie, co wystarcza dla 10 użytkowników.

### 3.2. Inni dostawcy

| Dostawca | `SMTP_HOST` | `SMTP_PORT` | `SMTP_SSL` / `SMTP_STARTTLS` | Uwagi |
| --- | --- | --- | --- | --- |
| Gmail | `smtp.gmail.com` | `587` | `false` / `true` | hasło aplikacji |
| Brevo (darmowe 300/dzień) | `smtp-relay.brevo.com` | `587` | `false` / `true` | login i klucz SMTP z panelu Brevo; zweryfikuj adres nadawcy |
| WP / Onet / Interia | wg dostawcy, np. `smtp.wp.pl` | `465` | `true` / `false` | włącz dostęp SMTP w ustawieniach skrzynki |
| Własna domena | wg hostingu | `465` lub `587` | wg portu | ustaw SPF, DKIM i DMARC, żeby kody nie trafiały do spamu |

Zasada: port **465** wymaga `SMTP_SSL=true`, a port **587** wymaga `SMTP_SSL=false` i `SMTP_STARTTLS=true`. `SMTP_FROM` powinien być tym samym adresem co `SMTP_USER`, chyba że dostawca pozwala wysyłać z innego.

### 3.3. Testowa skrzynka Mailpit (bez prawdziwej poczty)

Przydaje się na prezentacji bez internetu albo przy testach. Wszystkie wiadomości trafiają do lokalnej skrzynki zamiast do adresatów.

1. W `.env` ustaw `SMTP_HOST=mailpit`, `SMTP_PORT=1025`, `SMTP_STARTTLS=false`, `SMTP_SSL=false` i zostaw `SMTP_USER` puste.
2. Uruchom: `powershell -ExecutionPolicy Bypass -File .\uruchom-serwer.ps1 -Mailpit`.
3. Wiadomości z kodami czytaj na serwerze pod adresem http://localhost:8025.

## 4. Dostęp z innych komputerów

### 4.1. Sieć lokalna (domyślnie)

1. Na serwerze uruchom `uruchom-serwer.ps1` i odczytaj adres z linii „Z innych komputerow”, np. `http://192.168.1.20:8000`. Adres można też sprawdzić poleceniem `ipconfig` (pole „Adres IPv4”).
2. Na komputerze klienta wpisz ten adres w przeglądarce.
3. Jeśli strona się nie otwiera, przejdź do rozdziału 7.

Adres IP serwera może się zmienić po restarcie routera. Żeby był stały, ustaw na routerze rezerwację DHCP dla serwera.

### 4.2. Kiedy sieć lokalna nie wystarczy

Sieci uczelniane, firmowe, hotelowe i publiczne Wi-Fi często mają włączoną **izolację klientów**: urządzenia nie widzą się nawzajem, nawet jeśli są w tej samej sieci. Wtedy:

- użyj własnego routera albo hotspotu z telefonu i podłącz do niego serwer i klientów, albo
- użyj tunelu z punktu 4.3. Działa bez zmian w sieci.

### 4.3. Dostęp z internetu

**A. Tailscale (zalecane dla zespołu, bezpłatne, bez konfiguracji routera)**

1. Zainstaluj [Tailscale](https://tailscale.com/download) na serwerze i na komputerach klientów, a potem zaloguj się wszędzie tym samym kontem albo zaproś członków zespołu.
2. Klienci otwierają `http://NAZWA-SERWERA:8000` albo `http://100.x.y.z:8000` (adres serwera widoczny w aplikacji Tailscale).
3. Aplikacja jest dostępna tylko dla osób w Twojej sieci Tailscale i nie ma limitu wielkości plików.

**B. Cloudflare Tunnel (publiczny adres HTTPS w minutę)**

1. Zainstaluj na serwerze: `winget install Cloudflare.cloudflared`.
2. Uruchom: `cloudflared tunnel --url http://localhost:8000`.
3. W wyjściu pojawi się adres typu `https://losowe-slowa.trycloudflare.com`. Wyślij go klientom.

Ograniczenia: adres zmienia się przy każdym uruchomieniu, a darmowy Cloudflare przyjmuje żądania do **100 MB**, więc większych plików nie da się tą drogą wysłać. Do pełnego limitu 250 MB użyj wariantu A albo C.

**C. Własna domena i HTTPS (wdrożenie docelowe)**

1. Kup domenę i ustaw rekord DNS `A` na publiczny adres IP serwera.
2. Na routerze przekieruj porty **80** i **443** na serwer i dodaj je w zaporze Windows.
3. W `.env` ustaw:

   ```ini
   DOMAIN=konwerter.twoja-domena.pl
   APP_ENV=production
   COOKIE_SECURE=true
   BIND_ADDRESS=127.0.0.1
   ```

   `BIND_ADDRESS=127.0.0.1` sprawia, że z zewnątrz aplikacja jest dostępna wyłącznie przez HTTPS.
4. Uruchom: `docker compose --profile production up -d --build`. Caddy sam pobierze certyfikat HTTPS.
5. Klienci otwierają `https://konwerter.twoja-domena.pl`.

**Ważne:** `COOKIE_SECURE=true` ustawiaj tylko przy HTTPS (wariant C). Jeśli ustawisz go przy zwykłym `http://IP:8000`, przeglądarka nie zapisze sesji i logowanie „nie zadziała”, mimo poprawnego kodu.

## 5. Instrukcja dla użytkownika

### 5.1. Logowanie

1. Otwórz adres aplikacji podany przez administratora.
2. Wpisz swój adres e-mail i kliknij **„Wyślij kod”**. Konto zakłada się automatycznie przy pierwszym logowaniu.
3. Odbierz e-mail „Kod logowania do Konwertera plików” (sprawdź też folder SPAM) i wpisz 6-cyfrowy kod.
   - Kod jest ważny 10 minut i działa tylko raz.
   - Po 5 błędnych próbach kod przestaje działać. Kliknij „Użyj innego adresu” i zamów nowy.
   - Jeden adres może zamówić najwyżej 5 kodów w ciągu 15 minut.
4. Po zalogowaniu urządzenie pamięta Cię przez 30 dni. Na cudzym komputerze zawsze klikaj **„Wyloguj”**.

Komunikat „Serwer jest obecnie zajęty” oznacza, że z aplikacji korzysta już 10 osób. Spróbuj ponownie za kilka minut.

### 5.2. Konwersja plików

1. Dodaj **jeden lub dwa pliki**:
   - przeciągnij je na pole „Upuść pliki tutaj”, albo
   - kliknij **„Importuj pliki”** i wybierz je z dysku.
2. Dla każdego pliku wybierz format docelowy z listy. Dostępne są tylko formaty z tej samej kategorii:

   | Plik źródłowy | Możliwe formaty docelowe |
   | --- | --- |
   | FLAC, MP3, WAV (audio) | dwa pozostałe formaty audio |
   | JPG, PNG, HEIC (obrazy) | dwa pozostałe formaty obrazów |
   | GIF, MP4, MOV (wideo) | dwa pozostałe formaty wideo |

3. Przeczytaj ostrzeżenia pod listą, np. że JPG jest formatem stratnym albo że konwersja MP3 do FLAC nie odzyska utraconej jakości.
4. Kliknij **„Konwertuj”**. Zadanie pojawi się w sekcji „Twoje zadania”.

Ograniczenia: maksymalnie 250 MB na plik i 2 pliki na zadanie. Plik w innym formacie albo z niepasującą zawartością (np. dokument przemianowany na `.png`) zostanie odrzucony z komunikatem.

### 5.3. Statusy i pobieranie wyników

| Status | Znaczenie |
| --- | --- |
| oczekuje | plik czeka w kolejce |
| w toku | trwa konwersja |
| gotowe | wynik można pobrać przyciskiem **„Pobierz”** |
| błąd | konwersja się nie udała (np. plik jest uszkodzony); przycisk **„Ponów”** ponawia próbę |

Statusy odświeżają się same co 3 sekundy. Błąd jednego pliku nie wstrzymuje drugiego. Duże pliki wideo mogą konwertować się kilka minut.

**Wyniki i pliki źródłowe są usuwane 60 minut po zakończeniu konwersji.** Godzina usunięcia jest widoczna przy każdym pliku („Usunięcie: …”). Pobierz wynik przed tym terminem.

## 6. Administracja

### 6.1. Codzienna obsługa

| Czynność | Polecenie (w katalogu projektu) |
| --- | --- |
| Uruchomienie / restart po zmianie `.env` | `powershell -ExecutionPolicy Bypass -File .\uruchom-serwer.ps1` |
| Zatrzymanie | `powershell -ExecutionPolicy Bypass -File .\uruchom-serwer.ps1 -Stop` |
| Stan kontenera | `docker compose ps` |
| Logi na żywo | `docker compose logs -f app` |
| Stan aplikacji i poczty | http://localhost:8000/health |
| Test poczty | `docker compose exec app python -m app.mailtest adres@example.pl` |
| Aktualizacja kodu | podmień pliki projektu i uruchom skrypt ponownie (obraz przebuduje się sam) |

### 6.2. Dziennik administratora

1. Dopisz swój adres do `.env`: `ADMIN_EMAILS=admin@twoja-firma.pl` (kilka adresów rozdziel przecinkami).
2. Uruchom skrypt ponownie i zaloguj się tym adresem.
3. W prawym górnym rogu pojawi się przycisk **„Dziennik administratora”** z ostatnimi wpisami: logowania, nieudane próby, zadania, błędy konwersji i błędy FFmpeg.

Pełny dziennik jest zapisywany w pliku `/var/log/konwerter/application.log` w kontenerze, a nie w bazie danych. Można go skopiować poleceniem:

```powershell
docker compose cp app:/var/log/konwerter/application.log .\application.log
```

### 6.3. Dane i kopie zapasowe

Baza (użytkownicy, sesje, zadania) i pliki są w wolumenach Dockera `converter_data` i `converter_logs`. Przetrwają restart i przebudowę obrazu. Polecenie `docker compose down -v` **usuwa je bezpowrotnie**.

Kopia bazy:

```powershell
docker compose cp app:/var/lib/konwerter/converter.db .\kopia-converter.db
```

### 6.4. Bezpieczeństwo – lista przed udostępnieniem

- [ ] `APP_ENV=production` i działająca poczta (`mailtest` zwraca OK)
- [ ] losowy `SECRET_KEY` (skrypt ustawia go sam przy tworzeniu `.env`)
- [ ] `ADMIN_EMAILS` zawiera tylko zaufane adresy
- [ ] przy dostępie z internetu: HTTPS (rozdział 4.3 C) i `COOKIE_SECURE=true`
- [ ] reguła zapory ograniczona do profilu sieci Prywatna/Domena

## 7. Rozwiązywanie problemów

| Objaw | Przyczyna i rozwiązanie |
| --- | --- |
| Nie przychodzi e-mail z kodem | Uruchom `docker compose exec app python -m app.mailtest twoj@adres.pl` i postępuj według komunikatu. Sprawdź folder SPAM. Na http://localhost:8000/health pole `email` musi mieć wartość `smtp` |
| „Wysyłka e-maili nie jest skonfigurowana” | `APP_ENV=production` bez `SMTP_HOST`. Skonfiguruj pocztę (rozdział 3) albo do testów ustaw `APP_ENV=development` |
| „Nie udało się wysłać kodu” | Serwer SMTP odrzucił połączenie. Szczegóły są w `docker compose logs app`; użyj `mailtest` |
| Strona działa na serwerze, ale nie z innego komputera | 1) brak reguły zapory (rozdział 2.4); 2) profil sieci „Publiczna”; 3) `BIND_ADDRESS=127.0.0.1` w `.env`; 4) izolacja klientów w sieci (rozdział 4.2). Test z klienta: `Test-NetConnection IP-SERWERA -Port 8000` |
| Poprawny kod, ale po zalogowaniu wraca ekran logowania | `COOKIE_SECURE=true` przy połączeniu bez HTTPS. Ustaw `false` |
| Konwersja wideo kończy się błędem | Komunikat błędu jest widoczny pod plikiem, a pełny opis FFmpeg w dzienniku. Upewnij się, że `CONVERTER_MEMORY_MB=0` (niska wartość psuje kodowanie wideo) i że `APP_MEMORY_LIMIT` ma co najmniej `1536m` |
| „Przekroczono limit czasu konwersji” | Bardzo długi film. Zwiększ `CONVERSION_TIMEOUT_SECONDS` i `APP_CPUS` |
| „Serwer jest obecnie zajęty” | W ciągu ostatnich 15 minut aktywnych było 10 użytkowników. Poczekaj albo zwiększ `MAX_ACTIVE_USERS` |
| Skrypt: „Docker nie dziala” | Uruchom Docker Desktop i poczekaj na „Engine running” |
| Port 8000 jest zajęty | Ustaw w `.env` np. `APP_PORT=8080` i używaj adresu z `:8080` |

## 8. Uruchomienie bez Dockera

Wariant dla programistów. Na Windowsie nie działają w nim limity zasobów piaskownicy.

1. Zainstaluj Python 3.12 i FFmpeg: `winget install Python.Python.3.12 Gyan.FFmpeg`. Potem otwórz nowy terminal.
2. W katalogu projektu wykonaj:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements-dev.txt
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

3. Dostęp z innych komputerów działa tak samo jak w rozdziale 4, łącznie z regułą zapory z rozdziału 2.4.
