import socket
import sys

PORT = 1  # Domyślny port do komunikacji

# Funkcja dla serwera (Komputer oczekujący na połączenie)
def uruchom_serwer():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Tworzenie gniazda TCP/IP
    server_socket.bind(("0.0.0.0", PORT)) # Przypisanie gniazda do adresu IP i portu
    server_socket.listen(1) # Tryb nasłuchiwania (na wszystkich dostępnych kartach sieciowych)

    print(f"[SERWER] Oczekiwanie na połączenie na porcie {PORT}...")
    conn, addr = server_socket.accept()
    #conn - gniazdo do transmisji danych z konkretnym klientem
    print(f"[SERWER] Połączono z: {addr}")
    return conn

# Funkcja dla klienta (Komputer inicjujący połączenie)
def uruchom_klient():
    ip = input("IP drugiego komputera").strip()
    if not ip:
        ip = "127.0.0.1"

    # Podobnie jak u serwera tworzymy gniazda i wywołujemy połączenie
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"[KLIENT] Łączenie z {ip}:{PORT}...")
    client_socket.connect((ip, PORT))
    print("[KLIENT] Połączono pomyślnie!")
    return client_socket


def glowna_petla(sock):
    print("\n--- Rozpoczęto komunikację sieciową ---")
    print("Formaty komunikatów:")
    print(" STRZAL;numer(0-99)")
    print(" WYNIK;kod     (0 - pudło, 1 - trafiony, 2 - zatopiony, 3 - koniec)")
    print("Wpisz wiadomość i naciśnij Enter. Aby wyjść, wpisz 'q'.\n")

    while True:
        try:
            # 1. Wysyłanie wiadomości z klawiatury / zakończenie gry
            wiadomosc_do_wyslania = input("WYŚLIJ > ").strip()
            if wiadomosc_do_wyslania.lower() == "q":
                print("Zakończono połączenie.")
                break

            if not wiadomosc_do_wyslania:
                continue

            # Wysyłanie tekstu zakończonego znakiem nowej linii
            sock.sendall((wiadomosc_do_wyslania + "\n").encode("utf-8")) #encode zamienia tekst na bajty

            # 2. Oczekiwanie na odpowiedź
            dane = sock.recv(1024).decode("utf-8")
            if not dane:
                print("Drugi komputer rozłączył się.")
                break

            print(f"OTRZYMANO < {dane.strip()}")

        except Exception as e:
            print(f"Błąd połączenia: {e}")
            break

    sock.close()

if __name__ == "__main__":
    print("Wybierz tryb uruchomienia:")
    print("1 - Czekaj na połączenie (Serwer / Komputer 1)")
    print("2 - Połącz się z drugim komputerem (Klient / Komputer 2)")

    wybor = input("Twój wybór (1/2): ").strip()

    if wybor == "1":
        polaczenie = uruchom_serwer()
        glowna_petla(polaczenie)
    elif wybor == "2":
        polaczenie = uruchom_klient()
        glowna_petla(polaczenie)
    else:
        print("Nieprawidłowy wybór.")