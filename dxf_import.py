"""
dxf_import.py - DXF-Schnittstelle fuer die Verschnittoptimierung.

IMPORT  Liest DXF-Dateien (z.B. Abwicklungen aus HiCAD / Alucobond-Kassetten)
        und erkennt daraus die einzelnen Teile mit Aussenkontur, Ausschnitten
        und Fraes-/Falzlinien.

EXPORT  Schreibt den fertigen Schachtelplan wieder als DXF (R12, ASCII) -
        lesbar von HiCAD, AutoCAD und den gaengigen CAM-/Nesting-Systemen.

Zum Lesen wird ezdxf verwendet, falls installiert (unterstuetzt Splines,
Bloecke, binaeres DXF). Ohne ezdxf greift ein einfacher ASCII-Parser fuer
LINE / LWPOLYLINE / POLYLINE / ARC / CIRCLE.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

try:                                  # optional, aber empfohlen
    import ezdxf
    from ezdxf import recover
    EZDXF_VERFUEGBAR = True
except Exception:                     # pragma: no cover
    EZDXF_VERFUEGBAR = False


# ==========================================================
# 1. LAYER-ERKENNUNG
# ==========================================================

# Layer, die geschnitten werden (Aussenkontur + Ausschnitte)
LAYER_KONTUR = ("kontur", "aussen", "außen", "innen", "ausschnitt", "schnitt",
                "cut", "outer", "inner", "profil", "geometrie", "cutting")

# Layer, die nur gefraest/gefalzt/gebogen werden (kein Trennschnitt)
LAYER_STICH = ("fraes", "fräs", "fres", "falz", "bieg", "bend", "fold", "nut",
               "rill", "v-schnitt", "vschnitt", "kant", "knick", "abkant", "groove")

# Layer, die fuer die Geometrie irrelevant sind
LAYER_IGNORIEREN = ("bemass", "bemaß", "mass", "maß", "dim", "text", "beschrift",
                    "mittellinie", "hilfslinie", "achse", "rahmen", "stempel",
                    "schraffur", "hatch", "info", "defpoints", "kommentar",
                    "logo", "zeichnungskopf", "symbol")


def klassifiziere_layer(name: str) -> str:
    """Liefert 'kontur', 'stich' oder 'ignorieren' fuer einen Layernamen."""
    n = (name or "").strip().lower()
    for schluessel in LAYER_IGNORIEREN:
        if schluessel in n:
            return "ignorieren"
    for schluessel in LAYER_STICH:
        if schluessel in n:
            return "stich"
    for schluessel in LAYER_KONTUR:
        if schluessel in n:
            return "kontur"
    return "kontur"      # unbekannte Layer im Zweifel schneiden


# ==========================================================
# 2. DATENSTRUKTUREN
# ==========================================================


@dataclass
class DxfTeil:
    """Ein aus einer DXF-Datei erkanntes Teil."""
    bezeichnung: str
    breite: float
    hoehe: float
    kontur: list = field(default_factory=list)       # [aussen, loch1, loch2, ...]
    stichlinien: list = field(default_factory=list)  # Fraes-/Falzlinien
    anzahl: int = 1
    quelle: str = ""

    @property
    def flaeche(self) -> float:
        if not self.kontur:
            return self.breite * self.hoehe
        gesamt = 0.0
        for i, polygon in enumerate(self.kontur):
            a = abs(_polygonflaeche(polygon))
            gesamt += a if i == 0 else -a
        return max(gesamt, 0.0)

    @property
    def ausnutzung_bbox(self) -> float:
        """Wie gut fuellt die echte Kontur ihre Bounding-Box? (0..1)"""
        rechteck = self.breite * self.hoehe
        return self.flaeche / rechteck if rechteck else 0.0


@dataclass
class DxfErgebnis:
    teile: list[DxfTeil] = field(default_factory=list)
    layer: dict = field(default_factory=dict)     # layername -> (klasse, anzahl elemente)
    hinweise: list[str] = field(default_factory=list)
    einheit: str = "mm"


# ==========================================================
# 3. GEOMETRIE-HILFEN
# ==========================================================


def _polygonflaeche(punkte: list) -> float:
    n = len(punkte)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = punkte[i]
        x2, y2 = punkte[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def _bbox(punkte: list) -> tuple[float, float, float, float]:
    xs = [p[0] for p in punkte]
    ys = [p[1] for p in punkte]
    return min(xs), min(ys), max(xs), max(ys)


def _punkt_in_polygon(punkt, polygon) -> bool:
    """Ray-Casting."""
    x, y = punkt
    drin = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            schnitt_x = x1 + (y - y1) * (x2 - x1) / (y2 - y1) if y2 != y1 else x1
            if x < schnitt_x:
                drin = not drin
    return drin


def _bogen_punkte(mx, my, radius, start_grad, end_grad, segmente_pro_90=12) -> list:
    """Wandelt einen Bogen in einen Polygonzug (Sehnenzug) um."""
    start = math.radians(start_grad)
    ende = math.radians(end_grad)
    if ende <= start:
        ende += 2 * math.pi
    spanne = ende - start
    anzahl = max(2, int(abs(spanne) / (math.pi / 2) * segmente_pro_90) + 1)
    return [(mx + radius * math.cos(start + spanne * i / anzahl),
             my + radius * math.sin(start + spanne * i / anzahl))
            for i in range(anzahl + 1)]


def _entferne_doppelpunkte(punkte: list, tol: float = 1e-6) -> list:
    sauber = []
    for p in punkte:
        if not sauber or abs(p[0] - sauber[-1][0]) > tol or abs(p[1] - sauber[-1][1]) > tol:
            sauber.append((float(p[0]), float(p[1])))
    return sauber


def _ketten_bilden(segmente: list, tol: float = 0.05) -> tuple[list, list]:
    """
    Verbindet lose Segmente ueber gemeinsame Endpunkte zu Linienzuegen.

    Rueckgabe: (geschlossene Konturen, offene Ketten). Geschlossene Konturen
    werden ohne doppelten Endpunkt zurueckgegeben.
    """
    geschlossen: list = []
    rest: list = []
    for segment in segmente:
        kette = _entferne_doppelpunkte(segment)
        if len(kette) < 2:
            continue
        if len(kette) >= 4 and _abstand(kette[0], kette[-1]) <= tol:
            geschlossen.append(kette[:-1])
        else:
            rest.append(kette)

    offene: list = []
    while rest:
        aktuell = rest.pop(0)
        veraendert = True
        while veraendert and _abstand(aktuell[0], aktuell[-1]) > tol:
            veraendert = False
            for i, kandidat in enumerate(rest):
                if _abstand(aktuell[-1], kandidat[0]) <= tol:
                    aktuell = aktuell + kandidat[1:]
                elif _abstand(aktuell[-1], kandidat[-1]) <= tol:
                    aktuell = aktuell + list(reversed(kandidat))[1:]
                elif _abstand(aktuell[0], kandidat[-1]) <= tol:
                    aktuell = kandidat + aktuell[1:]
                elif _abstand(aktuell[0], kandidat[0]) <= tol:
                    aktuell = list(reversed(kandidat)) + aktuell[1:]
                else:
                    continue
                rest.pop(i)
                veraendert = True
                break

        aktuell = _entferne_doppelpunkte(aktuell)
        if len(aktuell) >= 4 and _abstand(aktuell[0], aktuell[-1]) <= tol:
            geschlossen.append(aktuell[:-1])
        elif len(aktuell) >= 3 and _abstand(aktuell[0], aktuell[-1]) <= max(tol * 10, 1.0):
            # kleine Restluecke (Rundungsfehler aus dem CAD) schliessen
            geschlossen.append(aktuell)
        else:
            offene.append(aktuell)

    return geschlossen, offene


def _abstand(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


# ==========================================================
# 4. DXF LESEN
# ==========================================================


def _elemente_ezdxf(daten: bytes, layer_override: dict | None = None) -> tuple[list, list, list, dict]:
    """Liest mit ezdxf. Rueckgabe: (konturseg, stichseg, texte, layerstatistik)"""
    import io
    layer_override = layer_override or {}
    doc, pruefung = recover.read(io.BytesIO(daten))
    msp = doc.modelspace()
    kontur, stich, texte = [], [], []
    layer_stat: dict = {}

    def verarbeite(e, transform_hinweis=""):
        typ = e.dxftype()
        layer = getattr(e.dxf, "layer", "0")
        klasse = layer_override.get(layer) or klassifiziere_layer(layer)
        layer_stat[layer] = (klasse, layer_stat.get(layer, (klasse, 0))[1] + 1)

        if typ in ("TEXT", "MTEXT"):
            try:
                inhalt = e.plain_text() if hasattr(e, "plain_text") else str(e.dxf.text)
                punkt = e.dxf.insert
                texte.append((str(inhalt).strip(), float(punkt[0]), float(punkt[1])))
            except Exception:
                pass
            return
        if klasse == "ignorieren":
            return

        ziel = kontur if klasse == "kontur" else stich
        try:
            if typ == "LINE":
                ziel.append([(e.dxf.start[0], e.dxf.start[1]),
                             (e.dxf.end[0], e.dxf.end[1])])
            elif typ == "LWPOLYLINE":
                punkte = [(p[0], p[1]) for p in e.get_points("xy")]
                if e.closed and punkte:
                    punkte = punkte + [punkte[0]]
                ziel.append(punkte)
            elif typ == "POLYLINE":
                punkte = [(v.dxf.location[0], v.dxf.location[1]) for v in e.vertices]
                if e.is_closed and punkte:
                    punkte = punkte + [punkte[0]]
                ziel.append(punkte)
            elif typ == "ARC":
                ziel.append(_bogen_punkte(e.dxf.center[0], e.dxf.center[1], e.dxf.radius,
                                          e.dxf.start_angle, e.dxf.end_angle))
            elif typ == "CIRCLE":
                punkte = _bogen_punkte(e.dxf.center[0], e.dxf.center[1], e.dxf.radius, 0, 360)
                ziel.append(punkte)
            elif typ in ("SPLINE", "ELLIPSE"):
                punkte = [(p[0], p[1]) for p in e.flattening(0.2)]
                ziel.append(punkte)
            elif typ == "INSERT":
                for unter in e.virtual_entities():
                    verarbeite(unter)
            elif typ == "HATCH":
                pass
        except Exception:
            pass

    for e in msp:
        verarbeite(e)
    return kontur, stich, texte, layer_stat


def _elemente_einfach(daten: bytes, layer_override: dict | None = None) -> tuple[list, list, list, dict]:
    """Minimal-Parser fuer ASCII-DXF ohne ezdxf."""
    layer_override = layer_override or {}
    text = daten.decode("utf-8", errors="ignore")
    if "\x00" in text[:2000]:
        raise ValueError("Binaeres DXF - bitte ezdxf installieren (pip install ezdxf).")
    zeilen = [z.strip() for z in text.splitlines()]
    kontur, stich, texte = [], [], []
    layer_stat: dict = {}

    i = 0
    # nur den ENTITIES-Bereich lesen
    while i < len(zeilen) - 1 and not (zeilen[i] == "2" and zeilen[i + 1] == "ENTITIES"):
        i += 1

    def ziel_fuer(layer):
        klasse = layer_override.get(layer) or klassifiziere_layer(layer)
        layer_stat[layer] = (klasse, layer_stat.get(layer, (klasse, 0))[1] + 1)
        if klasse == "ignorieren":
            return None
        return kontur if klasse == "kontur" else stich

    while i < len(zeilen) - 1:
        if zeilen[i] != "0":
            i += 2 if i + 1 < len(zeilen) else 1
            continue
        typ = zeilen[i + 1]
        if typ == "ENDSEC":
            break
        i += 2
        werte: dict = {}
        punkte_poly: list = []
        while i < len(zeilen) - 1 and zeilen[i] != "0":
            code, wert = zeilen[i], zeilen[i + 1]
            if code in ("10", "20") and typ in ("LWPOLYLINE",):
                if code == "10":
                    punkte_poly.append([_f(wert), 0.0])
                elif punkte_poly:
                    punkte_poly[-1][1] = _f(wert)
            else:
                werte.setdefault(code, []).append(wert)
            i += 2

        layer = werte.get("8", ["0"])[0]
        if typ == "TEXT":
            inhalt = werte.get("1", [""])[0]
            texte.append((inhalt.strip(), _f(werte.get("10", ["0"])[0]),
                          _f(werte.get("20", ["0"])[0])))
            continue
        ziel = ziel_fuer(layer)
        if ziel is None:
            continue

        if typ == "LINE":
            ziel.append([(_f(werte.get("10", ["0"])[0]), _f(werte.get("20", ["0"])[0])),
                         (_f(werte.get("11", ["0"])[0]), _f(werte.get("21", ["0"])[0]))])
        elif typ == "LWPOLYLINE":
            punkte = [(p[0], p[1]) for p in punkte_poly]
            flag = int(_f(werte.get("70", ["0"])[0]))
            if flag & 1 and punkte:
                punkte = punkte + [punkte[0]]
            if len(punkte) >= 2:
                ziel.append(punkte)
        elif typ == "CIRCLE":
            ziel.append(_bogen_punkte(_f(werte.get("10", ["0"])[0]),
                                      _f(werte.get("20", ["0"])[0]),
                                      _f(werte.get("40", ["0"])[0]), 0, 360))
        elif typ == "ARC":
            ziel.append(_bogen_punkte(_f(werte.get("10", ["0"])[0]),
                                      _f(werte.get("20", ["0"])[0]),
                                      _f(werte.get("40", ["0"])[0]),
                                      _f(werte.get("50", ["0"])[0]),
                                      _f(werte.get("51", ["0"])[0])))
        elif typ == "VERTEX":
            # POLYLINE-Stuetzpunkte sammeln wir vereinfacht als Einzelsegmente
            werte.setdefault("_vertex", [])
    return kontur, stich, texte, layer_stat


def _f(wert) -> float:
    try:
        return float(str(wert).strip())
    except ValueError:
        return 0.0


def lade_dxf(daten: bytes, dateiname: str = "", toleranz: float = 0.1,
             min_flaeche: float = 100.0, zusammenfassen: bool = True,
             layer_override: dict | None = None) -> DxfErgebnis:
    """
    Liest eine DXF-Datei und erkennt die enthaltenen Teile.

    toleranz        max. Luecke zwischen zwei Konturelementen in mm
    min_flaeche     Konturen unter dieser Flaeche (mm2) werden verworfen
    zusammenfassen  gleich grosse Teile zu einer Position mit Stueckzahl buendeln
    layer_override  {"Layername": "kontur"|"stich"|"ignorieren"} - haendische
                    Zuordnung, die die automatische Erkennung uebersteuert
    """
    ergebnis = DxfErgebnis()
    if isinstance(daten, str):
        daten = daten.encode("utf-8")

    if EZDXF_VERFUEGBAR:
        kontur_seg, stich_seg, texte, layer_stat = _elemente_ezdxf(daten, layer_override)
    else:
        kontur_seg, stich_seg, texte, layer_stat = _elemente_einfach(daten, layer_override)
        ergebnis.hinweise.append(
            "ezdxf ist nicht installiert - Splines und Bloecke werden ignoriert.")

    ergebnis.layer = layer_stat
    if not kontur_seg:
        ergebnis.hinweise.append("Keine Konturelemente gefunden. "
                                 "Layer-Zuordnung pruefen.")
        return ergebnis

    geschlossen, offen = _ketten_bilden(kontur_seg, tol=max(toleranz, 1e-3))
    if offen:
        ergebnis.hinweise.append(
            f"{len(offen)} offene Konturzuege konnten nicht geschlossen werden "
            f"(Toleranz {toleranz} mm) - diese Teile fehlen im Nesting.")

    # zu kleine Konturen (Bohrungen aus Symbolen o.ae.) verwerfen
    konturen = [k for k in geschlossen if abs(_polygonflaeche(k)) >= min_flaeche]
    if not konturen:
        ergebnis.hinweise.append("Alle gefundenen Konturen sind kleiner als "
                                 f"{min_flaeche:.0f} mm2.")
        return ergebnis

    # groesste Kontur zuerst -> Aussenkonturen, alles darin sind Ausschnitte
    konturen.sort(key=lambda k: abs(_polygonflaeche(k)), reverse=True)
    zugeordnet = [False] * len(konturen)
    rohteile: list[DxfTeil] = []

    for i, aussen in enumerate(konturen):
        if zugeordnet[i]:
            continue
        zugeordnet[i] = True
        loecher = []
        for j in range(i + 1, len(konturen)):
            if zugeordnet[j]:
                continue
            probe = konturen[j][0]
            if _punkt_in_polygon(probe, aussen):
                loecher.append(konturen[j])
                zugeordnet[j] = True

        x0, y0, x1, y1 = _bbox(aussen)
        verschoben = [[(p[0] - x0, p[1] - y0) for p in aussen]]
        verschoben += [[(p[0] - x0, p[1] - y0) for p in loch] for loch in loecher]

        # Fraes-/Falzlinien innerhalb der Bounding-Box zuordnen
        stiche = []
        for segment in stich_seg:
            if not segment:
                continue
            mx = sum(p[0] for p in segment) / len(segment)
            my = sum(p[1] for p in segment) / len(segment)
            if x0 - 1 <= mx <= x1 + 1 and y0 - 1 <= my <= y1 + 1:
                stiche.append([(p[0] - x0, p[1] - y0) for p in segment])

        # Bezeichnung aus einem Text innerhalb der Kontur uebernehmen
        name = ""
        for inhalt, tx, ty in texte:
            if inhalt and x0 <= tx <= x1 and y0 <= ty <= y1:
                if not name or (0 < len(inhalt) < len(name)):
                    name = inhalt
        if not name:
            basis = dateiname.rsplit(".", 1)[0] if dateiname else "Teil"
            name = basis if len(rohteile) == 0 else f"{basis}-{len(rohteile) + 1}"

        rohteile.append(DxfTeil(
            bezeichnung=name[:40],
            breite=round(x1 - x0, 2),
            hoehe=round(y1 - y0, 2),
            kontur=verschoben,
            stichlinien=stiche,
            anzahl=1,
            quelle=dateiname,
        ))

    if zusammenfassen:
        gebuendelt: list[DxfTeil] = []
        for teil in rohteile:
            for vorhanden in gebuendelt:
                if (abs(vorhanden.breite - teil.breite) < 0.5
                        and abs(vorhanden.hoehe - teil.hoehe) < 0.5
                        and abs(vorhanden.flaeche - teil.flaeche) < max(1.0, teil.flaeche * 0.001)):
                    vorhanden.anzahl += 1
                    break
            else:
                gebuendelt.append(teil)
        rohteile = gebuendelt

    ergebnis.teile = rohteile
    return ergebnis


# ==========================================================
# 5. DXF SCHREIBEN (Schachtelplan)
# ==========================================================

_LAYER_FARBEN = {
    "TAFEL": 8,          # grau
    "KONTUR": 7,         # weiss/schwarz
    "FRAESLINIE": 1,     # rot
    "BESCHRIFTUNG": 3,   # gruen
}


def _dxf_kopf() -> list[str]:
    zeilen = ["0", "SECTION", "2", "HEADER",
              "9", "$ACADVER", "1", "AC1009",
              "9", "$INSUNITS", "70", "4",       # 4 = Millimeter
              "0", "ENDSEC",
              "0", "SECTION", "2", "TABLES",
              "0", "TABLE", "2", "LAYER", "70", str(len(_LAYER_FARBEN))]
    for name, farbe in _LAYER_FARBEN.items():
        zeilen += ["0", "LAYER", "2", name, "70", "0", "62", str(farbe), "6", "CONTINUOUS"]
    zeilen += ["0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    return zeilen


def _dxf_polylinie(punkte: list, layer: str, geschlossen: bool = True) -> list[str]:
    if len(punkte) < 2:
        return []
    zeilen = ["0", "POLYLINE", "8", layer, "66", "1",
              "70", "1" if geschlossen else "0",
              "10", "0.0", "20", "0.0", "30", "0.0"]
    for x, y in punkte:
        zeilen += ["0", "VERTEX", "8", layer, "10", f"{x:.4f}", "20", f"{y:.4f}",
                   "30", "0.0"]
    zeilen += ["0", "SEQEND", "8", layer]
    return zeilen


def _dxf_text(inhalt: str, x: float, y: float, hoehe: float, layer: str) -> list[str]:
    sauber = "".join(c for c in str(inhalt) if 32 <= ord(c) < 127) or "?"
    return ["0", "TEXT", "8", layer, "10", f"{x:.4f}", "20", f"{y:.4f}", "30", "0.0",
            "40", f"{hoehe:.4f}", "1", sauber]


def plan_als_dxf(ergebnis, abstand: float = 200.0, mit_beschriftung: bool = True) -> str:
    """
    Schreibt einen 2D-Schachtelplan (Ergebnis2D aus nesting.py) als DXF (R12).
    Alle Tafeln liegen nebeneinander, getrennt durch 'abstand' mm.
    """
    zeilen = _dxf_kopf()
    versatz = 0.0

    for nr, plan in enumerate(ergebnis.plaene, start=1):
        # Tafelumriss
        zeilen += _dxf_polylinie(
            [(versatz, 0.0), (versatz + plan.breite, 0.0),
             (versatz + plan.breite, plan.hoehe), (versatz, plan.hoehe)],
            "TAFEL", geschlossen=True)

        if mit_beschriftung:
            zeilen += _dxf_text(
                f"Tafel {nr} - {plan.tafel} - {plan.breite:.0f}x{plan.hoehe:.0f} - "
                f"Ausnutzung {plan.ausnutzung * 100:.1f}%",
                versatz, plan.hoehe + 30.0, max(25.0, plan.hoehe / 60.0), "BESCHRIFTUNG")

        for p in plan.platzierungen:
            konturen = p.welt_kontur()
            if konturen:
                for polygon in konturen:
                    zeilen += _dxf_polylinie(
                        [(x + versatz, y) for x, y in polygon], "KONTUR", geschlossen=True)
                for linie in p.welt_stichlinien():
                    zeilen += _dxf_polylinie(
                        [(x + versatz, y) for x, y in linie], "FRAESLINIE", geschlossen=False)
            else:
                zeilen += _dxf_polylinie(
                    [(versatz + p.x, p.y), (versatz + p.x + p.breite, p.y),
                     (versatz + p.x + p.breite, p.y + p.hoehe), (versatz + p.x, p.y + p.hoehe)],
                    "KONTUR", geschlossen=True)

            if mit_beschriftung:
                hoehe_text = max(12.0, min(p.breite, p.hoehe) / 8.0)
                zeilen += _dxf_text(p.bezeichnung, versatz + p.x + hoehe_text * 0.4,
                                    p.y + hoehe_text * 0.6, hoehe_text, "BESCHRIFTUNG")

        versatz += plan.breite + abstand

    zeilen += ["0", "ENDSEC", "0", "EOF"]
    return "\n".join(zeilen) + "\n"


def teile_als_dxf(teile: list, spalten: int = 5, abstand: float = 100.0) -> str:
    """Schreibt erkannte Teile (DxfTeil) zur Kontrolle als DXF-Uebersicht."""
    zeilen = _dxf_kopf()
    x = y = 0.0
    zeilen_hoehe = 0.0
    for i, teil in enumerate(teile):
        for nr, polygon in enumerate(teil.kontur):
            zeilen += _dxf_polylinie([(px + x, py + y) for px, py in polygon],
                                     "KONTUR", geschlossen=True)
        for linie in teil.stichlinien:
            zeilen += _dxf_polylinie([(px + x, py + y) for px, py in linie],
                                     "FRAESLINIE", geschlossen=False)
        zeilen += _dxf_text(f"{teil.bezeichnung} ({teil.anzahl}x)", x, y - 40.0, 30.0,
                            "BESCHRIFTUNG")
        zeilen_hoehe = max(zeilen_hoehe, teil.hoehe)
        x += teil.breite + abstand
        if (i + 1) % spalten == 0:
            x = 0.0
            y += zeilen_hoehe + abstand + 60.0
            zeilen_hoehe = 0.0
    zeilen += ["0", "ENDSEC", "0", "EOF"]
    return "\n".join(zeilen) + "\n"
