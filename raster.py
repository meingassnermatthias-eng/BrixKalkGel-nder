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


def _index_nahe(werte: list, wert: float, toleranz: float):
    for i, w in enumerate(werte):
        if abs(w - wert) <= toleranz:
            return i
    return None


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

    Arbeitsweise: alle waagrechten und senkrechten Linien bilden ein Gitter.
    Benachbarte Gitterzellen, zwischen denen keine Linie liegt, gehoeren zum
    selben Feld. Ein Feld gilt nur, wenn sein ganzer Rand von Linien gedeckt
    ist - so bleiben Flaechen ausserhalb der Fassade (z. B. bei einem
    L-foermigen Umriss) unberuecksichtigt.

    Rueckgabe: (felder, hinweise)
    """
    hinweise = []
    felder = []

    # a) geschlossene Linienzuege sind bereits Felder (auch schraeg)
    polygone = _geschlossene_polygone(linienzuege, min_flaeche)
    for polygon in polygone:
        felder.append(Feld(polygon=polygon))

    # b) Gitter aus den achsparallelen Linien
    segmente = _segmente(linienzuege)
    waagrecht = [s for s in segmente if abs(s[0][1] - s[1][1]) <= toleranz
                 and abs(s[0][0] - s[1][0]) > toleranz]
    senkrecht = [s for s in segmente if abs(s[0][0] - s[1][0]) <= toleranz
                 and abs(s[0][1] - s[1][1]) > toleranz]
    schraeg = len(segmente) - len(waagrecht) - len(senkrecht)
    if schraeg and not polygone:
        hinweise.append(f"{schraeg} schraege Linie(n) uebersprungen - das Gitter "
                        f"wird aus den waagrechten und senkrechten Linien gebildet.")

    if waagrecht and senkrecht:
        gitterfelder, gitterhinweise = _felder_aus_gitter(
            waagrecht, senkrecht, toleranz, min_flaeche)
        hinweise.extend(gitterhinweise)
        for feld in gitterfelder:
            # Felder, die schon als geschlossenes Polygon erkannt wurden, nicht doppelt
            if any(punkt_in_polygon(feld.mitte, p) for p in polygone):
                continue
            felder.append(feld)
    elif not polygone:
        hinweise.append("Kein Gitter erkannt - es braucht waagrechte und "
                        "senkrechte Linien oder geschlossene Polylinien.")

    felder = _benenne(felder)
    return felder, hinweise


def _felder_aus_gitter(waagrecht: list, senkrecht: list, toleranz: float,
                       min_flaeche: float) -> tuple:
    hinweise = []
    xs = _cluster([p[0] for s in senkrecht for p in s]
                  + [p[0] for s in waagrecht for p in s], toleranz)
    ys = _cluster([p[1] for s in waagrecht for p in s]
                  + [p[1] for s in senkrecht for p in s], toleranz)
    if len(xs) < 2 or len(ys) < 2:
        return [], ["Zu wenige Rasterlinien fuer ein Gitter."]
    if (len(xs) - 1) * (len(ys) - 1) > 40000:
        return [], ["Das Linienraster ist zu feingliedrig (zu viele Schnittpunkte). "
                    "Bitte nur den Rasterlayer waehlen."]

    nx, ny = len(xs) - 1, len(ys) - 1

    # Kantendeckung: liegt auf der Zellkante eine gezeichnete Linie?
    unten = [[False] * nx for _ in range(ny + 1)]      # unten[j][i]: y=ys[j], Spalte i
    links = [[False] * (nx + 1) for _ in range(ny)]    # links[j][i]: x=xs[i], Zeile j

    for (a, b) in waagrecht:
        j = _index_nahe(ys, (a[1] + b[1]) / 2.0, toleranz)
        if j is None:
            continue
        von, bis = sorted((a[0], b[0]))
        for i in range(nx):
            if xs[i] >= von - toleranz and xs[i + 1] <= bis + toleranz:
                unten[j][i] = True
    for (a, b) in senkrecht:
        i = _index_nahe(xs, (a[0] + b[0]) / 2.0, toleranz)
        if i is None:
            continue
        von, bis = sorted((a[1], b[1]))
        for j in range(ny):
            if ys[j] >= von - toleranz and ys[j + 1] <= bis + toleranz:
                links[j][i] = True

    # Zellen verbinden, wo keine Linie trennt
    eltern = list(range(nx * ny))

    def wurzel(k):
        while eltern[k] != k:
            eltern[k] = eltern[eltern[k]]
            k = eltern[k]
        return k

    def verbinde(k1, k2):
        w1, w2 = wurzel(k1), wurzel(k2)
        if w1 != w2:
            eltern[max(w1, w2)] = min(w1, w2)

    for j in range(ny):
        for i in range(nx):
            if i + 1 < nx and not links[j][i + 1]:
                verbinde(j * nx + i, j * nx + i + 1)
            if j + 1 < ny and not unten[j + 1][i]:
                verbinde(j * nx + i, (j + 1) * nx + i)

    gruppen: dict = {}
    for j in range(ny):
        for i in range(nx):
            gruppen.setdefault(wurzel(j * nx + i), []).append((i, j))

    felder = []
    offen = 0
    for zellen in gruppen.values():
        if not _rand_gedeckt(zellen, unten, links, nx, ny):
            offen += 1
            continue
        polygon = _umriss(zellen, xs, ys)
        if len(polygon) < 3 or abs(flaeche(polygon)) < min_flaeche:
            continue
        felder.append(Feld(polygon=gegen_uhrzeiger(polygon)))
    if offen and not felder:
        hinweise.append("Kein geschlossenes Feld gefunden - sind die Rasterlinien "
                        "wirklich durchgezogen? Toleranz erhoehen hilft bei Luecken.")
    return felder, hinweise


def _rand_gedeckt(zellen: list, unten: list, links: list, nx: int, ny: int) -> bool:
    """Ist der Rand einer Zellgruppe vollstaendig von Linien gedeckt?"""
    menge = set(zellen)
    for (i, j) in zellen:
        if (i - 1, j) not in menge and not links[j][i]:
            return False
        if (i + 1, j) not in menge and not links[j][i + 1]:
            return False
        if (i, j - 1) not in menge and not unten[j][i]:
            return False
        if (i, j + 1) not in menge and not unten[j + 1][i]:
            return False
    return True


def _umriss(zellen: list, xs: list, ys: list) -> list:
    """Umriss einer Zellgruppe als Polygon (rechtwinklig, auch L-foermig)."""
    menge = set(zellen)
    kanten = []                      # gerichtete Randkanten, Flaeche links
    for (i, j) in zellen:
        if (i, j - 1) not in menge:                      # untere Kante nach rechts
            kanten.append(((xs[i], ys[j]), (xs[i + 1], ys[j])))
        if (i + 1, j) not in menge:                      # rechte Kante nach oben
            kanten.append(((xs[i + 1], ys[j]), (xs[i + 1], ys[j + 1])))
        if (i, j + 1) not in menge:                      # obere Kante nach links
            kanten.append(((xs[i + 1], ys[j + 1]), (xs[i], ys[j + 1])))
        if (i - 1, j) not in menge:                      # linke Kante nach unten
            kanten.append(((xs[i], ys[j + 1]), (xs[i], ys[j])))

    if not kanten:
        return []
    nachfolger: dict = {}
    for a, b in kanten:
        nachfolger.setdefault(a, []).append(b)

    start = min(nachfolger)
    weg = [start]
    jetzt = start
    for _ in range(len(kanten) + 1):
        ziele = nachfolger.get(jetzt)
        if not ziele:
            break
        jetzt = ziele.pop(0)
        if abs(jetzt[0] - start[0]) < 1e-9 and abs(jetzt[1] - start[1]) < 1e-9:
            break
        weg.append(jetzt)
    return _entferne_gestreckte(weg)


def _entferne_gestreckte(punkte: list) -> list:
    """Punkte auf einer Geraden zwischen Nachbarn weglassen."""
    n = len(punkte)
    if n < 4:
        return punkte
    raus = []
    for i in range(n):
        a, b, c = punkte[(i - 1) % n], punkte[i], punkte[(i + 1) % n]
        kreuz = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if abs(kreuz) > 1e-6:
            raus.append(b)
    return raus or punkte


def _benenne(felder: list) -> list:
    """Vergibt Feldnamen zeilenweise von links oben nach rechts unten."""
    if not felder:
        return felder
    mitten = [f.mitte for f in felder]
    hoehen = _cluster([m[1] for m in mitten], max(
        10.0, 0.4 * min((f.hoehe for f in felder), default=100.0)))
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
    zeilen = []
    for p in positionen:
        for platte in p.platten:
            feld = platte.feld
            zeilen.append({
                "Feld": feld.name,
                "Zeile": feld.zeile,
                "Spalte": feld.spalte,
                "Position": p.nummer,
                "Typ": p.typ,
                "Breite (mm)": round(platte.breite, 1),
                "Höhe (mm)": round(platte.hoehe, 1),
                "gedreht": feld.name in p.gedreht,
                "gespiegelt": feld.name in p.gespiegelt,
            })
    zeilen.sort(key=lambda z: (z["Zeile"], z["Spalte"]))
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
                        mit_platten: bool = True) -> str:
    """
    Montageplan der Fassade als DXF: Rasterfelder, Platten und Positionsnummern.

    Das ist die Zeichnung fuer die Baustelle - sie zeigt, welche Position in
    welches Feld gehoert.
    """
    import dxf_import

    nummern = position_je_feld(positionen)
    platten = platte_je_feld(positionen)
    polylinien, texte = [], []

    for feld in felder:
        polylinien.append((list(feld.polygon), "RASTER", True))
        x0, y0, x1, y1 = feld.bbox
        if feld.aus:
            polylinien.append(([(x0, y0), (x1, y1)], "OEFFNUNG", False))
            polylinien.append(([(x0, y1), (x1, y0)], "OEFFNUNG", False))
            continue
        platte = platten.get(feld.name)
        if mit_platten and platte:
            polylinien.append((list(platte.polygon), "KONTUR", True))

    for feld in felder:
        if feld.aus:
            beschriftung = "Oeffnung"
        else:
            beschriftung = f"{nummern.get(feld.name, '?')} ({feld.name})"
        hoehe = max(min(feld.hoehe / 10.0, feld.breite / 8.0, 120.0), 15.0)
        mx, my = feld.mitte
        texte.append((beschriftung, mx - len(beschriftung) * hoehe * 0.3,
                      my - hoehe / 2, hoehe, "BESCHRIFTUNG"))

    return dxf_import.zeichnung_als_dxf(polylinien, texte)


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
