import random
from enum import Enum

class WynikStrzalu(Enum):
    PUDLO = "PUDŁO"
    TRAFIONY = "TRAFIONY"
    ZATOPIONY = "ZATOPIONY"

class SilnikStatkow:
    def __init__(self):
        self.rozmiar = 10
        self.flota = [4, 3, 3, 2, 2, 2]
        self.statki = {}
        
        self.ostrzelane_pola = set()
        self.nowa_plansza()

    def nowa_plansza(self):
        self.statki.clear()
        self.ostrzelane_pola.clear()

        plansza_wewnetrzna = [[0] * self.rozmiar for _ in range(self.rozmiar)]
        id_statku = 1

        for dlugosc in self.flota:
            umieszczony = False
            while not umieszczony:
                wiersz = random.randint(0, self.rozmiar - 1)
                kolumna = random.randint(0, self.rozmiar - 1)
                poziomo = random.choice([True, False])
                
                if self._czy_mozna_umiescic(plansza_wewnetrzna, wiersz, kolumna, dlugosc, poziomo):
                    self.statki[id_statku] = set()
                    for i in range(dlugosc):
                        w = wiersz if poziomo else wiersz + i
                        k = kolumna + i if poziomo else kolumna
                        plansza_wewnetrzna[w][k] = id_statku
                        self.statki[id_statku].add((w, k))
                    id_statku += 1
                    umieszczony = True

    def _czy_mozna_umiescic(self, plansza, wiersz, kolumna, dlugosc, poziomo):
        # sprawdza czy statek mieści się na planszy i nie nachodzi na inne statki
        if poziomo:
            if kolumna + dlugosc > self.rozmiar: return False
            for i in range(dlugosc):
                if plansza[wiersz][kolumna + i] != 0: return False # kolizja (nachodzenie)
        else:
            if wiersz + dlugosc > self.rozmiar: return False
            for i in range(dlugosc):
                if plansza[wiersz + i][kolumna] != 0: return False # kolizja (nachodzenie)
        return True

    def strzal(self, wiersz, kolumna):
        # rozstrzyga strzał i weryfikuje jego poprawność
        if not (0 <= wiersz < self.rozmiar and 0 <= kolumna < self.rozmiar):
            raise ValueError(f"błąd: strzał poza planszę ({wiersz}, {kolumna})")
            
        if (wiersz, kolumna) in self.ostrzelane_pola:
            raise ValueError("błąd: pole już ostrzelane")
            
        self.ostrzelane_pola.add((wiersz, kolumna))
        
        for id_statku, segmenty in self.statki.items():
            if (wiersz, kolumna) in segmenty:
                segmenty.remove((wiersz, kolumna))
                if not segmenty:
                    return WynikStrzalu.ZATOPIONY
                else:
                    return WynikStrzalu.TRAFIONY
                    
        return WynikStrzalu.PUDLO

    def koniec_gry(self):
        # sprawdza czy wszystkie statki na planszy zostały zatopione
        return all(len(segmenty) == 0 for segmenty in self.statki.values())
