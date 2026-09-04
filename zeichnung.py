"""
zeichnung.py - SVG-Darstellung der Schnittplaene (fuer die Weboberflaeche).
"""

from __future__ import annotations

import zlib

FARBEN = [
    "#1E3A8A", "#0E7490", "#B45309", "#4D7C0F", "#7E22CE", "#BE123C",
    "#0F766E", "#A16207", "#1D4ED8", "#9D174D", "#166534", "#C2410C",
]
FARBE_REST = "#D1D5DB"
FARBE_REST_GUT = "#86EFAC"
FARBE_TAFEL = "#F3F4F6"


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
# 1D - Stange
# ==========================================================


def svg_stange(plan, nummer: int = 1, breite_px: int = 980, hoehe_px: int = 54,
               farben: dict | None = None) -> str:
    """Zeichnet den Schnittplan einer Stange."""
    rand = 8
    kopf = 20
    nutz_px = breite_px - 2 * rand
    skala = nutz_px / plan.stangen_laenge if plan.stangen_laenge else 1.0
    gesamt_h = hoehe_px + kopf + 26

    teile = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" '
        f'viewBox="0 0 {breite_px} {gesamt_h}" role="img">',
        f'<text x="{rand}" y="14" font-family="sans-serif" font-size="13" '
        f'font-weight="600" fill="#111">Stange {nummer}: {_esc(plan.stange)} '
        f'({plan.stangen_laenge:.0f} mm) &#183; {plan.anzahl_teile} Teile &#183; '
        f'Ausnutzung {plan.ausnutzung * 100:.1f} %</text>',
        f'<rect x="{rand}" y="{kopf}" width="{nutz_px}" height="{hoehe_px}" '
        f'fill="#FFFFFF" stroke="#374151" stroke-width="1.5" rx="3"/>',
    ]

    for p in plan.platzierungen:
        x = rand + p.start * skala
        b = max(1.0, p.laenge * skala)
        farbe = farbe_fuer(p.bezeichnung, farben)
        teile.append(
            f'<rect x="{x:.2f}" y="{kopf + 2}" width="{b:.2f}" height="{hoehe_px - 4}" '
            f'fill="{farbe}" fill-opacity="0.85" stroke="#111827" stroke-width="0.8"/>')
        if b > 46:
            mitte = x + b / 2
            teile.append(
                f'<text x="{mitte:.2f}" y="{kopf + hoehe_px / 2 - 2}" text-anchor="middle" '
                f'font-family="sans-serif" font-size="11" font-weight="700" fill="#FFFFFF">'
                f'{p.laenge:.0f}</text>')
            if b > 80:
                teile.append(
                    f'<text x="{mitte:.2f}" y="{kopf + hoehe_px / 2 + 12}" text-anchor="middle" '
                    f'font-family="sans-serif" font-size="9" fill="#F9FAFB">'
                    f'{_esc(p.bezeichnung)[:18]}</text>')

    # Restlaenge
    if plan.rest > 0.5:
        x = rand + (plan.stangen_laenge - plan.rest) * skala
        b = max(1.0, plan.rest * skala)
        farbe = FARBE_REST_GUT if plan.rest_verwertbar else FARBE_REST
        teile.append(
            f'<rect x="{x:.2f}" y="{kopf + 2}" width="{b:.2f}" height="{hoehe_px - 4}" '
            f'fill="{farbe}" stroke="#6B7280" stroke-width="0.8" stroke-dasharray="3 2"/>')
        if b > 40:
            teile.append(
                f'<text x="{x + b / 2:.2f}" y="{kopf + hoehe_px / 2 + 3}" text-anchor="middle" '
                f'font-family="sans-serif" font-size="10" fill="#374151">'
                f'{plan.rest:.0f}</text>')

    hinweis = ("Rest verwertbar" if plan.rest_verwertbar else "Verschnitt")
    teile.append(
        f'<text x="{rand}" y="{kopf + hoehe_px + 17}" font-family="sans-serif" '
        f'font-size="11" fill="#4B5563">Belegt {plan.belegt:.0f} mm &#183; '
        f'Rest {plan.rest:.0f} mm ({hinweis})'
        + (f' &#183; {plan.preis:.2f} EUR' if plan.preis else '') + '</text>')
    teile.append("</svg>")
    return "".join(teile)


# ==========================================================
# 2D - Tafel
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
                f'{p.breite:.0f} x {p.hoehe:.0f}{" &#8635;" if p.gedreht else ""}</text>')

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
