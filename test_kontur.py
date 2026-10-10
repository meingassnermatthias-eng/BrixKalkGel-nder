"""
Tests fuer das Konturnesting. Ausfuehren mit:  python3 test_kontur.py

Geprueft wird nicht das Raster, sondern die echte Geometrie: fuer jedes
Ergebnis werden alle platzierten Konturen exakt gegeneinander gerechnet
(Kantenschnitt, Einschluss, kleinster Abstand).
"""

import math
import time

from nesting import Tafel, Zuschnitt2D, drehe_polygone, optimize_2d
import kontur_nesting as kn
from kontur_nesting import (
    FEINE_WINKEL, FREIE_WINKEL, optimize_2d_kontur, rastere_kontur, weite_auf,
)

fehler = []


def pruefe(bedingung, text):
    if bedingung:
        print(f"  OK   {text}")
    else:
        print(f"  FEHL {text}")
        fehler.append(text)


# ==========================================================
# Exakte Geometriepruefung
# ==========================================================


def _in_polygon(punkt, polygon):
    x, y = punkt
    drin = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            if x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                drin = not drin
    return drin


def im_material(punkt, ringe):
    """Even-Odd ueber Aussenkontur und Ausschnitte: Loch = kein Material."""
    return sum(1 for ring in ringe if _in_polygon(punkt, ring)) % 2 == 1


def _abstand_punkt_strecke(p, a, b):
    px, py = p
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    laenge = dx * dx + dy * dy
    if laenge == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / laenge))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _schneiden(a, b, c, d):
    def richtung(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    d1, d2 = richtung(c, d, a), richtung(c, d, b)
    d3, d4 = richtung(a, b, c), richtung(a, b, d)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def _abstand_strecken(a, b, c, d):
    if _schneiden(a, b, c, d):
        return 0.0
    return min(_abstand_punkt_strecke(a, c, d), _abstand_punkt_strecke(b, c, d),
               _abstand_punkt_strecke(c, a, b), _abstand_punkt_strecke(d, a, b))


def _kanten(ringe):
    for ring in ringe:
        for i in range(len(ring)):
            yield ring[i], ring[(i + 1) % len(ring)]


def kleinster_abstand(ringe_a, ringe_b):
    """Kleinster Abstand zweier Teile; 0.0 bei Ueberschneidung oder Einschluss."""
    for punkt in ringe_a[0]:
        if im_material(punkt, ringe_b):
            return 0.0
    for punkt in ringe_b[0]:
        if im_material(punkt, ringe_a):
            return 0.0
    kanten_b = list(_kanten(ringe_b))
    kleinster = float("inf")
    for a, b in _kanten(ringe_a):
        for c, d in kanten_b:
            kleinster = min(kleinster, _abstand_strecken(a, b, c, d))
            if kleinster == 0.0:
                return 0.0
    return kleinster


def pruefe_plan(ergebnis, tafeln, saegeblatt, besaeumung, raster, name):
    """
    Prueft jeden Tafelplan exakt: Ueberschneidung, Abstand, Tafelrand.

    Verlangt wird die volle Schnittfuge - durch die nach aussen gerundete
    Rasterung ist sie garantiert, nicht nur naeherungsweise eingehalten.
    """
    toleranz = 0.01                          # nur Rundung, kein Rasterzuschlag
    for nr, plan in enumerate(ergebnis.plaene, start=1):
        konturen = [p.welt_kontur() for p in plan.platzierungen]
        for i, ringe in enumerate(konturen):
            if not ringe or len(ringe[0]) < 3:
                pruefe(False, f"{name}: Teil {i + 1} auf Tafel {nr} hat keine Kontur")
                return
            xs = [x for ring in ringe for x, _ in ring]
            ys = [y for ring in ringe for _, y in ring]
            innerhalb = (min(xs) >= besaeumung - 0.01
                         and min(ys) >= besaeumung - 0.01
                         and max(xs) <= plan.breite - besaeumung + 0.01
                         and max(ys) <= plan.hoehe - besaeumung + 0.01)
            if not innerhalb:
                pruefe(False, f"{name}: Teil {i + 1} auf Tafel {nr} liegt ausserhalb "
                              f"({min(xs):.1f}/{min(ys):.1f} bis {max(xs):.1f}/{max(ys):.1f})")
                return
        for i in range(len(konturen)):
            for j in range(i + 1, len(konturen)):
                abstand = kleinster_abstand(konturen[i], konturen[j])
                if abstand < saegeblatt - toleranz:
                    pruefe(False, f"{name}: Tafel {nr}, Teile {i + 1}/{j + 1} nur "
                                  f"{abstand:.2f} mm auseinander (Schnittfuge "
                                  f"{saegeblatt} mm)")
                    return
    pruefe(True, f"{name}: {len(ergebnis.plaene)} Tafel(n) exakt geprueft - keine "
                 f"Ueberschneidung, Schnittfuge eingehalten")


def stueckzahl(ergebnis):
    return sum(len(p.platzierungen) for p in ergebnis.plaene)


# ==========================================================
# Testfaelle
# ==========================================================


def dreieck(breite, hoehe):
    return [[(0.0, 0.0), (breite, 0.0), (0.0, hoehe)]]


def l_form(breite, hoehe, steg):
    return [[(0.0, 0.0), (breite, 0.0), (breite, steg), (steg, steg),
             (steg, hoehe), (0.0, hoehe)]]


def kassette(breite, hoehe, kante=30.0):
    b, h, k = breite, hoehe, kante
    return [[(k, 0.0), (b - k, 0.0), (b - k, k), (b, k), (b, h - k), (b - k, h - k),
             (b - k, h), (k, h), (k, h - k), (0.0, h - k), (0.0, k), (k, k)]]


def test_rasterung():
    print("Raster: Kontur wird korrekt umgesetzt")
    maske = rastere_kontur([[(0, 0), (100, 0), (100, 50), (0, 50)]], raster=5)
    pruefe(maske.shape == (10, 20), f"Rechteck 100x50 bei 5 mm -> {maske.shape}")
    pruefe(maske.all(), "Rechteck vollstaendig gefuellt")

    # Ausschnitt bleibt frei
    mit_loch = rastere_kontur([[(0, 0), (100, 0), (100, 100), (0, 100)],
                               [(40, 40), (60, 40), (60, 60), (40, 60)]], raster=5)
    pruefe(not mit_loch[9:11, 9:11].any(), "Ausschnitt bleibt im Raster frei")
    pruefe(mit_loch.sum() == 400 - 16, f"belegte Zellen {mit_loch.sum()} (erwartet 384)")

    # Dreieck: rund die Haelfte
    drei = rastere_kontur(dreieck(100, 100), raster=5)
    anteil = drei.sum() / (20 * 20)
    pruefe(0.4 < anteil < 0.6, f"Dreieck belegt {anteil * 100:.0f} % der Bounding-Box")

    aufgeweitet = weite_auf(rastere_kontur([[(0, 0), (50, 0), (50, 50), (0, 50)]],
                                           raster=5, rand=2), 2)
    pruefe(aufgeweitet.sum() > 100, f"Aufweitung vergroessert die Maske "
                                    f"({aufgeweitet.sum()} Zellen)")


def test_dreiecke_greifen_ineinander():
    print("Kontur: Dreiecke greifen ineinander")
    teile = [Zuschnitt2D(600, 400, 12, "Dreieck", kontur=dreieck(600, 400))]
    tafeln = [Tafel(1250, 2500, None, "Tafel")]

    bbox = optimize_2d(teile, tafeln, saegeblatt=4, besaeumung=5, modus="frei")
    kontur = optimize_2d_kontur(teile, tafeln, saegeblatt=4, besaeumung=5, raster=4)

    pruefe(stueckzahl(kontur) == 12, f"alle 12 Dreiecke platziert ({stueckzahl(kontur)})")
    pruefe(kontur.ausnutzung_echt_prozent > bbox.ausnutzung_echt_prozent + 15,
           f"Ausnutzung Kontur {kontur.ausnutzung_echt_prozent:.1f} % gegen "
           f"Bounding-Box {bbox.ausnutzung_echt_prozent:.1f} %")
    pruefe(kontur.anzahl_tafeln <= bbox.anzahl_tafeln,
           f"Tafeln: Kontur {kontur.anzahl_tafeln}, Bounding-Box {bbox.anzahl_tafeln}")
    pruefe_plan(kontur, tafeln, 4, 5, 4, "Dreiecke")


def test_l_formen():
    print("Kontur: L-Formen greifen ineinander")
    teile = [Zuschnitt2D(800, 800, 8, "Winkel", kontur=l_form(800, 800, 300))]
    tafeln = [Tafel(1500, 3000, None, "Tafel")]

    bbox = optimize_2d(teile, tafeln, saegeblatt=5, besaeumung=10, modus="frei")
    kontur = optimize_2d_kontur(teile, tafeln, saegeblatt=5, besaeumung=10, raster=5)

    pruefe(stueckzahl(kontur) == 8, f"alle 8 Winkel platziert ({stueckzahl(kontur)})")
    pruefe(kontur.ausnutzung_echt_prozent > bbox.ausnutzung_echt_prozent + 5,
           f"Ausnutzung Kontur {kontur.ausnutzung_echt_prozent:.1f} % gegen "
           f"Bounding-Box {bbox.ausnutzung_echt_prozent:.1f} %")
    pruefe_plan(kontur, tafeln, 5, 10, 5, "L-Formen")


def test_ausschnitt_wird_genutzt():
    print("Kontur: Teile werden in Ausschnitte gelegt")
    rahmen = [[(0.0, 0.0), (1200.0, 0.0), (1200.0, 1200.0), (0.0, 1200.0)],
              [(200.0, 200.0), (1000.0, 200.0), (1000.0, 1000.0), (200.0, 1000.0)]]
    teile = [Zuschnitt2D(1200, 1200, 2, "Rahmen", kontur=rahmen),
             Zuschnitt2D(700, 700, 2, "Einleger")]
    tafeln = [Tafel(1250, 2600, None, "Tafel")]

    # Ohne Nachverdichtung UND ohne Nachruecken: beide Wege koennen das Teil
    # in den Ausschnitt legen, darum muessen fuer den Vergleich beide aus sein.
    ohne = optimize_2d_kontur(teile, tafeln, saegeblatt=4, besaeumung=10, raster=5,
                              nachverdichten=False, verdichten=False)
    mit = optimize_2d_kontur(teile, tafeln, saegeblatt=4, besaeumung=10, raster=5,
                             nachverdichten=True, verdichten=False)
    pruefe(stueckzahl(mit) == 4, f"alle 4 Teile platziert ({stueckzahl(mit)})")
    pruefe(mit.anzahl_tafeln < ohne.anzahl_tafeln or
           mit.plaene[0].ausnutzung > ohne.plaene[0].ausnutzung + 0.05,
           f"Nachverdichtung nutzt die Ausschnitte: {mit.anzahl_tafeln} statt "
           f"{ohne.anzahl_tafeln} Tafeln")

    # Liegt wirklich ein Einleger im Ausschnitt eines Rahmens?
    im_loch = 0
    for plan in mit.plaene:
        rahmen_teile = [p for p in plan.platzierungen if p.bezeichnung == "Rahmen"]
        einleger = [p for p in plan.platzierungen if p.bezeichnung == "Einleger"]
        for e in einleger:
            mitte = (e.x + e.breite / 2, e.y + e.hoehe / 2)
            for r in rahmen_teile:
                ringe = r.welt_kontur()
                if _in_polygon(mitte, ringe[0]) and not im_material(mitte, ringe):
                    im_loch += 1
    pruefe(im_loch >= 1, f"{im_loch} Einleger liegen im Ausschnitt eines Rahmens")
    pruefe_plan(mit, tafeln, 4, 10, 5, "Ausschnitte")


def test_kassetten_alucobond():
    print("Kontur: Alucobond-Kassetten mit Eckausklinkungen")
    teile = [Zuschnitt2D(700, 700, 10, "Kassette", "Alucobond",
                         kontur=kassette(700, 700, 60))]
    tafeln = [Tafel(1500, 3200, None, "Alucobond 1500x3200", "Alucobond", preis=310.0)]

    bbox = optimize_2d(teile, tafeln, saegeblatt=6, besaeumung=10, modus="frei")
    kontur = optimize_2d_kontur(teile, tafeln, saegeblatt=6, besaeumung=10, raster=4)
    pruefe(stueckzahl(kontur) == 10, f"alle 10 Kassetten platziert ({stueckzahl(kontur)})")
    print(f"       -> Bounding-Box {bbox.anzahl_tafeln} Tafeln / "
          f"{bbox.ausnutzung_echt_prozent:.1f} %, Kontur {kontur.anzahl_tafeln} Tafeln / "
          f"{kontur.ausnutzung_echt_prozent:.1f} %")
    pruefe(kontur.ausnutzung_echt_prozent >= bbox.ausnutzung_echt_prozent - 0.5,
           "Kontur ist nicht schlechter als Bounding-Box")
    pruefe_plan(kontur, tafeln, 6, 10, 4, "Kassetten")


def test_laufrichtung():
    print("Kontur: Laufrichtung wird eingehalten")
    teile = [Zuschnitt2D(900, 400, 6, "Dekor", "Alucobond metallic", drehbar=False,
                         kontur=l_form(900, 400, 150))]
    tafeln = [Tafel(1500, 3200, None, "Tafel", "Alucobond metallic")]
    e = optimize_2d_kontur(teile, tafeln, saegeblatt=5, besaeumung=10, raster=5)
    pruefe(stueckzahl(e) == 6, f"alle 6 Teile platziert ({stueckzahl(e)})")
    for plan in e.plaene:
        for p in plan.platzierungen:
            pruefe(p.winkel == 0.0, f"Teil ungedreht (Winkel {p.winkel})")
    pruefe_plan(e, tafeln, 5, 10, 5, "Laufrichtung")


def test_rechtecke_ohne_kontur():
    print("Kontur: Teile ohne DXF-Kontur (Rechtecke)")
    teile = [Zuschnitt2D(600, 400, 8, "Blende"), Zuschnitt2D(300, 300, 6, "Lasche")]
    tafeln = [Tafel(1250, 2500, None, "Tafel")]
    e = optimize_2d_kontur(teile, tafeln, saegeblatt=4, besaeumung=10, raster=5)
    pruefe(stueckzahl(e) == 14, f"alle 14 Teile platziert ({stueckzahl(e)})")
    pruefe(e.anzahl_tafeln == 1, f"eine Tafel reicht ({e.anzahl_tafeln})")
    pruefe(e.ausnutzung_echt_prozent > 75,
           f"Ausnutzung {e.ausnutzung_echt_prozent:.1f} %")
    pruefe_plan(e, tafeln, 4, 10, 5, "Rechtecke")


def test_zu_grosses_teil():
    print("Kontur: uebergrosses Teil wird gemeldet")
    teile = [Zuschnitt2D(3000, 3000, 1, "Zu gross"), Zuschnitt2D(400, 400, 2, "Klein")]
    tafeln = [Tafel(1250, 2500, None, "Tafel")]
    e = optimize_2d_kontur(teile, tafeln, saegeblatt=4, besaeumung=10, raster=5)
    pruefe(len(e.fehlende) == 1 and e.fehlende[0][0] == "Zu gross",
           f"fehlend: {e.fehlende}")
    pruefe(stueckzahl(e) == 2, "die kleinen Teile sind trotzdem geplant")


def test_schnittfuge_wirkt():
    print("Kontur: groessere Schnittfuge braucht mehr Platz")
    teile = [Zuschnitt2D(400, 400, 12, "Platte")]
    tafeln = [Tafel(1250, 1300, None, "Tafel")]
    eng = optimize_2d_kontur(teile, tafeln, saegeblatt=2, besaeumung=0, raster=2)
    weit = optimize_2d_kontur(teile, tafeln, saegeblatt=60, besaeumung=0, raster=2)
    pruefe(eng.anzahl_tafeln < weit.anzahl_tafeln,
           f"2 mm Fuge: {eng.anzahl_tafeln} Tafeln, 60 mm Fuge: {weit.anzahl_tafeln}")
    pruefe_plan(eng, tafeln, 2, 0, 2, "Fuge 2 mm")
    pruefe_plan(weit, tafeln, 60, 0, 2, "Fuge 60 mm")


def test_bbox_sicherheitsnetz():
    print("Kontur: Rueckfall auf das einfache Verfahren, wenn es besser ist")
    teile = [Zuschnitt2D(1060, 660, 14, "Kassette A", "Alu", kontur=kassette(1060, 660)),
             Zuschnitt2D(860, 1260, 8, "Kassette B", "Alu", kontur=kassette(860, 1260)),
             Zuschnitt2D(600, 500, 10, "Blende", "Alu")]
    tafeln = [Tafel(1500, 3200, None, "Tafel", "Alu", preis=310.0)]

    pur = optimize_2d_kontur(teile, tafeln, saegeblatt=6, besaeumung=10, raster=5,
                             mindestens_bbox=False)
    mit_netz = optimize_2d_kontur(teile, tafeln, saegeblatt=6, besaeumung=10, raster=5,
                                  mindestens_bbox=True)
    einfach = optimize_2d(teile, tafeln, saegeblatt=6, besaeumung=10, modus="frei")

    pruefe(mit_netz.anzahl_tafeln <= pur.anzahl_tafeln,
           f"mit Netz {mit_netz.anzahl_tafeln} Tafeln, ohne {pur.anzahl_tafeln}")
    pruefe(mit_netz.anzahl_tafeln <= einfach.anzahl_tafeln,
           f"nie schlechter als das einfache Verfahren ({einfach.anzahl_tafeln})")
    pruefe(stueckzahl(mit_netz) == 32, f"alle 32 Teile geplant ({stueckzahl(mit_netz)})")
    if mit_netz.anzahl_tafeln < pur.anzahl_tafeln:
        pruefe(any("einfache Verfahren" in h for h in mit_netz.hinweise),
               f"Rueckfall wird gemeldet: {mit_netz.hinweise}")
    pruefe_plan(mit_netz, tafeln, 6, 10, 5, "Sicherheitsnetz")


def test_feine_winkel():
    print("Kontur: 45-Grad-Drehungen")
    # 1200 x 150 passt gerade nicht auf eine 1100er Tafel - diagonal aber schon
    teile = [Zuschnitt2D(1200, 150, 3, "Leiste")]
    tafeln = [Tafel(1100, 1100, None, "Tafel")]
    gerade = optimize_2d_kontur(teile, tafeln, saegeblatt=4, besaeumung=5, raster=4)
    schraeg = optimize_2d_kontur(teile, tafeln, saegeblatt=4, besaeumung=5, raster=4,
                                 winkel=FEINE_WINKEL)
    pruefe(sum(f[3] for f in gerade.fehlende) == 3,
           f"gerade passt nichts ({gerade.fehlende})")
    pruefe(stueckzahl(schraeg) == 3, f"diagonal passen alle 3 ({stueckzahl(schraeg)})")
    winkel = {p.winkel for plan in schraeg.plaene for p in plan.platzierungen}
    pruefe(winkel and all(w % 90 != 0 for w in winkel), f"Winkel {winkel}")
    pruefe_plan(schraeg, tafeln, 4, 5, 4, "45 Grad")


def test_rastergrenze():
    print("Kontur: Rasterweite wird bei Riesentafeln vergroebert")
    teile = [Zuschnitt2D(900, 700, 6, "Platte")]
    tafeln = [Tafel(3000, 8000, None, "Grosstafel")]
    e = optimize_2d_kontur(teile, tafeln, saegeblatt=5, besaeumung=10, raster=0.5)
    pruefe(any("Rasterweite" in h for h in e.hinweise), f"Hinweis: {e.hinweise}")
    pruefe(stueckzahl(e) == 6, f"trotzdem alle Teile geplant ({stueckzahl(e)})")


def test_ohne_tafeln():
    print("Kontur: ohne Tafeln bleibt alles offen")
    e = optimize_2d_kontur([Zuschnitt2D(500, 500, 3, "Teil")], [])
    pruefe(e.anzahl_tafeln == 0 and sum(f[3] for f in e.fehlende) == 3,
           f"3 Teile offen ({e.fehlende})")


def test_ausgabe_pdf_und_dxf():
    print("Kontur: Ausgabe als PDF und DXF")
    rahmen = [[(0.0, 0.0), (1100.0, 0.0), (1100.0, 1100.0), (0.0, 1100.0)],
              [(250.0, 250.0), (850.0, 250.0), (850.0, 850.0), (250.0, 850.0)]]
    teile = [Zuschnitt2D(800, 800, 5, "Winkel", "Stahl", kontur=l_form(800, 800, 300)),
             Zuschnitt2D(1100, 1100, 2, "Rahmen", "Stahl", kontur=rahmen),
             Zuschnitt2D(500, 500, 3, "Einleger", "Stahl")]
    tafeln = [Tafel(1500, 3000, None, "Blech", "Stahl", preis=210.0)]
    e = optimize_2d_kontur(teile, tafeln, saegeblatt=5, besaeumung=10, raster=4)
    pruefe(stueckzahl(e) == 10, f"alle 10 Teile geplant ({stueckzahl(e)})")

    # Ausnutzung darf trotz ueberlappender Bounding-Boxen nie ueber 100 % liegen
    for nr, plan in enumerate(e.plaene, start=1):
        pruefe(0.0 <= plan.ausnutzung <= 1.0,
               f"Tafel {nr}: Ausnutzung {plan.ausnutzung * 100:.1f} %")

    # --- PDF ---
    try:
        from pdf_export import pdf_2d, zeichne_kontur
        from fpdf import FPDF
        blatt = FPDF()
        blatt.add_page()
        pruefe(zeichne_kontur(blatt, [[(10, 10), (60, 10), (60, 40), (30, 40),
                                       (30, 60), (10, 60)]], "FD"),
               "Konturausgabe im PDF moeglich")
        # ohne polygon()-Methode (alte fpdf 1.7) muss der direkte Pfad greifen
        class OhnePolygon(FPDF):
            polygon = None
        alt = OhnePolygon()
        alt.add_page()
        pruefe(zeichne_kontur(alt, [[(10, 10), (60, 10), (35, 50)]], "FD"),
               "Konturausgabe auch ohne polygon()-Methode")
        daten = pdf_2d(e, "Test", {"saegeblatt": 5, "besaeumung": 10, "modus": "kontur"})
        pruefe(daten[:4] == b"%PDF" and len(daten) > 2000,
               f"PDF erzeugt ({len(daten)} Bytes)")
    except ImportError as exc:
        print(f"       (PDF uebersprungen: {exc})")

    # --- DXF: Exportpunkte gegen den Plan pruefen ---
    try:
        import io
        from dxf_import import plan_als_dxf
        from ezdxf import recover
        text = plan_als_dxf(e)
        doc, _ = recover.read(io.BytesIO(text.encode("utf-8")))
        polygone = [p for p in doc.modelspace()
                    if p.dxftype() == "POLYLINE" and p.dxf.layer == "KONTUR"]
        erwartet = sum(len(p.kontur) for plan in e.plaene for p in plan.platzierungen)
        pruefe(len(polygone) == erwartet,
               f"{len(polygone)} Konturzuege im DXF (erwartet {erwartet})")

        soll = []
        versatz = 0.0
        for plan in e.plaene:
            for p in plan.platzierungen:
                for ring in p.welt_kontur():
                    soll.append([(x + versatz, y) for x, y in ring])
            versatz += plan.breite + 200.0
        groesste = 0.0
        for polygon, punkte in zip(polygone, soll):
            ist = [(v.dxf.location[0], v.dxf.location[1]) for v in polygon.vertices]
            if len(ist) != len(punkte):
                groesste = float("inf")
                break
            for (ax, ay), (bx, by) in zip(ist, punkte):
                groesste = max(groesste, math.hypot(ax - bx, ay - by))
        pruefe(groesste < 0.001,
               f"DXF-Export deckt sich mit dem Plan (Abweichung {groesste:.4f} mm)")
    except ImportError as exc:
        print(f"       (DXF uebersprungen: {exc})")


def test_laufzeit():
    print("Kontur: Laufzeit bei einem realistischen Auftrag")
    teile = [Zuschnitt2D(1060, 660, 14, "Kassette A", "Alucobond",
                         kontur=kassette(1060, 660)),
             Zuschnitt2D(860, 1260, 8, "Kassette B", "Alucobond",
                         kontur=kassette(860, 1260)),
             Zuschnitt2D(600, 500, 10, "Blende", "Alucobond")]
    tafeln = [Tafel(1500, 3200, None, "Alucobond 1500x3200", "Alucobond", preis=310.0)]
    start = time.time()
    e = optimize_2d_kontur(teile, tafeln, saegeblatt=6, besaeumung=10, raster=5)
    dauer = time.time() - start
    pruefe(stueckzahl(e) == 32, f"alle 32 Teile platziert ({stueckzahl(e)})")
    pruefe(dauer < 25, f"Laufzeit {dauer:.1f} s")
    print(f"       -> {e.anzahl_tafeln} Tafeln, Ausnutzung "
          f"{e.ausnutzung_echt_prozent:.1f} %, {dauer:.1f} s")
    pruefe_plan(e, tafeln, 6, 10, 5, "Praxisfall")


def test_eigenwinkel():
    """Teile, die schief in ihrer Huelle liegen, werden selbst ausgerichtet."""
    print("\n14. Drehwinkel aus der Teileform")

    # Diagonalstreifen: Huelle 1400 x 1100, echte Breite nur 200 mm
    streifen = [[(0.0, 0.0), (200.0, 0.0), (1400.0, 1100.0), (1200.0, 1100.0)]]
    winkel = kn._eigenwinkel(streifen)
    # Die lange Kante steigt um 42,5 Grad; gedreht wird um 47,5 Grad, damit sie
    # waagrecht liegt.
    pruefe(any(abs(w % 180 - 47.5) < 3 for w in winkel),
           f"die Drehung fuer die lange Kante ist dabei "
           f"({[round(w, 1) for w in winkel]})")
    bester = min(winkel, key=lambda w: (lambda b, h: b * h)(*drehe_polygone(streifen, w)[1:]))
    _, b, h = drehe_polygone(streifen, bester)
    _, b0, h0 = drehe_polygone(streifen, 0.0)
    pruefe(b * h < 0.45 * b0 * h0,
           f"beste Lage hat weniger als die halbe Huellflaeche "
           f"({b:.0f}x{h:.0f} statt {b0:.0f}x{h0:.0f})")

    teile = [Zuschnitt2D(1400, 1100, 10, "Diagonale", "Alu", True, kontur=streifen)]
    tafeln = [Tafel(1500, 3000, None, "Tafel", "Alu")]
    # Hier geht es allein um die Drehwinkel - das Nachruecken wuerde den
    # Unterschied verwischen, weil es den festen Winkeln ebenfalls hilft.
    fest = optimize_2d_kontur(teile, tafeln, saegeblatt=5, besaeumung=0, raster=5,
                              winkel=kn.STANDARD_WINKEL, versuche=4, verdichten=False)
    frei = optimize_2d_kontur(teile, tafeln, saegeblatt=5, besaeumung=0, raster=5,
                              winkel=kn.FREIE_WINKEL, versuche=4, verdichten=False)
    print(f"       -> 90-Schritte: {fest.anzahl_tafeln} Tafeln "
          f"({fest.ausnutzung_echt_prozent:.1f} %), Eigenwinkel: "
          f"{frei.anzahl_tafeln} Tafeln ({frei.ausnutzung_echt_prozent:.1f} %)")
    pruefe(stueckzahl(fest) == 10 and stueckzahl(frei) == 10, "alle Teile platziert")
    pruefe(frei.anzahl_tafeln < fest.anzahl_tafeln,
           f"Eigenwinkel braucht weniger Tafeln ({frei.anzahl_tafeln} statt "
           f"{fest.anzahl_tafeln})")
    pruefe(frei.ausnutzung_echt_prozent > fest.ausnutzung_echt_prozent + 10,
           "Ausnutzung deutlich besser")
    pruefe_plan(frei, tafeln, 5, 0, 5, "Eigenwinkel")

    # Gegenprobe Rechtecke: darf nicht schlechter werden
    rechtecke = [Zuschnitt2D(700, 500, 20, "R", "Alu", True)]
    r_fest = optimize_2d_kontur(rechtecke, tafeln, saegeblatt=5, besaeumung=0,
                                raster=5, winkel=kn.STANDARD_WINKEL, versuche=4)
    r_frei = optimize_2d_kontur(rechtecke, tafeln, saegeblatt=5, besaeumung=0,
                                raster=5, winkel=kn.FREIE_WINKEL, versuche=4)
    pruefe(r_frei.anzahl_tafeln <= r_fest.anzahl_tafeln,
           f"Rechtecke werden nicht schlechter ({r_frei.anzahl_tafeln} vs "
           f"{r_fest.anzahl_tafeln} Tafeln)")

    # Nicht drehbare Teile bleiben trotz Eigenwinkeln stehen
    starr = [Zuschnitt2D(1400, 1100, 4, "Diagonale", "Alu", False, kontur=streifen)]
    e = optimize_2d_kontur(starr, tafeln, saegeblatt=5, besaeumung=0, raster=5,
                           winkel=kn.FREIE_WINKEL, versuche=2)
    gedreht = [p.winkel for plan in e.plaene for p in plan.platzierungen]
    pruefe(all(abs(w) < 1e-9 for w in gedreht),
           f"Laufrichtung schlaegt die Eigenwinkel ({gedreht})")


def test_nachruecken():
    """Die Rasterluft wird weggenommen - aber nie die Schnittfuge."""
    print("\n15. Nachruecken mit der echten Geometrie")
    FUGE, RAND = 5.0, 10.0

    def abstaende(ergebnis):
        raus = []
        for plan in ergebnis.plaene:
            ringe = [p.welt_kontur() for p in plan.platzierungen]
            seg = [kn._segmente_von(r) for r in ringe]
            for i in range(len(ringe)):
                for k in range(i + 1, len(ringe)):
                    d = kn._teile_abstand(ringe[i], ringe[k], seg[i], seg[k])
                    if d < 100:
                        raus.append(d)
        return sorted(raus)

    teile = [Zuschnitt2D(1000, 600, 14, "A", "Alu", True,
                         kontur=[[(0, 0), (1000, 0), (1000, 600), (0, 600)]]),
             Zuschnitt2D(800, 1200, 8, "B", "Alu", True,
                         kontur=[[(0, 0), (800, 0), (800, 1200), (0, 1200)]]),
             Zuschnitt2D(600, 500, 10, "C", "Alu", True)]
    tafeln = [Tafel(1500, 3200, None, "Tafel", "Alu")]

    ohne = optimize_2d_kontur(teile, tafeln, saegeblatt=FUGE, besaeumung=RAND,
                              raster=5, versuche=4, verdichten=False)
    mit = optimize_2d_kontur(teile, tafeln, saegeblatt=FUGE, besaeumung=RAND,
                             raster=5, versuche=4, verdichten=True)
    a_ohne, a_mit = abstaende(ohne), abstaende(mit)
    print(f"       -> ohne Nachruecken: kleinster Abstand {a_ohne[0]:.2f} mm, "
          f"Median {a_ohne[len(a_ohne)//2]:.2f} mm")
    print(f"       -> mit  Nachruecken: kleinster Abstand {a_mit[0]:.2f} mm, "
          f"Median {a_mit[len(a_mit)//2]:.2f} mm")

    pruefe(a_mit[0] >= FUGE - 0.01,
           f"Schnittfuge bleibt gewahrt ({a_mit[0]:.2f} mm bei {FUGE} mm Fuge)")
    pruefe(a_mit[0] < a_ohne[0] - 0.5 or
           a_mit[len(a_mit)//2] < a_ohne[len(a_ohne)//2] - 0.5,
           "die Teile ruecken naeher zusammen")
    pruefe(stueckzahl(mit) >= stueckzahl(ohne),
           f"es gehen nicht weniger Teile auf ({stueckzahl(mit)} statt "
           f"{stueckzahl(ohne)})")
    pruefe(mit.anzahl_tafeln <= ohne.anzahl_tafeln,
           f"nie mehr Tafeln als ohne ({mit.anzahl_tafeln} statt "
           f"{ohne.anzahl_tafeln})")
    pruefe_plan(mit, tafeln, FUGE, RAND, 5, "Nachruecken")

    # Teile im Ausschnitt duerfen nicht herausgeschoben werden
    rahmen = [[(0.0, 0.0), (1200.0, 0.0), (1200.0, 1200.0), (0.0, 1200.0)],
              [(200.0, 200.0), (1000.0, 200.0), (1000.0, 1000.0), (200.0, 1000.0)]]
    teile2 = [Zuschnitt2D(1200, 1200, 2, "Rahmen", "Alu", True, kontur=rahmen),
              Zuschnitt2D(700, 700, 2, "Einleger", "Alu", True)]
    e2 = optimize_2d_kontur(teile2, [Tafel(1250, 2600, None, "T", "Alu")],
                            saegeblatt=4, besaeumung=10, raster=5, versuche=4)
    pruefe(stueckzahl(e2) == 4, f"Rahmen und Einleger platziert ({stueckzahl(e2)})")
    pruefe_plan(e2, [Tafel(1250, 2600, None, "T", "Alu")], 4, 10, 5,
                "Nachruecken mit Ausschnitt")

    # Diagonalstreifen: hier spart das Nachruecken eine ganze Tafel
    streifen = [[(0.0, 0.0), (200.0, 0.0), (1400.0, 1100.0), (1200.0, 1100.0)]]
    teile3 = [Zuschnitt2D(1400, 1100, 10, "Diagonale", "Alu", True, kontur=streifen)]
    tafeln3 = [Tafel(1500, 3000, None, "Tafel", "Alu")]
    o3 = optimize_2d_kontur(teile3, tafeln3, saegeblatt=5, besaeumung=0, raster=5,
                            winkel=kn.STANDARD_WINKEL, versuche=4, verdichten=False)
    m3 = optimize_2d_kontur(teile3, tafeln3, saegeblatt=5, besaeumung=0, raster=5,
                            winkel=kn.STANDARD_WINKEL, versuche=4, verdichten=True)
    print(f"       -> Diagonalstreifen ohne {o3.anzahl_tafeln} Tafeln "
          f"({o3.ausnutzung_echt_prozent:.1f} %), mit {m3.anzahl_tafeln} Tafeln "
          f"({m3.ausnutzung_echt_prozent:.1f} %)")
    pruefe(m3.anzahl_tafeln < o3.anzahl_tafeln,
           f"Nachruecken spart hier eine Tafel ({m3.anzahl_tafeln} statt "
           f"{o3.anzahl_tafeln})")
    pruefe_plan(m3, tafeln3, 5, 0, 5, "Diagonalstreifen")


def test_kreuzende_kanten():
    """Der Abstand zweier Teile muss auch bei sich kreuzenden Kanten stimmen."""
    print("\n16. Abstandsmessung")
    import numpy as np
    waagrecht = (np.array([-10.0]), np.array([0.0]), np.array([10.0]), np.array([0.0]))
    senkrecht = (np.array([0.0]), np.array([-10.0]), np.array([0.0]), np.array([10.0]))
    pruefe(kn._kantenabstand(waagrecht, senkrecht) == 0.0,
           "sich kreuzende Kanten haben Abstand 0")
    entfernt = (np.array([0.0]), np.array([20.0]), np.array([0.0]), np.array([30.0]))
    pruefe(abs(kn._kantenabstand(waagrecht, entfernt) - 20.0) < 1e-9,
           "getrennte Kanten: richtiger Abstand")

    # Ein Teil ganz im Ausschnitt eines anderen liegt nicht "weit weg"
    rahmen = [[(0.0, 0.0), (1000.0, 0.0), (1000.0, 1000.0), (0.0, 1000.0)],
              [(100.0, 100.0), (900.0, 100.0), (900.0, 900.0), (100.0, 900.0)]]
    klein = [[(400.0, 400.0), (600.0, 400.0), (600.0, 600.0), (400.0, 600.0)]]
    pruefe(kn._teile_abstand(klein, rahmen, kn._segmente_von(klein),
                             kn._segmente_von(rahmen)) > 100.0,
           "Teil im Ausschnitt: Abstand zur Lochkante")
    ueberlappend = [[(500.0, 500.0), (1500.0, 500.0), (1500.0, 1500.0),
                     (500.0, 1500.0)]]
    pruefe(kn._teile_abstand(ueberlappend, rahmen, kn._segmente_von(ueberlappend),
                             kn._segmente_von(rahmen)) == 0.0,
           "ueberlappende Teile: Abstand 0")


if __name__ == "__main__":
    for fn in [test_rasterung, test_dreiecke_greifen_ineinander, test_l_formen,
               test_ausschnitt_wird_genutzt, test_kassetten_alucobond,
               test_laufrichtung, test_rechtecke_ohne_kontur, test_zu_grosses_teil,
               test_schnittfuge_wirkt, test_bbox_sicherheitsnetz, test_feine_winkel,
               test_rastergrenze, test_ohne_tafeln, test_ausgabe_pdf_und_dxf,
               test_eigenwinkel, test_nachruecken, test_kreuzende_kanten,
               test_laufzeit]:
        fn()
    print()
    if fehler:
        print(f"{len(fehler)} Test(s) fehlgeschlagen:")
        for f in fehler:
            print("  -", f)
        raise SystemExit(1)
    print("Alle Konturtests bestanden.")
