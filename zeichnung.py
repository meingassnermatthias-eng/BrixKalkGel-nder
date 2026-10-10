"""
zeichnung.py - SVG-Darstellung der Schachtelplaene (fuer die Weboberflaeche).
"""

from __future__ import annotations

import zlib

FARBEN = [
    "#1E3A8A", "#0E7490", "#B45309", "#4D7C0F", "#7E22CE", "#BE123C",
    "#0F766E", "#A16207", "#1D4ED8", "#9D174D", "#166534", "#C2410C",
]
FARBE_TAFEL = "#F3F4F6"

# Benannte Farben fuer die Plattentypen. Der Name steht in der Oberflaeche,
# der Wert faerbt die Zeichnung, die Nummer ist die AutoCAD-Farbe im DXF.
FARBNAMEN = {
    "Blau": ("#1E3A8A", 5),
    "Türkis": ("#0E7490", 4),
    "Orange": ("#B45309", 30),
    "Grün": ("#4D7C0F", 3),
    "Violett": ("#7E22CE", 6),
    "Rot": ("#BE123C", 1),
    "Petrol": ("#0F766E", 134),
    "Gold": ("#A16207", 2),
    "Hellblau": ("#1D4ED8", 150),
    "Magenta": ("#9D174D", 240),
    "Dunkelgrün": ("#166534", 94),
    "Ziegel": ("#C2410C", 20),
    "Grau": ("#6B7280", 8),
    "Schwarz": ("#111827", 250),
}


def farbe_nach_name(name: str, ersatz: str = "#1E3A8A") -> str:
    """Zeichenfarbe zu einem Farbnamen (siehe FARBNAMEN)."""
    eintrag = FARBNAMEN.get(str(name).strip())
    return eintrag[0] if eintrag else ersatz


def dxf_farbnummer(name: str, ersatz: int = 7) -> int:
    """AutoCAD-Farbnummer zu einem Farbnamen."""
    eintrag = FARBNAMEN.get(str(name).strip())
    return eintrag[1] if eintrag else ersatz


def farbe_fuer(name: str, karte: dict | None = None) -> str:
    """
    Farbe fuer eine Teilebezeichnung.

    Mit 'karte' (siehe farbkarte()) sind die Farben innerhalb eines Plans
    garantiert unterschiedlich, ohne sie wird stabil aus dem Namen abgeleitet.
    """
    if karte and name in karte:
        return karte[name]
    pruefsumme = zlib.crc32(str(name).encode("utf-8"))
    return FARBEN[pruefsumme % len(FARBEN)]


def farbkarte(namen) -> dict:
    """Ordnet den Bezeichnungen in der Reihenfolge ihres Auftretens Farben zu."""
    karte = {}
    for name in namen:
        if name not in karte:
            karte[name] = FARBEN[len(karte) % len(FARBEN)]
    return karte


def namen_aus_plan(ergebnis) -> list:
    """Alle Teilebezeichnungen eines Ergebnisses in Reihenfolge des Auftretens."""
    namen = []
    for plan in getattr(ergebnis, "plaene", []):
        for p in plan.platzierungen:
            if p.bezeichnung not in namen:
                namen.append(p.bezeichnung)
    return namen


def _esc(text) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# ==========================================================
# Tafel
# ==========================================================


def svg_tafel(plan, nummer: int = 1, max_px: int = 620,
              farben: dict | None = None) -> str:
    """Zeichnet den Schachtelplan einer Tafel (mit echter Kontur, falls vorhanden)."""
    rand = 10
    kopf = 22
    skala = (max_px - 2 * rand) / max(plan.breite, plan.hoehe)
    b_px = plan.breite * skala
    h_px = plan.hoehe * skala
    gesamt_b = b_px + 2 * rand
    gesamt_h = h_px + kopf + rand + 18

    def sx(x):
        return rand + x * skala

    def sy(y):
        return kopf + h_px - y * skala      # Y im DXF zeigt nach oben

    teile = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" '
        f'viewBox="0 0 {gesamt_b:.0f} {gesamt_h:.0f}" role="img">',
        f'<text x="{rand}" y="15" font-family="sans-serif" font-size="13" '
        f'font-weight="600" fill="#111">Tafel {nummer}: {_esc(plan.tafel)} '
        f'({plan.breite:.0f} x {plan.hoehe:.0f} mm) &#183; '
        f'{len(plan.platzierungen)} Teile &#183; Ausnutzung {plan.ausnutzung * 100:.1f} %</text>',
        f'<rect x="{rand}" y="{kopf}" width="{b_px:.2f}" height="{h_px:.2f}" '
        f'fill="{FARBE_TAFEL}" stroke="#374151" stroke-width="1.5"/>',
    ]

    # erst alle Flaechen, dann alle Beschriftungen - sonst verdeckt ein spaeter
    # gezeichnetes Teil den Text des darunterliegenden
    for p in plan.platzierungen:
        farbe = farbe_fuer(p.bezeichnung, farben)
        konturen = p.welt_kontur() if p.kontur else []
        if konturen:
            for i, polygon in enumerate(konturen):
                punkte = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y in polygon)
                fuellung = farbe if i == 0 else FARBE_TAFEL
                teile.append(
                    f'<polygon points="{punkte}" fill="{fuellung}" fill-opacity="0.85" '
                    f'stroke="#111827" stroke-width="0.9"/>')
            for linie in p.welt_stichlinien():
                punkte = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y in linie)
                teile.append(
                    f'<polyline points="{punkte}" fill="none" stroke="#DC2626" '
                    f'stroke-width="0.9" stroke-dasharray="4 3"/>')
        else:
            teile.append(
                f'<rect x="{sx(p.x):.2f}" y="{sy(p.y + p.hoehe):.2f}" '
                f'width="{p.breite * skala:.2f}" height="{p.hoehe * skala:.2f}" '
                f'fill="{farbe}" fill-opacity="0.85" stroke="#111827" stroke-width="0.9"/>')

    for p in plan.platzierungen:
        if p.breite * skala > 44 and p.hoehe * skala > 22:
            mx = sx(p.x + p.breite / 2)
            my = sy(p.y + p.hoehe / 2)
            teile.append(
                f'<text x="{mx:.2f}" y="{my - 3:.2f}" text-anchor="middle" '
                f'font-family="sans-serif" font-size="10" font-weight="700" fill="#FFFFFF">'
                f'{_esc(p.bezeichnung)[:16]}</text>')
            teile.append(
                f'<text x="{mx:.2f}" y="{my + 9:.2f}" text-anchor="middle" '
                f'font-family="sans-serif" font-size="9" fill="#F9FAFB">'
                f'{p.breite:.0f} x {p.hoehe:.0f}'
                + (f' &#8635;{p.winkel:.0f}&#176;' if p.winkel else '') + '</text>')

    teile.append(
        f'<text x="{rand}" y="{kopf + h_px + 14:.0f}" font-family="sans-serif" '
        f'font-size="11" fill="#4B5563">Verschnitt '
        f'{(1 - plan.ausnutzung) * 100:.1f} %'
        + (f' &#183; {plan.preis:.2f} EUR' if plan.preis else '') + '</text>')
    teile.append("</svg>")
    return "".join(teile)


# ==========================================================
# Einzelteil-Vorschau (DXF-Import)
# ==========================================================


def svg_teil(teil, max_px: int = 240, farben: dict | None = None) -> str:
    """Vorschau eines aus DXF gelesenen Teils."""
    rand = 6
    skala = (max_px - 2 * rand) / max(teil.breite, teil.hoehe, 1.0)
    b_px = teil.breite * skala
    h_px = teil.hoehe * skala

    def sx(x):
        return rand + x * skala

    def sy(y):
        return rand + h_px - y * skala

    teile = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{b_px + 2 * rand:.0f}" '
             f'height="{h_px + 2 * rand:.0f}" '
             f'viewBox="0 0 {b_px + 2 * rand:.0f} {h_px + 2 * rand:.0f}">']
    if teil.kontur:
        for i, polygon in enumerate(teil.kontur):
            punkte = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y in polygon)
            fuellung = farbe_fuer(teil.bezeichnung, farben) if i == 0 else "#FFFFFF"
            teile.append(f'<polygon points="{punkte}" fill="{fuellung}" fill-opacity="0.8" '
                         f'stroke="#111827" stroke-width="1"/>')
        for linie in teil.stichlinien:
            punkte = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y in linie)
            teile.append(f'<polyline points="{punkte}" fill="none" stroke="#DC2626" '
                         f'stroke-width="1" stroke-dasharray="4 3"/>')
    else:
        teile.append(f'<rect x="{rand}" y="{rand}" width="{b_px:.2f}" height="{h_px:.2f}" '
                     f'fill="{farbe_fuer(teil.bezeichnung, farben)}" fill-opacity="0.8" '
                     f'stroke="#111827" stroke-width="1"/>')
    teile.append("</svg>")
    return "".join(teile)


def legende(namen, farben: dict | None = None) -> str:
    """Farblegende fuer die Teilebezeichnungen."""
    eintraege = []
    for name in namen:
        eintraege.append(
            f'<span style="display:inline-flex;align-items:center;margin-right:14px;'
            f'font-size:12px;color:#374151;">'
            f'<span style="width:12px;height:12px;border-radius:2px;margin-right:5px;'
            f'background:{farbe_fuer(name, farben)};border:1px solid #111;"></span>{_esc(name)}</span>')
    return '<div style="margin:6px 0 10px 0;">' + "".join(eintraege) + '</div>'


# ==========================================================
# Fassadenansicht (Plattenraster)
# ==========================================================


def svg_fassade(felder, nummern: dict | None = None, farben: dict | None = None,
                max_px: int = 900, max_hoehe: int = 700,
                mit_massen: bool = True, titel: str = "",
                farbe_je_feld: dict | None = None) -> str:
    """
    Zeichnet die Fassadenansicht eines Plattenrasters.

    nummern        Feldname -> Positionsnummer (Beschriftung im Feld)
    farben         Farbkarte fuer die Positionsnummern bzw. Plattentypen
    farbe_je_feld  Feldname -> Farbe; uebersteuert die Einfaerbung, damit sich
                   die Ansicht z. B. nach Plattentyp einfaerben laesst
    """
    if not felder:
        return '<div style="color:#6B7280">Kein Raster vorhanden.</div>'

    xs = [p[0] for f in felder for p in f.polygon]
    ys = [p[1] for f in felder for p in f.polygon]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    mm_breit = max(x1 - x0, 1.0)
    mm_hoch = max(y1 - y0, 1.0)
    rand = 14
    kopf = 22 if titel else 6
    skala = min((max_px - 2 * rand) / mm_breit, (max_hoehe - 2 * rand) / mm_hoch)
    b_px = mm_breit * skala
    h_px = mm_hoch * skala
    gesamt_b = b_px + 2 * rand
    gesamt_h = h_px + 2 * rand + kopf

    def sx(x):
        return rand + (x - x0) * skala

    def sy(y):
        return kopf + rand + h_px - (y - y0) * skala

    teile = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" '
        f'viewBox="0 0 {gesamt_b:.0f} {gesamt_h:.0f}" role="img">',
        '<defs><pattern id="fassade_schraeg" width="8" height="8" '
        'patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
        '<line x1="0" y1="0" x2="0" y2="8" stroke="#6B7280" stroke-width="2"/>'
        '</pattern></defs>',
    ]
    if titel:
        teile.append(
            f'<text x="{rand}" y="15" font-family="sans-serif" font-size="13" '
            f'font-weight="600" fill="#111">{_esc(titel)}</text>')

    for feld in felder:
        punkte = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y in feld.polygon)
        if feld.aus:
            teile.append(f'<polygon points="{punkte}" fill="#E5E7EB" '
                         f'stroke="#374151" stroke-width="1.2"/>')
            teile.append(f'<polygon points="{punkte}" fill="url(#fassade_schraeg)" '
                         f'fill-opacity="0.45" stroke="none"/>')
            continue
        marke = (nummern or {}).get(feld.name, feld.typ)
        fuellung = ((farbe_je_feld or {}).get(feld.name)
                    or farbe_fuer(marke, farben))
        teile.append(f'<polygon points="{punkte}" fill="{fuellung}" '
                     f'fill-opacity="0.85" stroke="#111827" stroke-width="1.2"/>')

    for feld in felder:
        b_feld, h_feld = feld.breite * skala, feld.hoehe * skala
        if b_feld < 40 or h_feld < 18:
            continue
        mx, my = feld.mitte
        mx, my = sx(mx), sy(my)
        if feld.aus:
            teile.append(
                f'<text x="{mx:.1f}" y="{my + 4:.1f}" text-anchor="middle" '
                f'font-family="sans-serif" font-size="10" font-weight="600" '
                f'fill="#374151">&#214;ffnung</text>')
            continue
        marke = (nummern or {}).get(feld.name, feld.typ)
        versatz = -3 if (mit_massen and h_feld > 34) else 4
        teile.append(
            f'<text x="{mx:.1f}" y="{my + versatz:.1f}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="11" font-weight="700" '
            f'fill="#FFFFFF">{_esc(marke)}</text>')
        if mit_massen and h_feld > 34:
            # schiefe Felder: das Mass ist die Huelle, nicht die Plattenkante
            vorsatz = "" if feld.rechteckig else "H&#252;lle "
            teile.append(
                f'<text x="{mx:.1f}" y="{my + 11:.1f}" text-anchor="middle" '
                f'font-family="sans-serif" font-size="9" fill="#F9FAFB">'
                f'{feld.name} &#183; {vorsatz}{feld.breite:.0f} &#215; '
                f'{feld.hoehe:.0f}</text>')

    teile.append("</svg>")
    return "".join(teile)
