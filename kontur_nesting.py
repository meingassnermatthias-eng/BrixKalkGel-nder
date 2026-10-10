"""
kontur_nesting.py - Echtes Konturnesting (True Shape Nesting).

Im Gegensatz zum Bounding-Box-Nesting in nesting.py wird hier mit der
tatsaechlichen Teilekontur gerechnet: Teile duerfen ineinandergreifen,
Ausklinkungen und Ausschnitte werden mitgenutzt. Typischer Anwendungsfall
sind Alucobond-Kassetten (Abwicklung mit Eckausklinkungen) und alle
L-, T- oder trapezfoermigen Zuschnitte.

Verfahren
---------
Jede Kontur wird je Drehwinkel in ein Raster umgesetzt (Scanline-Fuellung,
Even-Odd-Regel, dadurch sind Ausschnitte automatisch frei). Die Maske wird
anschliessend um die halbe Schnittfuge aufgeweitet, sodass zwischen zwei
Teilen immer mindestens die volle Schnittfuge frei bleibt.

Platziert wird nach Bottom-Left-Fill mit Schwerkraft: fuer jede Spalte wird
die aktuelle Hoehenlinie der Tafel gefuehrt, das Teil faellt an der guenstigsten
Position nach unten und rutscht dabei in vorhandene Taschen. Die Reihenfolge
(gross zuerst, hoch zuerst, breit zuerst) wird mehrfach durchprobiert, das
beste Ergebnis gewinnt.

Das Raster ist bewusst konservativ: Teile werden nie zu klein gerastert und
die Aufweitung ist immer mindestens eine Rasterzelle. Dadurch kann der
Abstand groesser als die Schnittfuge ausfallen, aber niemals kleiner.
"""

from __future__ import annotations

import math

import numpy as np

from nesting import (
    Ergebnis2D, Platzierung2D, Tafel, Tafelplan, Zuschnitt2D,
    drehe_polygone, optimize_2d, versatz_fuer,
)

STANDARD_WINKEL = (0.0, 90.0, 180.0, 270.0)
FEINE_WINKEL = (0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0)
# Zusaetzlich zu den festen Schritten die Winkel aus der Teileform selbst -
# das ist der Gewinn bei schiefwinkligen Teilen.
FREIE_WINKEL = (0.0, 90.0, 180.0, 270.0, "eigen")
RASTER_MIN, RASTER_MAX = 0.5, 25.0
MAX_ZELLEN = 4_000_000          # Obergrenze je Tafel (Speicher und Laufzeit)


# ==========================================================
# 1. RASTERUNG
# ==========================================================


def rastere_kontur(polygone: list, raster: float, rand: int = 0) -> np.ndarray:
    """
    Setzt eine Kontur (Aussenkontur + Ausschnitte) in eine boolesche Maske um.

    Gerastert wird bewusst nach aussen: eine Zelle gilt als belegt, sobald die
    Kontur sie auch nur beruehrt. Die Maske ueberdeckt das Teil damit immer
    vollstaendig - das ist die Voraussetzung dafuer, dass ueberschneidungsfreie
    Masken auch ueberschneidungsfreie Teile bedeuten.

    Die Polygone muessen im Nullpunkt liegen (siehe drehe_polygone()).
    Zeile 0 der Maske ist unten, Spalte 0 links. 'rand' fuegt ringsum leere
    Zellen an, in die die Aufweitung wachsen kann.
    """
    if not polygone or len(polygone[0]) < 3:
        return np.zeros((1, 1), dtype=bool)

    xs = [x for x, _ in polygone[0]]
    ys = [y for _, y in polygone[0]]
    breite, hoehe = max(xs), max(ys)
    spalten = int(math.ceil(breite / raster - 1e-9)) + 2 * rand
    zeilen = int(math.ceil(hoehe / raster - 1e-9)) + 2 * rand
    maske = np.zeros((max(zeilen, 1), max(spalten, 1)), dtype=bool)

    kanten = []
    eckpunkt_y = set()
    for polygon in polygone:
        n = len(polygon)
        for i in range(n):
            kanten.append((polygon[i], polygon[(i + 1) % n]))
            eckpunkt_y.add(polygon[i][1])
    eckpunkte = sorted(eckpunkt_y)

    winzig = raster * 1e-6
    for zeile in range(maske.shape[0]):
        unten = (zeile - rand) * raster
        oben = unten + raster
        # Abtastlinien: Zellenober- und -unterkante sowie jede Ecke dazwischen
        linien = [unten + winzig, oben - winzig]
        linien += [y for y in eckpunkte if unten < y < oben]

        spannen = []
        for y in linien:
            schnitte = []
            for (x1, y1), (x2, y2) in kanten:
                if (y1 > y) != (y2 > y):
                    schnitte.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
            if len(schnitte) < 2:
                continue
            schnitte.sort()
            spannen.extend(zip(schnitte[0::2], schnitte[1::2]))

        for a, b in spannen:
            von = int(math.floor(a / raster + rand + 1e-9))
            bis = int(math.ceil(b / raster + rand - 1e-9)) - 1
            von, bis = max(von, 0), min(bis, maske.shape[1] - 1)
            if bis >= von:
                maske[zeile, von:bis + 1] = True

    # Sehr schmale Teile duerfen nicht wegrastern
    if not maske.any():
        maske[maske.shape[0] // 2, maske.shape[1] // 2] = True
    return maske


def weite_auf(maske: np.ndarray, zellen: int) -> np.ndarray:
    """
    Weitet eine Maske um 'zellen' Rasterzellen auf (quadratisch, separierbar).

    Quadratisch statt kreisfoermig, weil das Quadrat den Kreis mit demselben
    Radius vollstaendig einschliesst - die Aufweitung deckt die halbe
    Schnittfuge damit garantiert ab.
    """
    if zellen <= 0:
        return maske
    ergebnis = maske.copy()
    for achse in (0, 1):
        gewachsen = ergebnis.copy()
        laenge = ergebnis.shape[achse]
        for versatz in range(1, zellen + 1):
            if versatz >= laenge:
                break
            if achse == 0:
                gewachsen[versatz:, :] |= ergebnis[:laenge - versatz, :]
                gewachsen[:laenge - versatz, :] |= ergebnis[versatz:, :]
            else:
                gewachsen[:, versatz:] |= ergebnis[:, :laenge - versatz]
                gewachsen[:, :laenge - versatz] |= ergebnis[:, versatz:]
        ergebnis = gewachsen
    return ergebnis


def _profile(maske: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Unterkante und Oberkante je Spalte.

    unten[j] = unterste belegte Zeile der Spalte j (grosse Zahl, wenn leer)
    oben[j]  = oberste belegte Zeile der Spalte j (-1, wenn leer)
    """
    zeilen = maske.shape[0]
    belegt = maske.any(axis=0)
    unten = np.where(belegt, maske.argmax(axis=0), 10 ** 6).astype(np.int64)
    oben = np.where(belegt, zeilen - 1 - maske[::-1].argmax(axis=0), -1).astype(np.int64)
    return unten, oben


# ==========================================================
# 2. TEILEVORBEREITUNG
# ==========================================================


def _kontur_von(teil: Zuschnitt2D) -> list:
    """Liefert die Kontur des Teils; ohne DXF-Kontur ein Rechteck."""
    if teil.kontur and len(teil.kontur[0]) >= 3:
        return teil.kontur
    return [[(0.0, 0.0), (teil.breite, 0.0), (teil.breite, teil.hoehe), (0.0, teil.hoehe)]]


EIGENWINKEL = "eigen"           # Drehwinkel aus der Teileform ableiten
EIGENWINKEL_HOECHSTENS = 3      # beste Ausrichtungen je Teil


def _konvexe_huelle(punkte: list) -> list:
    """Konvexe Huelle (Andrews Monotone Chain)."""
    punkte = sorted(set((round(float(x), 4), round(float(y), 4)) for x, y in punkte))
    if len(punkte) < 3:
        return punkte

    def halb(folge):
        rand = []
        for p in folge:
            while len(rand) >= 2:
                (x1, y1), (x2, y2) = rand[-2], rand[-1]
                if (x2 - x1) * (p[1] - y1) - (y2 - y1) * (p[0] - x1) > 1e-9:
                    break
                rand.pop()
            rand.append(p)
        return rand[:-1]

    return halb(punkte) + halb(reversed(punkte))


def _eigenwinkel(kontur: list, hoechstens: int = EIGENWINKEL_HOECHSTENS) -> list:
    """
    Drehwinkel, die das Teil an seinen eigenen Kanten ausrichten.

    Bei schiefwinkligen Teilen (Parallelogramme, Dreiecke, Trapeze) bringen
    feste 90- oder 45-Grad-Schritte nichts: das Teil steht schief auf der
    Tafel und verschenkt Platz. Gedreht man es dagegen so, dass eine seiner
    eigenen Kanten waagrecht liegt, wird die Huellflaeche am kleinsten und
    gleiche Teile greifen ineinander. Genau diese Winkel liefert diese
    Funktion - je Kante der konvexen Huelle einen, die mit der kleinsten
    Huellflaeche zuerst.
    """
    punkte = [p for ring in kontur[:1] for p in ring]
    huelle = _konvexe_huelle(punkte)
    if len(huelle) < 3:
        return []
    bewertet = {}
    for a, b in zip(huelle, huelle[1:] + huelle[:1]):
        grad = round((-math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))) % 90.0, 2)
        if grad in bewertet:
            continue
        _, breite, hoehe = drehe_polygone(kontur, grad)
        bewertet[grad] = breite * hoehe
    beste = sorted(bewertet, key=lambda g: bewertet[g])[:max(hoechstens, 1)]
    winkel = []
    for grad in beste:
        for zusatz in (0.0, 90.0, 180.0, 270.0):
            wert = round((grad + zusatz) % 360.0, 2)
            if wert not in winkel:
                winkel.append(wert)
    return winkel


def _winkel_fuer(teil: Zuschnitt2D, winkel) -> list:
    """
    Erlaubte Drehwinkel eines Teils.

    Nicht drehbare Teile (Walz-/Dekorrichtung, z. B. Alucobond metallic)
    bleiben bei 0 Grad - auch 180 Grad wuerde die Laufrichtung umkehren.

    Steht in der Liste der Eintrag 'eigen', kommen die aus der Teileform
    abgeleiteten Winkel dazu (siehe _eigenwinkel).
    """
    if not teil.drehbar:
        return [0.0]
    fest = [w for w in winkel if not isinstance(w, str)]
    if EIGENWINKEL not in winkel:
        return list(fest)
    erlaubt = list(fest)
    for grad in _eigenwinkel(_kontur_von(teil)):
        if all(abs(grad - w) > 0.05 for w in erlaubt):
            erlaubt.append(grad)
    return erlaubt


def _varianten(teil: Zuschnitt2D, raster: float, aufweitung: int, winkel: tuple) -> list:
    """Rastermasken je erlaubtem Drehwinkel."""
    kontur = _kontur_von(teil)
    varianten = []
    gesehen = set()
    for grad in _winkel_fuer(teil, winkel):
        gedreht, breite, hoehe = drehe_polygone(kontur, grad)
        schluessel = (round(breite, 3), round(hoehe, 3))
        maske = weite_auf(rastere_kontur(gedreht, raster, rand=aufweitung), aufweitung)
        # gleiche Silhouette (z. B. 0 und 180 Grad bei symmetrischen Teilen)
        signatur = (schluessel, maske.tobytes())
        if signatur in gesehen:
            continue
        gesehen.add(signatur)
        unten, oben = _profile(maske)
        varianten.append({
            "winkel": grad,
            "maske": maske,
            # Huellflaeche dieser Drehlage in Rasterzellen - Mass dafuer, wie
            # sparsam das Teil in dieser Lage auf der Tafel liegt
            "huelle": int(maske.shape[0]) * int(maske.shape[1]),
            "zellen": int(maske.sum()),       # belegte Zellen (fuer Vorpruefungen)
            "rand": aufweitung,
            "unten": unten,
            "oben": oben,
            "breite": breite,
            "hoehe": hoehe,
            "versatz": versatz_fuer(kontur, grad),
        })
    return varianten


# ==========================================================
# 2b. VOLLSTAENDIGE POSITIONSSUCHE (fuer Ausschnitte und Taschen)
# ==========================================================
# Die Schwerkraftsuche erreicht nur Positionen, zu denen ein Teil von oben
# herunterfallen kann. Ein Fensterausschnitt mitten in einer Kassette oder eine
# Tasche unter einem Ueberhang bleibt dabei ungenutzt. Fuer die Teile, die per
# Schwerkraft nicht mehr unterkommen, wird deshalb das komplette Stellungsfeld
# durchsucht: die Ueberdeckung aller Positionen auf einmal ueber eine
# Kreuzkorrelation (FFT). Das ist teurer als die Schwerkraftsuche und laeuft
# darum nur fuer die uebrig gebliebenen Teile.


# Soviele Lagen werden hoechstens einzeln genau geprueft, bevor sich die
# Faltung ueber die ganze Tafel lohnt.
KANDIDATEN_GENAU = 1500


def _gute_laenge(n: int) -> int:
    """Naechste FFT-freundliche Laenge (nur Faktoren 2, 3, 5)."""
    while True:
        rest = n
        for teiler in (2, 3, 5):
            while rest % teiler == 0:
                rest //= teiler
        if rest == 1:
            return n
        n += 1


def _fft_form(gitter_form: tuple, masken_form: tuple) -> tuple:
    """Transformationsgroesse ohne zyklische Ueberlappung."""
    return (_gute_laenge(gitter_form[0] + masken_form[0] - 1),
            _gute_laenge(gitter_form[1] + masken_form[1] - 1))


class _Suchspeicher:
    """
    Haelt die Transformationen fuer die Positionssuche.

    Die Masken aendern sich nie - ihre Transformation wird einmal berechnet und
    bleibt. Nur das Gitter aendert sich mit jedem gesetzten Teil; dafuer genuegt
    eine Transformation je Stand. Beides zusammen in einem Speicher, der nach
    jedem Teil geleert wird, war der groesste Zeitfresser: dann wurden auch die
    teuren Maskentransformationen jedes Mal neu gerechnet.

    Alle Masken benutzen dieselbe Transformationsgroesse (nach der groessten
    Maske bemessen) - sonst braeuchte jede Maskengroesse ihre eigene
    Gittertransformation.
    """

    __slots__ = ("form", "masken", "gitter_fft", "stand", "summen", "summen_stand")

    def __init__(self, gitter_form: tuple, groesste_maske: tuple):
        self.form = _fft_form(gitter_form, groesste_maske)
        self.masken: dict = {}
        self.gitter_fft = None
        self.stand = -1
        self.summen = None
        self.summen_stand = -1

    def fuer_gitter(self, gitter: np.ndarray, stand: int):
        if self.stand != stand:
            self.gitter_fft = np.fft.rfft2(gitter.astype(np.float64), s=self.form)
            self.stand = stand
        return self.gitter_fft

    def summentafel(self, gitter: np.ndarray, stand: int):
        """
        Summentafel der belegten Zellen (Integralbild).

        Damit ist in einem Schritt fuer jede Lage ablesbar, wieviel im
        Huellrechteck des Teils belegt ist - viel billiger als eine
        Faltung und genau genug als Vorauswahl.
        """
        if self.summen_stand != stand:
            summen = np.zeros((gitter.shape[0] + 1, gitter.shape[1] + 1),
                              dtype=np.int32)
            np.cumsum(np.cumsum(gitter, axis=0, dtype=np.int32), axis=1,
                      out=summen[1:, 1:])
            self.summen = summen
            self.summen_stand = stand
        return self.summen

    def fuer_maske(self, maske: np.ndarray):
        schluessel = id(maske)
        if schluessel not in self.masken:
            self.masken[schluessel] = np.fft.rfft2(
                maske[::-1, ::-1].astype(np.float64), s=self.form)
        return self.masken[schluessel]


def _freier_platz(gitter: np.ndarray, variante: dict, speicher: "_Suchspeicher",
                  stand: int = 0, freie_zellen: int = -1):
    """
    Sucht die unterste, linkeste freie Position fuer eine Maske - ueberall auf
    der Tafel, auch innerhalb von Ausschnitten. Rueckgabe (zeile, spalte) oder None.
    """
    maske = variante["maske"]
    m_zeilen, m_spalten = maske.shape
    g_zeilen, g_spalten = gitter.shape
    if m_zeilen > g_zeilen or m_spalten > g_spalten:
        return None
    # Billige Vorpruefung: passt die Teileflaeche ueberhaupt noch?
    if 0 <= freie_zellen < int(variante.get("zellen", 0)):
        return None

    # 1. Grobfilter: Im Huellrechteck des Teils duerfen hoechstens so viele
    #    Zellen belegt sein, dass die Zellen des Teils noch frei bleiben
    #    koennen. Wo das nicht gilt, ist eine Ueberschneidung sicher.
    summen = speicher.summentafel(gitter, stand)
    belegt = (summen[m_zeilen:, m_spalten:] - summen[:-m_zeilen, m_spalten:]
              - summen[m_zeilen:, :-m_spalten] + summen[:-m_zeilen, :-m_spalten])
    moeglich = belegt <= (m_zeilen * m_spalten - int(variante["zellen"]))
    anzahl = int(moeglich.sum())
    if anzahl == 0:
        return None

    # 2. Die Kandidaten von unten links her genau pruefen
    if anzahl <= KANDIDATEN_GENAU:
        zeilen, spalten = np.nonzero(moeglich)
        for i in np.lexsort((spalten, zeilen)):
            zeile, spalte = int(zeilen[i]), int(spalten[i])
            if not (gitter[zeile:zeile + m_zeilen,
                           spalte:spalte + m_spalten] & maske).any():
                return zeile, spalte
        return None                   # alle Kandidaten geprueft: kein Platz

    # 3. Zu viele Kandidaten - dann lohnt die Faltung ueber die ganze Tafel
    form = speicher.form
    gitter_fft = speicher.fuer_gitter(gitter, stand)
    masken_fft = speicher.fuer_maske(maske)

    korrelation = np.fft.irfft2(gitter_fft * masken_fft, s=form)
    bereich = korrelation[m_zeilen - 1:g_zeilen, m_spalten - 1:g_spalten]
    frei = bereich < 0.5
    if not frei.any():
        return None

    zeilen, spalten = np.nonzero(frei)
    reihenfolge = np.lexsort((spalten, zeilen))
    for i in reihenfolge[:40]:
        zeile, spalte = int(zeilen[i]), int(spalten[i])
        # Gegenprobe am echten Gitter (die FFT rechnet mit Gleitkommazahlen)
        if not (gitter[zeile:zeile + m_zeilen,
                       spalte:spalte + m_spalten] & maske).any():
            return zeile, spalte
    return None


# ==========================================================
# 3. EINE TAFEL FUELLEN
# ==========================================================


# Hinweis zur Pruefung "liegt hier schon etwas?": Der Ausdruck
#   (gitter[ausschnitt] & maske).any()
# ist rund dreissigmal schneller als gitter[ausschnitt][maske].any() - die
# Form mit eckigen Klammern baut erst eine Kopie aller Maskenzellen auf. Da
# diese Pruefung der haeufigste Schritt im ganzen Verfahren ist, lohnt der
# Unterschied sehr.


def _bester_platz(gitter: np.ndarray, hoehenlinie: np.ndarray, variante: dict,
                  kandidaten: int = 12):
    """
    Sucht die Bottom-Left-Position fuer eine Maske.

    Rueckgabe: (zeile, spalte, verlust) oder None.

    Zuerst wird ueber die Hoehenlinie die tiefstmoegliche Lage je Spalte
    berechnet (schnell und garantiert ueberschneidungsfrei), danach rutscht das
    Teil exakt am Gitter weiter nach unten in vorhandene Taschen. 'verlust' ist
    die Flaeche, die unter dem Teil eingeschlossen wird - je kleiner, desto
    besser fuegt sich das Teil ein (negativ, wenn es eine Tasche fuellt).
    """
    maske = variante["maske"]
    m_zeilen, m_spalten = maske.shape
    g_zeilen, g_spalten = gitter.shape
    if m_spalten > g_spalten or m_zeilen > g_zeilen:
        return None

    fenster = np.lib.stride_tricks.sliding_window_view(hoehenlinie, m_spalten)
    tiefste = np.maximum((fenster - variante["unten"]).max(axis=1), 0)
    moeglich = np.nonzero(tiefste + m_zeilen <= g_zeilen)[0]
    if moeglich.size == 0:
        return None

    reihenfolge = moeglich[np.lexsort((moeglich, tiefste[moeglich]))][:kandidaten]
    belegt = variante["unten"] < 10 ** 5
    bestes = None
    for spalte in reihenfolge:
        spalte = int(spalte)
        zeile = int(tiefste[spalte])
        if (gitter[zeile:zeile + m_zeilen, spalte:spalte + m_spalten] & maske).any():
            continue                  # sollte nicht vorkommen, aber sicher ist sicher
        while zeile > 0:
            probe = zeile - 1
            if (gitter[probe:probe + m_zeilen,
                       spalte:spalte + m_spalten] & maske).any():
                break
            zeile = probe
        verlust = float(np.sum(zeile + variante["unten"][belegt]
                               - hoehenlinie[spalte:spalte + m_spalten][belegt]))
        if bestes is None or (zeile, spalte) < (bestes[0], bestes[1]):
            bestes = (zeile, spalte, verlust)
    return bestes


def _setze(gitter, hoehenlinie, variante, zeile, spalte) -> None:
    """Traegt ein platziertes Teil in Gitter und Hoehenlinie ein."""
    maske = variante["maske"]
    m_zeilen, m_spalten = maske.shape
    gitter[zeile:zeile + m_zeilen, spalte:spalte + m_spalten] |= maske
    belegt = variante["oben"] >= 0
    spalten = np.arange(m_spalten)[belegt] + spalte
    hoehenlinie[spalten] = np.maximum(hoehenlinie[spalten],
                                      variante["oben"][belegt] + zeile + 1)


# Bewertungsstrategien: kleinster Wert gewinnt. Bewertet wird eine moegliche
# Platzierung, beschrieben durch
#   verlust  eingeschlossene Flaeche unter dem Teil (Rasterzellen)
#   zeile    Hoehe der Platzierung        spalte   Lage von links
#   flaeche  echte Groesse des Teils      hoch     Hoehe dieser Drehlage
#   breit    Breite dieser Drehlage       huelle   Huellflaeche dieser Drehlage
#
# Die Strategien unterscheiden sich darin, was zuerst zaehlt: gross, tief,
# flach, schmal oder gut ausgenutzt. Je nach Auftrag gewinnt eine andere -
# darum werden mehrere durchgerechnet und die beste genommen.
#
# 'huelle' entscheidet zwischen den Drehlagen desselben Teils: bei schiefen
# Teilen (Parallelogramm, Trapez, Dreieck) ist die Huelle in der guenstigen
# Lage viel kleiner als in der ungedrehten - ohne dieses Kriterium bliebe das
# Teil flach liegen und verschenkte die halbe Tafel.
def _gross_dicht(lage):
    return (-lage["flaeche"], lage["huelle"], lage["verlust"],
            lage["zeile"], lage["spalte"])


def _tief(lage):
    return (lage["zeile"], lage["hoch"], -lage["flaeche"], lage["spalte"])


def _gross_flach(lage):
    return (-lage["flaeche"], lage["hoch"], lage["verlust"],
            lage["zeile"], lage["spalte"])


def _gross_schmal(lage):
    return (-lage["flaeche"], lage["breit"], lage["verlust"],
            lage["zeile"], lage["spalte"])


def _links_unten(lage):
    return (lage["zeile"], lage["spalte"], -lage["flaeche"], lage["verlust"])


def _tasche(lage):
    return (lage["verlust"], lage["zeile"], -lage["flaeche"], lage["spalte"])


STRATEGIEN = (_gross_dicht, _tief, _gross_flach, _gross_schmal,
              _links_unten, _tasche)


def _fuelle_tafel(typen: list, g_spalten: int, g_zeilen: int, strategie,
                  nachverdichten: bool = True):
    """
    Legt so viele Teile wie moeglich auf eine leere Tafel.

    typen: [{"index", "varianten", "offen", "flaeche"}] - offen = Stueckzahl.
    In jedem Schritt werden alle noch offenen Teilesorten und alle erlaubten
    Drehungen bewertet und die beste Platzierung ausgefuehrt (Best-Fit).

    Rueckgabe: (gesetzte Teile, verbleibende Stueckzahlen je Typindex)
    """
    gitter = np.zeros((g_zeilen, g_spalten), dtype=bool)
    hoehenlinie = np.zeros(g_spalten, dtype=np.int64)
    rest = [{"index": t["index"], "varianten": t["varianten"],
             "offen": t["offen"], "flaeche": t["flaeche"]} for t in typen]
    gesetzt = []

    while any(t["offen"] > 0 for t in rest):
        bestes = None
        for typ in rest:
            if typ["offen"] <= 0:
                continue
            for variante in typ["varianten"]:
                platz = _bester_platz(gitter, hoehenlinie, variante)
                if platz is None:
                    continue
                zeile, spalte, verlust = platz
                bewertung = strategie({
                    "verlust": verlust, "zeile": zeile, "spalte": spalte,
                    "flaeche": typ["flaeche"],
                    "hoch": variante["maske"].shape[0],
                    "breit": variante["maske"].shape[1],
                    "huelle": variante["huelle"],
                })
                if bestes is None or bewertung < bestes[0]:
                    bestes = (bewertung, typ, variante, zeile, spalte)
        if bestes is None:
            break
        _, typ, variante, zeile, spalte = bestes
        _setze(gitter, hoehenlinie, variante, zeile, spalte)
        gesetzt.append((typ["index"], variante, zeile, spalte))
        typ["offen"] -= 1

    if nachverdichten and any(t["offen"] > 0 for t in rest):
        _nachverdichten(gitter, hoehenlinie, rest, gesetzt)

    return gesetzt, {t["index"]: t["offen"] for t in rest}


def _nachverdichten(gitter, hoehenlinie, rest, gesetzt) -> None:
    """
    Zweiter Durchgang fuer die per Schwerkraft nicht platzierten Teile: sucht
    freie Stellen auf der ganzen Tafel, also auch in Ausschnitten und unter
    Ueberhaengen.
    """
    varianten = [v for typ in rest if typ["offen"] > 0 for v in typ["varianten"]]
    if not varianten:
        return
    groesste = (max(v["maske"].shape[0] for v in varianten),
                max(v["maske"].shape[1] for v in varianten))
    speicher = _Suchspeicher(gitter.shape, groesste)
    # Auf dem Gitter kommt nur etwas hinzu, nie etwas weg: was einmal keinen
    # Platz mehr findet, findet auch spaeter keinen. Diese Absagen gelten
    # darum dauerhaft - frueher wurden sie nach jedem Teil verworfen und
    # dieselbe teure Suche wieder und wieder gerechnet.
    ohne_chance: set = set()
    stand = 0
    freie_zellen = int(gitter.size - gitter.sum())

    weiter = True
    while weiter:
        weiter = False
        for typ in rest:
            while typ["offen"] > 0:
                platz = None
                gewaehlt = None
                for variante in typ["varianten"]:
                    if id(variante) in ohne_chance:
                        continue
                    platz = _freier_platz(gitter, variante, speicher, stand,
                                          freie_zellen)
                    if platz is None:
                        ohne_chance.add(id(variante))
                        continue
                    gewaehlt = variante
                    break
                if platz is None:
                    break
                zeile, spalte = platz
                _setze(gitter, hoehenlinie, gewaehlt, zeile, spalte)
                gesetzt.append((typ["index"], gewaehlt, zeile, spalte))
                typ["offen"] -= 1
                stand += 1                    # Gitter hat sich geaendert
                freie_zellen -= int(gewaehlt["zellen"])
                weiter = True


# ==========================================================
# 4. HAUPTFUNKTION
# ==========================================================


def optimize_2d_kontur(
    teile,
    tafeln,
    saegeblatt: float = 5.0,
    besaeumung: float = 0.0,
    raster: float = 5.0,
    winkel: tuple = STANDARD_WINKEL,
    versuche: int = 3,
    nachverdichten: bool = True,
    mindestens_bbox: bool = True,
    verdichten: bool = True,
) -> Ergebnis2D:
    """
    Konturnesting: schachtelt Teile anhand ihrer echten Kontur.

    saegeblatt  Schnittfuge / Fraeserdurchmesser - Mindestabstand zwischen
                zwei Teilen und zum Tafelrand
    besaeumung  umlaufender Randabschnitt der Tafel
    raster      Rasterweite in mm (klein = genauer, aber langsamer)
    winkel      erlaubte Drehwinkel in Grad
    versuche    Anzahl durchprobierter Bewertungsstrategien (1 bis 5)
    nachverdichten  zweiter Durchgang, der Ausschnitte und Taschen unter
                Ueberhaengen mitbenutzt (etwas langsamer)
    verdichten  nach jeder Tafel die Teile mit der echten Geometrie
                nachruecken (die Rasterluft wegnehmen) und den gewonnenen
                Platz noch einmal anbieten
    mindestens_bbox  zusaetzlich das schnelle Bounding-Box-Nesting rechnen und
                dessen Ergebnis nehmen, falls es weniger Tafeln braucht. Damit
                ist das Konturnesting nie schlechter als das einfache Verfahren.

    Die Optimierung laeuft je Material getrennt.
    """
    raster = min(max(float(raster), RASTER_MIN), RASTER_MAX)
    teile = [t for t in teile if t.breite > 0 and t.hoehe > 0 and t.anzahl > 0]
    tafeln = [t for t in tafeln if t.breite > 0 and t.hoehe > 0
              and (t.anzahl is None or t.anzahl > 0)]
    ergebnis = Ergebnis2D()
    if not teile or not tafeln:
        if teile:
            for t in teile:
                ergebnis.fehlende.append((t.bezeichnung, t.breite, t.hoehe, t.anzahl))
        return ergebnis

    # Rasterweite so weit vergroebern, dass die groesste Tafel handhabbar bleibt
    groesste = max(t.breite * t.hoehe for t in tafeln)
    if groesste / (raster * raster) > MAX_ZELLEN:
        gerundet = math.ceil(math.sqrt(groesste / MAX_ZELLEN) * 10) / 10
        ergebnis.hinweise.append(
            f"Rasterweite auf {gerundet:.1f} mm vergroebert - {raster:.1f} mm waeren "
            f"bei dieser Tafelgroesse zu rechenintensiv.")
        raster = min(max(gerundet, RASTER_MIN), RASTER_MAX)

    # Aufweitung je Teil: halbe Schnittfuge, aufgerundet auf Rasterzellen.
    # Zusammen mit der nach aussen gerundeten Rasterung gilt: ueberschneidungs-
    # freie Masken  =>  echte Konturen liegen mindestens die volle Schnittfuge
    # auseinander. Eine zusaetzliche Sicherheitszelle ist deshalb nicht noetig
    # und wuerde nur unnoetig Material kosten.
    aufweitung = int(math.ceil((saegeblatt / 2.0) / raster - 1e-9))

    materialien = []
    for t in teile:
        if t.material not in materialien:
            materialien.append(t.material)

    for material in materialien:
        m_teile = [t for t in teile if t.material == material]
        m_tafeln = [t for t in tafeln if t.material == material]
        if not m_tafeln:
            m_tafeln = [t for t in tafeln if not t.material]
        if not m_tafeln and not material:
            m_tafeln = list(tafeln)
        if not m_tafeln:
            for t in m_teile:
                ergebnis.fehlende.append((t.bezeichnung, t.breite, t.hoehe, t.anzahl))
            continue

        _nest_material(material, m_teile, m_tafeln, raster, aufweitung, besaeumung,
                       winkel, versuche, nachverdichten, mindestens_bbox,
                       saegeblatt, ergebnis, verdichten)

    return ergebnis


def _nest_material(material, m_teile, m_tafeln, raster, aufweitung, besaeumung,
                   winkel, versuche, nachverdichten, mindestens_bbox, saegeblatt,
                   ergebnis: Ergebnis2D, verdichten: bool = True) -> None:
    """Nestet ein einzelnes Material (Hilfsfunktion von optimize_2d_kontur)."""
    typen = []
    for nr, teil in enumerate(m_teile):
        varianten = _varianten(teil, raster, aufweitung, winkel)
        if not varianten:
            continue
        typen.append({
            "index": nr,
            "teil": teil,
            "varianten": varianten,
            "offen": int(teil.anzahl),
            "flaeche": max(v["breite"] * v["hoehe"] for v in varianten),
        })
    if not typen:
        return

    bestes_ergebnis = None
    for strategie in STRATEGIEN[:max(1, min(int(versuche), len(STRATEGIEN)))]:
        plaene, offen = _laufe_durch(typen, m_tafeln, raster, besaeumung, material,
                                     strategie, nachverdichten,
                                     saegeblatt=saegeblatt, aufweitung=aufweitung,
                                     verdichten=verdichten)
        # Reihenfolge der Kriterien: erst moeglichst alles unterbringen,
        # dann moeglichst wenige Tafeln, dann die vollere Tafel.
        bewertung = (sum(offen.values()), len(plaene),
                     -sum(p.belegte_flaeche for p in plaene))
        if bestes_ergebnis is None or bewertung < bestes_ergebnis[0]:
            bestes_ergebnis = (bewertung, plaene, offen)

    _, plaene, offen = bestes_ergebnis

    if mindestens_bbox:
        # Sicherheitsnetz: das schnelle Bounding-Box-Nesting gegenrechnen und
        # uebernehmen, falls es mit weniger Tafeln auskommt.
        einfach = optimize_2d(m_teile, m_tafeln, saegeblatt=saegeblatt,
                              besaeumung=besaeumung, modus="frei")
        offene_bbox = sum(f[3] for f in einfach.fehlende)
        if (offene_bbox, einfach.anzahl_tafeln) < (sum(offen.values()), len(plaene)):
            for plan in einfach.plaene:
                for p in plan.platzierungen:
                    _ergaenze_kontur(p)
            ergebnis.plaene.extend(einfach.plaene)
            ergebnis.fehlende.extend(einfach.fehlende)
            ergebnis.hinweise.append(
                f"{material or 'Ohne Material'}: Das einfache Verfahren kam mit "
                f"{einfach.anzahl_tafeln} statt {len(plaene)} Tafeln aus - dieser Plan "
                f"wurde uebernommen. Das passiert vor allem bei reinen Rechteckteilen.")
            return

    ergebnis.plaene.extend(plaene)
    for typ in typen:
        uebrig = offen.get(typ["index"], 0)
        if uebrig > 0:
            teil = typ["teil"]
            ergebnis.fehlende.append((teil.bezeichnung, teil.breite, teil.hoehe, uebrig))


def _ergaenze_kontur(platzierung: Platzierung2D) -> None:
    """
    Ergaenzt bei Rechteckteilen die Kontur, damit jede Platzierung im
    Konturmodus eine zeichenbare und exportierbare Kontur hat.
    """
    if platzierung.kontur:
        return
    if platzierung.gedreht:
        breite, hoehe = platzierung.hoehe, platzierung.breite
    else:
        breite, hoehe = platzierung.breite, platzierung.hoehe
    platzierung.kontur = [[(0.0, 0.0), (breite, 0.0), (breite, hoehe), (0.0, hoehe)]]


def _laufe_durch(typen, m_tafeln, raster, besaeumung, material, strategie,
                 nachverdichten=True, saegeblatt: float = 0.0,
                 aufweitung: int = 0, verdichten: bool = True):
    """Fuellt so lange Tafeln, bis nichts mehr platzierbar ist."""
    lager = [{"tafel": t, "offen": t.anzahl} for t in m_tafeln]
    lager.sort(key=lambda l: l["tafel"].breite * l["tafel"].hoehe)
    plaene = []
    offen = {t["index"]: t["offen"] for t in typen}
    nach_index = {t["index"]: t for t in typen}
    sicherung = 0

    while sum(offen.values()) > 0 and sicherung < 500:
        sicherung += 1
        bester = None

        aktuell = [{"index": i, "varianten": nach_index[i]["varianten"],
                    "offen": n, "flaeche": nach_index[i]["flaeche"]}
                   for i, n in offen.items() if n > 0]

        for pos in lager:
            if pos["offen"] is not None and pos["offen"] <= 0:
                continue
            tafel = pos["tafel"]
            g_spalten = int(math.floor((tafel.breite - 2 * besaeumung) / raster + 1e-9))
            g_zeilen = int(math.floor((tafel.hoehe - 2 * besaeumung) / raster + 1e-9))
            if g_spalten < 1 or g_zeilen < 1:
                continue

            gesetzt, verbleibend = _fuelle_tafel(aktuell, g_spalten, g_zeilen,
                                                 strategie, nachverdichten)
            if not gesetzt:
                continue

            genutzt = sum(v["breite"] * v["hoehe"] for _, v, _, _ in gesetzt)
            preis = tafel.preis if tafel.preis > 0 else (tafel.breite * tafel.hoehe) / 1e6
            bewertung = preis / genutzt if genutzt else float("inf")
            if bester is None or bewertung < bester[0] - 1e-15:
                bester = (bewertung, pos, gesetzt, verbleibend)

        if bester is None:
            break

        _, pos, gesetzt, verbleibend = bester
        tafel = pos["tafel"]
        plan = Tafelplan(tafel=tafel.bezeichnung, material=material,
                         breite=tafel.breite, hoehe=tafel.hoehe, preis=tafel.preis)

        for index, variante, zeile, spalte in gesetzt:
            teil = nach_index[index]["teil"]
            rand = int(variante.get("rand", 0))
            plan.platzierungen.append(Platzierung2D(
                bezeichnung=teil.bezeichnung,
                x=besaeumung + (spalte + rand) * raster,
                y=besaeumung + (zeile + rand) * raster,
                breite=variante["breite"], hoehe=variante["hoehe"],
                gedreht=abs(variante["winkel"] - 90.0) < 1e-9,
                kontur=_kontur_von(teil),
                stichlinien=teil.stichlinien,
                winkel=variante["winkel"],
                versatz=variante["versatz"],
            ))

        # Rasterluft wegnehmen - und den gewonnenen Platz gleich noch einmal
        # anbieten. Oft geht dadurch noch ein Teil mit auf die Tafel.
        offen = dict(verbleibend)
        if verdichten:
            _verdichte_tafel(plan, nach_index, offen, raster, aufweitung,
                             besaeumung, saegeblatt)

        plaene.append(plan)
        if pos["offen"] is not None:
            pos["offen"] -= 1

    return plaene, offen


# ==========================================================
# 6. NACHRUECKEN: DIE RASTERLUFT WEGNEHMEN
# ==========================================================
# Das Schachteln rechnet im Raster. Dadurch steht jedes Teil bis zu eine
# Rasterzelle weiter vom Nachbarn weg als noetig - bei 5 mm Raster also bis zu
# 5 mm je Seite, bei schiefen Kanten noch mehr. Hier wird jedes Teil mit der
# echten Geometrie so weit nachgerueckt, bis es genau die Schnittfuge zum
# Nachbarn einhaelt. Das macht den Plan dichter und das Restblech groesser.

NACHRUECK_SCHRITTE = (16.0, 8.0, 4.0, 2.0, 1.0, 0.5)


def _segmente_von(ringe: list) -> tuple:
    """Alle Kanten eines Teils als Felder (ax, ay, bx, by)."""
    ax, ay, bx, by = [], [], [], []
    for ring in ringe:
        n = len(ring)
        for i in range(n):
            a, b = ring[i], ring[(i + 1) % n]
            ax.append(a[0]); ay.append(a[1]); bx.append(b[0]); by.append(b[1])
    return (np.array(ax), np.array(ay), np.array(bx), np.array(by))


def _punkt_in_ringen(punkt, ringe: list) -> bool:
    """Even-odd-Regel ueber alle Ringe - Ausschnitte zaehlen als aussen."""
    x, y = punkt
    drin = False
    for ring in ringe:
        n = len(ring)
        for i in range(n):
            x1, y1 = ring[i]
            x2, y2 = ring[(i + 1) % n]
            if (y1 > y) != (y2 > y):
                if x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                    drin = not drin
    return drin


def _kantenabstand(sa: tuple, sb: tuple) -> float:
    """
    Kleinster Abstand zwischen zwei Kantenmengen (alle Paare auf einmal).

    Achtung: Der Abstand ueber die vier Endpunkte allein genuegt nicht - zwei
    sich kreuzende Kanten (wie ein Pluszeichen) haben Abstand 0, obwohl kein
    Endpunkt nahe der anderen Kante liegt. Darum wird zuerst auf Kreuzung
    geprueft.
    """
    a1x, a1y, a2x, a2y = (v[:, None] for v in sa)
    b1x, b1y, b2x, b2y = (v[None, :] for v in sb)

    def seite(px, py, qx, qy, rx, ry):
        return (qx - px) * (ry - py) - (qy - py) * (rx - px)

    d1 = seite(b1x, b1y, b2x, b2y, a1x, a1y)
    d2 = seite(b1x, b1y, b2x, b2y, a2x, a2y)
    d3 = seite(a1x, a1y, a2x, a2y, b1x, b1y)
    d4 = seite(a1x, a1y, a2x, a2y, b2x, b2y)
    if np.any((d1 * d2 < 0) & (d3 * d4 < 0)):
        return 0.0

    def punkt_zu_strecke(px, py, qx, qy, rx, ry):
        dx, dy = rx - qx, ry - qy
        laenge2 = dx * dx + dy * dy
        with np.errstate(invalid="ignore", divide="ignore"):
            t = np.where(laenge2 > 1e-12,
                         ((px - qx) * dx + (py - qy) * dy) / np.where(laenge2 > 1e-12,
                                                                      laenge2, 1.0),
                         0.0)
        t = np.clip(t, 0.0, 1.0)
        return np.hypot(px - (qx + t * dx), py - (qy + t * dy))

    abstand = np.minimum(
        np.minimum(punkt_zu_strecke(a1x, a1y, b1x, b1y, b2x, b2y),
                   punkt_zu_strecke(a2x, a2y, b1x, b1y, b2x, b2y)),
        np.minimum(punkt_zu_strecke(b1x, b1y, a1x, a1y, a2x, a2y),
                   punkt_zu_strecke(b2x, b2y, a1x, a1y, a2x, a2y)))
    return float(abstand.min()) if abstand.size else float("inf")


def _zu_nah(ringe_a: list, ringe_b: list, sa: tuple, sb: tuple,
            mindest: float) -> bool:
    """
    Liegen zwei Teile naeher beieinander als 'mindest'?

    Schneller als der genaue Abstand, weil nur die Frage zaehlt: Zuerst werden
    die Kantenpaare ueber ihre Huellen vorsortiert - nur die wenigen, die
    ueberhaupt nahe genug liegen koennen, werden genau gerechnet. Beim
    Nachruecken ist das der haeufigste Schritt ueberhaupt.
    """
    if _punkt_in_ringen(ringe_a[0][0], ringe_b) or _punkt_in_ringen(ringe_b[0][0],
                                                                    ringe_a):
        return True

    a1x, a1y, a2x, a2y = (v[:, None] for v in sa)
    b1x, b1y, b2x, b2y = (v[None, :] for v in sb)

    # Kreuzen sich zwei Kanten, liegt der Abstand bei 0
    def seite(px, py, qx, qy, rx, ry):
        return (qx - px) * (ry - py) - (qy - py) * (rx - px)

    d1 = seite(b1x, b1y, b2x, b2y, a1x, a1y)
    d2 = seite(b1x, b1y, b2x, b2y, a2x, a2y)
    d3 = seite(a1x, a1y, a2x, a2y, b1x, b1y)
    d4 = seite(a1x, a1y, a2x, a2y, b2x, b2y)
    if np.any((d1 * d2 < 0) & (d3 * d4 < 0)):
        return True

    # Vorauswahl ueber die Huellen der Kanten
    axmin = np.minimum(a1x, a2x); axmax = np.maximum(a1x, a2x)
    aymin = np.minimum(a1y, a2y); aymax = np.maximum(a1y, a2y)
    bxmin = np.minimum(b1x, b2x); bxmax = np.maximum(b1x, b2x)
    bymin = np.minimum(b1y, b2y); bymax = np.maximum(b1y, b2y)
    dx = np.maximum(0.0, np.maximum(axmin - bxmax, bxmin - axmax))
    dy = np.maximum(0.0, np.maximum(aymin - bymax, bymin - aymax))
    nah = (dx * dx + dy * dy) < mindest * mindest
    if not nah.any():
        return False

    i, k = np.nonzero(nah)
    av = tuple(v[i] for v in sa)
    bv = tuple(v[k] for v in sb)
    return _abstand_paare(av, bv) < mindest


def _abstand_paare(sa: tuple, sb: tuple) -> float:
    """Kleinster Abstand einander zugeordneter Kantenpaare."""
    a1x, a1y, a2x, a2y = sa
    b1x, b1y, b2x, b2y = sb

    def punkt_zu_strecke(px, py, qx, qy, rx, ry):
        dx, dy = rx - qx, ry - qy
        laenge2 = dx * dx + dy * dy
        sicher = np.where(laenge2 > 1e-12, laenge2, 1.0)
        t = np.clip(((px - qx) * dx + (py - qy) * dy) / sicher, 0.0, 1.0)
        return np.hypot(px - (qx + t * dx), py - (qy + t * dy))

    werte = np.minimum(
        np.minimum(punkt_zu_strecke(a1x, a1y, b1x, b1y, b2x, b2y),
                   punkt_zu_strecke(a2x, a2y, b1x, b1y, b2x, b2y)),
        np.minimum(punkt_zu_strecke(b1x, b1y, a1x, a1y, a2x, a2y),
                   punkt_zu_strecke(b2x, b2y, a1x, a1y, a2x, a2y)))
    return float(werte.min()) if werte.size else float("inf")


def _teile_abstand(ringe_a: list, ringe_b: list, sa: tuple, sb: tuple) -> float:
    """
    Abstand zweier Teile - 0, wenn sie sich ueberschneiden oder eines im
    anderen liegt.
    """
    if _punkt_in_ringen(ringe_a[0][0], ringe_b) or _punkt_in_ringen(ringe_b[0][0],
                                                                    ringe_a):
        return 0.0
    return _kantenabstand(sa, sb)


def _huelle_von(ringe: list) -> tuple:
    xs = [p[0] for ring in ringe for p in ring]
    ys = [p[1] for ring in ringe for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def _gitter_aus_plan(plan, raster: float, besaeumung: float,
                    aufweitung: int) -> np.ndarray:
    """
    Baut das Rastergitter einer Tafel aus den tatsaechlichen Lagen der Teile.

    Nach dem Nachruecken liegen die Teile nicht mehr auf Rasterpunkten. Darum
    wird jedes Teil an seiner echten Stelle neu gerastert - der Versatz
    innerhalb der Zelle geht dabei mit ein, damit die Maske das Teil wie
    gewohnt vollstaendig ueberdeckt.
    """
    g_spalten = int(math.floor((plan.breite - 2 * besaeumung) / raster + 1e-9))
    g_zeilen = int(math.floor((plan.hoehe - 2 * besaeumung) / raster + 1e-9))
    gitter = np.zeros((max(g_zeilen, 1), max(g_spalten, 1)), dtype=bool)

    for p in plan.platzierungen:
        ringe = p.welt_kontur()
        if not ringe:
            continue
        x0 = min(x for ring in ringe for x, _ in ring) - besaeumung
        y0 = min(y for ring in ringe for _, y in ring) - besaeumung
        spalte0 = int(math.floor(x0 / raster))
        zeile0 = int(math.floor(y0 / raster))
        dx, dy = x0 - spalte0 * raster, y0 - zeile0 * raster
        lokal = [[(x - besaeumung - x0 + dx, y - besaeumung - y0 + dy)
                  for x, y in ring] for ring in ringe]
        maske = weite_auf(rastere_kontur(lokal, raster, rand=aufweitung), aufweitung)
        z = zeile0 - aufweitung
        s = spalte0 - aufweitung
        # Ueberstand an den Raendern abschneiden
        mz0 = max(0, -z)
        ms0 = max(0, -s)
        mz1 = min(maske.shape[0], gitter.shape[0] - z)
        ms1 = min(maske.shape[1], gitter.shape[1] - s)
        if mz1 <= mz0 or ms1 <= ms0:
            continue
        gitter[z + mz0:z + mz1, s + ms0:s + ms1] |= maske[mz0:mz1, ms0:ms1]
    return gitter


def _verdichte_tafel(plan, nach_index: dict, offen: dict, raster: float,
                     aufweitung: int, besaeumung: float, saegeblatt: float,
                     runden: int = 2) -> int:
    """
    Nachruecken und den gewonnenen Platz gleich noch einmal anbieten.

    Rueckgabe: Anzahl der Teile, die dadurch zusaetzlich auf die Tafel passen.
    """
    zusaetzlich = 0
    for _ in range(max(runden, 1)):
        bewegt = nachruecken(plan, saegeblatt, besaeumung)
        if not any(offen.values()):
            break
        if bewegt < 0.5 and zusaetzlich == 0 and _ > 0:
            break

        gitter = _gitter_aus_plan(plan, raster, besaeumung, aufweitung)
        varianten = [v for index, menge in offen.items() if menge > 0
                     for v in nach_index[index]["varianten"]]
        if not varianten:
            break
        groesste = (max(v["maske"].shape[0] for v in varianten),
                    max(v["maske"].shape[1] for v in varianten))
        speicher = _Suchspeicher(gitter.shape, groesste)
        stand = 0
        ohne_chance: set = set()
        neu = 0

        weiter = True
        while weiter:
            weiter = False
            for index in list(offen):
                while offen[index] > 0:
                    gewaehlt = platz = None
                    for variante in nach_index[index]["varianten"]:
                        if id(variante) in ohne_chance:
                            continue
                        platz = _freier_platz(gitter, variante, speicher, stand)
                        if platz is None:
                            ohne_chance.add(id(variante))
                            continue
                        gewaehlt = variante
                        break
                    if platz is None:
                        break
                    zeile, spalte = platz
                    _setze_maske(gitter, gewaehlt["maske"], zeile, spalte)
                    stand += 1
                    teil = nach_index[index]["teil"]
                    rand = int(gewaehlt.get("rand", 0))
                    plan.platzierungen.append(Platzierung2D(
                        bezeichnung=teil.bezeichnung,
                        x=besaeumung + (spalte + rand) * raster,
                        y=besaeumung + (zeile + rand) * raster,
                        breite=gewaehlt["breite"], hoehe=gewaehlt["hoehe"],
                        gedreht=abs(gewaehlt["winkel"] - 90.0) < 1e-9,
                        kontur=_kontur_von(teil), stichlinien=teil.stichlinien,
                        winkel=gewaehlt["winkel"], versatz=gewaehlt["versatz"]))
                    offen[index] -= 1
                    neu += 1
                    weiter = True
        zusaetzlich += neu
        if neu == 0:
            break
    return zusaetzlich


def _setze_maske(gitter: np.ndarray, maske: np.ndarray, zeile: int,
                 spalte: int) -> None:
    gitter[zeile:zeile + maske.shape[0],
           spalte:spalte + maske.shape[1]] |= maske


def nachruecken(plan, saegeblatt: float, besaeumung: float = 0.0,
                runden: int = 2) -> float:
    """
    Rueckt alle Teile einer Tafel so dicht zusammen, wie die Schnittfuge es
    zulaesst - erst nach unten, dann nach links.

    Gerechnet wird mit der echten Kontur, nicht im Raster: der Abstand zum
    Nachbarn wird exakt gemessen und nie kleiner als 'saegeblatt'. Das Teil
    wird nur verschoben, nie gedreht; die Plaene bleiben also gueltig.

    Rueckgabe: wie weit insgesamt nachgerueckt wurde (mm).
    """
    teile = list(plan.platzierungen)
    if not teile:
        return 0.0

    # Je Teil einmal die Grundgeometrie (ohne Tafelposition) aufbauen. Beim
    # Probieren wird davon nur noch der Versatz addiert - das ist um ein
    # Vielfaches billiger, als die Punktlisten jedes Mal neu zu bauen.
    grund_ringe, grund_segmente, grund_huelle = [], [], []
    for p in teile:
        ringe = [[(x - p.x, y - p.y) for x, y in ring] for ring in p.welt_kontur()]
        if not ringe:
            ringe = [[(0.0, 0.0)]]
        grund_ringe.append(ringe)
        grund_segmente.append(_segmente_von(ringe))
        grund_huelle.append(_huelle_von(ringe))

    lage = [(p.x, p.y) for p in teile]

    def huelle_bei(i, x, y):
        x0, y0, x1, y1 = grund_huelle[i]
        return x0 + x, y0 + y, x1 + x, y1 + y

    def segmente_bei(i, x, y):
        ax, ay, bx, by = grund_segmente[i]
        return ax + x, ay + y, bx + x, by + y

    def ringe_bei(i, x, y):
        return [[(px + x, py + y) for px, py in ring] for ring in grund_ringe[i]]

    gewonnen = 0.0

    def frei(i, x, y) -> bool:
        x0, y0, x1, y1 = huelle_bei(i, x, y)
        if (x0 < besaeumung - 1e-6 or y0 < besaeumung - 1e-6
                or x1 > plan.breite - besaeumung + 1e-6
                or y1 > plan.hoehe - besaeumung + 1e-6):
            return False
        meine_segmente = None
        meine_ringe = None
        for k in range(len(teile)):
            if k == i:
                continue
            kx0, ky0, kx1, ky1 = huelle_bei(k, *lage[k])
            if (x0 > kx1 + saegeblatt or kx0 > x1 + saegeblatt
                    or y0 > ky1 + saegeblatt or ky0 > y1 + saegeblatt):
                continue                      # weit genug weg, nicht rechnen
            if meine_segmente is None:
                meine_segmente = segmente_bei(i, x, y)
                meine_ringe = ringe_bei(i, x, y)
            if _zu_nah(meine_ringe, ringe_bei(k, *lage[k]), meine_segmente,
                       segmente_bei(k, *lage[k]), saegeblatt - 1e-6):
                return False
        return True

    for _ in range(max(runden, 1)):
        bewegt = 0.0
        # von unten links her, damit die Luecken nach unten durchgereicht werden
        for i in sorted(range(len(teile)), key=lambda k: (lage[k][1], lage[k][0])):
            for richtung in ((0.0, -1.0), (-1.0, 0.0)):
                for schritt in NACHRUECK_SCHRITTE:
                    while True:
                        x = lage[i][0] + richtung[0] * schritt
                        y = lage[i][1] + richtung[1] * schritt
                        if not frei(i, x, y):
                            break
                        lage[i] = (x, y)
                        bewegt += schritt
        gewonnen += bewegt
        if bewegt < 0.5:
            break

    for p, (x, y) in zip(teile, lage):
        p.x, p.y = x, y
    return gewonnen
