"""
test_raster.py - Prueft das Rastermodul: Felder, Fugen, Gleichteilsuche.

Aufruf:  python3 test_raster.py
"""

import io
import math
import sys

import raster as r
from nesting import Tafel, Zuschnitt2D, optimize_2d

fehler = []


def pruefe(bedingung, text):
    if bedingung:
        print(f"  OK   {text}")
    else:
        print(f"  FEHL {text}")
        fehler.append(text)


def nahe(a, b, tol=0.01):
    return abs(a - b) <= tol


def feld(name, felder):
    return next(f for f in felder if f.name == name)


# ==========================================================
print("\n1. Masskette lesen")
# ==========================================================

pruefe(r.masse_lesen("1250 1250 900") == [1250.0, 1250.0, 900.0], "Leerzeichen")
pruefe(r.masse_lesen("3x1250, 900") == [1250.0, 1250.0, 1250.0, 900.0], "3x1250")
pruefe(r.masse_lesen("2*1000+500") == [1000.0, 1000.0, 500.0], "2*1000+500")
pruefe(r.masse_lesen("1250,5 900") == [1250.5, 900.0], "Komma als Dezimaltrenner")
pruefe(r.masse_lesen("") == [], "leere Eingabe")
pruefe(r.gleiche_teilung(3600, 3) == [1200.0, 1200.0, 1200.0], "gleiche Teilung")


# ==========================================================
print("\n2. Raster von Hand")
# ==========================================================

felder = r.felder_aus_raster([1250, 1250, 900], [1000, 1000])
pruefe(len(felder) == 6, "3 Spalten x 2 Zeilen = 6 Felder")
pruefe([f.name for f in felder] == ["Z1/S1", "Z1/S2", "Z1/S3",
                                    "Z2/S1", "Z2/S2", "Z2/S3"],
       "Benennung zeilenweise von links oben")
oben_links = feld("Z1/S1", felder)
unten_rechts = feld("Z2/S3", felder)
pruefe(nahe(oben_links.breite, 1250) and nahe(oben_links.hoehe, 1000),
       "Feldgroesse 1250 x 1000")
pruefe(nahe(unten_rechts.breite, 900), "dritte Spalte ist 900 breit")
pruefe(oben_links.mitte[1] > unten_rechts.mitte[1], "Zeile 1 liegt oben")
pruefe(all(f.rechteckig for f in felder), "alle Felder rechteckig")
pruefe(nahe(sum(f.flaeche for f in felder), 3400 * 2000), "Gesamtflaeche stimmt")


# ==========================================================
print("\n3. Fuge und Zugabe")
# ==========================================================

platten, hinweise = r.platten_aus_feldern(felder, fuge=15.0)
pruefe(len(platten) == 6 and not hinweise, "6 Platten ohne Hinweis")
nach_feld = {p.feld.name: p for p in platten}
pruefe(nahe(nach_feld["Z1/S2"].breite, 1250 - 15),
       "Mittelfeld: beidseitig halbe Fuge abgezogen (1235)")
pruefe(nahe(nach_feld["Z1/S1"].breite, 1250 - 7.5),
       "Randfeld links: nur innen Fuge (1242,5)")
pruefe(nahe(nach_feld["Z1/S1"].hoehe, 1000 - 7.5),
       "Randfeld oben: nur unten Fuge (992,5)")
pruefe(nahe(nach_feld["Z2/S2"].hoehe, 1000 - 7.5),
       "Mittelfeld unten: nur oben Fuge")

platten_rand, _ = r.platten_aus_feldern(felder, fuge=15.0, rand_fuge=True)
pruefe(all(nahe(p.breite, p.feld.breite - 15) for p in platten_rand),
       "mit Randfuge: ueberall volle Fuge abgezogen")

platten_zugabe, _ = r.platten_aus_feldern(felder, fuge=15.0, zugabe=25.0)
pruefe(nahe(nach_feld["Z1/S2"].breite + 50,
            next(p for p in platten_zugabe if p.feld.name == "Z1/S2").breite),
       "Zugabe 25 mm je Seite macht die Platte 50 mm breiter")

eng = r.felder_aus_raster([100], [100])
_, enge_hinweise = r.platten_aus_feldern(eng, fuge=250.0, rand_fuge=True)
pruefe(bool(enge_hinweise), "zu grosse Fuge wird gemeldet, nicht gerechnet")

# Oeffnung bleibt ohne Platte
felder[4].aus = True
platten_mit_loch, _ = r.platten_aus_feldern(felder, fuge=15.0)
pruefe(len(platten_mit_loch) == 5, "Oeffnung erzeugt keine Platte")
pruefe(nahe(next(p for p in platten_mit_loch if p.feld.name == "Z2/S1").breite,
            1250 - 7.5),
       "Nachbar der Oeffnung behaelt die Fuge zur Oeffnung nicht")
felder[4].aus = False


# Verschieden grosse Nachbarn: die Fuge muss trotzdem an der richtigen Kante
# sitzen (die Nachbarsuche arbeitet mit einem Grobraster).
breit = r.Feld(polygon=r.rechteck(0, 0, 2400, 1100), name="breit")
schmal_links = r.Feld(polygon=r.rechteck(0, 1100, 1200, 2200), name="links")
schmal_rechts = r.Feld(polygon=r.rechteck(1200, 1100, 2400, 2200), name="rechts")
gemischt, _ = r.platten_aus_feldern([breit, schmal_links, schmal_rechts], fuge=20.0)
nach_name = {p.feld.name: p for p in gemischt}
pruefe(nahe(nach_name["breit"].hoehe, 1100 - 10),
       "breites Feld: Fuge nur nach oben (Nachbarn darueber)")
pruefe(nahe(nach_name["breit"].breite, 2400),
       "breites Feld: seitlich kein Nachbar, keine Fuge")
pruefe(nahe(nach_name["links"].breite, 1200 - 10),
       "schmales Feld: Fuge nur zum Nachbarn rechts")
pruefe(nahe(nach_name["links"].hoehe, 1100 - 10),
       "schmales Feld: Fuge nur nach unten")


# ==========================================================
print("\n4. Gleichteilsuche")
# ==========================================================

positionen = r.gleichteile(platten, modus="gleich")
# 1242,5 x 992,5 (Spalte 1, 2x) | 1235 x 992,5 (Spalte 2, 2x) | 892,5 x 992,5 (2x)
pruefe(len(positionen) == 3,
       f"3x2-Raster mit Fuge: 3 Positionen (hier {len(positionen)})")
pruefe(sum(p.anzahl for p in positionen) == 6, "alle 6 Platten zugeordnet")
pruefe(positionen[0].anzahl >= positionen[-1].anzahl,
       "Positionen nach Stueckzahl geordnet")
pruefe([p.nummer for p in positionen] == ["P01", "P02", "P03"],
       "fortlaufende Positionsnummern")

# Gleiche Groesse, verschiedener Typ -> verschiedene Positionen
for f in felder:
    f.typ = "Anthrazit" if f.spalte == 1 else "Silber"
platten_typ, _ = r.platten_aus_feldern(felder, fuge=15.0, rand_fuge=True)
positionen_typ = r.gleichteile(platten_typ, modus="gleich")
pruefe(all(len({pl.typ for pl in p.platten}) == 1 for p in positionen_typ),
       "Typen werden nie gemischt")
pruefe(len(positionen_typ) >= 2, "verschiedene Typen = verschiedene Positionen")
for f in felder:
    f.typ = r.STANDARDTYP

# Hochkant und quer: nur im Modus 'gedreht' ein Gleichteil
quer = r.Feld(polygon=r.rechteck(0, 0, 800, 400), name="A")
hoch = r.Feld(polygon=r.rechteck(1000, 0, 1400, 800), name="B")
paar, _ = r.platten_aus_feldern([quer, hoch])
pruefe(len(r.gleichteile(paar, "gleich")) == 2,
       "800x400 und 400x800 sind ohne Drehen zwei Positionen")
gedreht = r.gleichteile(paar, "gedreht")
pruefe(len(gedreht) == 1 and gedreht[0].anzahl == 2,
       "mit Drehen eine Position mit 2 Stueck")
pruefe(gedreht[0].gedreht == ["B"], "das gedrehte Feld ist vermerkt")

# L-Form: Drehung ja, Spiegelung nur im Modus 'gespiegelt'
L = [(0, 0), (600, 0), (600, 300), (300, 300), (300, 700), (0, 700)]
L_gedreht = r._drehe(L, 90.0)
L_gespiegelt = r._spiegel(L)
pruefe(nahe(abs(r.flaeche(L)), 600 * 300 + 300 * 400), "Flaeche der L-Form")

felder_L = [r.Feld(polygon=r.gegen_uhrzeiger(L), name="L1"),
            r.Feld(polygon=r.gegen_uhrzeiger(L_gedreht), name="L2"),
            r.Feld(polygon=r.gegen_uhrzeiger(L_gespiegelt), name="L3")]
platten_L = [r.Platte(polygon=f.polygon, feld=f) for f in felder_L]
pruefe(len(r.gleichteile(platten_L, "gleich")) == 3, "L-Formen: ohne Drehen 3x")
nach_drehen = r.gleichteile(platten_L, "gedreht")
pruefe(len(nach_drehen) == 2,
       f"L-Formen: mit Drehen 2 Positionen (hier {len(nach_drehen)}) - "
       f"die gespiegelte bleibt eigen")
nach_spiegeln = r.gleichteile(platten_L, "gespiegelt")
pruefe(len(nach_spiegeln) == 1 and nach_spiegeln[0].anzahl == 3,
       "L-Formen: mit Spiegeln eine Position mit 3 Stueck")
pruefe(nach_spiegeln[0].gespiegelt == ["L3"], "gespiegeltes Feld ist vermerkt")


# ==========================================================
print("\n5. Versatz (Fuge) bei beliebigen Polygonen")
# ==========================================================

versetzt = r.versetze_polygon(r.gegen_uhrzeiger(L), 10.0)
pruefe(len(versetzt) == 6, "L-Form bleibt nach dem Versatz ein Sechseck")
xs = [p[0] for p in versetzt]
ys = [p[1] for p in versetzt]
pruefe(nahe(max(xs) - min(xs), 600 - 20) and nahe(max(ys) - min(ys), 700 - 20),
       "Huellmass um 2 x 10 mm kleiner")
pruefe(abs(r.flaeche(versetzt)) < abs(r.flaeche(L)), "Flaeche wird kleiner")
# der Versatz muss ueberall den Abstand einhalten
abstand_ok = True
for i in range(len(versetzt)):
    for j in range(len(L)):
        a, b = L[j], L[(j + 1) % len(L)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        laenge2 = dx * dx + dy * dy
        t = max(0.0, min(1.0, ((versetzt[i][0] - a[0]) * dx
                               + (versetzt[i][1] - a[1]) * dy) / laenge2))
        d = math.hypot(versetzt[i][0] - (a[0] + t * dx),
                       versetzt[i][1] - (a[1] + t * dy))
        if d < 9.99:
            abstand_ok = False
pruefe(abstand_ok, "kein Punkt liegt naeher als 10 mm an der Feldkante")
pruefe(r.versetze_polygon(r.gegen_uhrzeiger(L), 400.0) == [],
       "unmoeglicher Versatz liefert leer statt Unsinn")


# ==========================================================
print("\n6. Raster aus Linien (DXF)")
# ==========================================================

def gitter_linien(xs, ys):
    """Volles Linienraster: alle waagrechten und senkrechten Linien."""
    linien = []
    for y in ys:
        linien.append([(min(xs), y), (max(xs), y)])
    for x in xs:
        linien.append([(x, min(ys)), (x, max(ys))])
    return linien

linien = gitter_linien([0, 1250, 2500, 3400], [0, 1000, 2000])
erkannt, hinweise = r.felder_aus_linien(linien, toleranz=2.0)
pruefe(len(erkannt) == 6, f"volles Gitter: 6 Felder (hier {len(erkannt)})")
pruefe(not hinweise, "keine Hinweise beim sauberen Gitter")
pruefe(nahe(sum(f.flaeche for f in erkannt), 3400 * 2000), "Flaeche vollstaendig")
pruefe(all(f.rechteckig for f in erkannt), "alle erkannten Felder rechteckig")
pruefe([f.name for f in erkannt][0] == "Z1/S1", "Felder werden benannt")
pruefe(nahe(feld("Z1/S1", erkannt).breite, 1250), "linkes oberes Feld 1250 breit")

# fehlende Trennlinie -> ein doppelt breites Feld
teil_linien = [l for l in linien]
teil_linien.remove([(1250, 0), (1250, 2000)])
teil_linien.append([(1250, 0), (1250, 1000)])          # nur unten getrennt
offen, _ = r.felder_aus_linien(teil_linien, toleranz=2.0)
pruefe(len(offen) == 5, f"fehlende Trennung: 5 Felder (hier {len(offen)})")
pruefe(any(nahe(f.breite, 2500) for f in offen),
       "zwei Zellen ohne Trennlinie werden ein Feld")

# L-foermiger Umriss: die Flaeche ausserhalb darf kein Feld werden
L_linien = [
    [(0, 0), (2000, 0)], [(0, 1000), (2000, 1000)], [(0, 2000), (1000, 2000)],
    [(0, 0), (0, 2000)], [(1000, 0), (1000, 2000)], [(2000, 0), (2000, 1000)],
]
L_felder, _ = r.felder_aus_linien(L_linien, toleranz=2.0)
pruefe(len(L_felder) == 3, f"L-Umriss: 3 Felder (hier {len(L_felder)}) - "
       f"die offene Ecke zaehlt nicht mit")
pruefe(nahe(sum(f.flaeche for f in L_felder), 3 * 1000 * 1000),
       "nur die geschlossenen Felder")

# L-foermiges Feld aus Zellen
L_zellen = [
    [(0, 0), (2000, 0)], [(0, 2000), (2000, 2000)],
    [(0, 0), (0, 2000)], [(2000, 0), (2000, 2000)],
    [(1000, 0), (1000, 1000)], [(1000, 1000), (2000, 1000)],
]
# Die Trennlinien liegen nur unten links und rechts der Mitte: daraus werden
# ein L-foermiges Feld (drei Zellen) und ein Quadrat.
zusammen, _ = r.felder_aus_linien(L_zellen, toleranz=2.0)
pruefe(len(zusammen) == 2, f"zwei Felder, eines L-foermig (hier {len(zusammen)})")
eckig = [f for f in zusammen if not f.rechteckig]
pruefe(len(eckig) == 1 and len(eckig[0].polygon) == 6,
       "das L-foermige Feld hat sechs Ecken")
pruefe(nahe(eckig[0].flaeche, 3 * 1000 * 1000),
       "Flaeche des L-Feldes stimmt (drei Zellen)")

# geschlossene Polylinie
polylinie = [[(0, 0), (500, 0), (500, 400), (0, 400), (0, 0)]]
poly_felder, _ = r.felder_aus_linien(polylinie, toleranz=2.0)
pruefe(len(poly_felder) == 1 and nahe(poly_felder[0].flaeche, 500 * 400),
       "geschlossene Polylinie wird ein Feld")

# Luecken in den Linien: Toleranz hilft
lueckig = [
    [(0, 0), (999, 0)], [(1001, 0), (2000, 0)],
    [(0, 1000), (2000, 1000)], [(0, 0), (0, 1000)], [(2000, 0), (2000, 1000)],
]
mit_toleranz, _ = r.felder_aus_linien(lueckig, toleranz=3.0)
pruefe(len(mit_toleranz) == 1, "kleine Luecke mit Toleranz ueberbrueckt")


# ----------------------------------------------------------
# Schiefwinklige Ansicht (perspektivische Skizze): die Felder sind keine
# Rechtecke, trotzdem muss jede umschlossene Masche ein Feld werden.
# ----------------------------------------------------------

def schiefes_raster(spalten=4, zeilen=2, breite=1200.0, hoehe=1100.0,
                    schraeg=0.35):
    """Ein Raster, dessen senkrechte Linien schraeg stehen (Scherung)."""
    def punkt(i, j):
        return (i * breite + j * hoehe * schraeg, j * hoehe)
    linien = []
    for j in range(zeilen + 1):                      # waagrechte Linien
        linien.append([punkt(0, j), punkt(spalten, j)])
    for i in range(spalten + 1):                     # schraege Linien
        linien.append([punkt(i, 0), punkt(i, zeilen)])
    return linien

schief = schiefes_raster()
schiefe_felder, schiefe_hinweise = r.felder_aus_linien(schief, toleranz=2.0)
pruefe(len(schiefe_felder) == 8,
       f"schiefes Raster 4x2: 8 Felder (hier {len(schiefe_felder)})")
pruefe(not schiefe_hinweise, "schiefes Raster ohne Hinweise")
pruefe(all(len(f.polygon) == 4 for f in schiefe_felder),
       "jedes Feld ein Viereck")
pruefe(all(not f.rechteckig for f in schiefe_felder),
       "die Felder sind keine Rechtecke")
pruefe(nahe(sum(f.flaeche for f in schiefe_felder), 4 * 1200 * 2 * 1100, 1.0),
       "Flaechensumme stimmt (Parallelogramme)")
pruefe(all(f.name.startswith("F") for f in schiefe_felder),
       f"ohne Zeilen/Spalten wird durchnumeriert: {schiefe_felder[0].name}")
schiefe_platten, _ = r.platten_aus_feldern(schiefe_felder, fuge=20.0)
pruefe(len(schiefe_platten) == 8, "auch schiefe Felder werden zu Platten")
pruefe(all(p.flaeche < p.feld.flaeche for p in schiefe_platten),
       "die Fuge verkleinert jede schiefe Platte")
schiefe_positionen = r.gleichteile(schiefe_platten, "gleich")
pruefe(len(schiefe_positionen) <= 4,
       f"gleiche Parallelogramme werden gebuendelt ({len(schiefe_positionen)} "
       f"Positionen fuer 8 Platten)")

# Dreieckige Felder (Giebel)
giebel = [
    [(0, 0), (4000, 0)], [(0, 0), (2000, 1500)], [(2000, 1500), (4000, 0)],
    [(1000, 750), (3000, 750)],
]
giebel_felder, _ = r.felder_aus_linien(giebel, toleranz=2.0)
pruefe(len(giebel_felder) == 2,
       f"Giebeldreieck mit Teilung: 2 Felder (hier {len(giebel_felder)})")
pruefe(nahe(sum(f.flaeche for f in giebel_felder), 4000 * 1500 / 2, 1.0),
       "Dreiecksflaeche vollstaendig")

# Umriss und Teilung auf verschiedenen Layern: nur zusammen ergibt es Felder
umriss = [[(0, 0), (3000, 0)], [(3000, 0), (3000, 2000)],
          [(3000, 2000), (0, 2000)], [(0, 2000), (0, 0)]]
teilung = [[(1500, 0), (1500, 2000)]]
nur_teilung, _ = r.felder_aus_linien(teilung, toleranz=2.0)
pruefe(len(nur_teilung) == 0, "nur die Teilung ergibt kein Feld")
zusammen_felder, _ = r.felder_aus_linien(umriss + teilung, toleranz=2.0)
pruefe(len(zusammen_felder) == 2,
       f"Umriss + Teilung ergibt 2 Felder (hier {len(zusammen_felder)})")

# Linien, die ueber den Umriss hinausstehen (ueberstehende Enden)
ueberstand = umriss + [[(1500, -300), (1500, 2300)]]
ueber_felder, _ = r.felder_aus_linien(ueberstand, toleranz=2.0)
pruefe(len(ueber_felder) == 2,
       f"ueberstehende Linienenden stoeren nicht (hier {len(ueber_felder)})")
pruefe(nahe(sum(f.flaeche for f in ueber_felder), 3000 * 2000),
       "Flaeche trotz Ueberstand richtig")


# ==========================================================
print("\n7. Oeffnungen aus Texten")
# ==========================================================

felder_text = r.felder_aus_raster([1000, 1000], [1000])
treffer = r.oeffnungen_aus_texten(felder_text, [("Fenster F1", 500, 500),
                                                ("P 12", 1500, 500)])
pruefe(treffer == 1, "ein Text als Oeffnung erkannt")
pruefe(felder_text[0].aus and not felder_text[1].aus,
       "nur das Feld mit dem Fenstertext ist Oeffnung")


# ==========================================================
print("\n8. Uebergabe an das Nesting")
# ==========================================================

felder_bv = r.felder_aus_raster([1250, 1250, 1250], [900, 900, 900])
felder_bv[4].aus = True                       # Fenster in der Mitte
platten_bv, _ = r.platten_aus_feldern(felder_bv, fuge=20.0)
positionen_bv = r.gleichteile(platten_bv, "gleich")
pruefe(len(platten_bv) == 8, "8 Platten (ein Feld ist Fenster)")

teile = [Zuschnitt2D(p.breite, p.hoehe, p.anzahl, p.nummer, "Alucobond 4 mm",
                     False, kontur=[[(x, y) for x, y in p.polygon]])
         for p in positionen_bv]
ergebnis = optimize_2d(teile, [Tafel(1500, 3200, None, "Alucobond", "Alucobond 4 mm")],
                       saegeblatt=5.0, besaeumung=0.0)
pruefe(ergebnis.anzahl_tafeln >= 1, "Positionen lassen sich schachteln")
pruefe(not ergebnis.fehlende,
       f"alle Positionen eingeplant (offen: {ergebnis.fehlende})")
eingeplant = sum(len(plan.platzierungen) for plan in ergebnis.plaene)
pruefe(eingeplant == 8, f"8 Platten im Plan (hier {eingeplant})")

kennzahlen = r.kennzahlen(felder_bv, platten_bv, positionen_bv)
pruefe(kennzahlen["oeffnungen"] == 1 and kennzahlen["platten"] == 8,
       "Kennzahlen stimmen")
pruefe(nahe(kennzahlen["rasterflaeche"], 3750 * 2700 / 1e6, 0.01),
       "Rasterflaeche in m2")

zeilen = r.positionsliste(positionen_bv)
pruefe(len(zeilen) == len(positionen_bv) and "Felder" in zeilen[0],
       "Positionsliste erzeugt Zeilen")
felder_zeilen = r.feldliste(positionen_bv)
pruefe(len(felder_zeilen) == 8, "Feldliste hat eine Zeile je Platte")
pruefe(felder_zeilen[0]["Zeile"] == 1, "Feldliste beginnt oben")


# ==========================================================
print("\n8b. Verschiedene Plattentypen (Farben) je Feld")
# ==========================================================

felder_typ = r.felder_aus_raster([1200, 1200, 1200], [1000, 1000])
for feld_eintrag in felder_typ:                      # obere Zeile anthrazit
    feld_eintrag.typ = "Anthrazit" if feld_eintrag.zeile == 1 else "Silber"
felder_typ[4].aus = True                             # Fenster in der Mitte unten
platten_typ, _ = r.platten_aus_feldern(felder_typ, fuge=20.0)
positionen_typ = r.gleichteile(platten_typ, "gleich")

pruefe(all(len({pl.typ for pl in p.platten}) == 1 for p in positionen_typ),
       "jede Position hat genau einen Plattentyp")
anthrazit = [p for p in positionen_typ if p.typ == "Anthrazit"]
silber = [p for p in positionen_typ if p.typ == "Silber"]
pruefe(sum(p.anzahl for p in anthrazit) == 3 and sum(p.anzahl for p in silber) == 2,
       f"3 anthrazit, 2 silber (hier {sum(p.anzahl for p in anthrazit)}/"
       f"{sum(p.anzahl for p in silber)})")

typen = [{"name": "Anthrazit", "farbe_name": "Schwarz", "material": "Alucobond anthrazit"},
         {"name": "Silber", "farbe_name": "Grau", "material": "Alucobond silber"}]
uebersicht = r.typ_uebersicht(positionen_typ, typen)
pruefe(len(uebersicht) == 2, "Uebersicht hat eine Zeile je Typ")
pruefe({z["Plattentyp"]: z["Platten"] for z in uebersicht}
       == {"Anthrazit": 3, "Silber": 2}, "Stueckzahlen je Typ stimmen")
pruefe(uebersicht[0]["Material"] == "Alucobond anthrazit",
       "Material aus der Typentabelle steht in der Uebersicht")
pruefe(nahe(sum(z["Fläche (m²)"] for z in uebersicht),
            sum(p.flaeche * p.anzahl for p in positionen_typ) / 1e6, 0.01),
       "Flaechensumme je Typ stimmt")

# Gleich grosse Platten verschiedener Farbe duerfen nie eine Position werden
quadrat_a = r.Feld(polygon=r.rechteck(0, 0, 800, 800), name="A", typ="Anthrazit")
quadrat_b = r.Feld(polygon=r.rechteck(2000, 0, 2800, 800), name="B", typ="Silber")
gemischt, _ = r.platten_aus_feldern([quadrat_a, quadrat_b])
pruefe(len(r.gleichteile(gemischt, "gespiegelt")) == 2,
       "gleich grosse Platten verschiedener Farbe bleiben getrennt")

# Montageplan: je Typ ein eigener Layer
plan_dxf = r.montageplan_als_dxf(felder_typ, positionen_typ,
                                 farben={"Anthrazit": "Schwarz", "Silber": "Grau"})
pruefe("TYP_ANTHRAZIT" in plan_dxf and "TYP_SILBER" in plan_dxf,
       "Montageplan hat je Plattentyp einen Layer")
pruefe(plan_dxf.count("TYP_ANTHRAZIT") >= 4,
       "die anthrazitfarbenen Platten liegen auf ihrem Layer")
pruefe("Anthrazit" in plan_dxf, "der Plattentyp steht in der Beschriftung")

# Farbnamen und DXF-Farbnummern
from zeichnung import FARBNAMEN, farbe_nach_name, dxf_farbnummer, svg_fassade
pruefe(farbe_nach_name("Schwarz").startswith("#") and dxf_farbnummer("Schwarz") > 0,
       "Farbname liefert Zeichenfarbe und DXF-Farbnummer")
pruefe(farbe_nach_name("gibt es nicht") == "#1E3A8A", "unbekannte Farbe faellt zurueck")

bild = svg_fassade(felder_typ, r.position_je_feld(positionen_typ),
                   farbe_je_feld={f.name: farbe_nach_name("Schwarz"
                                                          if f.typ == "Anthrazit"
                                                          else "Grau")
                                  for f in felder_typ})
pruefe(farbe_nach_name("Schwarz") in bild and farbe_nach_name("Grau") in bild,
       "die Ansicht laesst sich nach Plattentyp einfaerben")


# ----------------------------------------------------------
# Zwei Farben duerfen nie auf derselben Tafel landen
# ----------------------------------------------------------

typen_ohne = [{"name": "Anthrazit", "material": ""},
              {"name": "Silber", "material": ""}]
material = r.material_je_typ(typen_ohne)
pruefe(material == {"Anthrazit": "Anthrazit", "Silber": "Silber"},
       "ohne Materialangabe wird der Typname zum Material")
pruefe(r.material_je_typ([{"name": "Silber", "material": " Alucobond silber "}])
       == {"Silber": "Alucobond silber"},
       "mit Materialangabe bleibt diese stehen")

felder_farbe = r.felder_aus_raster([1200, 1200], [1000, 1000])
for feld_eintrag in felder_farbe:
    feld_eintrag.typ = "Anthrazit" if feld_eintrag.spalte == 1 else "Silber"
platten_farbe, _ = r.platten_aus_feldern(felder_farbe, fuge=15.0)
positionen_farbe = r.gleichteile(platten_farbe, "gleich")
teile_farbe = [Zuschnitt2D(p.breite, p.hoehe, p.anzahl, p.nummer,
                           material[p.typ], True,
                           kontur=[[(x, y) for x, y in p.polygon]])
               for p in positionen_farbe]
ergebnis_farbe = optimize_2d(teile_farbe,
                             [Tafel(2000, 4000, None, "Tafel", "")],
                             saegeblatt=5.0, besaeumung=0.0, modus="frei")
typ_je_position = {p.nummer: p.typ for p in positionen_farbe}
gemischt = [nr for nr, plan in enumerate(ergebnis_farbe.plaene, start=1)
            if len({typ_je_position[pl.bezeichnung]
                    for pl in plan.platzierungen}) > 1]
pruefe(not gemischt,
       f"keine Tafel traegt zwei Plattentypen (gemischt: {gemischt})")
pruefe(ergebnis_farbe.anzahl_tafeln >= 2,
       "zwei Farben brauchen mindestens zwei Tafeln")
pruefe(not ergebnis_farbe.fehlende,
       "trotz Materialtrennung sind alle Platten eingeplant "
       "(leeres Materialfeld der Tafel passt zu jedem Teil)")


# ==========================================================
print("\n9. Fassadenraster aus einer DXF-Datei")
# ==========================================================

import dxf_import as dx


def baue_raster_dxf(spalten, zeilen, texte=(), layer="0", muell=True):
    """Schreibt ein Fassadenraster, wie es aus HiCAD oder AutoCAD kommt."""
    import ezdxf
    doc = ezdxf.new("R2010")
    for name in {layer, "BEMASSUNG"}:
        if name != "0":
            doc.layers.add(name)
    msp = doc.modelspace()
    xs, ys = [0.0], [0.0]
    for breite in spalten:
        xs.append(xs[-1] + breite)
    for hoehe in zeilen:
        ys.append(ys[-1] + hoehe)
    for y in ys:
        msp.add_line((xs[0], y), (xs[-1], y), dxfattribs={"layer": layer})
    for x in xs:
        msp.add_line((x, ys[0]), (x, ys[-1]), dxfattribs={"layer": layer})
    for inhalt, x, y in texte:
        msp.add_text(inhalt, height=50).set_placement((x, y))
    if muell:
        # Bemassung und Hilfslinien, die den Rasterimport nicht stoeren duerfen
        msp.add_line((xs[0], ys[0] - 500), (xs[-1], ys[0] - 500),
                     dxfattribs={"layer": "BEMASSUNG"})
        msp.add_line((xs[0] - 300, ys[0]), (xs[0] - 300, ys[-1]),
                     dxfattribs={"layer": "BEMASSUNG"})
    puffer = io.StringIO()
    doc.write(puffer)
    return puffer.getvalue().encode("utf-8")


try:
    import ezdxf
    ezdxf_da = True
except ImportError:
    ezdxf_da = False

if not ezdxf_da:
    print("  --   ezdxf nicht installiert, DXF-Teil uebersprungen")
else:
    daten = baue_raster_dxf([1250, 1250, 900], [1000, 1000],
                            texte=[("Fenster", 1875, 1500)])
    gelesen = dx.lade_linien(daten)
    pruefe(set(gelesen["linien"]) == {"0", "BEMASSUNG"},
           f"Layer erkannt: {sorted(gelesen['linien'])}")
    pruefe(len(gelesen["linien"]["0"]) == 3 + 4,
           "alle Rasterlinien auf Layer 0 gelesen")
    pruefe(any("Fenster" in t[0] for t in gelesen["texte"]), "Text gelesen")

    dxf_felder, dxf_hinweise = r.felder_aus_linien(gelesen["linien"]["0"],
                                                   toleranz=2.0)
    pruefe(len(dxf_felder) == 6,
           f"6 Felder aus dem DXF-Raster (hier {len(dxf_felder)})")
    pruefe(nahe(sum(f.flaeche for f in dxf_felder), 3400 * 2000),
           "Rasterflaeche aus dem DXF stimmt")
    pruefe(r.oeffnungen_aus_texten(dxf_felder, gelesen["texte"]) == 1,
           "Fenstertext markiert genau ein Feld als Oeffnung")

    # Bemassungslayer mitnehmen: dann darf nichts Falsches entstehen
    alle = [z for liste in gelesen["linien"].values() for z in liste]
    mit_muell, _ = r.felder_aus_linien(alle, toleranz=2.0)
    pruefe(len(mit_muell) == 6,
           f"Bemassungslinien erzeugen keine Scheinfelder (hier {len(mit_muell)})")

    dxf_platten, _ = r.platten_aus_feldern(dxf_felder, fuge=20.0)
    dxf_positionen = r.gleichteile(dxf_platten, "gleich")
    pruefe(len(dxf_platten) == 5, "ein Feld ist Fenster, 5 Platten bleiben")
    pruefe(sum(p.anzahl for p in dxf_positionen) == 5,
           "alle Platten in Positionen")


# ==========================================================
if fehler:
    print(f"\n{len(fehler)} Test(s) fehlgeschlagen:")
    for text in fehler:
        print(f"  - {text}")
    sys.exit(1)
print("\nAlle Rastertests bestanden.")
