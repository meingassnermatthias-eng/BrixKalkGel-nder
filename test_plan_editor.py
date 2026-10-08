"""
Tests fuer den Plan-Editor. Ausfuehren mit:  python3 test_plan_editor.py

Geprueft wird die Python-Seite: Vorgabe fuer die Oberflaeche, Ruecknahme der
Aenderungen in den Plan und die Buchhaltung der nicht eingeplanten Teile.
"""

import math

from nesting import Tafel, Zuschnitt2D, optimize_2d
from plan_editor import daten_fuer, kontur_karte, uebernehme, vorrat_fuer

fehler = []


def pruefe(bedingung, text):
    if bedingung:
        print(f"  OK   {text}")
    else:
        print(f"  FEHL {text}")
        fehler.append(text)


def l_form(breite, hoehe, steg):
    return [[(0.0, 0.0), (breite, 0.0), (breite, steg), (steg, steg),
             (steg, hoehe), (0.0, hoehe)]]


def beispiel():
    teile = [Zuschnitt2D(600, 400, 3, "Blende", "Stahl"),
             Zuschnitt2D(800, 800, 2, "Winkel", "Stahl", kontur=l_form(800, 800, 300))]
    tafeln = [Tafel(1500, 3000, None, "Blech", "Stahl", preis=200.0)]
    return optimize_2d(teile, tafeln, saegeblatt=5, besaeumung=10, modus="frei")


def test_vorgabe():
    print("Editor: Vorgabe fuer die Oberflaeche")
    erg = beispiel()
    plan = erg.plaene[0]
    farben = {"Blende": "#111111", "Winkel": "#222222"}
    daten = daten_fuer(plan, 1, saegeblatt=5, besaeumung=10, farben=farben, vorrat=[])

    pruefe(daten["tafel"]["breite"] == 1500 and daten["tafel"]["hoehe"] == 3000,
           "Tafelmasse uebergeben")
    pruefe(daten["saegeblatt"] == 5 and daten["tafel"]["besaeumung"] == 10,
           "Schnittfuge und Besaeumung uebergeben")
    pruefe(len(daten["teile"]) == len(plan.platzierungen),
           f"{len(daten['teile'])} Teile uebergeben")
    for eintrag, p in zip(daten["teile"], plan.platzierungen):
        pruefe(eintrag["sorte"] == p.bezeichnung, f"Bezeichnung {eintrag['sorte']}")
        pruefe(len(eintrag["kontur"]) >= 1 and len(eintrag["kontur"][0]) >= 3,
               "Kontur vorhanden (auch bei Rechtecken)")
        pruefe(eintrag["farbe"] == farben[p.bezeichnung], "Farbe uebernommen")
    # alles muss sich als JSON verschicken lassen
    import json
    pruefe(isinstance(json.dumps(daten), str), "Vorgabe ist JSON-tauglich")


def test_verschieben():
    print("Editor: Verschieben wird uebernommen")
    erg = beispiel()
    plan = erg.plaene[0]
    karte = kontur_karte(erg)
    vorher = [(p.x, p.y) for p in plan.platzierungen]

    rueckgabe = {"teile": [
        {"id": f"t{i}", "sorte": p.bezeichnung, "x": p.x + 25, "y": p.y + 40,
         "winkel": p.winkel}
        for i, p in enumerate(plan.platzierungen)]}
    meldungen = uebernehme(erg, 0, rueckgabe, karte)

    pruefe(len(plan.platzierungen) == len(vorher), "Teilezahl unveraendert")
    for (x, y), p in zip(vorher, plan.platzierungen):
        pruefe(abs(p.x - (x + 25)) < 1e-6 and abs(p.y - (y + 40)) < 1e-6,
               f"Teil steht bei {p.x:.0f}/{p.y:.0f}")
    pruefe(any("verschoben" in m for m in meldungen), f"Meldung: {meldungen}")


def test_rechteck_ohne_kontur():
    print("Editor: Rechteckteile ohne DXF-Kontur behalten ihre Masse")
    erg = beispiel()
    plan = erg.plaene[0]
    karte = kontur_karte(erg)
    # genau die Teile, die keine eigene Kontur mitbringen
    ohne = [(i, p) for i, p in enumerate(plan.platzierungen) if p.bezeichnung == "Blende"]
    pruefe(bool(ohne), "Beispiel enthaelt Rechteckteile")
    masse_vorher = {i: (p.breite, p.hoehe) for i, p in ohne}

    rueckgabe = {"teile": [
        {"id": f"t{i}", "sorte": p.bezeichnung, "x": p.x + 10, "y": p.y,
         "winkel": p.winkel}
        for i, p in enumerate(plan.platzierungen)]}
    uebernehme(erg, 0, rueckgabe, karte)

    pruefe(len(plan.platzierungen) == len(rueckgabe["teile"]),
           f"kein Teil verloren ({len(plan.platzierungen)})")
    for i, _ in ohne:
        p = plan.platzierungen[i]
        pruefe(p.breite > 0 and p.hoehe > 0,
               f"Teil {i}: {p.breite:.0f} x {p.hoehe:.0f} mm")
        pruefe((round(p.breite, 3), round(p.hoehe, 3))
               == (round(masse_vorher[i][0], 3), round(masse_vorher[i][1], 3)),
               f"Masse unveraendert ({p.breite:.0f} x {p.hoehe:.0f})")
    pruefe(plan.ausnutzung > 0, f"Ausnutzung {plan.ausnutzung*100:.1f} % > 0")

    # und nach dem Drehen passt die Bounding-Box weiterhin
    rueckgabe = {"teile": [
        {"id": f"t{i}", "sorte": p.bezeichnung, "x": p.x, "y": p.y,
         "winkel": 90.0 if p.bezeichnung == "Blende" else p.winkel}
        for i, p in enumerate(plan.platzierungen)]}
    uebernehme(erg, 0, rueckgabe, karte)
    for i, _ in ohne:
        p = plan.platzierungen[i]
        breite, hoehe = masse_vorher[i]
        pruefe(abs(p.breite - hoehe) < 0.01 and abs(p.hoehe - breite) < 0.01,
               f"gedreht: {p.breite:.0f} x {p.hoehe:.0f} (vorher {breite:.0f} x {hoehe:.0f})")
        ringe = p.welt_kontur()
        xs = [x for ring in ringe for x, _ in ring]
        pruefe(abs((max(xs) - min(xs)) - p.breite) < 0.01, "Kontur passt zur Breite")


def test_drehen():
    print("Editor: Drehen rechnet Masse und Kontur um")
    erg = beispiel()
    plan = erg.plaene[0]
    karte = kontur_karte(erg)
    winkel_teil = next(i for i, p in enumerate(plan.platzierungen)
                       if p.bezeichnung == "Winkel")

    rueckgabe = {"teile": []}
    for i, p in enumerate(plan.platzierungen):
        rueckgabe["teile"].append({
            "id": f"t{i}", "sorte": p.bezeichnung, "x": 100.0, "y": 200.0,
            "winkel": 37.0 if i == winkel_teil else p.winkel})
    uebernehme(erg, 0, rueckgabe, karte)

    p = plan.platzierungen[winkel_teil]
    pruefe(abs(p.winkel - 37.0) < 1e-9, f"Winkel {p.winkel}")
    ringe = p.welt_kontur()
    xs = [x for ring in ringe for x, _ in ring]
    ys = [y for ring in ringe for _, y in ring]
    pruefe(abs(min(xs) - 100.0) < 0.01 and abs(min(ys) - 200.0) < 0.01,
           f"Kontur beginnt bei {min(xs):.1f}/{min(ys):.1f}")
    pruefe(abs((max(xs) - min(xs)) - p.breite) < 0.01
           and abs((max(ys) - min(ys)) - p.hoehe) < 0.01,
           f"Aussenmasse passen zur gedrehten Kontur ({p.breite:.0f}x{p.hoehe:.0f})")
    # 800x800-Winkel um 37 Grad gedreht ist breiter als 800
    pruefe(p.breite > 800, f"gedrehte Breite {p.breite:.0f} mm")


def test_ablegen_und_einsetzen():
    print("Editor: Ablegen und Einsetzen")
    erg = beispiel()
    plan = erg.plaene[0]
    karte = kontur_karte(erg)
    anzahl = len(plan.platzierungen)
    sorte = plan.platzierungen[0].bezeichnung
    offen_vorher = sum(a for _, _, _, a in erg.fehlende)

    # erstes Teil ablegen
    rueckgabe = {"teile": [
        {"id": f"t{i}", "sorte": p.bezeichnung, "x": p.x, "y": p.y, "winkel": p.winkel}
        for i, p in enumerate(plan.platzierungen) if i != 0]}
    meldungen = uebernehme(erg, 0, rueckgabe, karte)

    pruefe(len(plan.platzierungen) == anzahl - 1, "ein Teil weniger auf der Tafel")
    offen = sum(a for b, _, _, a in erg.fehlende if b == sorte)
    pruefe(offen == 1, f"{sorte} steht jetzt {offen}× in der Restliste")
    pruefe(any("abgelegt" in m for m in meldungen), f"Meldung: {meldungen}")

    # dasselbe Teil wieder einsetzen
    rueckgabe = {"teile": [
        {"id": f"t{i}", "sorte": p.bezeichnung, "x": p.x, "y": p.y, "winkel": p.winkel}
        for i, p in enumerate(plan.platzierungen)]}
    rueckgabe["teile"].append({"id": "neu1", "sorte": sorte, "x": 50.0, "y": 60.0,
                               "winkel": 90.0})
    meldungen = uebernehme(erg, 0, rueckgabe, karte)

    pruefe(len(plan.platzierungen) == anzahl, "Teil wieder auf der Tafel")
    offen = sum(a for b, _, _, a in erg.fehlende if b == sorte)
    pruefe(offen == 0, f"{sorte} nicht mehr offen ({offen})")
    neu = plan.platzierungen[-1]
    pruefe(neu.bezeichnung == sorte and abs(neu.x - 50) < 1e-6 and neu.winkel == 90.0,
           f"eingesetzt als {neu.bezeichnung} bei {neu.x:.0f}/{neu.y:.0f}, "
           f"{neu.winkel:.0f}°")
    pruefe(len(neu.kontur) >= 1, "eingesetztes Teil hat seine Kontur")
    pruefe(sum(a for _, _, _, a in erg.fehlende) == offen_vorher,
           "Restliste wieder im Ausgangsstand")
    pruefe(any("eingesetzt" in m for m in meldungen), f"Meldung: {meldungen}")


def test_unbekanntes_teil():
    print("Editor: unbekannte Bezeichnung wird uebersprungen")
    erg = beispiel()
    plan = erg.plaene[0]
    anzahl = len(plan.platzierungen)
    rueckgabe = {"teile": [
        {"id": f"t{i}", "sorte": p.bezeichnung, "x": p.x, "y": p.y, "winkel": p.winkel}
        for i, p in enumerate(plan.platzierungen)]}
    rueckgabe["teile"].append({"id": "neu9", "sorte": "Gibt es nicht",
                               "x": 10.0, "y": 10.0, "winkel": 0.0})
    uebernehme(erg, 0, rueckgabe, kontur_karte(erg))
    pruefe(len(plan.platzierungen) == anzahl, "Plan bleibt unveraendert gross")


def test_vorrat():
    print("Editor: Restliste als Vorrat")
    teile = [Zuschnitt2D(600, 400, 2, "Blende", "Stahl"),
             Zuschnitt2D(4000, 400, 1, "Zu lang", "Stahl")]
    erg = optimize_2d(teile, [Tafel(1500, 3000, None, "Blech", "Stahl")],
                      saegeblatt=5, besaeumung=10, modus="frei")
    karte = kontur_karte(erg)
    posten = vorrat_fuer(erg, erg.plaene[0], karte, {"Zu lang": "#333333"})
    pruefe(len(posten) == 1 and posten[0]["sorte"] == "Zu lang",
           f"Vorrat: {[p['sorte'] for p in posten]}")
    pruefe(len(posten[0]["kontur"][0]) == 4,
           "Ersatzkontur (Rechteck) fuer Teile ohne DXF-Kontur")
    pruefe(posten[0]["anzahl"] == 1, "Stueckzahl uebernommen")


def test_flaeche_nach_aenderung():
    print("Editor: Kennzahlen rechnen neu")
    erg = beispiel()
    plan = erg.plaene[0]
    vorher = plan.ausnutzung
    karte = kontur_karte(erg)
    rueckgabe = {"teile": [
        {"id": f"t{i}", "sorte": p.bezeichnung, "x": p.x, "y": p.y, "winkel": p.winkel}
        for i, p in enumerate(plan.platzierungen) if i > 0]}
    uebernehme(erg, 0, rueckgabe, karte)
    pruefe(plan.ausnutzung < vorher, f"Ausnutzung faellt von {vorher*100:.1f} % "
                                     f"auf {plan.ausnutzung*100:.1f} %")
    pruefe(0 <= plan.ausnutzung <= 1, "Ausnutzung bleibt plausibel")


if __name__ == "__main__":
    for fn in [test_vorgabe, test_verschieben, test_rechteck_ohne_kontur,
               test_drehen, test_ablegen_und_einsetzen,
               test_unbekanntes_teil, test_vorrat, test_flaeche_nach_aenderung]:
        fn()
    print()
    if fehler:
        print(f"{len(fehler)} Test(s) fehlgeschlagen:")
        for f in fehler:
            print("  -", f)
        raise SystemExit(1)
    print("Alle Editor-Tests bestanden.")
