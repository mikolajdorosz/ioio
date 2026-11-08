from silnik_regul import SilnikStatkow

def testy_silnika():
    print("1. TEST Z PRZYKŁADU")
    silnik = SilnikStatkow()

    silnik.statki.clear()
    silnik.ostrzelane_pola.clear()
    silnik.statki[1] = {(3, 4), (3, 5)}
    
    print(f"Strzał (0, 0): {silnik.strzal(0, 0).value}")
    print(f"Strzał (3, 4): {silnik.strzal(3, 4).value}")
    print(f"Strzał (3, 5): {silnik.strzal(3, 5).value}")
    try:
        silnik.strzal(3, 5)
    except ValueError as e:
        print(f"Strzał (3, 5) ponownie: {e}")


    print("\n 2. TEST ROZGRYWKI (GRA KOMPUTER vs GRACZ)")
    gracz = SilnikStatkow()
    komputer = SilnikStatkow()
    # w grze uczestniczą obiekty dwóch graczy, spełniając wymóg równoległej obsługi dwóch plansz
    
    print("Początkowy status 'Koniec gry' dla gracza:", gracz.koniec_gry())
    
    # pobieramy lokalizację wszystkich statków gracza, by przeprowadzić test pełnego zatopienia
    wszystkie_pozycje = []
    for segmenty in gracz.statki.values():
        wszystkie_pozycje.extend(list(segmenty))
        
    print(f"Silnik wygenerował losową flotę o rozmiarze {len(wszystkie_pozycje)} pól.")
    
    # strzelamy i zatapiamy całą flotę
    print("Rozpoczęcie serii strzałów komputera w planszę gracza...")
    for (w, k) in wszystkie_pozycje:
        wynik = gracz.strzal(w, k)
    
    print("Wynik ostatniego strzału w ostatni statek:", wynik.value)
    print("Czy po serii strzałów niszczących flotę zgłoszony jest koniec gry?:", gracz.koniec_gry())

if __name__ == "__main__":
    testy_silnika()
