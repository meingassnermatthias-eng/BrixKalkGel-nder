"""
Tests fuer den DXF-Import/-Export. Ausfuehren mit:  python3 test_dxf.py

Erzeugt eine kuenstliche Alucobond-Kassetten-Abwicklung, wie sie HiCAD
ausgibt (Aussenkontur mit Eckausklinkungen, Fraeslinien, Ausschnitt,
Positionstext) und prueft den kompletten Weg DXF -> Nesting -> DXF.
"""

import io

import dxf_import as dx
from dxf_import import lade_dxf, plan_als_dxf, teile_als_dxf, klassifiziere_layer
from nesting import Tafel, Zuschnitt2D, optimize_2d

fehler = []


def pruefe(bedingung, text):
    if bedingung:
        print(f"  OK   {text}")
    else:
        print(f"  FEHL {text}")
        fehler.append(text)


def kassette_kontur(x0, y0, breite, hoehe, kante=30.0):
    """Abwicklung einer Kassette: Rechteck mit vier Eckausklinkungen."""
    b, h, k = breite, hoehe, kante
    return [(x0 + k, y0), (x0 + b - k, y0), (x0 + b - k, y0 + k), (x0 + b, y0 + k),
            (x0 + b, y0 + h - k), (x0 + b - k, y0 + h - k), (x0 + b - k, y0 + h),
            (x0 + k, y0 + h), (x0 + k, y0 + h - k), (x0, y0 + h - k),
            (x0, y0 + k), (x0 + k, y0 + k)]


def baue_hicad_dxf(kassetten):
    """Schreibt eine DXF-Datei im Stil eines HiCAD-Exports."""
    import ezdxf
    doc = ezdxf.new("R2010")
    doc.layers.add("AUSSENKONTUR", color=7)
    doc.layers.add("FRAESUNG", color=1)
    doc.layers.add("BEMASSUNG", color=4)
    doc.layers.add("BESCHRIFTUNG", color=3)
    msp = doc.modelspace()

    for (x0, y0, b, h, name, mit_loch) in kassetten:
        msp.add_lwpolyline(kassette_kontur(x0, y0, b, h), close=True,
                           dxfattribs={"layer": "AUSSENKONTUR"})
        # Fraesnuten (Falzlinien) 30 mm innen
        k = 30.0
        for (a, e) in [((x0 + k, y0 + k), (x0 + b - k, y0 + k)),
                       ((x0 + k, y0 + h - k), (x0 + b - k, y0 + h - k)),
                       ((x0 + k, y0 + k), (x0 + k, y0 + h - k)),
                       ((x0 + b - k, y0 + k), (x0 + b - k, y0 + h - k))]:
            msp.add_line(a, e, dxfattribs={"layer": "FRAESUNG"})
        if mit_loch:
            msp.add_circle((x0 + b / 2, y0 + h / 2), 40.0,
                           dxfattribs={"layer": "AUSSENKONTUR"})
        msp.add_text(name, height=25,
                     dxfattribs={"layer": "BESCHRIFTUNG"}).set_placement((x0 + 60, y0 + 60))
        # Bemassung auf einem Layer, der ignoriert werden muss
        msp.add_line((x0, y0 - 100), (x0 + b, y0 - 100), dxfattribs={"layer": "BEMASSUNG"})

    puffer = io.StringIO()
    doc.write(puffer)
    return puffer.getvalue().encode("utf-8")


def test_layer_erkennung():
    print("DXF: Layer-Klassifizierung")
    pruefe(klassifiziere_layer("AUSSENKONTUR") == "kontur", "AUSSENKONTUR -> kontur")
    pruefe(klassifiziere_layer("FRAESUNG") == "stich", "FRAESUNG -> stich")
    pruefe(klassifiziere_layer("Fräsnut") == "stich", "Fraesnut -> stich")
    pruefe(klassifiziere_layer("Biegelinie") == "stich", "Biegelinie -> stich")
    pruefe(klassifiziere_layer("BEMASSUNG") == "ignorieren", "BEMASSUNG -> ignorieren")
    pruefe(klassifiziere_layer("Defpoints") == "ignorieren", "Defpoints -> ignorieren")
    pruefe(klassifiziere_layer("0") == "kontur", "unbekannter Layer -> kontur")


def test_import_einzelteil():
    print("DXF: Import einer Kassette")
    daten = baue_hicad_dxf([(0, 0, 1060, 660, "POS-1", True)])
    e = lade_dxf(daten, "kassette.dxf")
    pruefe(len(e.teile) == 1, f"1 Teil erkannt, erhalten {len(e.teile)}")
    if not e.teile:
        return
    t = e.teile[0]
    pruefe(abs(t.breite - 1060) < 0.6 and abs(t.hoehe - 660) < 0.6,
           f"Aussenmass {t.breite}x{t.hoehe} (erwartet 1060x660)")
    pruefe(t.bezeichnung == "POS-1", f"Bezeichnung aus Text: {t.bezeichnung}")
    pruefe(len(t.kontur) == 2, f"Aussenkontur + 1 Ausschnitt, erhalten {len(t.kontur)}")
    # Flaeche = Rechteck - 4 Ecken - Loch
    soll = 1060 * 660 - 4 * 30 * 30 - 3.14159 * 40 ** 2
    pruefe(abs(t.flaeche - soll) / soll < 0.01, f"Flaeche {t.flaeche:.0f} mm2 (soll {soll:.0f})")
    pruefe(len(t.stichlinien) == 4, f"4 Fraeslinien, erhalten {len(t.stichlinien)}")
    pruefe("BEMASSUNG" in e.layer and e.layer["BEMASSUNG"][0] == "ignorieren",
           "Bemassungslayer erkannt und ignoriert")
    pruefe(t.ausnutzung_bbox < 1.0, f"Kontur fuellt Bounding-Box zu {t.ausnutzung_bbox*100:.1f} %")


def test_import_mehrere_und_buendeln():
    print("DXF: mehrere Teile, gleiche Teile buendeln")
    daten = baue_hicad_dxf([
        (0, 0, 1060, 660, "POS-1", False),
        (1500, 0, 1060, 660, "POS-1", False),      # identisch -> Stueckzahl 2
        (3000, 0, 800, 500, "POS-2", False),
    ])
    e = lade_dxf(daten, "mehrere.dxf")
    pruefe(len(e.teile) == 2, f"2 Positionen nach Buendelung, erhalten {len(e.teile)}")
    gesamt = sum(t.anzahl for t in e.teile)
    pruefe(gesamt == 3, f"3 Teile insgesamt, erhalten {gesamt}")
    gross = [t for t in e.teile if t.breite > 1000]
    pruefe(gross and gross[0].anzahl == 2, "gleiche Kassetten zu 2 Stueck gebuendelt")

    ohne = lade_dxf(daten, "mehrere.dxf", zusammenfassen=False)
    pruefe(len(ohne.teile) == 3, f"ohne Buendelung 3 Positionen, erhalten {len(ohne.teile)}")


def test_fallback_parser():
    print("DXF: Parser ohne ezdxf")
    daten = baue_hicad_dxf([(0, 0, 1060, 660, "POS-1", True)])
    original = dx.EZDXF_VERFUEGBAR
    try:
        dx.EZDXF_VERFUEGBAR = False
        e = lade_dxf(daten, "kassette.dxf")
        pruefe(len(e.teile) == 1, f"1 Teil auch ohne ezdxf, erhalten {len(e.teile)}")
        if e.teile:
            t = e.teile[0]
            pruefe(abs(t.breite - 1060) < 1 and abs(t.hoehe - 660) < 1,
                   f"Aussenmass {t.breite}x{t.hoehe}")
            pruefe(len(t.stichlinien) == 4, f"4 Fraeslinien, erhalten {len(t.stichlinien)}")
        pruefe(any("ezdxf" in h for h in e.hinweise), "Hinweis auf fehlendes ezdxf")
    finally:
        dx.EZDXF_VERFUEGBAR = original


def test_dxf_nach_nesting_und_export():
    print("DXF: kompletter Weg DXF -> Nesting -> DXF")
    daten = baue_hicad_dxf([(0, 0, 1060, 660, "Kassette", False)])
    e = lade_dxf(daten, "kassette.dxf")
    t = e.teile[0]

    teile = [Zuschnitt2D(t.breite, t.hoehe, 6, t.bezeichnung, "Alucobond 4 mm",
                         drehbar=False, kontur=t.kontur, stichlinien=t.stichlinien)]
    tafeln = [Tafel(1500, 3200, None, "Alucobond 1500x3200", "Alucobond 4 mm", preis=310.0)]
    plan = optimize_2d(teile, tafeln, saegeblatt=8, besaeumung=10, modus="guillotine")

    pruefe(not plan.fehlende, f"alle Kassetten platziert, fehlend: {plan.fehlende}")
    pruefe(plan.anzahl_tafeln >= 1, f"{plan.anzahl_tafeln} Tafel(n)")
    for tp in plan.plaene:
        for p in tp.platzierungen:
            pruefe(not p.gedreht, "Laufrichtung eingehalten (nicht gedreht)")
            pruefe(len(p.kontur) >= 1, "Kontur an der Platzierung vorhanden")
            welt = p.welt_kontur()[0]
            xs = [q[0] for q in welt]
            ys = [q[1] for q in welt]
            pruefe(min(xs) >= p.x - 0.01 and max(xs) <= p.x + p.breite + 0.01,
                   "Kontur liegt in der Bounding-Box (X)")
            pruefe(min(ys) >= p.y - 0.01 and max(ys) <= p.y + p.hoehe + 0.01,
                   "Kontur liegt in der Bounding-Box (Y)")

    text = plan_als_dxf(plan)
    pruefe(text.startswith("0\nSECTION") and text.rstrip().endswith("EOF"),
           "DXF-Grundstruktur")
    pruefe("FRAESLINIE" in text, "Fraeslinien-Layer im Export")

    # Export mit ezdxf gegenlesen
    import ezdxf
    from ezdxf import recover
    doc, _ = recover.read(io.BytesIO(text.encode("utf-8")))
    msp = doc.modelspace()
    layer = {ent.dxf.layer for ent in msp}
    pruefe({"TAFEL", "KONTUR", "FRAESLINIE", "BESCHRIFTUNG"} <= layer,
           f"alle Layer vorhanden: {sorted(layer)}")
    konturen = [ent for ent in msp if ent.dxftype() == "POLYLINE"
                and ent.dxf.layer == "KONTUR"]
    pruefe(len(konturen) == 6, f"6 Kassettenkonturen im Export, erhalten {len(konturen)}")
    ecken = len(list(konturen[0].vertices))
    pruefe(ecken == 12, f"Kontur mit 12 Eckpunkten uebernommen, erhalten {ecken}")

    uebersicht = teile_als_dxf(e.teile)
    doc2, _ = recover.read(io.BytesIO(uebersicht.encode("utf-8")))
    pruefe(len(list(doc2.modelspace())) > 0, "Teileuebersicht als DXF lesbar")


def test_gedrehte_kontur():
    print("DXF: Kontur wird korrekt mitgedreht")
    daten = baue_hicad_dxf([(0, 0, 1200, 400, "Streifen", False)])
    e = lade_dxf(daten, "streifen.dxf")
    t = e.teile[0]
    teile = [Zuschnitt2D(t.breite, t.hoehe, 3, t.bezeichnung, drehbar=True,
                         kontur=t.kontur, stichlinien=t.stichlinien)]
    tafeln = [Tafel(500, 4000, None, "Schmale Tafel")]
    plan = optimize_2d(teile, tafeln, saegeblatt=0, modus="guillotine")
    pruefe(not plan.fehlende, "gedrehte Teile passen auf die schmale Tafel")
    for tp in plan.plaene:
        for p in tp.platzierungen:
            pruefe(p.gedreht, "Teil wurde gedreht")
            welt = p.welt_kontur()[0]
            xs = [q[0] for q in welt]
            ys = [q[1] for q in welt]
            pruefe(abs((max(xs) - min(xs)) - 400) < 1, f"Breite nach Drehung {max(xs)-min(xs):.0f}")
            pruefe(abs((max(ys) - min(ys)) - 1200) < 1, f"Hoehe nach Drehung {max(ys)-min(ys):.0f}")
            pruefe(min(xs) >= p.x - 0.01 and max(xs) <= p.x + p.breite + 0.01,
                   "gedrehte Kontur bleibt in der Bounding-Box")


def test_offene_kontur_meldung():
    print("DXF: offene Kontur wird gemeldet")
    import ezdxf
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    # Rechteck mit 5 mm Luecke
    msp.add_line((0, 0), (1000, 0), dxfattribs={"layer": "KONTUR"})
    msp.add_line((1000, 0), (1000, 500), dxfattribs={"layer": "KONTUR"})
    msp.add_line((1000, 500), (0, 500), dxfattribs={"layer": "KONTUR"})
    msp.add_line((0, 500), (0, 5), dxfattribs={"layer": "KONTUR"})
    puffer = io.StringIO()
    doc.write(puffer)
    e = lade_dxf(puffer.getvalue().encode("utf-8"), "offen.dxf", toleranz=0.1)
    pruefe(any("offen" in h.lower() for h in e.hinweise), f"Hinweis erzeugt: {e.hinweise}")
    # mit groesserer Toleranz wird die Kontur geschlossen
    e2 = lade_dxf(puffer.getvalue().encode("utf-8"), "offen.dxf", toleranz=6.0)
    pruefe(len(e2.teile) == 1, f"mit 6 mm Toleranz geschlossen, Teile: {len(e2.teile)}")


if __name__ == "__main__":
    for fn in [test_layer_erkennung, test_import_einzelteil, test_import_mehrere_und_buendeln,
               test_fallback_parser, test_dxf_nach_nesting_und_export, test_gedrehte_kontur,
               test_offene_kontur_meldung]:
        fn()
    print()
    if fehler:
        print(f"{len(fehler)} Test(s) fehlgeschlagen:")
        for f in fehler:
            print("  -", f)
        raise SystemExit(1)
    print("Alle DXF-Tests bestanden.")
