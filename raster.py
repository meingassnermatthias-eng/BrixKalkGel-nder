"""
raster.py - Plattenraster einer Fassade in Platten und Positionen umrechnen.

Ablauf:

  1  Raster festlegen - von Hand (Spalten- und Zeilenmasse) oder aus einem DXF
     (beliebiges Linienraster, z. B. auf Layer 0).
  2  Felder zuordnen - Plattentyp je Feld, Fensteroeffnungen wegklicken.
  3  Platten rechnen - Fugenbreite abziehen, Zugabe (Aufkantung) aufschlagen.
  4  Gleichteile suchen - gleiche Platten werden zu einer Position mit
     Stueckzahl gebuendelt. Die Positionen gehen anschliessend ins Nesting.

Alle Masse in Millimeter. Die Rasterlinien gelten als Fugenmitte: zwischen zwei
Feldern wird je Seite die halbe Fuge abgezogen. Am Aussenrand bleibt die Platte
auf der Linie, solange 'rand_fuge' nicht gesetzt ist.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field as datenfeld

TOLERANZ = 0.5          # mm; darunter gelten zwei Masse als gleich
STANDARDTYP = "Standard"

# Schluesselwoerter, die ein Feld als Oeffnung erkennen lassen
OEFFNUNG_WORTE = ("fenster", "tuer", "tür", "oeffnung", "öffnung", "aussparung",
                  "ausschnitt", "verglasung", "luefter", "lüfter", "entfall")


# ==========================================================
# 1. DATENTYPEN
# ==========================================================


@dataclass
class Feld:
    """Ein Rasterfeld der Fassadenansicht."""
    polygon: list                       # [(x, y), ...] gegen den Uhrzeigersinn
    name: str = ""
    typ: str = STANDARDTYP
    aus: bool = False                   # True = Oeffnung, keine Platte
    zeile: int = 0
    spalte: int = 0

    @property
    def bbox(self) -> tuple:
        xs = [p[0] for p in self.polygon]
        ys = [p[1] for p in self.polygon]
        return min(xs), min(ys), max(xs), max(ys)

    @property
    def breite(self) -> float:
        x0, _, x1, _ = self.bbox
        return x1 - x0

    @property
    def hoehe(self) -> float:
        _, y0, _, y1 = self.bbox
        return y1 - y0

    @property
    def flaeche(self) -> float:
        return abs(flaeche(self.polygon))

    @property
    def mitte(self) -> tuple:
        return schwerpunkt(self.polygon)

    @property
    def rechteckig(self) -> bool:
        return len(self.polygon) == 4 and abs(self.flaeche - self.breite * self.hoehe) < 1.0


@dataclass
class Platte:
    """Eine fertige Platte: Feld minus Fuge, plus Zugabe."""
    polygon: list
    feld: Feld
    typ: str = STANDARDTYP

    @property
    def breite(self) -> float:
        xs = [p[0] for p in self.polygon]
        return max(xs) - min(xs)

    @property
    def hoehe(self) -> float:
        ys = [p[1] for p in self.polygon]
        return max(ys) - min(ys)

    @property
    def flaeche(self) -> float:
        return abs(flaeche(self.polygon))


@dataclass
class Position:
    """Mehrere gleiche Platten - eine Position der Stueckliste."""
    nummer: str
    polygon: list                       # im Nullpunkt, gegen den Uhrzeigersinn
    typ: str = STANDARDTYP
    platten: list = datenfeld(default_factory=list)
    gedreht: list = datenfeld(default_factory=list)   # Feldnamen, die gedreht sind
    gespiegelt: list = datenfeld(default_factory=list)
    lagen: dict = datenfeld(default_factory=dict)     # Feldname -> (Winkel, gespiegelt)
    muster: tuple = ()                                # Kennzeichen der Musterlage

    @property
    def anzahl(self) -> int:
        return len(self.platten)

    @property
    def felder(self) -> list:
        return [p.feld.name for p in self.platten]

    @property
    def breite(self) -> float:
        xs = [p[0] for p in self.polygon]
        return max(xs) - min(xs)

    @property
    def hoehe(self) -> float:
        ys = [p[1] for p in self.polygon]
        return max(ys) - min(ys)

    @property
    def flaeche(self) -> float:
        return abs(flaeche(self.polygon))

    @property
    def rechteckig(self) -> bool:
        return len(self.polygon) == 4 and abs(self.flaeche - self.breite * self.hoehe) < 1.0


# ==========================================================
# 2. GEOMETRIE
# ==========================================================


def flaeche(polygon: list) -> float:
    """Vorzeichenbehaftete Flaeche (positiv = gegen den Uhrzeigersinn)."""
    summe = 0.0
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        summe += x1 * y2 - x2 * y1
    return summe / 2.0


def schwerpunkt(polygon: list) -> tuple:
    a = flaeche(polygon)
    if abs(a) < 1e-9:
        xs = [p[0] for p in polygon]
        ys = [p[1] for p in polygon]
        return sum(xs) / len(xs), sum(ys) / len(ys)
    cx = cy = 0.0
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        kreuz = x1 * y2 - x2 * y1
        cx += (x1 + x2) * kreuz
        cy += (y1 + y2) * kreuz
    return cx / (6 * a), cy / (6 * a)


def gegen_uhrzeiger(polygon: list) -> list:
    """Dreht die Punktfolge so, dass sie gegen den Uhrzeigersinn laeuft."""
    return list(polygon) if flaeche(polygon) >= 0 else list(reversed(polygon))


def punkt_in_polygon(punkt, polygon: list) -> bool:
    """Strahlverfahren."""
    x, y = punkt
    drin = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            schnitt = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < schnitt:
                drin = not drin
    return drin


def _normale(a, b) -> tuple:
    """Einheitsnormale links der Richtung a->b (bei CCW zeigt sie nach innen)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    laenge = math.hypot(dx, dy)
    if laenge < 1e-12:
        return 0.0, 0.0
    return -dy / laenge, dx / laenge


def _schnitt(p1, r1, p2, r2):
    """Schnittpunkt der Geraden p1+t*r1 und p2+s*r2, None bei parallel."""
    nenner = r1[0] * r2[1] - r1[1] * r2[0]
    if abs(nenner) < 1e-9:
        return None
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    t = (dx * r2[1] - dy * r2[0]) / nenner
    return p1[0] + t * r1[0], p1[1] + t * r1[1]


def versetze_polygon(polygon: list, abstaende) -> list:
    """
    Versetzt jede Kante um ihren Abstand nach innen (Gehrungsschnitt).

    'abstaende' ist eine Zahl fuer alle Kanten oder eine Liste je Kante
    (Kante i laeuft von Punkt i zu Punkt i+1).
    """
    punkte = gegen_uhrzeiger(polygon)
    n = len(punkte)
    if n < 3:
        return list(polygon)
    if not isinstance(abstaende, (list, tuple)):
        abstaende = [float(abstaende)] * n
    if len(abstaende) != n:
        abstaende = list(abstaende) + [0.0] * (n - len(abstaende))

    geraden = []
    for i in range(n):
        a, b = punkte[i], punkte[(i + 1) % n]
        nx, ny = _normale(a, b)
        d = abstaende[i]
        geraden.append(((a[0] + nx * d, a[1] + ny * d),
                        (b[0] - a[0], b[1] - a[1])))

    neu = []
    for i in range(n):
        vorher = geraden[(i - 1) % n]
        jetzt = geraden[i]
        punkt = _schnitt(vorher[0], vorher[1], jetzt[0], jetzt[1])
        if punkt is None:                       # gestreckte Ecke: Punkt mitnehmen
            nx, ny = _normale(punkte[i], punkte[(i + 1) % n])
            punkt = (punkte[i][0] + nx * abstaende[i], punkte[i][1] + ny * abstaende[i])
        neu.append(punkt)

    neu = _ohne_doppelpunkte(neu)
    if len(neu) < 3 or flaeche(neu) <= 0 or _schneidet_sich(neu):
        return []
    # Bei zu grossem Versatz klappt das Polygon durch: die Kanten schieben sich
    # aneinander vorbei, und es entsteht wieder eine - falsche - Flaeche.
    # Nach innen muss das Ergebnis im Feld liegen, nach aussen umgekehrt.
    if min(abstaende) >= 0:
        if abs(flaeche(neu)) > abs(flaeche(punkte)) + 1e-6:
            return []
        if not _liegt_in(neu, punkte):
            return []
    elif max(abstaende) <= 0:
        if abs(flaeche(neu)) < abs(flaeche(punkte)) - 1e-6:
            return []
        if not _liegt_in(punkte, neu):
            return []
    return neu


def _liegt_in(punkte: list, polygon: list) -> bool:
    """Liegen alle Punkte im Polygon (Punkte auf der Kante zaehlen mit)?"""
    for punkt in punkte:
        if punkt_in_polygon(punkt, polygon):
            continue
        if _abstand_zum_rand(punkt, polygon) <= 1e-6:
            continue                    # Kante ohne Versatz: Punkt liegt darauf
        return False
    return True


def _schneidet_sich(polygon: list) -> bool:
    """Kreuzen sich zwei nicht benachbarte Kanten?"""
    n = len(polygon)
    for i in range(n):
        a1, a2 = polygon[i], polygon[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue                # benachbart ueber den Anfang hinweg
            b1, b2 = polygon[j], polygon[(j + 1) % n]
            if _kreuzt(a1, a2, b1, b2):
                return True
    return False


def _kreuzt(a1, a2, b1, b2) -> bool:
    def richtung(p, q, r):
        wert = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        if abs(wert) < 1e-9:
            return 0
        return 1 if wert > 0 else -1

    d1, d2 = richtung(b1, b2, a1), richtung(b1, b2, a2)
    d3, d4 = richtung(a1, a2, b1), richtung(a1, a2, b2)
    return d1 * d2 < 0 and d3 * d4 < 0


def _abstand_punkt_segment(punkt, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    laenge2 = dx * dx + dy * dy
    if laenge2 < 1e-18:
        return math.hypot(punkt[0] - a[0], punkt[1] - a[1])
    t = ((punkt[0] - a[0]) * dx + (punkt[1] - a[1]) * dy) / laenge2
    t = max(0.0, min(1.0, t))
    return math.hypot(punkt[0] - (a[0] + t * dx), punkt[1] - (a[1] + t * dy))


def _abstand_zum_rand(punkt, polygon: list) -> float:
    n = len(polygon)
    return min(_abstand_punkt_segment(punkt, polygon[i], polygon[(i + 1) % n])
               for i in range(n))


def _ohne_doppelpunkte(punkte: list, tol: float = 1e-6) -> list:
    raus = []
    for p in punkte:
        if not raus or abs(p[0] - raus[-1][0]) > tol or abs(p[1] - raus[-1][1]) > tol:
            raus.append((float(p[0]), float(p[1])))
    while len(raus) > 1 and abs(raus[0][0] - raus[-1][0]) < tol \
            and abs(raus[0][1] - raus[-1][1]) < tol:
        raus.pop()
    return raus


def in_nullpunkt(polygon: list) -> list:
    """Schiebt ein Polygon in den Nullpunkt (linke untere Ecke der Hueelle)."""
    if not polygon:
        return []
    x0 = min(p[0] for p in polygon)
    y0 = min(p[1] for p in polygon)
    return [(p[0] - x0, p[1] - y0) for p in polygon]


def rechteck(x0: float, y0: float, x1: float, y1: float) -> list:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# ==========================================================
# 3. RASTER VON HAND
# ==========================================================


def masse_lesen(text: str) -> list:
    """
    Liest eine Masskette: '1250 1250 900' oder '3x1250, 900' oder '3*1250+900'.

    Rueckgabe: Liste der Einzelmasse in der angegebenen Reihenfolge.
    """
    # Komma mit einer oder zwei Stellen dahinter ist ein Dezimaltrenner
    # ("1250,5"), sonst trennt es zwei Masse ("1250, 900").
    text = re.sub(r",(\d{1,2})(?!\d)", r".\1", str(text or ""))
    masse = []
    for stueck in re.split(r"[,;\n\+]+|\s{1,}", text):
        stueck = stueck.strip().lower().replace(",", ".")
        if not stueck:
            continue
        treffer = re.fullmatch(r"(\d+)\s*[x*]\s*([\d.]+)", stueck)
        if treffer:
            anzahl, mass = int(treffer.group(1)), float(treffer.group(2))
            if mass > 0:
                masse.extend([mass] * max(anzahl, 0))
            continue
        try:
            mass = float(stueck)
        except ValueError:
            continue
        if mass > 0:
            masse.append(mass)
    return masse


def gleiche_teilung(gesamt: float, anzahl: int) -> list:
    """Gesamtmass in 'anzahl' gleiche Felder teilen."""
    anzahl = max(int(anzahl), 1)
    einzel = float(gesamt) / anzahl
    return [einzel] * anzahl


def felder_aus_raster(spalten: list, zeilen: list, x0: float = 0.0,
                      y0: float = 0.0) -> list:
    """
    Baut die Felder eines rechtwinkligen Rasters.

    spalten  Breiten von links nach rechts
    zeilen   Hoehen von oben nach unten (wie in der Ansicht gelesen)
    """
    spalten = [float(s) for s in spalten if float(s) > 0]
    zeilen = [float(z) for z in zeilen if float(z) > 0]
    gesamt_hoehe = sum(zeilen)
    felder = []
    y_oben = y0 + gesamt_hoehe
    for z, hoehe in enumerate(zeilen, start=1):
        x_links = x0
        for s, breite in enumerate(spalten, start=1):
            felder.append(Feld(
                polygon=rechteck(x_links, y_oben - hoehe, x_links + breite, y_oben),
                name=f"Z{z}/S{s}", zeile=z, spalte=s))
            x_links += breite
        y_oben -= hoehe
    return felder


# ==========================================================
# 4. RASTER AUS DXF
# ==========================================================


def _cluster(werte: list, toleranz: float) -> list:
    """Nahe beieinander liegende Koordinaten zu einem Wert zusammenfassen."""
    gruppen = []
    for wert in sorted(werte):
        if gruppen and wert - gruppen[-1][-1] <= toleranz:
            gruppen[-1].append(wert)
        else:
            gruppen.append([wert])
    return [sum(g) / len(g) for g in gruppen]


def _segmente(linienzuege: list) -> list:
    """Linienzuege in Einzelstrecken aufloesen."""
    segmente = []
    for zug in linienzuege:
        punkte = [(float(p[0]), float(p[1])) for p in zug]
        for a, b in zip(punkte, punkte[1:]):
            if abs(a[0] - b[0]) > 1e-9 or abs(a[1] - b[1]) > 1e-9:
                segmente.append((a, b))
    return segmente


def _geschlossene_polygone(linienzuege: list, min_flaeche: float) -> list:
    """Geschlossene Linienzuege (z. B. LWPOLYLINE mit Schliessflag) als Felder."""
    polygone = []
    for zug in linienzuege:
        punkte = _ohne_doppelpunkte([(float(p[0]), float(p[1])) for p in zug])
        if len(punkte) < 3:
            continue
        erst, letzt = zug[0], zug[-1]
        geschlossen = (abs(erst[0] - letzt[0]) < TOLERANZ
                       and abs(erst[1] - letzt[1]) < TOLERANZ)
        if not geschlossen:
            continue
        if abs(flaeche(punkte)) < min_flaeche:
            continue
        polygone.append(gegen_uhrzeiger(punkte))
    return polygone


def felder_aus_linien(linienzuege: list, toleranz: float = 2.0,
                      min_flaeche: float = 10000.0) -> tuple:
    """
    Erkennt die Felder eines beliebigen Linienrasters.

    Arbeitsweise: alle Linien werden an ihren Kreuzungspunkten geteilt und zu
    einem Netz verknuepft. Jede Masche dieses Netzes - jede Flaeche, die
    rundum von Linien umschlossen ist - wird ein Feld. Das funktioniert fuer
    rechtwinklige Raster ebenso wie fuer schiefwinklige oder perspektivisch
    gezeichnete Ansichten, und Felder duerfen beliebig viele Ecken haben.

    Flaechen, deren Rand nicht geschlossen ist, entstehen gar nicht erst: ein
    L-foermiger Umriss bekommt in der offenen Ecke kein Scheinfeld.

    toleranz     Luecken und Ungenauigkeiten bis zu diesem Mass werden
                 ueberbrueckt (Linienenden zusammengezogen, Beruehrpunkte
                 als Kreuzung gewertet)
    min_flaeche  kleinere Maschen gelten als Hilfslinien

    Rueckgabe: (felder, hinweise)
    """
    hinweise = []
    felder = []

    # a) geschlossene Linienzuege sind bereits Felder
    polygone = _geschlossene_polygone(linienzuege, min_flaeche)
    for polygon in polygone:
        felder.append(Feld(polygon=polygon))

    # b) alles uebrige als Netz auswerten
    segmente = _segmente(linienzuege)
    if segmente:
        maschen, netzhinweise = _felder_aus_netz(segmente, toleranz, min_flaeche)
        hinweise.extend(netzhinweise)
        for polygon in maschen:
            # was schon als geschlossenes Polygon erkannt wurde, nicht doppelt
            mitte = schwerpunkt(polygon)
            if any(punkt_in_polygon(mitte, p) for p in polygone):
                continue
            felder.append(Feld(polygon=polygon))

    if not felder and not hinweise:
        hinweise.append("Keine geschlossene Flaeche gefunden - sind die "
                        "Rasterlinien durchgezogen? Groessere Toleranz hilft "
                        "bei Luecken, und der Umriss muss mit ausgewaehlt sein.")

    felder = _benenne(felder)
    return felder, hinweise


# ----------------------------------------------------------
# Ebene Flaechenzerlegung: aus Linien werden Maschen
# ----------------------------------------------------------

HOECHSTE_SEGMENTE = 4000


def _felder_aus_netz(segmente: list, toleranz: float, min_flaeche: float) -> tuple:
    """Zerlegt ein Liniennetz in seine Maschen. Rueckgabe: (polygone, hinweise)"""
    hinweise = []
    if len(segmente) > HOECHSTE_SEGMENTE:
        return [], [f"Zu viele Linien ({len(segmente)}) - bitte nur die Layer "
                    f"mit dem Raster auswaehlen."]

    teile = _teile_an_kreuzungen(segmente, toleranz)
    knoten, kanten = _netz_bauen(teile, toleranz)
    kanten = _enden_kappen(kanten)
    if not kanten:
        return [], ["Keine geschlossene Masche gefunden - die Linien bilden "
                    "keine umschlossene Flaeche."]

    polygone = []
    for masche in _maschen(knoten, kanten):
        polygon = _entferne_gestreckte(_ohne_doppelpunkte(masche))
        if len(polygon) < 3:
            continue
        if flaeche(polygon) < min_flaeche:
            continue                    # zu klein oder Aussenmasche (negativ)
        polygone.append(polygon)
    return polygone, hinweise


def _teile_an_kreuzungen(segmente: list, toleranz: float) -> list:
    """Teilt jede Strecke an allen Kreuzungen und Beruehrpunkten."""
    kaesten = [(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))
               for a, b in segmente]
    stellen = [[0.0, 1.0] for _ in segmente]

    for i in range(len(segmente)):
        a1, a2 = segmente[i]
        for j in range(i + 1, len(segmente)):
            if (kaesten[i][0] > kaesten[j][2] + toleranz
                    or kaesten[j][0] > kaesten[i][2] + toleranz
                    or kaesten[i][1] > kaesten[j][3] + toleranz
                    or kaesten[j][1] > kaesten[i][3] + toleranz):
                continue
            b1, b2 = segmente[j]
            treffer = _kreuzungsstelle(a1, a2, b1, b2, toleranz)
            if treffer is not None:
                t, s = treffer
                stellen[i].append(t)
                stellen[j].append(s)
                continue
            # Beruehrpunkt: Ende der einen Strecke liegt auf der anderen (T-Stoss)
            for punkt, eigen in ((b1, j), (b2, j)):
                t = _lot(punkt, a1, a2)
                if t is not None and _abstand_punkt_segment(punkt, a1, a2) <= toleranz:
                    stellen[i].append(t)
            for punkt in (a1, a2):
                s = _lot(punkt, b1, b2)
                if s is not None and _abstand_punkt_segment(punkt, b1, b2) <= toleranz:
                    stellen[j].append(s)

    teile = []
    for (a, b), liste in zip(segmente, stellen):
        laenge = math.hypot(b[0] - a[0], b[1] - a[1])
        if laenge < 1e-9:
            continue
        grenze = max(toleranz / laenge, 1e-9)
        sortiert = []
        for t in sorted(min(max(t, 0.0), 1.0) for t in liste):
            if not sortiert or t - sortiert[-1] > grenze:
                sortiert.append(t)
        if sortiert[-1] < 1.0 - grenze:
            sortiert.append(1.0)
        for t1, t2 in zip(sortiert, sortiert[1:]):
            p1 = (a[0] + t1 * (b[0] - a[0]), a[1] + t1 * (b[1] - a[1]))
            p2 = (a[0] + t2 * (b[0] - a[0]), a[1] + t2 * (b[1] - a[1]))
            teile.append((p1, p2))
    return teile


def _kreuzungsstelle(a1, a2, b1, b2, toleranz: float):
    """Parameter (t, s) der Kreuzung zweier Strecken, sonst None."""
    r = (a2[0] - a1[0], a2[1] - a1[1])
    s_ = (b2[0] - b1[0], b2[1] - b1[1])
    nenner = r[0] * s_[1] - r[1] * s_[0]
    if abs(nenner) < 1e-12:
        return None                     # parallel oder deckungsgleich
    dx, dy = b1[0] - a1[0], b1[1] - a1[1]
    t = (dx * s_[1] - dy * s_[0]) / nenner
    s = (dx * r[1] - dy * r[0]) / nenner
    la = math.hypot(*r) or 1.0
    lb = math.hypot(*s_) or 1.0
    if -toleranz / la <= t <= 1 + toleranz / la and -toleranz / lb <= s <= 1 + toleranz / lb:
        return min(max(t, 0.0), 1.0), min(max(s, 0.0), 1.0)
    return None


def _lot(punkt, a, b):
    """Fusspunktparameter des Lots, None wenn ausserhalb der Strecke."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    laenge2 = dx * dx + dy * dy
    if laenge2 < 1e-18:
        return None
    t = ((punkt[0] - a[0]) * dx + (punkt[1] - a[1]) * dy) / laenge2
    return t if 0.0 <= t <= 1.0 else None


def _netz_bauen(teile: list, toleranz: float) -> tuple:
    """Zieht nahe Punkte zusammen und baut die Nachbarschaftsliste."""
    knoten: list = []
    raster: dict = {}
    weite = max(toleranz, 1e-6)

    def knoten_fuer(punkt) -> int:
        gx, gy = int(punkt[0] // weite), int(punkt[1] // weite)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for index in raster.get((gx + dx, gy + dy), ()):
                    if math.hypot(knoten[index][0] - punkt[0],
                                  knoten[index][1] - punkt[1]) <= toleranz:
                        return index
        knoten.append((float(punkt[0]), float(punkt[1])))
        raster.setdefault((gx, gy), []).append(len(knoten) - 1)
        return len(knoten) - 1

    kanten: dict = {}
    for a, b in teile:
        ka, kb = knoten_fuer(a), knoten_fuer(b)
        if ka == kb:
            continue
        kanten.setdefault(ka, set()).add(kb)
        kanten.setdefault(kb, set()).add(ka)
    return knoten, kanten


def _enden_kappen(kanten: dict) -> dict:
    """Entfernt freie Enden - sie gehoeren zu keiner Masche."""
    kanten = {k: set(v) for k, v in kanten.items()}
    offen = [k for k, v in kanten.items() if len(v) < 2]
    while offen:
        k = offen.pop()
        for nachbar in list(kanten.get(k, ())):
            kanten[nachbar].discard(k)
            if len(kanten[nachbar]) < 2:
                offen.append(nachbar)
        kanten.pop(k, None)
    return {k: v for k, v in kanten.items() if v}


def _maschen(knoten: list, kanten: dict):
    """
    Laeuft alle Maschen des Netzes ab.

    An jedem Knoten wird die naechste Kante im Uhrzeigersinn genommen - so
    werden die inneren Flaechen gegen den Uhrzeigersinn umrundet (positive
    Flaeche), die Aussenmasche im Uhrzeigersinn (negative Flaeche).
    """
    winkel: dict = {}
    for k, nachbarn in kanten.items():
        liste = sorted(nachbarn,
                       key=lambda n: math.atan2(knoten[n][1] - knoten[k][1],
                                                knoten[n][0] - knoten[k][0]))
        winkel[k] = liste

    benutzt = set()
    for start_k, nachbarn in kanten.items():
        for start_n in nachbarn:
            if (start_k, start_n) in benutzt:
                continue
            masche = []
            k, n = start_k, start_n
            for _ in range(4 * sum(len(v) for v in kanten.values()) + 4):
                benutzt.add((k, n))
                masche.append(knoten[k])
                liste = winkel[n]
                platz = liste.index(k)
                naechster = liste[(platz - 1) % len(liste)]
                k, n = n, naechster
                if (k, n) == (start_k, start_n):
                    break
            else:                       # Reissleine, sollte nie eintreten
                continue
            if len(masche) >= 3:
                yield masche


def _entferne_gestreckte(punkte: list) -> list:
    """Punkte, die auf der Geraden zwischen ihren Nachbarn liegen, weglassen."""
    n = len(punkte)
    if n < 4:
        return punkte
    raus = []
    for i in range(n):
        a, b, c = punkte[(i - 1) % n], punkte[i], punkte[(i + 1) % n]
        kreuz = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        laenge = (math.hypot(b[0] - a[0], b[1] - a[1])
                  * math.hypot(c[0] - b[0], c[1] - b[1]))
        if laenge < 1e-12 or abs(kreuz) / laenge > 1e-4:
            raus.append(b)
    return raus or punkte


def _benenne(felder: list) -> list:
    """
    Vergibt die Feldnamen.

    Bei einem rechtwinkligen Raster zeilenweise als 'Z2/S3' - das liest sich
    auf der Baustelle am leichtesten. Bei schiefwinkligen oder frei
    gezeichneten Ansichten gibt es keine Zeilen und Spalten; dort werden die
    Felder von links oben nach rechts unten durchnumeriert ('F01').
    """
    if not felder:
        return felder
    if all(f.rechteckig for f in felder):
        return _benenne_raster(felder)
    return _benenne_frei(felder)


def _benenne_raster(felder: list) -> list:
    """Zeilenweise Benennung Z<Zeile>/S<Spalte> von links oben."""
    mitten = [f.mitte for f in felder]
    hoehen = _cluster([m[1] for m in mitten],
                      max(10.0, 0.4 * min(f.hoehe for f in felder)))
    hoehen = list(reversed(hoehen))                     # oben zuerst
    reihen: dict = {}
    for feld, mitte in zip(felder, mitten):
        zeile = min(range(len(hoehen)), key=lambda k: abs(hoehen[k] - mitte[1])) + 1
        reihen.setdefault(zeile, []).append(feld)
    geordnet = []
    for zeile in sorted(reihen):
        for spalte, feld in enumerate(sorted(reihen[zeile], key=lambda f: f.mitte[0]),
                                      start=1):
            feld.zeile, feld.spalte = zeile, spalte
            if not feld.name:
                feld.name = f"Z{zeile}/S{spalte}"
            geordnet.append(feld)
    return geordnet


def _benenne_frei(felder: list) -> list:
    """Durchnumerierung von links oben nach rechts unten."""
    geordnet = sorted(felder, key=lambda f: (-f.mitte[1], f.mitte[0]))
    for nummer, feld in enumerate(geordnet, start=1):
        feld.zeile, feld.spalte = 0, 0        # keine Zeilen/Spalten vorhanden
        if not feld.name:
            feld.name = f"F{nummer:02d}"
    return geordnet


def oeffnungen_aus_texten(felder: list, texte: list) -> int:
    """
    Markiert Felder als Oeffnung, in denen ein entsprechender Text steht
    ('Fenster', 'Tuer', 'Aussparung' ...). Rueckgabe: Anzahl der Treffer.
    """
    treffer = 0
    for inhalt, x, y in texte or []:
        klein = str(inhalt).strip().lower()
        if not any(wort in klein for wort in OEFFNUNG_WORTE):
            continue
        for feld in felder:
            if not feld.aus and punkt_in_polygon((x, y), feld.polygon):
                feld.aus = True
                treffer += 1
                break
    return treffer


# ==========================================================
# 5. FELDER -> PLATTEN
# ==========================================================


def _kanten_innen(felder: list, nachbarn: list | None = None,
                  toleranz: float = TOLERANZ) -> dict:
    """
    Fuer jedes Feld je Kante: liegt dahinter ein Nachbarfeld (dann Fuge) oder
    der Aussenrand (dann keine Fuge)?

    'nachbarn' sind die Felder, die als Nachbar zaehlen - standardmaessig die
    Felder selbst. Fensteroeffnungen gehoeren dazu: zur Oeffnung hin braucht
    die Platte ebenso eine Fuge wie zur Nachbarplatte.
    """
    nachbarn = felder if nachbarn is None else nachbarn
    kanten: dict = {}
    for index, feld in enumerate(felder):
        punkte = gegen_uhrzeiger(feld.polygon)
        for i in range(len(punkte)):
            a, b = punkte[i], punkte[(i + 1) % len(punkte)]
            kanten.setdefault(index, []).append((a, b))

    # Grobraster, damit bei vielen Feldern nicht jedes gegen jedes geprueft wird
    eimer, weite = _eimer(nachbarn)

    innen: dict = {}
    for index, liste in kanten.items():
        innen[index] = []
        for (a, b) in liste:
            mx, my = (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0
            nx, ny = _normale(a, b)
            # kurz nach aussen schauen: liegt da ein anderes Feld?
            probe = (mx - nx * (toleranz + 1.0), my - ny * (toleranz + 1.0))
            schluessel = (int(probe[0] // weite), int(probe[1] // weite))
            nachbar = any(f is not felder[index] and punkt_in_polygon(probe, f.polygon)
                          for f in eimer.get(schluessel, ()))
            innen[index].append(nachbar)
    return innen


def _eimer(felder: list) -> tuple:
    """Teilt die Felder in ein Grobraster ein (Nachbarsuche)."""
    if not felder:
        return {}, 1000.0
    weite = max(max(f.breite for f in felder), max(f.hoehe for f in felder), 1.0)
    eimer: dict = {}
    for feld in felder:
        x0, y0, x1, y1 = feld.bbox
        for gx in range(int(x0 // weite), int(x1 // weite) + 1):
            for gy in range(int(y0 // weite), int(y1 // weite) + 1):
                eimer.setdefault((gx, gy), []).append(feld)
    return eimer, weite


def platten_aus_feldern(felder: list, fuge: float = 0.0, zugabe: float = 0.0,
                        rand_fuge: bool = False) -> tuple:
    """
    Rechnet die Felder in Platten um.

    fuge        Fugenbreite zwischen zwei Platten (je Seite die Haelfte)
    zugabe      Aufschlag je Seite, z. B. Aufkantung/Falz der Kassette
    rand_fuge   True = auch am Aussenrand des Rasters die halbe Fuge abziehen

    Rueckgabe: (platten, hinweise)
    """
    hinweise = []
    aktiv = [f for f in felder if not f.aus]
    # Nachbar ist auch eine Oeffnung: zur Fensterlaibung gehoert dieselbe Fuge.
    innen = _kanten_innen(aktiv, felder) if (fuge and not rand_fuge) else {}
    platten = []
    for index, feld in enumerate(aktiv):
        punkte = gegen_uhrzeiger(feld.polygon)
        if fuge and not rand_fuge:
            abstaende = [fuge / 2.0 if nachbar else 0.0
                         for nachbar in innen.get(index, [])]
        else:
            abstaende = [fuge / 2.0] * len(punkte)

        # Zwei Schritte, damit sich Abzug und Aufschlag nicht vermischen:
        # erst die Fuge nach innen, dann die Zugabe nach aussen.
        polygon = versetze_polygon(punkte, abstaende) if any(abstaende) else punkte
        if polygon and zugabe:
            polygon = versetze_polygon(polygon, [-zugabe] * len(polygon))
        if not polygon:
            hinweise.append(f"Feld {feld.name}: Fuge/Zugabe passt nicht zur "
                            f"Feldgroesse - uebersprungen.")
            continue
        platten.append(Platte(polygon=polygon, feld=feld, typ=feld.typ))
    return platten, hinweise


# ==========================================================
# 6. GLEICHTEILSUCHE
# ==========================================================

MODI = {
    "gleich": "nur gleich ausgerichtet",
    "gedreht": "auch um 90/180/270 Grad gedreht",
    "gespiegelt": "auch gedreht und gespiegelt",
}


def _runde(wert: float, toleranz: float) -> float:
    schritt = max(toleranz, 1e-6)
    return round(wert / schritt) * schritt


def _spiegel(polygon: list) -> list:
    """Spiegelt ein Polygon an der senkrechten Achse."""
    return in_nullpunkt([(-x, y) for x, y in polygon])


def _drehe(polygon: list, grad: float) -> list:
    b = math.radians(grad)
    c, s = math.cos(b), math.sin(b)
    return in_nullpunkt([(x * c - y * s, x * s + y * c) for x, y in polygon])


def _ausrichtung(polygon: list, toleranz: float) -> tuple:
    """
    Kennzeichen einer Platte in genau dieser Lage.

    Zwei Platten mit gleichem Kennzeichen sind deckungsgleich, ohne drehen
    oder spiegeln. Der Startpunkt der Punktfolge spielt keine Rolle.
    """
    punkte = gegen_uhrzeiger(_ohne_doppelpunkte(in_nullpunkt(polygon)))
    if not punkte:
        return ()
    kette = tuple((_runde(x, toleranz), _runde(y, toleranz)) for x, y in punkte)
    n = len(kette)
    return min(tuple(kette[(i + k) % n] for k in range(n)) for i in range(n))


def _lagen(modus: str) -> list:
    """Lagen, in denen eine Platte verbaut werden darf: (Winkel, gespiegelt)."""
    lagen = [(0.0, False)]
    if modus in ("gedreht", "gespiegelt"):
        lagen += [(90.0, False), (180.0, False), (270.0, False)]
    if modus == "gespiegelt":
        lagen += [(grad, True) for grad in (0.0, 90.0, 180.0, 270.0)]
    return lagen


def _in_lage(polygon: list, grad: float, gespiegelt: bool) -> list:
    return _drehe(_spiegel(polygon) if gespiegelt else polygon, grad)


def _passt(polygon: list, muster: tuple, modus: str, toleranz: float):
    """(Winkel, gespiegelt), in der die Platte auf das Muster passt - sonst None."""
    for grad, gespiegelt in _lagen(modus):
        if _ausrichtung(_in_lage(polygon, grad, gespiegelt), toleranz) == muster:
            return grad, gespiegelt
    return None


def _fach(platte, toleranz: float) -> tuple:
    """
    Grobes Fach fuer die Vorauswahl.

    Flaeche und die (sortierten) Huellmasse aendern sich beim Drehen und
    Spiegeln nicht - nur Platten im selben Fach koennen gleich sein.
    """
    masse = sorted((platte.breite, platte.hoehe))
    return (platte.typ, _runde(platte.flaeche, 10.0),
            _runde(masse[0], toleranz), _runde(masse[1], toleranz))


def gleichteile(platten: list, modus: str = "gleich",
                toleranz: float = TOLERANZ) -> list:
    """
    Buendelt deckungsgleiche Platten zu Positionen (Gleichteilsuche).

    modus  'gleich'     nur Platten gleicher Groesse und Ausrichtung
           'gedreht'    auch um 90/180/270 Grad gedrehte Platten
           'gespiegelt' zusaetzlich gespiegelte - Vorsicht bei Dekorseite
                        oder Walzrichtung, die Sichtseite dreht sich dabei

    Platten verschiedener Typen werden nie zusammengefasst, auch wenn sie
    gleich gross sind: der Typ steht fuer Material bzw. Farbe.
    """
    if modus not in MODI:
        modus = "gleich"
    faecher: dict = {}
    positionen = []

    for platte in platten:
        fach = _fach(platte, toleranz)
        ziel = None
        for position in faecher.get(fach, []):
            lage = _passt(platte.polygon, position.muster, modus, toleranz)
            if lage is not None:
                ziel = (position, lage)
                break
        if ziel is None:
            position = Position(nummer="", typ=platte.typ,
                                polygon=in_nullpunkt(gegen_uhrzeiger(platte.polygon)))
            position.muster = _ausrichtung(position.polygon, toleranz)
            faecher.setdefault(fach, []).append(position)
            positionen.append(position)
            ziel = (position, (0.0, False))
        position, (grad, gespiegelt) = ziel
        position.platten.append(platte)
        position.lagen[platte.feld.name] = (grad, gespiegelt)
        if gespiegelt:
            position.gespiegelt.append(platte.feld.name)
        elif grad:
            position.gedreht.append(platte.feld.name)

    # groesste Stueckzahl zuerst - so steht in der Liste oben, was zaehlt
    positionen.sort(key=lambda p: (-p.anzahl, -p.flaeche, p.typ))
    for nr, position in enumerate(positionen, start=1):
        position.nummer = f"P{nr:02d}"
    return positionen


# ==========================================================
# 7. LISTEN UND UEBERGABE
# ==========================================================


def positionsliste(positionen: list) -> list:
    """Zeilen der Positionsliste (Stueckliste)."""
    zeilen = []
    for p in positionen:
        zeilen.append({
            "Position": p.nummer,
            "Typ": p.typ,
            "Breite (mm)": round(p.breite, 1),
            "Höhe (mm)": round(p.hoehe, 1),
            "Form": "Rechteck" if p.rechteckig else f"{len(p.polygon)}-Eck",
            "Anzahl": p.anzahl,
            "Fläche/Stück (m²)": round(p.flaeche / 1e6, 3),
            "Fläche gesamt (m²)": round(p.flaeche * p.anzahl / 1e6, 3),
            "Felder": ", ".join(p.felder),
        })
    return zeilen


def feldliste(positionen: list) -> list:
    """Zeilen der Feldliste: welches Feld bekommt welche Position?"""
    # Zeile und Spalte gibt es nur beim rechtwinkligen Raster
    mit_raster = any(platte.feld.spalte for p in positionen for platte in p.platten)
    zeilen = []
    for p in positionen:
        for platte in p.platten:
            feld = platte.feld
            zeile = {"Feld": feld.name}
            if mit_raster:
                zeile["Zeile"] = feld.zeile
                zeile["Spalte"] = feld.spalte
            zeile.update({
                "Position": p.nummer,
                "Typ": p.typ,
                "Breite (mm)": round(platte.breite, 1),
                "Höhe (mm)": round(platte.hoehe, 1),
                "Ecken": len(platte.polygon),
                "gedreht": feld.name in p.gedreht,
                "gespiegelt": feld.name in p.gespiegelt,
            })
            zeilen.append(zeile)
    if mit_raster:
        zeilen.sort(key=lambda z: (z["Zeile"], z["Spalte"]))
    else:
        zeilen.sort(key=lambda z: z["Feld"])
    return zeilen


def kennzahlen(felder: list, platten: list, positionen: list) -> dict:
    """Zahlen fuer die Oberflaeche."""
    aus = [f for f in felder if f.aus]
    return {
        "felder": len(felder),
        "oeffnungen": len(aus),
        "platten": len(platten),
        "positionen": len(positionen),
        "flaeche": sum(p.flaeche for p in platten) / 1e6,
        "rasterflaeche": sum(f.flaeche for f in felder) / 1e6,
        "oeffnungsflaeche": sum(f.flaeche for f in aus) / 1e6,
    }


# ==========================================================
# 8. AUSGABE
# ==========================================================


def position_je_feld(positionen: list) -> dict:
    """Nachschlagewerk Feldname -> Positionsnummer."""
    karte = {}
    for position in positionen:
        for platte in position.platten:
            karte[platte.feld.name] = position.nummer
    return karte


def platte_je_feld(positionen: list) -> dict:
    """Nachschlagewerk Feldname -> Platte."""
    return {platte.feld.name: platte
            for position in positionen for platte in position.platten}


def montageplan_als_dxf(felder: list, positionen: list,
                        mit_platten: bool = True,
                        farben: dict | None = None) -> str:
    """
    Montageplan der Fassade als DXF: Rasterfelder, Platten und Positionsnummern.

    Das ist die Zeichnung fuer die Baustelle - sie zeigt, welche Position in
    welches Feld gehoert und welchen Plattentyp (Farbe) sie bekommt.

    farben  {Plattentyp: Farbname} - dann bekommt jeder Typ einen eigenen
            Layer 'TYP_<name>' in seiner Farbe, der sich in CAD einzeln ein-
            und ausblenden laesst.
    """
    import dxf_import
    from zeichnung import dxf_farbnummer

    nummern = position_je_feld(positionen)
    platten = platte_je_feld(positionen)
    typ_je_feld = {platte.feld.name: position.typ
                   for position in positionen for platte in position.platten}
    polylinien, texte = [], []
    zusatz_layer: dict = {}

    def layer_fuer(typ: str) -> str:
        name = dxf_import._layername(f"TYP_{typ}")
        zusatz_layer.setdefault(name, dxf_farbnummer((farben or {}).get(typ, "")))
        return name

    for feld in felder:
        polylinien.append((list(feld.polygon), "RASTER", True))
        x0, y0, x1, y1 = feld.bbox
        if feld.aus:
            polylinien.append(([(x0, y0), (x1, y1)], "OEFFNUNG", False))
            polylinien.append(([(x0, y1), (x1, y0)], "OEFFNUNG", False))
            continue
        platte = platten.get(feld.name)
        if mit_platten and platte:
            polylinien.append((list(platte.polygon),
                               layer_fuer(typ_je_feld.get(feld.name, STANDARDTYP)),
                               True))

    for feld in felder:
        if feld.aus:
            beschriftung = "Oeffnung"
        else:
            typ = typ_je_feld.get(feld.name, "")
            beschriftung = f"{nummern.get(feld.name, '?')} ({feld.name})"
            if typ and typ != STANDARDTYP:
                beschriftung += f" {typ}"
        hoehe = max(min(feld.hoehe / 10.0, feld.breite / 8.0, 120.0), 15.0)
        mx, my = feld.mitte
        texte.append((beschriftung, mx - len(beschriftung) * hoehe * 0.3,
                      my - hoehe / 2, hoehe, "BESCHRIFTUNG"))

    return dxf_import.zeichnung_als_dxf(polylinien, texte, zusatz_layer)


def material_je_typ(typen: list) -> dict:
    """
    Material je Plattentyp.

    Ein Typ ohne eigenes Material bekommt seinen Namen als Material. Das
    Nesting trennt die Tafeln naemlich nach dem Material - ohne diese Regel
    lagen zwei Farben auf derselben Tafel, und am Blech sieht man nicht, was
    anthrazit und was silber werden soll.
    """
    material = {}
    for eintrag in typen or []:
        name = str(eintrag.get("name", "")).strip()
        if not name:
            continue
        material[name] = str(eintrag.get("material") or "").strip() or name
    return material


def typ_uebersicht(positionen: list, typen: list | None = None) -> list:
    """
    Zeilen je Plattentyp: wieviele Platten, wieviel Flaeche, welches Material.

    Das ist die Liste zum Bestellen - je Farbe eine Zeile.
    """
    angaben = {str(t.get("name")): t for t in (typen or [])}
    zusammen: dict = {}
    for position in positionen:
        eintrag = zusammen.setdefault(position.typ, {"stueck": 0, "flaeche": 0.0,
                                                     "positionen": 0})
        eintrag["stueck"] += position.anzahl
        eintrag["flaeche"] += position.flaeche * position.anzahl
        eintrag["positionen"] += 1
    zeilen = []
    for typ in sorted(zusammen, key=lambda t: -zusammen[t]["flaeche"]):
        angabe = angaben.get(typ, {})
        breite = float(angabe.get("tafel_breite") or 0)
        hoehe = float(angabe.get("tafel_hoehe") or 0)
        zeilen.append({
            "Plattentyp": typ,
            "Farbe": angabe.get("farbe_name", ""),
            "Material": angabe.get("material", ""),
            "Tafel": f"{breite:.0f} x {hoehe:.0f}" if breite and hoehe else "",
            "Positionen": zusammen[typ]["positionen"],
            "Platten": zusammen[typ]["stueck"],
            "Fläche (m²)": round(zusammen[typ]["flaeche"] / 1e6, 2),
        })
    return zeilen


def positionen_als_dxf(positionen: list, spalten: int = 4,
                       abstand: float = 150.0) -> str:
    """Alle Positionen einzeln nebeneinander - zum Abgleich in CAD."""
    import dxf_import

    polylinien, texte = [], []
    x, y, zeilenhoehe, spalte = 0.0, 0.0, 0.0, 0
    for position in positionen:
        punkte = in_nullpunkt(position.polygon)
        polylinien.append(([(px + x, py + y) for px, py in punkte], "KONTUR", True))
        texte.append((f"{position.nummer}  {position.anzahl}x", x, y - 90.0,
                      70.0, "BESCHRIFTUNG"))
        zeilenhoehe = max(zeilenhoehe, position.hoehe)
        x += position.breite + abstand
        spalte += 1
        if spalte >= spalten:
            spalte, x = 0, 0.0
            y += zeilenhoehe + abstand + 120.0
            zeilenhoehe = 0.0
    return dxf_import.zeichnung_als_dxf(polylinien, texte)
