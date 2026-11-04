"""Sprawdza konfigurację SMTP, wysyłając wiadomość testową.

Użycie:  python -m app.mailtest adres@example.pl
W Dockerze:  docker compose exec app python -m app.mailtest adres@example.pl
"""

from __future__ import annotations

import smtplib
import socket
import ssl
import sys

from .config import settings
from .services import send_email


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Użycie: python -m app.mailtest adres@example.pl")
        return 2
    address = argv[1]
    if not settings.smtp_host:
        print("SMTP_HOST jest pusty w pliku .env – aplikacja nie wyśle żadnej wiadomości.")
        return 1
    mode = "SSL" if settings.smtp_ssl else ("STARTTLS" if settings.smtp_starttls else "bez szyfrowania")
    print(f"Serwer: {settings.smtp_host}:{settings.smtp_port} ({mode}), użytkownik: {settings.smtp_user or '(brak)'}")
    print(f"Nadawca: {settings.smtp_from or settings.smtp_user or 'konwerter@localhost'}")
    try:
        send_email(
            address,
            "Test poczty – Konwerter plików",
            "Ta wiadomość potwierdza, że Konwerter plików może wysyłać kody logowania.",
        )
    except smtplib.SMTPAuthenticationError as exc:
        print(f"BŁĄD logowania do SMTP: {exc}")
        print("Sprawdź SMTP_USER i SMTP_PASSWORD. Gmail wymaga hasła aplikacji (16 znaków), nie zwykłego hasła do konta.")
        return 1
    except (smtplib.SMTPServerDisconnected, ssl.SSLError) as exc:
        print(f"BŁĄD połączenia: {exc}")
        print("Port 465 wymaga SMTP_SSL=true, port 587 wymaga SMTP_SSL=false i SMTP_STARTTLS=true.")
        return 1
    except (socket.gaierror, TimeoutError, ConnectionError, OSError) as exc:
        print(f"BŁĄD sieci: {exc}")
        print("Sprawdź SMTP_HOST i SMTP_PORT oraz czy zapora lub dostawca internetu nie blokuje tego portu.")
        return 1
    except smtplib.SMTPException as exc:
        print(f"BŁĄD SMTP: {exc}")
        print("Częsta przyczyna: SMTP_FROM inny niż adres konta, z którego wysyłasz.")
        return 1
    print(f"OK – wiadomość wysłana do {address}. Sprawdź skrzynkę (także folder SPAM).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
