"""
nesting.py - Rechenkern fuer die Verschnittoptimierung (Nesting).

Enthaelt keine Streamlit-/Pandas-Abhaengigkeiten, damit die Logik separat
getestet und auch von anderen Skripten verwendet werden kann.

Zwei Betriebsarten:

  1D  Stangen- und Profilzuschnitt (Rohre, Flachstahl, Handlauf, ...)
      -> optimize_1d()

  2D  Blechzuschnitt / Plattenzuschnitt (Tafeln, Bleche, Glas, ...)
      -> optimize_2d()

Alle Laengenangaben in Millimetern.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Optional

# ==========================================================
# 1. DATENSTRUKTUREN
# ==========================================================


@dataclass
class Teil:
    """Ein zu schneidendes Teil (1D)."""
    laenge: float
    anzahl: int = 1
    bezeichnung: str = "Teil"
    profil: str = ""          # Materialgruppe, z.B. "Rohr 40x40x2"


@dataclass
class Stange:
    """Eine verfuegbare Rohstange / Lagerlaenge (1D)."""
    laenge: float
    anzahl: Optional[int] = None   # None = unbegrenzt verfuegbar
    bezeichnung: str = "Stange"
    profil: str = ""
    preis: float = 0.0             # EUR pro Stange (0 = unbekannt)
    reststueck: bool = False       # True = Reststueck aus dem Lager


@dataclass
class Platzierung1D:
    """Ein Teil an einer konkreten Position auf der Stange."""
    bezeichnung: str
    laenge: float
    start: float
    ende: float


@dataclass
class Stangenplan:
    """Schnittplan fuer genau eine Stange."""
    stange: str
    profil: str
    stangen_laenge: float
    nutzlaenge: float                       # nach Anschnitt/Endschnitt
    platzierungen: list[Platzierung1D] = field(default_factory=list)
    rest: float = 0.0                       # Reststueck am Stangenende
    rest_verwertbar: bool = False
    preis: float = 0.0
    reststueck: bool = False

    @property
    def belegt(self) -> float:
        return sum(p.laenge for p in self.platzierungen)

    @property
    def anzahl_teile(self) -> int:
        return len(self.platzierungen)

    @property
    def ausnutzung(self) -> float:
        """Anteil Nutzteil an der Gesamtstange (0..1)."""
        return self.belegt / self.stangen_laenge if self.stangen_laenge else 0.0


@dataclass
class Ergebnis1D:
    plaene: list[Stangenplan] = field(default_factory=list)
    fehlende: list[tuple[str, float, int]] = field(default_factory=list)
    # (bezeichnung, laenge, anzahl) fuer Teile, die auf keine Stange passen

    # --- Kennzahlen -------------------------------------------------
    @property
    def anzahl_stangen(self) -> int:
        return len(self.plaene)

    @property
    def gesamt_material(self) -> float:
        return sum(p.stangen_laenge for p in self.plaene)

    @property
    def gesamt_nutzteil(self) -> float:
        return sum(p.belegt for p in self.plaene)

    @property
    def gesamt_kosten(self) -> float:
        return sum(p.preis for p in self.plaene)

    @property
    def verwertbare_reste(self) -> float:
        return sum(p.rest for p in self.plaene if p.rest_verwertbar)

    @property
    def verschnitt(self) -> float:
        """Echter Abfall = Material - Nutzteil - verwertbare Reste."""
        return self.gesamt_material - self.gesamt_nutzteil - self.verwertbare_reste

    @property
    def verschnitt_prozent(self) -> float:
        return 100.0 * self.verschnitt / self.gesamt_material if self.gesamt_material else 0.0

    @property
    def ausnutzung_prozent(self) -> float:
        return 100.0 * self.gesamt_nutzteil / self.gesamt_material if self.gesamt_material else 0.0


@dataclass
class Tafel:
    """Eine verfuegbare Blechtafel / Platte (2D)."""
    breite: float
    hoehe: float
    anzahl: Optional[int] = None
    bezeichnung: str = "Tafel"
    material: str = ""
    preis: float = 0.0


@dataclass
class Zuschnitt2D:
    """
    Ein zu schneidendes Teil (2D).

    breite/hoehe sind immer die Aussenmasse (Bounding-Box). Optional kann
    aus einem DXF die echte Kontur mitgeliefert werden - sie wird fuer die
    Zeichnung und den DXF-Export verwendet, geschachtelt wird ueber die
    Bounding-Box.

    kontur     Liste von Polygonzuegen [(x, y), ...] in Teilkoordinaten
               (Nullpunkt = linke untere Ecke der Bounding-Box)
    stichlinien  Fraes-, Falz- und Biegelinien (nicht schneidend)
    """
    breite: float
    hoehe: float
    anzahl: int = 1
    bezeichnung: str = "Teil"
    material: str = ""
    drehbar: bool = True      # False z.B. bei Dekor-/Walzrichtung
    kontur: list = field(default_factory=list)
    stichlinien: list = field(default_factory=list)


@dataclass
class Platzierung2D:
    """
    Ein platziertes Teil auf einer Tafel.

    x/y/breite/hoehe beschreiben die Bounding-Box in Tafelkoordinaten.
    'kontur' bleibt immer in den ungedrehten Teilkoordinaten; die Lage in der
    Tafel ergibt sich aus winkel + versatz (siehe welt_kontur()).
    """
    bezeichnung: str
    x: float
    y: float
    breite: float
    hoehe: float
    gedreht: bool = False
    kontur: list = field(default_factory=list)
    stichlinien: list = field(default_factory=list)
    winkel: float = 0.0                       # Drehung in Grad, gegen den Uhrzeigersinn
    versatz: tuple = (0.0, 0.0)               # Nullpunktkorrektur nach der Drehung

    @property
    def flaeche(self) -> float:
        return self.breite * self.hoehe

    @property
    def kontur_flaeche(self) -> float:
        """Echte Teileflaeche laut Kontur (Fallback: Bounding-Box)."""
        if not self.kontur:
            return self.flaeche
        gesamt = 0.0
        for i, polygon in enumerate(self.kontur):
            a = abs(_polygon_flaeche(polygon))
            gesamt += a if i == 0 else -a      # weitere Polygone = Ausschnitte
        return gesamt if gesamt > 0 else self.flaeche

    def welt_kontur(self) -> list:
        """Kontur gedreht und an die Tafelposition verschoben."""
        return [_transformiere(pl, self) for pl in self.kontur]

    def welt_stichlinien(self) -> list:
        return [_transformiere(pl, self) for pl in self.stichlinien]


@dataclass
class Tafelplan:
    tafel: str
    material: str
    breite: float
    hoehe: float
    platzierungen: list[Platzierung2D] = field(default_factory=list)
    preis: float = 0.0

    @property
    def belegte_flaeche(self) -> float:
        return sum(p.flaeche for p in self.platzierungen)

    @property
    def teile_flaeche(self) -> float:
        """Flaeche der echten Konturen (bei Rechtecken identisch mit belegte_flaeche)."""
        return sum(p.kontur_flaeche for p in self.platzierungen)

    @property
    def flaeche(self) -> float:
        return self.breite * self.hoehe

    @property
    def ausnutzung(self) -> float:
        """
        Anteil echtes Nutzmaterial an der Tafel.

        Bezugsgroesse ist die Konturflaeche, nicht die Bounding-Box: bei
        verzahnten Teilen ueberlappen sich die Bounding-Boxen, die Summe
        koennte sonst ueber 100 % liegen.
        """
        return self.teile_flaeche / self.flaeche if self.flaeche else 0.0


@dataclass
class Ergebnis2D:
    plaene: list[Tafelplan] = field(default_factory=list)
    fehlende: list[tuple[str, float, float, int]] = field(default_factory=list)
    hinweise: list[str] = field(default_factory=list)

    @property
    def anzahl_tafeln(self) -> int:
        return len(self.plaene)

    @property
    def gesamt_flaeche(self) -> float:
        return sum(p.flaeche for p in self.plaene)

    @property
    def genutzte_flaeche(self) -> float:
        return sum(p.belegte_flaeche for p in self.plaene)

    @property
    def gesamt_kosten(self) -> float:
        return sum(p.preis for p in self.plaene)

    @property
    def echte_flaeche(self) -> float:
        """Summe der echten Konturflaechen (ohne Bounding-Box-Zuschlag)."""
        return sum(p.teile_flaeche for p in self.plaene)

    @property
    def verschnitt_prozent(self) -> float:
        if not self.gesamt_flaeche:
            return 0.0
        return 100.0 * (self.gesamt_flaeche - self.genutzte_flaeche) / self.gesamt_flaeche

    @property
    def ausnutzung_prozent(self) -> float:
        return 100.0 - self.verschnitt_prozent

    @property
    def ausnutzung_echt_prozent(self) -> float:
        """Ausnutzung bezogen auf die echte Teilekontur."""
        if not self.gesamt_flaeche:
            return 0.0
        return 100.0 * self.echte_flaeche / self.gesamt_flaeche


def _polygon_flaeche(punkte: list) -> float:
    """Gauss'sche Trapezformel (vorzeichenbehaftet)."""
    n = len(punkte)
    if n < 3:
        return 0.0
    summe = 0.0
    for i in range(n):
        x1, y1 = punkte[i][0], punkte[i][1]
        x2, y2 = punkte[(i + 1) % n][0], punkte[(i + 1) % n][1]
        summe += x1 * y2 - x2 * y1
    return summe / 2.0


def _transformiere(punkte: list, p: "Platzierung2D") -> list:
    """
    Rechnet Teilkoordinaten in Tafelkoordinaten um:
    erst um 'winkel' drehen, dann um 'versatz' korrigieren (damit die gedrehte
    Bounding-Box wieder bei 0/0 beginnt), dann an die Tafelposition schieben.
    """
    bogen = math.radians(p.winkel or 0.0)
    cos, sin = math.cos(bogen), math.sin(bogen)
    dx, dy = p.versatz if p.versatz else (0.0, 0.0)
    ergebnis = []
    for punkt in punkte:
        x, y = float(punkt[0]), float(punkt[1])
        if bogen:
            x, y = x * cos - y * sin, x * sin + y * cos
        ergebnis.append((p.x + x + dx, p.y + y + dy))
    return ergebnis


def drehe_polygone(polygone: list, winkel: float) -> tuple[list, float, float]:
    """
    Dreht eine Teilekontur (Aussenkontur + Ausschnitte) um 'winkel' Grad und
    schiebt sie in den Nullpunkt.

    Rueckgabe: (gedrehte Polygone, Breite, Hoehe) der neuen Bounding-Box.
    """
    bogen = math.radians(winkel)
    cos, sin = math.cos(bogen), math.sin(bogen)
    gedreht = [[(x * cos - y * sin, x * sin + y * cos) for x, y in polygon]
               for polygon in polygone]
    if not gedreht or not gedreht[0]:
        return gedreht, 0.0, 0.0
    xs = [x for x, _ in gedreht[0]]
    ys = [y for _, y in gedreht[0]]
    x0, y0 = min(xs), min(ys)
    verschoben = [[(x - x0, y - y0) for x, y in polygon] for polygon in gedreht]
    return verschoben, max(xs) - x0, max(ys) - y0


def versatz_fuer(polygone: list, winkel: float) -> tuple[float, float]:
    """Nullpunktkorrektur, die drehe_polygone() anwenden wuerde."""
    if not polygone or not polygone[0]:
        return (0.0, 0.0)
    bogen = math.radians(winkel)
    cos, sin = math.cos(bogen), math.sin(bogen)
    xs = [x * cos - y * sin for x, y in polygone[0]]
    ys = [x * sin + y * cos for x, y in polygone[0]]
    return (-min(xs), -min(ys))


# ==========================================================
# 2. 1D - STANGEN- UND PROFILZUSCHNITT
# ==========================================================


def _knapsack_fuellung(kapazitaet: int, groessen: list[int], limits: list[int]) -> list[int]:
    """
    Begrenztes Rucksackproblem: fuelle 'kapazitaet' (ganzzahlig, mm) so gut wie
    moeglich mit Teilen der Groesse groessen[i], hoechstens limits[i] Stueck.

    Rueckgabe: Stueckzahl je Teilesorte. Da Wert == Gewicht, ist das Ergebnis
    die bestmoegliche Belegung genau dieser einen Stange.
    """
    if kapazitaet <= 0:
        return [0] * len(groessen)

    NEG = -1
    # dp[c] = maximal belegte Laenge mit Kapazitaet c
    dp = [NEG] * (kapazitaet + 1)
    dp[0] = 0
    # wahl[c] = (sorte, vorher_c) zur Rekonstruktion
    wahl: list[Optional[tuple[int, int]]] = [None] * (kapazitaet + 1)

    for i, g in enumerate(groessen):
        if g <= 0 or g > kapazitaet or limits[i] <= 0:
            continue
        # Anzahl der bereits verwendeten Stueck dieser Sorte je Kapazitaet
        anzahl = [0] * (kapazitaet + 1)
        for c in range(g, kapazitaet + 1):
            if dp[c - g] == NEG:
                continue
            if anzahl[c - g] >= limits[i]:
                continue
            kandidat = dp[c - g] + g
            if kandidat > dp[c]:
                dp[c] = kandidat
                anzahl[c] = anzahl[c - g] + 1
                wahl[c] = (i, c - g)

    # beste Kapazitaet suchen
    best_c = max(range(kapazitaet + 1), key=lambda c: dp[c])
    ergebnis = [0] * len(groessen)
    c = best_c
    while c > 0 and wahl[c] is not None:
        i, prev = wahl[c]
        ergebnis[i] += 1
        c = prev
    return ergebnis


def optimize_1d(
    teile: Iterable[Teil],
    stangen: Iterable[Stange],
    saegeblatt: float = 3.0,
    anschnitt: float = 0.0,
    endschnitt: float = 0.0,
    min_reststueck: float = 300.0,
    reste_zuerst: bool = True,
) -> Ergebnis1D:
    """
    Optimiert den Zuschnitt von Teilen auf Lagerstangen.

    saegeblatt     Schnittbreite je Schnitt in mm (Saegeblattstaerke)
    anschnitt      Besaeumung am Stangenanfang in mm
    endschnitt     Sicherheitsabstand am Stangenende in mm
    min_reststueck Reste ab dieser Laenge gelten als verwertbar (kein Verschnitt)
    reste_zuerst   Reststuecke aus dem Lager bevorzugt verbrauchen

    Die Optimierung laeuft je Profil getrennt (Teile verschiedener Profile
    koennen nicht auf derselben Stange liegen).
    """
    teile = [t for t in teile if t.laenge > 0 and t.anzahl > 0]
    stangen = [s for s in stangen if s.laenge > 0 and (s.anzahl is None or s.anzahl > 0)]
    ergebnis = Ergebnis1D()
    if not teile:
        return ergebnis

    profile = []
    for t in teile:
        if t.profil not in profile:
            profile.append(t.profil)

    for profil in profile:
        p_teile = [t for t in teile if t.profil == profil]
        # Stangen desselben Profils; Stangen ohne Profilangabe passen immer
        p_stangen = [s for s in stangen if s.profil == profil]
        if not p_stangen:
            p_stangen = [s for s in stangen if not s.profil]
        if not p_stangen and not profil:
            # Teile ohne Profilangabe duerfen auf jede Stange
            p_stangen = list(stangen)
        if not p_stangen:
            for t in p_teile:
                ergebnis.fehlende.append((t.bezeichnung, t.laenge, t.anzahl))
            continue

        _optimize_1d_profil(
            profil, p_teile, p_stangen, saegeblatt, anschnitt, endschnitt,
            min_reststueck, reste_zuerst, ergebnis,
        )

    ergebnis.plaene.sort(key=lambda p: (p.profil, -p.stangen_laenge))
    return ergebnis


def _optimize_1d_profil(profil, teile, stangen, saegeblatt, anschnitt, endschnitt,
                        min_reststueck, reste_zuerst, ergebnis: Ergebnis1D) -> None:
    """Optimiert ein einzelnes Profil (Hilfsfunktion von optimize_1d)."""

    # Teilesorten zusammenfassen (gleiche Laenge + Bezeichnung)
    sorten: list[dict] = []
    for t in teile:
        key = (round(t.laenge, 3), t.bezeichnung)
        for s in sorten:
            if s["key"] == key:
                s["offen"] += int(t.anzahl)
                break
        else:
            sorten.append({
                "key": key,
                "bezeichnung": t.bezeichnung,
                "laenge": float(t.laenge),
                # Bedarf inkl. Saegeschnitt, aufgerundet auf mm (sichere Seite)
                "bedarf": int(math.ceil(t.laenge + saegeblatt - 1e-9)),
                "offen": int(t.anzahl),
            })

    # Lagerbestand je Stangentyp
    lager = []
    for s in stangen:
        nutz = s.laenge - anschnitt - endschnitt
        if nutz <= 0:
            continue
        lager.append({
            "stange": s,
            "nutz": int(math.floor(nutz + 1e-9)),
            "offen": s.anzahl,   # None = unbegrenzt
        })
    if not lager:
        for s in sorten:
            if s["offen"] > 0:
                ergebnis.fehlende.append((s["bezeichnung"], s["laenge"], s["offen"]))
        return

    # Reihenfolge: Reststuecke zuerst, dann kurze vor langen Lagerstangen
    lager.sort(key=lambda l: (not (reste_zuerst and l["stange"].reststueck), l["nutz"]))

    sicherung = 0
    max_durchlaeufe = 10000
    while any(s["offen"] > 0 for s in sorten) and sicherung < max_durchlaeufe:
        sicherung += 1

        bester = None       # (score, lagerposition, belegung)
        for pos in lager:
            if pos["offen"] is not None and pos["offen"] <= 0:
                continue
            groessen = [s["bedarf"] for s in sorten]
            limits = [s["offen"] for s in sorten]
            belegung = _knapsack_fuellung(pos["nutz"], groessen, limits)
            gefuellt = sum(b * s["bedarf"] for b, s in zip(belegung, sorten))
            if gefuellt <= 0:
                continue

            stange = pos["stange"]
            rest = pos["nutz"] - gefuellt
            preis = stange.preis if stange.preis > 0 else stange.laenge / 1000.0
            # Verwertbarer Rest wird anteilig gutgeschrieben
            if rest >= min_reststueck and not stange.reststueck:
                preis_effektiv = preis * (1.0 - rest / stange.laenge)
            else:
                preis_effektiv = preis
            # Nutzteil ohne Saegeschnitte
            nutzteil = sum(b * s["laenge"] for b, s in zip(belegung, sorten))
            score = preis_effektiv / nutzteil if nutzteil else float("inf")
            # Reststuecke aus dem Lager klar bevorzugen
            if reste_zuerst and stange.reststueck:
                score *= 0.5

            if bester is None or score < bester[0] - 1e-12:
                bester = (score, pos, belegung)

        if bester is None:
            break   # kein offenes Teil passt mehr auf eine verfuegbare Stange

        _, pos, belegung = bester
        stange = pos["stange"]
        plan = Stangenplan(
            stange=stange.bezeichnung,
            profil=profil,
            stangen_laenge=stange.laenge,
            nutzlaenge=float(pos["nutz"]),
            preis=stange.preis,
            reststueck=stange.reststueck,
        )

        # Teile der Reihe nach (lang -> kurz) auf der Stange platzieren
        platzierbar = []
        for anzahl, sorte in zip(belegung, sorten):
            platzierbar.extend([sorte] * anzahl)
        platzierbar.sort(key=lambda s: -s["laenge"])

        cursor = anschnitt
        for sorte in platzierbar:
            plan.platzierungen.append(Platzierung1D(
                bezeichnung=sorte["bezeichnung"],
                laenge=sorte["laenge"],
                start=cursor,
                ende=cursor + sorte["laenge"],
            ))
            cursor += sorte["laenge"] + saegeblatt
            sorte["offen"] -= 1

        plan.rest = max(0.0, stange.laenge - endschnitt - cursor)
        plan.rest_verwertbar = plan.rest >= min_reststueck
        ergebnis.plaene.append(plan)

        if pos["offen"] is not None:
            pos["offen"] -= 1

    for s in sorten:
        if s["offen"] > 0:
            ergebnis.fehlende.append((s["bezeichnung"], s["laenge"], s["offen"]))


# ==========================================================
# 3. 2D - BLECH- UND PLATTENZUSCHNITT
# ==========================================================


def _freie_rechtecke_einfuegen(freie: list[tuple], neu: tuple) -> None:
    """Fuegt ein freies Rechteck hinzu, sofern es nicht in einem anderen enthalten ist."""
    x, y, b, h = neu
    if b <= 0 or h <= 0:
        return
    for (fx, fy, fb, fh) in freie:
        if fx <= x and fy <= y and fx + fb >= x + b and fy + fh >= y + h:
            return
    freie.append(neu)


def _freie_rechtecke_aufraeumen(freie: list[tuple]) -> list[tuple]:
    """Entfernt vollstaendig enthaltene Rechtecke."""
    sauber = []
    for i, a in enumerate(freie):
        enthalten = False
        for j, b in enumerate(freie):
            if i == j:
                continue
            if (b[0] <= a[0] and b[1] <= a[1]
                    and b[0] + b[2] >= a[0] + a[2]
                    and b[1] + b[3] >= a[1] + a[3]
                    and (a[2] * a[3] < b[2] * b[3] or j < i)):
                enthalten = True
                break
        if not enthalten:
            sauber.append(a)
    return sauber


def _maxrects_tafel(freie_teile: list[dict], breite: float, hoehe: float,
                    x0: float, y0: float, saegeblatt: float) -> list[Platzierung2D]:
    """
    Freies Nesting einer Tafel nach MaxRects (Best-Short-Side-Fit).
    Teile duerfen beliebig verteilt werden - erfordert eine Maschine, die
    Innenkonturen faehrt (Laser/Plasma), keine Tafelschere.
    """
    freie: list[tuple] = [(x0, y0, breite, hoehe)]
    platzierungen: list[Platzierung2D] = []

    while True:
        bestes = None
        for teil in freie_teile:
            if teil["offen"] <= 0:
                continue
            varianten = [(teil["breite"], teil["hoehe"], False)]
            if teil["drehbar"] and teil["breite"] != teil["hoehe"]:
                varianten.append((teil["hoehe"], teil["breite"], True))
            for (tb, th, gedreht) in varianten:
                bb, bh = tb + saegeblatt, th + saegeblatt
                for (fx, fy, fb, fh) in freie:
                    if bb > fb + 1e-9 or bh > fh + 1e-9:
                        continue
                    kurz = min(fb - bb, fh - bh)
                    lang = max(fb - bb, fh - bh)
                    schluessel = (kurz, lang, fy, fx)
                    if bestes is None or schluessel < bestes[0]:
                        bestes = (schluessel, teil, tb, th, gedreht, (fx, fy, fb, fh))
        if bestes is None:
            break

        _, teil, tb, th, gedreht, rechteck = bestes
        fx, fy, fb, fh = rechteck
        platzierungen.append(Platzierung2D(
            teil["bezeichnung"], fx, fy, tb, th, gedreht,
            teil.get("kontur", []), teil.get("stichlinien", []),
            winkel=90.0 if gedreht else 0.0,
            versatz=(tb, 0.0) if gedreht else (0.0, 0.0)))
        teil["offen"] -= 1

        bb, bh = tb + saegeblatt, th + saegeblatt
        belegt = (fx, fy, bb, bh)

        neue: list[tuple] = []
        for (rx, ry, rb, rh) in freie:
            if (belegt[0] >= rx + rb or belegt[0] + belegt[2] <= rx
                    or belegt[1] >= ry + rh or belegt[1] + belegt[3] <= ry):
                neue.append((rx, ry, rb, rh))
                continue
            # ueberlappendes Rechteck in bis zu 4 Teilstuecke zerlegen
            if belegt[0] > rx:
                _freie_rechtecke_einfuegen(neue, (rx, ry, belegt[0] - rx, rh))
            if belegt[0] + belegt[2] < rx + rb:
                _freie_rechtecke_einfuegen(
                    neue, (belegt[0] + belegt[2], ry, rx + rb - (belegt[0] + belegt[2]), rh))
            if belegt[1] > ry:
                _freie_rechtecke_einfuegen(neue, (rx, ry, rb, belegt[1] - ry))
            if belegt[1] + belegt[3] < ry + rh:
                _freie_rechtecke_einfuegen(
                    neue, (rx, belegt[1] + belegt[3], rb, ry + rh - (belegt[1] + belegt[3])))
        freie = _freie_rechtecke_aufraeumen(neue)

    return platzierungen


def _guillotine_tafel(freie_teile: list[dict], breite: float, hoehe: float,
                      x0: float, y0: float, saegeblatt: float) -> list[Platzierung2D]:
    """
    Streifenweises Nesting (2-stufig guillotinierbar): erst durchgehende
    Querschnitte, dann Schnitte innerhalb des Streifens. Passt zu Tafelschere,
    Plattensaege und Kreissaege.
    """
    platzierungen: list[Platzierung2D] = []
    y = y0
    rest_hoehe = hoehe

    while rest_hoehe > 0:
        # Streifenhoehe = hoechstes noch offenes Teil, das hineinpasst
        streifen_h = 0.0
        for teil in freie_teile:
            if teil["offen"] <= 0:
                continue
            for (tb, th, _g) in _varianten(teil):
                if th + saegeblatt <= rest_hoehe + 1e-9 and tb + saegeblatt <= breite + 1e-9:
                    streifen_h = max(streifen_h, th)
        if streifen_h <= 0:
            break

        x = x0
        rest_breite = breite
        while True:
            bestes = None
            for teil in freie_teile:
                if teil["offen"] <= 0:
                    continue
                for (tb, th, gedreht) in _varianten(teil):
                    if th > streifen_h + 1e-9:
                        continue
                    if tb + saegeblatt > rest_breite + 1e-9:
                        continue
                    schluessel = (-(tb * th), -th)
                    if bestes is None or schluessel < bestes[0]:
                        bestes = (schluessel, teil, tb, th, gedreht)
            if bestes is None:
                break
            _, teil, tb, th, gedreht = bestes
            platzierungen.append(Platzierung2D(
                teil["bezeichnung"], x, y, tb, th, gedreht,
                teil.get("kontur", []), teil.get("stichlinien", []),
                winkel=90.0 if gedreht else 0.0,
                versatz=(tb, 0.0) if gedreht else (0.0, 0.0)))
            teil["offen"] -= 1
            x += tb + saegeblatt
            rest_breite -= tb + saegeblatt

        y += streifen_h + saegeblatt
        rest_hoehe -= streifen_h + saegeblatt

    return platzierungen


def _varianten(teil: dict) -> list[tuple[float, float, bool]]:
    varianten = [(teil["breite"], teil["hoehe"], False)]
    if teil["drehbar"] and teil["breite"] != teil["hoehe"]:
        varianten.append((teil["hoehe"], teil["breite"], True))
    return varianten


def optimize_2d(
    teile: Iterable[Zuschnitt2D],
    tafeln: Iterable[Tafel],
    saegeblatt: float = 3.0,
    besaeumung: float = 0.0,
    modus: str = "guillotine",
) -> Ergebnis2D:
    """
    Optimiert den Zuschnitt rechteckiger Teile auf Blechtafeln.

    saegeblatt   Schnittfuge / Schneidspalt in mm
    besaeumung   umlaufender Randabschnitt der Tafel in mm
    modus        "guillotine" (durchgehende Schnitte, Tafelschere/Saege)
                 "frei"       (MaxRects, fuer Laser/Plasma)

    Die Optimierung laeuft je Material getrennt.
    """
    teile = [t for t in teile if t.breite > 0 and t.hoehe > 0 and t.anzahl > 0]
    tafeln = [t for t in tafeln if t.breite > 0 and t.hoehe > 0 and (t.anzahl is None or t.anzahl > 0)]
    ergebnis = Ergebnis2D()
    if not teile:
        return ergebnis

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
            # Teile ohne Materialangabe duerfen auf jede Tafel
            m_tafeln = list(tafeln)
        if not m_tafeln:
            for t in m_teile:
                ergebnis.fehlende.append((t.bezeichnung, t.breite, t.hoehe, t.anzahl))
            continue

        offen = [{
            "bezeichnung": t.bezeichnung,
            "breite": float(t.breite),
            "hoehe": float(t.hoehe),
            "drehbar": bool(t.drehbar),
            "offen": int(t.anzahl),
            "kontur": t.kontur,
            "stichlinien": t.stichlinien,
        } for t in m_teile]
        # grosse Teile zuerst
        offen.sort(key=lambda t: (-(t["breite"] * t["hoehe"]), -max(t["breite"], t["hoehe"])))

        lager = [{"tafel": t, "offen": t.anzahl} for t in m_tafeln]
        # kleine Tafeln zuerst anbieten, damit Reste verbraucht werden
        lager.sort(key=lambda l: l["tafel"].breite * l["tafel"].hoehe)

        sicherung = 0
        while any(t["offen"] > 0 for t in offen) and sicherung < 5000:
            sicherung += 1
            bester = None

            for pos in lager:
                if pos["offen"] is not None and pos["offen"] <= 0:
                    continue
                tafel = pos["tafel"]
                nutz_b = tafel.breite - 2 * besaeumung
                nutz_h = tafel.hoehe - 2 * besaeumung
                if nutz_b <= 0 or nutz_h <= 0:
                    continue

                probe = [dict(t) for t in offen]
                fn = _guillotine_tafel if modus == "guillotine" else _maxrects_tafel
                platzierungen = fn(probe, nutz_b, nutz_h, besaeumung, besaeumung, saegeblatt)
                if not platzierungen:
                    continue

                genutzt = sum(p.flaeche for p in platzierungen)
                preis = tafel.preis if tafel.preis > 0 else (tafel.breite * tafel.hoehe) / 1e6
                score = preis / genutzt if genutzt else float("inf")
                if bester is None or score < bester[0] - 1e-15:
                    bester = (score, pos, platzierungen, probe)

            if bester is None:
                break

            _, pos, platzierungen, probe = bester
            tafel = pos["tafel"]
            ergebnis.plaene.append(Tafelplan(
                tafel=tafel.bezeichnung,
                material=material,
                breite=tafel.breite,
                hoehe=tafel.hoehe,
                platzierungen=platzierungen,
                preis=tafel.preis,
            ))
            for t, p in zip(offen, probe):
                t["offen"] = p["offen"]
            if pos["offen"] is not None:
                pos["offen"] -= 1

        for t in offen:
            if t["offen"] > 0:
                ergebnis.fehlende.append((t["bezeichnung"], t["breite"], t["hoehe"], t["offen"]))

    return ergebnis


# ==========================================================
# 4. EINGABE-PARSER (Schnellerfassung)
# ==========================================================


def parse_1d_eingabe(text: str) -> list[Teil]:
    """
    Parst eine Schnellerfassung fuer 1D, eine Zeile je Position:

        1250 x 4                -> 4 Stueck a 1250 mm
        1250x4 Handlauf         -> mit Bezeichnung
        2000;2;Pfosten;Rohr 40  -> Laenge;Anzahl;Bezeichnung;Profil
    """
    teile: list[Teil] = []
    for zeile in text.splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#"):
            continue
        bezeichnung, profil = "", ""
        if ";" in zeile:
            felder = [f.strip() for f in zeile.split(";")]
            laenge = _zahl(felder[0])
            anzahl = int(_zahl(felder[1])) if len(felder) > 1 and felder[1] else 1
            bezeichnung = felder[2] if len(felder) > 2 else ""
            profil = felder[3] if len(felder) > 3 else ""
        else:
            rest = zeile.replace("*", "x").replace("X", "x")
            teilstuecke = rest.split("x")
            laenge = _zahl(teilstuecke[0])
            anzahl, bezeichnung = 1, ""
            if len(teilstuecke) > 1:
                schwanz = teilstuecke[1].strip()
                zahl = ""
                for zeichen in schwanz:
                    if zeichen.isdigit():
                        zahl += zeichen
                    else:
                        break
                anzahl = int(zahl) if zahl else 1
                bezeichnung = schwanz[len(zahl):].strip()
        if laenge <= 0:
            continue
        teile.append(Teil(
            laenge=laenge,
            anzahl=max(1, anzahl),
            bezeichnung=bezeichnung or f"{laenge:.0f} mm",
            profil=profil,
        ))
    return teile


def parse_2d_eingabe(text: str) -> list[Zuschnitt2D]:
    """
    Parst eine Schnellerfassung fuer 2D, eine Zeile je Position:

        1000 x 500 x 3                  -> 3 Stueck 1000x500 mm
        1000;500;3;Wange;Blech 2mm      -> Breite;Hoehe;Anzahl;Bezeichnung;Material
    """
    teile: list[Zuschnitt2D] = []
    for zeile in text.splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#"):
            continue
        if ";" in zeile:
            felder = [f.strip() for f in zeile.split(";")]
            breite = _zahl(felder[0])
            hoehe = _zahl(felder[1]) if len(felder) > 1 else 0.0
            anzahl = int(_zahl(felder[2])) if len(felder) > 2 and felder[2] else 1
            bezeichnung = felder[3] if len(felder) > 3 else ""
            material = felder[4] if len(felder) > 4 else ""
        else:
            teilstuecke = zeile.replace("*", "x").replace("X", "x").split("x")
            breite = _zahl(teilstuecke[0])
            hoehe = _zahl(teilstuecke[1]) if len(teilstuecke) > 1 else 0.0
            anzahl = int(_zahl(teilstuecke[2])) if len(teilstuecke) > 2 and _zahl(teilstuecke[2]) else 1
            bezeichnung, material = "", ""
        if breite <= 0 or hoehe <= 0:
            continue
        teile.append(Zuschnitt2D(
            breite=breite, hoehe=hoehe, anzahl=max(1, anzahl),
            bezeichnung=bezeichnung or f"{breite:.0f}x{hoehe:.0f}",
            material=material,
        ))
    return teile


def _zahl(wert) -> float:
    """Robuste Zahlenkonvertierung ('1.250,5' / '1250.5' / '1250 mm')."""
    if wert is None:
        return 0.0
    if isinstance(wert, (int, float)):
        return float(wert)
    s = str(wert).strip().lower().replace("mm", "").strip()
    if not s:
        return 0.0
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    gefiltert = "".join(c for c in s if c.isdigit() or c in ".-")
    try:
        return float(gefiltert)
    except ValueError:
        return 0.0
