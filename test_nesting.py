"""
Tests fuer den Rechenkern (Bounding-Box-Nesting).
Ausfuehren mit:  python3 test_nesting.py
"""

from nesting import Tafel, Zuschnitt2D, optimize_2d, parse_2d_eingabe

fehler = []


def pruefe(bedingung, text):
    if bedingung:
        print(f"  OK   {text}")
    else:
        print(f"  FEHL {text}")
        fehler.append(text)


def _keine_ueberlappung(plan):
    for i, a in enumerate(plan.platzierungen):
        for b in plan.platzierungen[i + 1:]:
            trennt = (a.x + a.breite <= b.x + 1e-6 or b.x + b.breite <= a.x + 1e-6
                      or a.y + a.hoehe <= b.y + 1e-6 or b.y + b.hoehe <= a.y + 1e-6)
            if not trennt:
                return False
    return True


def test_2d_guillotine():
    print("2D: Streifen-/Guillotineschnitt")
    teile = [Zuschnitt2D(1000, 500, 8, "Blende")]
    tafeln = [Tafel(2000, 1000, None, "Tafel 2000x1000")]
    e = optimize_2d(teile, tafeln, saegeblatt=0, modus="guillotine")
    pruefe(e.anzahl_tafeln == 2, f"2 Tafeln erwartet, erhalten {e.anzahl_tafeln}")
    pruefe(not e.fehlende, "alle Teile platziert")
    pruefe(e.ausnutzung_prozent > 99, f"Ausnutzung {e.ausnutzung_prozent:.1f} %")
    for plan in e.plaene:
        pruefe(_keine_ueberlappung(plan), "keine Ueberlappung")
        for p in plan.platzierungen:
            pruefe(p.x >= -1e-6 and p.y >= -1e-6
                   and p.x + p.breite <= plan.breite + 1e-6
                   and p.y + p.hoehe <= plan.hoehe + 1e-6, "Teil liegt auf der Tafel")


def test_2d_frei_und_drehung():
    print("2D: freies Nesting mit Drehung")
    teile = [Zuschnitt2D(1200, 400, 5, "Steg", drehbar=True)]
    tafeln = [Tafel(2500, 1250, None, "Tafel 2500x1250")]
    e = optimize_2d(teile, tafeln, saegeblatt=3, modus="frei")
    pruefe(e.anzahl_tafeln == 1, f"1 Tafel reicht, erhalten {e.anzahl_tafeln}")
    pruefe(not e.fehlende, "alle Teile platziert")
    for plan in e.plaene:
        pruefe(_keine_ueberlappung(plan), "keine Ueberlappung")


def test_2d_nicht_drehbar():
    print("2D: Walzrichtung (nicht drehbar) wird respektiert")
    teile = [Zuschnitt2D(2000, 300, 3, "Dekor", drehbar=False)]
    tafeln = [Tafel(2000, 1000, None, "Tafel")]
    e = optimize_2d(teile, tafeln, saegeblatt=0, modus="frei")
    for plan in e.plaene:
        for p in plan.platzierungen:
            pruefe(not p.gedreht and p.breite == 2000, "Teil wurde nicht gedreht")


def test_2d_besaeumung():
    print("2D: Besaeumung reduziert die Nutzflaeche")
    teile = [Zuschnitt2D(990, 990, 4, "Platte")]
    tafeln = [Tafel(2000, 2000, None, "Tafel")]
    ohne = optimize_2d(teile, tafeln, saegeblatt=0, besaeumung=0, modus="guillotine")
    mit = optimize_2d(teile, tafeln, saegeblatt=0, besaeumung=20, modus="guillotine")
    pruefe(ohne.anzahl_tafeln == 1, f"ohne Besaeumung 1 Tafel, erhalten {ohne.anzahl_tafeln}")
    # 1960 mm Nutzbreite fasst nur noch ein 990er Teil je Streifen -> 4 Tafeln
    pruefe(mit.anzahl_tafeln == 4, f"mit Besaeumung 4 Tafeln, erhalten {mit.anzahl_tafeln}")
    for plan in mit.plaene:
        for p in plan.platzierungen:
            pruefe(p.x >= 20 - 1e-6 and p.y >= 20 - 1e-6, "Teil liegt innerhalb der Besaeumung")


def test_material_zuordnung():
    print("Zuordnung: leere Materialangabe passt auf alles")
    # 2D: Teil ohne Material, Tafel mit Material
    e = optimize_2d([Zuschnitt2D(500, 400, 2, "DXF-Teil", material="")],
                    [Tafel(1250, 2500, None, "Tafel", material="Alucobond 4 mm")],
                    saegeblatt=0)
    pruefe(not e.fehlende and e.anzahl_tafeln == 1, f"Teil ohne Material platziert: {e.fehlende}")

    # 2D: Materialien vorhanden -> keine Vermischung
    e2 = optimize_2d([Zuschnitt2D(500, 400, 2, "Alu", material="Alu"),
                      Zuschnitt2D(500, 400, 2, "Stahl", material="Stahl")],
                     [Tafel(1250, 2500, None, "Alutafel", material="Alu")],
                     saegeblatt=0)
    pruefe(len(e2.fehlende) == 1 and e2.fehlende[0][0] == "Stahl",
           f"Stahlteile bleiben offen: {e2.fehlende}")
    for plan in e2.plaene:
        for p in plan.platzierungen:
            pruefe(p.bezeichnung == "Alu", "kein Materialmix auf einer Tafel")


def test_parser():
    print("Parser: Schnellerfassung")
    z = parse_2d_eingabe("1000 x 500 x 3\n800;600;2;Wange;Blech 2 mm")
    pruefe(len(z) == 2, f"2 Positionen, erhalten {len(z)}")
    pruefe(z[0].breite == 1000 and z[0].hoehe == 500 and z[0].anzahl == 3, f"{z[0]}")
    pruefe(z[1].material == "Blech 2 mm", f"{z[1]}")


def test_realistischer_fall():
    print("Praxisfall: Fassadenblech")
    teile = [Zuschnitt2D(1060, 660, 12, "Kassette", "Alucobond 4 mm", drehbar=False),
             Zuschnitt2D(600, 500, 8, "Blende", "Alucobond 4 mm"),
             Zuschnitt2D(1200, 300, 6, "Attika", "Alucobond 4 mm")]
    tafeln = [Tafel(1500, 3200, None, "Alucobond 1500x3200", "Alucobond 4 mm",
                    preis=310.0)]
    e = optimize_2d(teile, tafeln, saegeblatt=6, besaeumung=10, modus="frei")
    pruefe(not e.fehlende, f"alles geplant, fehlend: {e.fehlende}")
    pruefe(e.ausnutzung_prozent > 60, f"Ausnutzung {e.ausnutzung_prozent:.1f} %")
    for plan in e.plaene:
        pruefe(_keine_ueberlappung(plan), "keine Ueberlappung")
    print(f"       -> {e.anzahl_tafeln} Tafeln, {e.gesamt_kosten:.2f} EUR, "
          f"Verschnitt {e.verschnitt_prozent:.1f} %")


if __name__ == "__main__":
    for fn in [
        test_2d_guillotine, test_2d_frei_und_drehung, test_2d_nicht_drehbar,
        test_2d_besaeumung, test_material_zuordnung, test_parser,
        test_realistischer_fall,
    ]:
        fn()
    print()
    if fehler:
        print(f"{len(fehler)} Test(s) fehlgeschlagen:")
        for f in fehler:
            print("  -", f)
        raise SystemExit(1)
    print("Alle Tests bestanden.")
