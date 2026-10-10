"""
hilfe_bilder.py - Erklaerbilder fuer die Hilfe.

Alle Bilder entstehen als SVG im Code: keine Bilddateien, die mitgeliefert
werden muessen, und bei jeder Bildschirmgroesse scharf.
"""

from __future__ import annotations

BLAU = "#1E3A8A"
HELLBLAU = "#0E7490"
GRUEN = "#4D7C0F"
ORANGE = "#C2410C"
GRAU = "#6B7280"
HELLGRAU = "#E5E7EB"
ROT = "#DC2626"


def _rahmen(inhalt: str, breite: int, hoehe: int) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {breite} {hoehe}" '
            f'width="100%" style="max-width:{breite}px;height:auto" '
            f'font-family="system-ui, sans-serif">{inhalt}</svg>')


def _text(x, y, inhalt, groesse=12, farbe="#111827", anker="start", fett=False):
    return (f'<text x="{x}" y="{y}" font-size="{groesse}" fill="{farbe}" '
            f'text-anchor="{anker}"'
            + (' font-weight="700"' if fett else '') + f'>{inhalt}</text>')


def _pfeil_markierung() -> str:
    return ('<defs><marker id="spitze" viewBox="0 0 10 10" refX="9" refY="5" '
            'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{GRAU}"/></marker></defs>')


# ==========================================================
# 1. Ablauf in drei Schritten
# ==========================================================


def bild_ablauf() -> str:
    kaesten = [
        (14, "1", "Raster", "Fassadenraster zeichnen<br/>oder aus DXF holen", ORANGE),
        (190, "2", "Teile", "Positionen, DXF-Abwicklungen<br/>oder von Hand", HELLBLAU),
        (366, "3", "Material", "Tafeln und<br/>Schnittparameter", GRUEN),
        (542, "4", "Plan", "Schachteln, nachbessern,<br/>ausgeben", BLAU),
    ]
    teile = [_pfeil_markierung()]
    for x, nummer, titel, zeile, farbe in kaesten:
        teile.append(f'<rect x="{x}" y="22" width="150" height="86" rx="10" '
                     f'fill="#FFFFFF" stroke="{farbe}" stroke-width="2"/>')
        teile.append(f'<circle cx="{x + 24}" cy="48" r="13" fill="{farbe}"/>')
        teile.append(_text(x + 24, 53, nummer, 14, "#FFFFFF", "middle", True))
        teile.append(_text(x + 45, 53, titel, 14, "#111827", "start", True))
        for i, stueck in enumerate(zeile.split("<br/>")):
            teile.append(_text(x + 12, 78 + i * 15, stueck, 10.5, GRAU))
    for x in (166, 342, 518):
        teile.append(f'<line x1="{x}" y1="65" x2="{x + 22}" y2="65" stroke="{GRAU}" '
                     f'stroke-width="2" marker-end="url(#spitze)"/>')
    teile.append(_text(14, 124, "Schritt 1 ist freiwillig: wer die Teile schon hat, "
                       "faengt bei Schritt 2 an.", 11, GRAU))
    return _rahmen("".join(teile), 706, 132)


# ==========================================================
# 2. Schnittfuge und Besaeumung
# ==========================================================


def bild_schnittfuge() -> str:
    teile = [_pfeil_markierung()]
    # Tafel
    teile.append(f'<rect x="30" y="28" width="360" height="190" fill="#FAFAFA" '
                 f'stroke="#374151" stroke-width="2"/>')
    # Besaeumung
    teile.append(f'<rect x="52" y="50" width="316" height="146" fill="none" '
                 f'stroke="{GRAU}" stroke-width="1.5" stroke-dasharray="6 4"/>')
    # zwei Teile
    teile.append(f'<rect x="62" y="60" width="130" height="126" fill="{HELLBLAU}" '
                 f'fill-opacity="0.85" stroke="#111827"/>')
    teile.append(f'<rect x="212" y="60" width="146" height="126" fill="{GRUEN}" '
                 f'fill-opacity="0.85" stroke="#111827"/>')
    teile.append(_text(127, 128, "Teil A", 13, "#FFFFFF", "middle", True))
    teile.append(_text(285, 128, "Teil B", 13, "#FFFFFF", "middle", True))
    # Schnittfuge
    teile.append(f'<rect x="192" y="60" width="20" height="126" fill="{ROT}" '
                 f'fill-opacity="0.18"/>')
    teile.append(f'<line x1="202" y1="60" x2="202" y2="186" stroke="{ROT}" '
                 f'stroke-width="1.5" stroke-dasharray="4 3"/>')
    teile.append(f'<line x1="430" y1="123" x2="214" y2="123" stroke="{GRAU}" '
                 f'stroke-width="1.5" marker-end="url(#spitze)"/>')
    teile.append(_text(438, 120, "Schnittfuge", 12.5, "#111827", "start", True))
    teile.append(_text(438, 136, "Platz f&#252;r S&#228;ge oder Fr&#228;ser", 11.5, GRAU))
    # Besaeumung
    teile.append(f'<line x1="430" y1="40" x2="60" y2="42" stroke="{GRAU}" '
                 f'stroke-width="1.5" marker-end="url(#spitze)"/>')
    teile.append(_text(438, 37, "Bes&#228;umung", 12.5, "#111827", "start", True))
    teile.append(_text(438, 53, "Rand der Tafel, der", 11.5, GRAU))
    teile.append(_text(438, 68, "nicht genutzt wird", 11.5, GRAU))
    teile.append(_text(30, 238, "Beide Werte stehen im Schritt &#8222;Material &amp; "
                                "Nesting&#8220; und gelten f&#252;r den ganzen Plan.",
                       11.5, GRAU))
    return _rahmen("".join(teile), 690, 250)


# ==========================================================
# 3. Schnittarten im Vergleich
# ==========================================================


def _mini_tafel(x, titel, untertitel, stuecke, linien=()) -> str:
    """Eine kleine Tafel mit Teilen; 'stuecke' sind (Punkte, Farbe)-Paare."""
    teile = [f'<rect x="{x}" y="34" width="190" height="150" fill="#FFFFFF" '
             f'stroke="#374151" stroke-width="1.6"/>']
    teile.append(_text(x, 22, titel, 13, "#111827", "start", True))
    for punkte, farbe in stuecke:
        verschoben = " ".join(f"{x + px},{34 + py}" for px, py in punkte)
        teile.append(f'<polygon points="{verschoben}" fill="{farbe}" '
                     f'fill-opacity="0.85" stroke="#111827" stroke-width="0.8"/>')
    for y in linien:      # durchgehende Schnitte
        teile.append(f'<line x1="{x}" y1="{34 + y}" x2="{x + 190}" y2="{34 + y}" '
                     f'stroke="{ROT}" stroke-width="1.4" stroke-dasharray="5 3"/>')
    for i, zeile in enumerate(untertitel.split("|")):
        teile.append(_text(x, 202 + i * 15, zeile, 11.5, GRAU))
    return "".join(teile)


def _kasten(x, y, b, h):
    return [(x, y), (x + b, y), (x + b, y + h), (x, y + h)]


def bild_schnittarten() -> str:
    teile = []

    # Guillotine: gleich hohe Streifen, Schnitt geht immer durch die ganze Tafel.
    # Was im Streifen rechts uebrig bleibt, ist verloren.
    teile.append(_mini_tafel(
        20, "Guillotine",
        "Schnitt geht immer durch,|Rest im Streifen bleibt liegen",
        [(_kasten(8, 6, 52, 58), HELLBLAU), (_kasten(64, 6, 52, 58), HELLBLAU),
         (_kasten(120, 6, 52, 58), HELLBLAU),
         (_kasten(8, 72, 80, 58), GRUEN), (_kasten(92, 72, 80, 58), GRUEN)],
        linien=(68,)))

    # Frei: dieselben Teile, aber die Luecken werden mit kleineren gefuellt
    teile.append(_mini_tafel(
        250, "Frei",
        "Rechtecke dicht gepackt,|L&#252;cken werden gef&#252;llt",
        [(_kasten(8, 6, 52, 58), HELLBLAU), (_kasten(64, 6, 52, 58), HELLBLAU),
         (_kasten(120, 6, 52, 58), HELLBLAU),
         (_kasten(8, 68, 80, 58), GRUEN), (_kasten(92, 68, 80, 58), GRUEN),
         (_kasten(8, 130, 52, 14), ORANGE), (_kasten(64, 130, 52, 14), ORANGE),
         (_kasten(120, 130, 52, 14), ORANGE)]))

    # Kontur: zwei Dreiecke ergeben zusammen ein Rechteck - darum zwei Farben
    paare = []
    for sx_ in (8, 98):
        for sy_ in (6, 74):
            paare.append(([(sx_, sy_), (sx_ + 82, sy_), (sx_, sy_ + 62)], ORANGE))
            paare.append(([(sx_ + 84, sy_ + 64), (sx_ + 2, sy_ + 64),
                           (sx_ + 84, sy_ + 2)], BLAU))
    teile.append(_mini_tafel(
        480, "Kontur",
        "Echte Form: die Teile greifen|ineinander, kaum Abfall", paare))
    return _rahmen("".join(teile), 690, 272)


# ==========================================================
# 4. DXF-Layer
# ==========================================================


def bild_dxf_layer() -> str:
    k = 26
    b, h, x0, y0 = 300, 170, 40, 40
    kontur = [(k, 0), (b - k, 0), (b - k, k), (b, k), (b, h - k), (b - k, h - k),
              (b - k, h), (k, h), (k, h - k), (0, h - k), (0, k), (k, k)]
    punkte = " ".join(f"{x0 + px},{y0 + py}" for px, py in kontur)
    teile = [_pfeil_markierung()]
    teile.append(f'<polygon points="{punkte}" fill="{HELLBLAU}" fill-opacity="0.18" '
                 f'stroke="#111827" stroke-width="2"/>')
    for a, e in [((k, k), (b - k, k)), ((k, h - k), (b - k, h - k)),
                 ((k, k), (k, h - k)), ((b - k, k), (b - k, h - k))]:
        teile.append(f'<line x1="{x0 + a[0]}" y1="{y0 + a[1]}" x2="{x0 + e[0]}" '
                     f'y2="{y0 + e[1]}" stroke="{ROT}" stroke-width="1.6" '
                     f'stroke-dasharray="6 4"/>')
    # ignorierte Bemassung
    teile.append(f'<line x1="{x0}" y1="{y0 + h + 22}" x2="{x0 + b}" y2="{y0 + h + 22}" '
                 f'stroke="{HELLGRAU}" stroke-width="1.5"/>')
    teile.append(_text(x0 + b / 2, y0 + h + 18, "1060", 11, "#9CA3AF", "middle"))

    teile.append(f'<line x1="408" y1="52" x2="{x0 + b / 2}" y2="{y0 + 4}" '
                 f'stroke="{GRAU}" stroke-width="1.4" marker-end="url(#spitze)"/>')
    teile.append(_text(416, 50, "Aussenkontur", 12.5, "#111827", "start", True))
    teile.append(_text(416, 66, "wird geschnitten", 11.5, GRAU))

    teile.append(f'<line x1="408" y1="118" x2="{x0 + b - k + 4}" y2="{y0 + h / 2}" '
                 f'stroke="{GRAU}" stroke-width="1.4" marker-end="url(#spitze)"/>')
    teile.append(_text(416, 116, "Fr&#228;s- oder Falzlinie", 12.5, ROT, "start", True))
    teile.append(_text(416, 132, "wird nur geritzt, nicht", 11.5, GRAU))
    teile.append(_text(416, 147, "getrennt", 11.5, GRAU))

    teile.append(f'<line x1="408" y1="200" x2="{x0 + b / 2 + 20}" y2="{y0 + h + 20}" '
                 f'stroke="{GRAU}" stroke-width="1.4" marker-end="url(#spitze)"/>')
    teile.append(_text(416, 198, "Bema&#223;ung, Text, Achsen", 12.5, "#9CA3AF",
                       "start", True))
    teile.append(_text(416, 214, "werden ignoriert", 11.5, GRAU))
    return _rahmen("".join(teile), 690, 250)


# ==========================================================
# 5. Editor
# ==========================================================


def bild_editor() -> str:
    teile = [_pfeil_markierung()]
    teile.append(f'<rect x="30" y="34" width="210" height="170" fill="#FFFFFF" '
                 f'stroke="#374151" stroke-width="1.8"/>')
    teile.append(_text(30, 26, "Tafel 1", 12, BLAU, "start", True))
    teile.append(f'<rect x="300" y="34" width="210" height="170" fill="#FFFFFF" '
                 f'stroke="{BLAU}" stroke-width="2.4"/>')
    teile.append(_text(300, 26, "Tafel 2  (aktiv)", 12, BLAU, "start", True))

    teile.append(f'<rect x="40" y="44" width="92" height="76" fill="{HELLBLAU}" '
                 f'fill-opacity="0.85" stroke="#111827"/>')
    teile.append(f'<rect x="140" y="44" width="92" height="76" fill="{GRUEN}" '
                 f'fill-opacity="0.85" stroke="#111827"/>')
    teile.append(f'<rect x="40" y="128" width="92" height="66" fill="{ORANGE}" '
                 f'fill-opacity="0.85" stroke="#111827"/>')
    # gezogenes Teil
    teile.append(f'<rect x="310" y="44" width="92" height="76" fill="{ORANGE}" '
                 f'fill-opacity="0.5" stroke="{ROT}" stroke-width="2" '
                 f'stroke-dasharray="5 3"/>')
    teile.append(f'<path d="M 150 165 Q 250 150 316 86" fill="none" stroke="{GRAU}" '
                 f'stroke-width="1.8" stroke-dasharray="5 4" marker-end="url(#spitze)"/>')
    teile.append(_text(176, 150, "ziehen", 12, GRAU, "start", True))

    teile.append(_text(30, 232, "Teile lassen sich auch von einer Tafel auf die andere "
                                "ziehen. Wer ein Teil rot losl&#228;sst,", 11.5, GRAU))
    teile.append(_text(30, 248, "bekommt es automatisch auf die n&#228;chste freie "
                                "Stelle ger&#252;ckt.", 11.5, GRAU))
    return _rahmen("".join(teile), 690, 260)


# ==========================================================
# 6. Plattenraster: Raster -> Platte
# ==========================================================


def bild_raster() -> str:
    """Rasterlinie = Fugenmitte; die Platte ist um die halbe Fuge kleiner."""
    teile = [_pfeil_markierung()]
    x0, y0 = 30, 46
    spalten = [150, 150]
    zeilen = [96, 96]
    fuge = 16

    teile.append(_text(x0, 24, "Raster (Achsmasse, gestrichelt)", 12, GRAU,
                       "start", True))
    y = y0
    for hoehe in zeilen:
        x = x0
        for breite in spalten:
            teile.append(f'<rect x="{x}" y="{y}" width="{breite}" height="{hoehe}" '
                         f'fill="#FFFFFF" stroke="{GRAU}" stroke-width="1.4" '
                         f'stroke-dasharray="6 4"/>')
            x += breite
        y += hoehe
    y = y0
    for hoehe in zeilen:
        x = x0
        for breite in spalten:
            teile.append(f'<rect x="{x + fuge / 2}" y="{y + fuge / 2}" '
                         f'width="{breite - fuge}" height="{hoehe - fuge}" rx="2" '
                         f'fill="{HELLBLAU}" fill-opacity="0.85" stroke="#111827" '
                         f'stroke-width="1"/>')
            x += breite
        y += hoehe
    teile.append(_text(x0 + spalten[0] / 2, y0 + zeilen[0] / 2 + 4, "Platte", 12,
                       "#FFFFFF", "middle", True))

    # Fugenmitte hervorheben
    mx = x0 + spalten[0]
    unten = y0 + sum(zeilen)
    teile.append(f'<line x1="{mx}" y1="{y0 - 6}" x2="{mx}" y2="{unten + 6}" '
                 f'stroke="{ROT}" stroke-width="1.4"/>')
    rechts = x0 + sum(spalten) + 40
    teile.append(f'<line x1="{mx}" y1="{y0 + 40}" x2="{rechts - 8}" y2="{y0 + 10}" '
                 f'stroke="{ROT}" stroke-width="1" stroke-dasharray="3 3"/>')
    teile.append(_text(rechts, y0 + 6, "Rasterlinie = Fugenmitte", 12, ROT,
                       "start", True))
    teile.append(_text(rechts, y0 + 26, "Je Seite wird die halbe Fuge", 11.5, GRAU))
    teile.append(_text(rechts, y0 + 42, "abgezogen - zwischen zwei", 11.5, GRAU))
    teile.append(_text(rechts, y0 + 58, "Platten also die ganze.", 11.5, GRAU))

    # Fugenbreite bemassen
    teile.append(f'<line x1="{mx - fuge / 2}" y1="{unten + 22}" '
                 f'x2="{mx + fuge / 2}" y2="{unten + 22}" stroke="{ROT}" '
                 f'stroke-width="1.4" marker-start="url(#spitze)" '
                 f'marker-end="url(#spitze)"/>')
    teile.append(_text(mx + 18, unten + 26, "Fuge (z. B. 15 mm)", 11.5, ROT))

    # Aussenkante
    teile.append(f'<line x1="{x0}" y1="{unten + 10}" x2="{x0}" y2="{unten + 30}" '
                 f'stroke="{GRUEN}" stroke-width="1.6"/>')
    teile.append(_text(x0 + 8, unten + 44,
                       "Aussenkante: Platte geht bis zur Linie (umstellbar)",
                       11.5, GRUEN))
    teile.append(_text(x0, unten + 66,
                       "Zugabe (Aufkantung der Kassette) kommt danach dazu "
                       "und macht die Platte wieder groesser.", 11.5, GRAU))
    return _rahmen("".join(teile), 690, 324)


# ==========================================================
# 7. Felder zuordnen
# ==========================================================


def bild_felder() -> str:
    """Farbe je Plattentyp, Fenster weggeklickt."""
    teile = ['<defs><pattern id="hilfe_schraeg" width="7" height="7" '
             'patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
             f'<line x1="0" y1="0" x2="0" y2="7" stroke="{GRAU}" stroke-width="2"/>'
             '</pattern></defs>']
    felder = [
        (0, 0, HELLBLAU, ""), (1, 0, HELLBLAU, ""), (2, 0, ORANGE, ""),
        (0, 1, HELLBLAU, ""), (1, 1, None, "Fenster"), (2, 1, ORANGE, ""),
        (0, 2, GRUEN, ""), (1, 2, GRUEN, ""), (2, 2, ORANGE, ""),
    ]
    x0, y0, b, h = 30, 30, 112, 62
    for sp, ze, farbe, text in felder:
        x, y = x0 + sp * b, y0 + ze * h
        if farbe is None:
            teile.append(f'<rect x="{x}" y="{y}" width="{b}" height="{h}" '
                         f'fill="{HELLGRAU}" stroke="#374151" stroke-width="1.2"/>')
            teile.append(f'<rect x="{x}" y="{y}" width="{b}" height="{h}" '
                         f'fill="url(#hilfe_schraeg)" fill-opacity="0.5"/>')
            teile.append(_text(x + b / 2, y + h / 2 + 4, text, 11, "#374151",
                               "middle", True))
        else:
            teile.append(f'<rect x="{x}" y="{y}" width="{b}" height="{h}" '
                         f'fill="{farbe}" fill-opacity="0.85" stroke="#111827" '
                         f'stroke-width="1.2"/>')
    beschriftung = [(HELLBLAU, "RAL 7016 anthrazit - Alucobond 4 mm"),
                    (ORANGE, "RAL 9006 silber - Alucobond 4 mm"),
                    (GRUEN, "Lochblech - Blech 2 mm"),
                    (HELLGRAU, "Oeffnung - keine Platte")]
    for i, (farbe, text) in enumerate(beschriftung):
        y = y0 + 8 + i * 22
        teile.append(f'<rect x="{x0 + 3 * b + 24}" y="{y - 10}" width="14" height="14" '
                     f'rx="3" fill="{farbe}" stroke="#111827" stroke-width="1"/>')
        teile.append(_text(x0 + 3 * b + 44, y + 1, text, 11.5, "#111827"))
    teile.append(_text(x0, y0 + 3 * h + 20,
                       "Feld anklicken oder mit gedrueckter Maustaste "
                       "ueber mehrere Felder ziehen.", 11, GRAU))
    teile.append(_text(x0, y0 + 3 * h + 36,
                       "Je Plattentyp eine Farbe und ein eigenes Material - "
                       "gleich grosse Platten verschiedener", 11, GRAU))
    teile.append(_text(x0, y0 + 3 * h + 52,
                       "Typen bleiben getrennte Positionen.", 11, GRAU))
    return _rahmen("".join(teile), 690, 272)


# ==========================================================
# 8. Gleichteilsuche
# ==========================================================


def bild_gleichteile() -> str:
    teile = [_pfeil_markierung()]
    teile.append(_text(24, 20, "9 Felder", 12, GRAU, "start", True))
    masse = [(96, 54), (96, 54), (70, 54), (96, 54), (96, 54), (70, 54),
             (96, 40), (96, 40), (70, 40)]
    farben = [HELLBLAU, HELLBLAU, ORANGE, HELLBLAU, HELLBLAU, ORANGE,
              GRUEN, GRUEN, BLAU]
    x, y = 24, 32
    for i, ((b, h), farbe) in enumerate(zip(masse, farben)):
        teile.append(f'<rect x="{x}" y="{y + (54 - h)}" width="{b}" height="{h}" '
                     f'rx="2" fill="{farbe}" fill-opacity="0.85" stroke="#111827" '
                     f'stroke-width="1"/>')
        x += b + 8
        if (i + 1) % 3 == 0:
            x, y = 24, y + 62
    teile.append(f'<line x1="300" y1="110" x2="340" y2="110" stroke="{GRAU}" '
                 f'stroke-width="2" marker-end="url(#spitze)"/>')
    teile.append(_text(302, 100, "Gleichteilsuche", 11, GRAU))

    teile.append(_text(366, 20, "4 Positionen", 12, GRAU, "start", True))
    posten = [("P01", 4, HELLBLAU, 96, 54), ("P02", 2, ORANGE, 70, 54),
              ("P03", 2, GRUEN, 96, 40), ("P04", 1, BLAU, 70, 40)]
    x, y = 366, 32
    for i, (nummer, anzahl, farbe, b, h) in enumerate(posten):
        teile.append(f'<rect x="{x}" y="{y + (54 - h)}" width="{b}" height="{h}" '
                     f'rx="2" fill="{farbe}" fill-opacity="0.85" stroke="#111827" '
                     f'stroke-width="1"/>')
        teile.append(_text(x + b / 2, y + 54 - h / 2 + 4, nummer, 11, "#FFFFFF",
                           "middle", True))
        teile.append(_text(x + b + 6, y + 54 - h / 2 + 4, f"{anzahl}x", 12, "#111827",
                           "start", True))
        x += b + 44
        if (i + 1) % 2 == 0:
            x, y = 366, y + 62
    teile.append(_text(24, 240, "Nur gleich grosse Platten desselben Typs werden "
                       "zusammengefasst. Wahlweise zaehlen auch", 11.5, GRAU))
    teile.append(_text(24, 258, "gedrehte Platten als Gleichteil - gespiegelte nur "
                       "dann, wenn die Sichtseite es zulaesst.", 11.5, GRAU))
    return _rahmen("".join(teile), 690, 272)


BILDER = {
    "raster": bild_raster,
    "felder": bild_felder,
    "gleichteile": bild_gleichteile,
    "ablauf": bild_ablauf,
    "schnittfuge": bild_schnittfuge,
    "schnittarten": bild_schnittarten,
    "dxf_layer": bild_dxf_layer,
    "editor": bild_editor,
}
