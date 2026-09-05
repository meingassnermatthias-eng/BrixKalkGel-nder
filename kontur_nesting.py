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


def _winkel_fuer(teil: Zuschnitt2D, winkel: tuple) -> list:
    """
    Erlaubte Drehwinkel eines Teils.

    Nicht drehbare Teile (Walz-/Dekorrichtung, z. B. Alucobond metallic)
    bleiben bei 0 Grad - auch 180 Grad wuerde die Laufrichtung umkehren.
    """
    if not teil.drehbar:
        return [0.0]
    return list(winkel)


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


def _freier_platz(gitter: np.ndarray, variante: dict, zwischenspeicher: dict):
    """
    Sucht die unterste, linkeste freie Position fuer eine Maske - ueberall auf
    der Tafel, auch innerhalb von Ausschnitten. Rueckgabe (zeile, spalte) oder None.
    """
    maske = variante["maske"]
    m_zeilen, m_spalten = maske.shape
    g_zeilen, g_spalten = gitter.shape
    if m_zeilen > g_zeilen or m_spalten > g_spalten:
        return None

    form = _fft_form(gitter.shape, maske.shape)
    schluessel = ("gitter", form)
    if schluessel not in zwischenspeicher:
        zwischenspeicher[schluessel] = np.fft.rfft2(gitter.astype(np.float64), s=form)
    gitter_fft = zwischenspeicher[schluessel]

    masken_schluessel = ("maske", id(maske), form)
    if masken_schluessel not in zwischenspeicher:
        zwischenspeicher[masken_schluessel] = np.fft.rfft2(
            maske[::-1, ::-1].astype(np.float64), s=form)
    masken_fft = zwischenspeicher[masken_schluessel]

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
        if not gitter[zeile:zeile + m_zeilen, spalte:spalte + m_spalten][maske].any():
            return zeile, spalte
    return None


# ==========================================================
# 3. EINE TAFEL FUELLEN
# ==========================================================


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
        if gitter[zeile:zeile + m_zeilen, spalte:spalte + m_spalten][maske].any():
            continue                  # sollte nicht vorkommen, aber sicher ist sicher
        while zeile > 0:
            probe = zeile - 1
            if gitter[probe:probe + m_zeilen, spalte:spalte + m_spalten][maske].any():
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


# Bewertungsstrategien: kleinster Wert gewinnt. Uebergeben werden
#   verlust  eingeschlossene Flaeche unter dem Teil (Rasterzellen)
#   zeile    Hoehe der Platzierung        spalte  Lage von links
#   flaeche  Groesse des Teils            hoch    Hoehe der gedrehten Lage
# Die Strategien unterscheiden sich vor allem darin, ob zuerst gross, zuerst
# tief oder zuerst flach gelegt wird - je nach Auftrag gewinnt eine andere.
STRATEGIEN = (
    lambda verlust, zeile, spalte, flaeche, hoch: (-flaeche, hoch, verlust, zeile, spalte),
    lambda verlust, zeile, spalte, flaeche, hoch: (zeile, hoch, -flaeche, spalte),
    lambda verlust, zeile, spalte, flaeche, hoch: (-flaeche, verlust, zeile, spalte),
    lambda verlust, zeile, spalte, flaeche, hoch: (zeile, spalte, -flaeche, verlust),
    lambda verlust, zeile, spalte, flaeche, hoch: (verlust, zeile, -flaeche, spalte),
)


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
                bewertung = strategie(verlust, zeile, spalte, typ["flaeche"],
                                      variante["maske"].shape[0])
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
    zwischenspeicher: dict = {}
    ohne_chance: set = set()          # Varianten, die auf dem aktuellen Gitter scheitern

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
                    platz = _freier_platz(gitter, variante, zwischenspeicher)
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
                zwischenspeicher.clear()      # Gitter hat sich geaendert
                ohne_chance.clear()
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
                       saegeblatt, ergebnis)

    return ergebnis


def _nest_material(material, m_teile, m_tafeln, raster, aufweitung, besaeumung,
                   winkel, versuche, nachverdichten, mindestens_bbox, saegeblatt,
                   ergebnis: Ergebnis2D) -> None:
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
                                     strategie, nachverdichten)
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
                 nachverdichten=True):
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

        plaene.append(plan)
        offen = dict(verbleibend)
        if pos["offen"] is not None:
            pos["offen"] -= 1

    return plaene, offen
