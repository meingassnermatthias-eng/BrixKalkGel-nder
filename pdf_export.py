"""
pdf_export.py - Werkstattdruck der Schachtelplaene.

Funktioniert mit fpdf (1.7) und fpdf2.
"""

from __future__ import annotations

import datetime
import os

from fpdf import FPDF

from zeichnung import FARBEN, farbe_fuer, farbkarte, namen_aus_plan

LOGO_KANDIDATEN = ("Meingassner Metalltechnik 2023.png", "logo_firma.png", "logo.png")


def _txt(wert) -> str:
    """Latin-1-sicherer Text fuer FPDF."""
    s = str(wert)
    s = (s.replace("€", "EUR").replace("–", "-").replace("—", "-")
         .replace("„", '"').replace("“", '"').replace("·", "-"))
    return s.encode("latin-1", "replace").decode("latin-1")


def _hex_rgb(hexfarbe: str):
    hexfarbe = hexfarbe.lstrip("#")
    return (int(hexfarbe[0:2], 16), int(hexfarbe[2:4], 16), int(hexfarbe[4:6], 16))


def _ausgabe(pdf) -> bytes:
    """Vereinheitlicht die Ausgabe von fpdf 1.7 und fpdf2."""
    daten = pdf.output(dest="S") if _ist_altes_fpdf(pdf) else pdf.output()
    if isinstance(daten, str):
        return daten.encode("latin-1", "replace")
    return bytes(daten)


def _ist_altes_fpdf(pdf) -> bool:
    try:
        import inspect
        return "dest" in inspect.signature(pdf.output).parameters
    except Exception:
        return False


class _Blatt(FPDF):
    kopfzeile = "Schnittplan"
    untertitel = ""

    def header(self):
        logo = next((d for d in LOGO_KANDIDATEN if os.path.exists(d)), None)
        if logo:
            try:
                self.image(logo, 10, 8, 32)
            except Exception:
                pass
        self.set_xy(45, 10)
        self.set_font("Arial", "B", 15)
        self.cell(0, 7, _txt(self.kopfzeile), 0, 1, "L")
        self.set_x(45)
        self.set_font("Arial", "", 9)
        self.set_text_color(90, 90, 90)
        self.cell(0, 5, _txt(self.untertitel), 0, 1, "L")
        self.set_text_color(0, 0, 0)
        self.set_draw_color(180, 180, 180)
        self.line(10, 26, 200, 26)
        self.set_y(31)

    def footer(self):
        self.set_y(-12)
        self.set_font("Arial", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, _txt(f"Erstellt am {datetime.datetime.now():%d.%m.%Y %H:%M}"), 0, 0, "L")
        self.cell(0, 8, _txt(f"Seite {self.page_no()}"), 0, 0, "R")
        self.set_text_color(0, 0, 0)


def _fuellstil(style: str) -> str:
    """PDF-Operator fuer Fuellen/Umranden mit Even-Odd-Regel (Ausschnitte)."""
    return {"F": "f*", "FD": "B*", "DF": "B*", "D": "S"}.get(style, "S")


def zeichne_kontur(pdf, ringe, style: str = "FD") -> bool:
    """
    Zeichnet eine Teilekontur samt Ausschnitten als einen Pfad.

    Geschrieben wird direkt in den Seiteninhalt (funktioniert mit fpdf 1.7 und
    fpdf2). Ausschnitte bleiben durch die Even-Odd-Regel frei. Rueckgabe False,
    wenn die Ausgabe nicht moeglich war - dann zeichnet der Aufrufer ein Rechteck.
    """
    if not ringe or len(ringe[0]) < 3:
        return False
    try:
        k, hoehe = pdf.k, pdf.h
        stuecke = []
        for ring in ringe:
            if len(ring) < 3:
                continue
            x, y = ring[0]
            stuecke.append(f"{x * k:.2f} {(hoehe - y) * k:.2f} m")
            for x, y in ring[1:]:
                stuecke.append(f"{x * k:.2f} {(hoehe - y) * k:.2f} l")
            stuecke.append("h")
        stuecke.append(_fuellstil(style))
        pdf._out(" ".join(stuecke))
        return True
    except Exception:
        pass
    # Notnagel: wenigstens die Aussenkontur ueber die Bibliothek zeichnen
    if hasattr(pdf, "polygon"):
        try:
            pdf.polygon(list(ringe[0]), style=style)
            return True
        except Exception:
            return False
    return False


def _kennzahlen(pdf, zeilen):
    pdf.set_font("Arial", "", 9)
    for links, rechts in zeilen:
        pdf.set_font("Arial", "B", 9)
        pdf.cell(48, 5.5, _txt(links), 0, 0)
        pdf.set_font("Arial", "", 9)
        pdf.cell(45, 5.5, _txt(rechts), 0, 1)
    pdf.ln(2)


def _tabellenkopf(pdf, spalten):
    pdf.set_font("Arial", "B", 8.5)
    pdf.set_fill_color(230, 233, 238)
    for text, breite, _ in spalten:
        pdf.cell(breite, 6, _txt(text), 1, 0, "C", True)
    pdf.ln()
    pdf.set_font("Arial", "", 8.5)


def _tabellenzeile(pdf, spalten, werte, fuellen=False):
    pdf.set_fill_color(247, 248, 250)
    for (_, breite, ausrichtung), wert in zip(spalten, werte):
        pdf.cell(breite, 5.5, _txt(wert), 1, 0, ausrichtung, fuellen)
    pdf.ln()


def pdf_2d(ergebnis, projekt: str = "", parameter: dict | None = None) -> bytes:
    parameter = parameter or {}
    farben = farbkarte(namen_aus_plan(ergebnis))
    pdf = _Blatt()
    pdf.kopfzeile = "Schachtelplan Bleche / Platten"
    pdf.untertitel = projekt or "Verschnittoptimierung"
    pdf.set_auto_page_break(True, 18)
    pdf.add_page()

    _kennzahlen(pdf, [
        ("Tafeln gesamt:", f"{ergebnis.anzahl_tafeln}"),
        ("Tafelflaeche:", f"{ergebnis.gesamt_flaeche / 1e6:.2f} m2"),
        ("Genutzte Flaeche:", f"{ergebnis.genutzte_flaeche / 1e6:.2f} m2 "
                              f"({ergebnis.ausnutzung_prozent:.1f} %)"),
        ("Verschnitt:", f"{(ergebnis.gesamt_flaeche - ergebnis.genutzte_flaeche) / 1e6:.2f} m2 "
                        f"({ergebnis.verschnitt_prozent:.1f} %)"),
        ("Genutzt (echte Kontur):", f"{ergebnis.echte_flaeche / 1e6:.2f} m2 "
                                    f"({ergebnis.ausnutzung_echt_prozent:.1f} %)"),
        ("Materialkosten:", f"{ergebnis.gesamt_kosten:.2f} EUR"),
        ("Schnittfuge / Besaeumung:", f"{parameter.get('saegeblatt', 0):.1f} mm / "
                                      f"{parameter.get('besaeumung', 0):.0f} mm"),
        ("Schnittart:", {"guillotine": "Guillotine (durchgehende Schnitte)",
                         "frei": "Frei (Bounding-Box)",
                         "kontur": "Kontur (echtes Nesting)"}.get(
                             parameter.get("modus", "guillotine"),
                             parameter.get("modus", "guillotine"))),
    ])

    for nr, plan in enumerate(ergebnis.plaene, start=1):
        pdf.add_page()
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 6, _txt(f"Tafel {nr}: {plan.tafel} - "
                            f"{plan.breite:.0f} x {plan.hoehe:.0f} mm"), 0, 1)
        pdf.set_font("Arial", "", 9)
        pdf.cell(0, 5, _txt(f"{plan.material}   Teile: {len(plan.platzierungen)}   "
                            f"Ausnutzung: {plan.ausnutzung * 100:.1f} %   "
                            f"Verschnitt: {(1 - plan.ausnutzung) * 100:.1f} %"), 0, 1)
        pdf.ln(1)

        y0 = pdf.get_y()
        max_b, max_h = 190.0, 185.0
        skala = min(max_b / plan.breite, max_h / plan.hoehe)
        b_mm, h_mm = plan.breite * skala, plan.hoehe * skala
        x0 = 10.0

        def px(x):
            return x0 + x * skala

        def py(y):
            return y0 + h_mm - y * skala

        pdf.set_draw_color(60, 60, 60)
        pdf.set_line_width(0.35)
        pdf.set_fill_color(245, 245, 247)
        pdf.rect(x0, y0, b_mm, h_mm, "FD")

        # erst alle Flaechen, dann alle Beschriftungen - sonst deckt ein spaeter
        # gezeichnetes Teil die Beschriftung des darunterliegenden zu
        for p in plan.platzierungen:
            r, g, bl = _hex_rgb(farbe_fuer(p.bezeichnung, farben))
            pdf.set_fill_color(r, g, bl)
            pdf.set_line_width(0.25)
            konturen = p.welt_kontur() if p.kontur else []
            gezeichnet = False
            if konturen:
                gezeichnet = zeichne_kontur(
                    pdf, [[(px(x), py(y)) for x, y in ring] for ring in konturen], "FD")
            if not gezeichnet:
                pdf.rect(px(p.x), py(p.y + p.hoehe), p.breite * skala,
                         p.hoehe * skala, "FD")

            # Fraes-/Falzlinien
            pdf.set_draw_color(200, 30, 30)
            pdf.set_line_width(0.2)
            for linie in (p.welt_stichlinien() if p.stichlinien else []):
                for a, b in zip(linie, linie[1:]):
                    pdf.line(px(a[0]), py(a[1]), px(b[0]), py(b[1]))
            pdf.set_draw_color(60, 60, 60)

        for p in plan.platzierungen:
            if p.breite * skala > 16 and p.hoehe * skala > 7:
                pdf.set_xy(px(p.x), py(p.y + p.hoehe / 2) - 2.6)
                pdf.set_font("Arial", "B", 6.5)
                pdf.set_text_color(255, 255, 255)
                pdf.cell(p.breite * skala, 2.6, _txt(p.bezeichnung[:18]), 0, 2, "C")
                pdf.set_font("Arial", "", 6)
                pdf.cell(p.breite * skala, 2.6,
                         _txt(f"{p.breite:.0f}x{p.hoehe:.0f}"
                              + (f" {p.winkel:.0f}Grad" if p.winkel else "")), 0, 0, "C")
                pdf.set_text_color(0, 0, 0)

        pdf.set_y(y0 + h_mm + 4)
        spalten = [("Pos", 12, "C"), ("Teil", 62, "L"), ("Breite", 22, "R"),
                   ("Hoehe", 22, "R"), ("X", 22, "R"), ("Y", 22, "R"),
                   ("Drehung", 22, "C")]
        _tabellenkopf(pdf, spalten)
        for i, p in enumerate(plan.platzierungen, start=1):
            if pdf.get_y() > 265:
                pdf.add_page()
                _tabellenkopf(pdf, spalten)
            _tabellenzeile(pdf, spalten, [
                i, p.bezeichnung, f"{p.breite:.0f}", f"{p.hoehe:.0f}",
                f"{p.x:.0f}", f"{p.y:.0f}", f"{p.winkel:.0f} Grad",
            ], i % 2 == 0)

    if ergebnis.fehlende:
        pdf.add_page()
        pdf.set_font("Arial", "B", 10)
        pdf.set_text_color(180, 0, 0)
        pdf.cell(0, 6, _txt("Nicht eingeplante Teile:"), 0, 1)
        pdf.set_font("Arial", "", 9)
        for bez, b, h, anzahl in ergebnis.fehlende:
            pdf.cell(0, 5, _txt(f"  - {anzahl} x {bez} ({b:.0f} x {h:.0f} mm)"), 0, 1)
        pdf.set_text_color(0, 0, 0)

    return _ausgabe(pdf)
