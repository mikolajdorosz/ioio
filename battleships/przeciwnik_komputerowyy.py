import random
import sys

def pobierz_sasiadow(kolumna, wiersz):
    siedzi = []
    # góra, dół, lewo, prawo
    for dk, dw in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
        nk, nw = kolumna + dk, wiersz + dw
        if 1 <= nk <= 8 and 1 <= nw <= 8:
            siedzi.append((nk, nw))
    return siedzi

def graj():
    nieostrzelane = set((k, w) for k in range(1, 9) for w in range(1, 9))
    pola_do_dobicia = set()

    while nieostrzelane:
        # Aktualizacja pól do dobicia (usunięcie tych, które mogły już zostać strzelone)
        pola_do_dobicia = pola_do_dobicia.intersection(nieostrzelane)

        if pola_do_dobicia:
            # 2. Dobijanie
            strzal = pola_do_dobicia.pop()
        else:
            # 1. Szukanie
            parzyste_nieostrzelane = [(k, w) for k, w in nieostrzelane if (k + w) % 2 == 0]
            if parzyste_nieostrzelane:
                strzal = random.choice(parzyste_nieostrzelane)
            else:
                strzal = random.choice(list(nieostrzelane))

        nieostrzelane.remove(strzal)
        # Wypisanie strzału na standardowe wyjście
        print(f"{strzal[0]} {strzal[1]}")
        sys.stdout.flush()

        # Odczyt odpowiedzi ze standardowego wejścia
        try:
            odpowiedz = input().strip().upper()
        except EOFError:
            break

        if odpowiedz == 'T':
            # Po trafieniu dodaj sąsiadujące, nieostrzelane pola do puli dobijania
            sasiedzi = pobierz_sasiadow(strzal[0], strzal[1])
            for sasiad in sasiedzi:
                if sasiad in nieostrzelane:
                    pola_do_dobicia.add(sasiad)
        elif odpowiedz == 'P':
            continue

    if __name__ == "__main__":
        graj()
