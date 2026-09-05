"""
Tests fuer den Nesting-Rechenkern. Ausfuehren mit:  python3 test_nesting.py
"""

from nesting import (
    Teil, Stange, Tafel, Zuschnitt2D,
    optimize_1d, optimize_2d, parse_1d_eingabe, parse_2d_eingabe,
)

fehler = []


def pruefe(bedingung, text):
    if bedingung:
        print(f"  OK   {text}")
    else:
        print(f"  FEHL {text}")
        fehler.append(text)


def test_1d_grundfall():
    print("1D: exakte Aufteilung ohne Saegeblatt")
    teile = [Teil(2000, 3, "A"), Teil(1000, 3, "B")]
    stangen = [Stange(6000, None, "Stange 6 m")]
    e = optimize_1d(teile, stangen, saegeblatt=0, min_reststueck=99999)
    pruefe(e.anzahl_stangen == 2, f"2 Stangen erwartet, erhalten {e.anzahl_stangen}")
    pruefe(not e.fehlende, "keine fehlenden Teile")
    pruefe(abs(e.gesamt_nutzteil - 9000) < 1e-6, f"9000 mm Nutzteil, erhalten {e.gesamt_nutzteil}")
    pruefe(e.verschnitt_prozent < 26, f"Verschnitt {e.verschnitt_prozent:.1f} % < 26 %")
    for plan in e.plaene:
        summe = sum(p.laenge for p in plan.platzierungen)
        pruefe(summe <= plan.nutzlaenge + 1e-6, "Stange nicht ueberfuellt")


def test_1d_saegeblatt_und_positionen():
    print("1D: Saegeblatt wird beruecksichtigt")
    teile = [Teil(2000, 3, "A")]
    stangen = [Stange(6000, None, "Stange 6 m")]
    e = optimize_1d(teile, stangen, saegeblatt=5, min_reststueck=99999)
    # 3 x (2000+5) = 6015 > 6000 -> passt nicht auf eine Stange
    pruefe(e.anzahl_stangen == 2, f"2 Stangen wegen Schnittfuge, erhalten {e.anzahl_stangen}")
    plan = e.plaene[0]
    for a, b in zip(plan.platzierungen, plan.platzierungen[1:]):
        pruefe(abs(b.start - a.ende - 5) < 1e-6, "Schnittfuge zwischen den Teilen")


def test_1d_anschnitt_und_rest():
    print("1D: Anschnitt, Endschnitt und Restverwertung")
    teile = [Teil(1000, 4, "A")]
    stangen = [Stange(6000, None, "Stange 6 m")]
    e = optimize_1d(teile, stangen, saegeblatt=3, anschnitt=20, endschnitt=10,
                    min_reststueck=1500)
    plan = e.plaene[0]
    pruefe(plan.platzierungen[0].start == 20, "erstes Teil startet nach dem Anschnitt")
    pruefe(plan.rest >= 1500 and plan.rest_verwertbar, f"Rest {plan.rest:.0f} mm ist verwertbar")
    # verwertbarer Rest zaehlt nicht als Verschnitt
    pruefe(e.verschnitt < 600, f"Verschnitt {e.verschnitt:.0f} mm ohne verwertbaren Rest")


def test_1d_reststuecke_zuerst():
    print("1D: Reststuecke aus dem Lager werden bevorzugt")
    teile = [Teil(1400, 2, "A")]
    stangen = [
        Stange(6000, None, "Neuware 6 m"),
        Stange(3000, 1, "Rest 3 m", reststueck=True),
    ]
    e = optimize_1d(teile, stangen, saegeblatt=3, reste_zuerst=True, min_reststueck=500)
    pruefe(any(p.reststueck for p in e.plaene), "Reststueck wurde verwendet")
    pruefe(e.anzahl_stangen == 1, f"1 Stange reicht, erhalten {e.anzahl_stangen}")


def test_1d_mehrere_profile():
    print("1D: getrennte Optimierung je Profil")
    teile = [
        Teil(2500, 2, "Pfosten", "Rohr 40x40"),
        Teil(1800, 2, "Handlauf", "Rohr 42,4"),
    ]
    stangen = [
        Stange(6000, None, "Rohr 40x40 - 6 m", profil="Rohr 40x40"),
        Stange(6000, None, "Rohr 42,4 - 6 m", profil="Rohr 42,4"),
    ]
    e = optimize_1d(teile, stangen, saegeblatt=3)
    profile = {p.profil for p in e.plaene}
    pruefe(profile == {"Rohr 40x40", "Rohr 42,4"}, f"beide Profile geplant: {profile}")
    for plan in e.plaene:
        for pl in plan.platzierungen:
            passend = ("Pfosten" if plan.profil == "Rohr 40x40" else "Handlauf")
            pruefe(pl.bezeichnung == passend, "kein Profilmix auf einer Stange")


def test_1d_zu_langes_teil():
    print("1D: uebergrosses Teil wird gemeldet")
    teile = [Teil(7000, 1, "Zu lang"), Teil(1000, 2, "OK")]
    stangen = [Stange(6000, None, "Stange 6 m")]
    e = optimize_1d(teile, stangen, saegeblatt=3)
    pruefe(len(e.fehlende) == 1 and e.fehlende[0][0] == "Zu lang", f"fehlend: {e.fehlende}")
    pruefe(e.anzahl_stangen == 1, "restliche Teile trotzdem geplant")


def test_1d_begrenzter_bestand():
    print("1D: begrenzter Lagerbestand")
    teile = [Teil(2000, 6, "A")]
    stangen = [Stange(6000, 1, "Stange 6 m")]
    e = optimize_1d(teile, stangen, saegeblatt=0)
    pruefe(e.anzahl_stangen == 1, "nur die vorhandene Stange verwendet")
    pruefe(e.fehlende and e.fehlende[0][2] == 3, f"3 Teile offen, erhalten {e.fehlende}")


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
    print("Zuordnung: leere Material-/Profilangabe passt auf alles")
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

    # 1D: Teil ohne Profil, Stange mit Profil
    e3 = optimize_1d([Teil(1000, 3, "Teil", profil="")],
                     [Stange(6000, None, "Rohr", profil="Rohr 40x40")], saegeblatt=0)
    pruefe(not e3.fehlende and e3.anzahl_stangen == 1,
           f"Teil ohne Profil platziert: {e3.fehlende}")


def test_parser():
    print("Parser: Schnellerfassung")
    t = parse_1d_eingabe("1250 x 4\n2000*2 Pfosten\n3000;2;Handlauf;Rohr 42,4\n# Kommentar\n")
    pruefe(len(t) == 3, f"3 Positionen, erhalten {len(t)}")
    pruefe(t[0].laenge == 1250 and t[0].anzahl == 4, f"{t[0]}")
    pruefe(t[1].anzahl == 2 and t[1].bezeichnung == "Pfosten", f"{t[1]}")
    pruefe(t[2].profil == "Rohr 42,4" and t[2].anzahl == 2, f"{t[2]}")

    z = parse_2d_eingabe("1000 x 500 x 3\n800;600;2;Wange;Blech 2 mm")
    pruefe(len(z) == 2, f"2 Positionen, erhalten {len(z)}")
    pruefe(z[0].breite == 1000 and z[0].hoehe == 500 and z[0].anzahl == 3, f"{z[0]}")
    pruefe(z[1].material == "Blech 2 mm", f"{z[1]}")


def test_realistischer_fall():
    print("Praxisfall: Gelaender 12 lfm")
    teile = [
        Teil(1050, 9, "Pfosten", "Rohr 40x40x2"),
        Teil(1980, 6, "Handlauf", "Rohr 42,4x2"),
        Teil(940, 24, "Fuellstab", "Rundstahl 12"),
    ]
    stangen = [
        Stange(6000, None, "Rohr 40x40x2 - 6 m", profil="Rohr 40x40x2", preis=48.0),
        Stange(6000, None, "Rohr 42,4x2 - 6 m", profil="Rohr 42,4x2", preis=39.0),
        Stange(6000, None, "Rundstahl 12 - 6 m", profil="Rundstahl 12", preis=12.5),
    ]
    e = optimize_1d(teile, stangen, saegeblatt=3, anschnitt=10, endschnitt=10,
                    min_reststueck=400)
    pruefe(not e.fehlende, f"alles geplant, fehlend: {e.fehlende}")
    pruefe(e.ausnutzung_prozent > 85, f"Ausnutzung {e.ausnutzung_prozent:.1f} % > 85 %")
    print(f"       -> {e.anzahl_stangen} Stangen, {e.gesamt_kosten:.2f} EUR, "
          f"Verschnitt {e.verschnitt_prozent:.1f} %, verwertbare Reste "
          f"{e.verwertbare_reste:.0f} mm")


if __name__ == "__main__":
    for fn in [
        test_1d_grundfall, test_1d_saegeblatt_und_positionen, test_1d_anschnitt_und_rest,
        test_1d_reststuecke_zuerst, test_1d_mehrere_profile, test_1d_zu_langes_teil,
        test_1d_begrenzter_bestand, test_2d_guillotine, test_2d_frei_und_drehung,
        test_2d_nicht_drehbar, test_2d_besaeumung, test_material_zuordnung,
        test_parser, test_realistischer_fall,
    ]:
        fn()
    print()
    if fehler:
        print(f"{len(fehler)} Test(s) fehlgeschlagen:")
        for f in fehler:
            print("  -", f)
        raise SystemExit(1)
    print("Alle Tests bestanden.")
