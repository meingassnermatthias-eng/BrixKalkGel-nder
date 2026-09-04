# Nesting – Verschnittoptimierung

Zuschnittoptimierung für die Werkstatt: Stangen und Profile (1D), Bleche und
Platten (2D) sowie DXF-Import von Abwicklungen aus HiCAD (z. B.
Alucobond-Kassetten).

## Starten

```bash
pip install -r requirements.txt
streamlit run app_nesting.py
```

## Dateien

| Datei | Inhalt |
|---|---|
| `app_nesting.py` | Streamlit-Oberfläche (1D, 2D, DXF-Import, Hilfe) |
| `nesting.py` | Rechenkern, ohne Fremdbibliotheken |
| `dxf_import.py` | DXF lesen (HiCAD/Alucobond) und Schachtelplan als DXF schreiben |
| `zeichnung.py` | Schnittpläne als SVG für die Oberfläche |
| `pdf_export.py` | Werkstattdruck als PDF |
| `test_nesting.py` | Tests des Rechenkerns – `python3 test_nesting.py` |
| `test_dxf.py` | Tests des DXF-Wegs – `python3 test_dxf.py` |

Alle Maße in Millimeter.

## 1D – Stangen und Profile

Teile und Lagerlängen erfassen, „Zuschnitt optimieren“ drücken. Berücksichtigt
werden Sägeblattstärke, Anschnitt am Stangenanfang, Reserve am Stangenende und
die Grenze, ab der ein Reststück als verwertbar gilt.

* Für jede Stange wird die bestmögliche Belegung exakt gerechnet (begrenztes
  Rucksackproblem, 1-mm-Raster), danach die nächste Stange.
* Teile werden nur mit Teilen desselben **Profils** kombiniert. Ein leeres
  Profilfeld heißt „passt auf jede Stange“, eine Lagerstange ohne Profil
  „passt für alle Teile“.
* Reststücke aus dem Lager (Haken *Reststück*) werden bevorzugt verbraucht.
* Ausgabe: Schnittplan als PDF, Schnitt-/Stangen-/Bestellliste als Excel, CSV.

Schnellerfassung statt Tabelle:

```
1050 x 9 Pfosten
1980;6;Handlauf;Rohr 42,4x2
```

## 2D – Bleche und Platten

Zwei Schnittarten:

* **Guillotine** – durchgehende Schnitte in Streifen, passend für Tafelschere,
  Plattensäge und Kreissäge.
* **Frei** – dichte Verschachtelung (MaxRects), nur sinnvoll, wenn die Maschine
  Konturen fährt (Laser, Plasma, CNC-Fräse).

Schnittfuge (bzw. Fräserdurchmesser) und umlaufende Besäumung werden
mitgerechnet. Teile können um 90° gedreht werden; bei Walz- oder Dekorrichtung
(z. B. Alucobond metallic) den Haken *Drehbar* entfernen.

Ausgabe: Schachtelplan als PDF, Teileliste als Excel/CSV und der komplette
Schachtelplan als DXF (Layer `TAFEL`, `KONTUR`, `FRAESLINIE`, `BESCHRIFTUNG`).

## DXF-Import (HiCAD / Alucobond)

Eine oder mehrere DXF-Dateien hochladen. Erkannt werden Außenkontur,
Ausschnitte (Löcher) und Fräs-/Falzlinien; identische Teile werden zu einer
Position mit Stückzahl gebündelt, ein Text innerhalb der Kontur wird als
Positionsbezeichnung übernommen.

Zuordnung der Layer:

| Layername enthält | Bedeutung |
|---|---|
| Kontur, Außen, Innen, Ausschnitt, Schnitt, Cut | wird geschnitten |
| Fräs, Falz, Biege, Nut, Kant, Knick, Fold, Bend | Fräs-/Falzlinie, kein Schnitt |
| Bemaßung, Maß, Text, Beschriftung, Achse, Defpoints | wird ignoriert |

Unbekannte Layer gelten im Zweifel als Kontur. Jede Zuordnung lässt sich unter
*Layer-Zuordnung anpassen* von Hand ändern.

Weitere Stellschrauben:

* **Konturtoleranz** – maximale Lücke zwischen zwei Elementen, die noch als
  geschlossene Kontur gilt. Meldet das Programm offene Konturzüge, hilft ein
  größerer Wert (typisch 0,1–1 mm).
* **Kleinste Teilefläche** – kleinere Konturen (Symbole, Bohrbilder) werden
  ignoriert.

Mit *Erkannte Teile als DXF* lässt sich vor dem Nesting prüfen, was das
Programm gelesen hat.

## Grenzen

* Geschachtelt wird 2D über die **Außenmaße** (Bounding-Box), auch wenn die
  echte Kontur bekannt ist. Bei Kassetten mit Eckausklinkungen bleibt dadurch
  Material liegen, das ein echtes Konturnesting noch nutzen könnte. Die Kontur
  wird in Plan, PDF und DXF-Export trotzdem maßhaltig dargestellt.
* Gedreht wird um 90°, nicht um beliebige Winkel.
* Die Optimierung ist eine sehr gute Heuristik, kein mathematisches Optimum.
* Der ausgegebene Plan ersetzt die Kontrolle in der Werkstatt nicht.
