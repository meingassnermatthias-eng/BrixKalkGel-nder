# Nesting – Verschnittoptimierung

Zuschnittoptimierung für die Werkstatt: Stangen und Profile (1D), Bleche und
Platten (2D) sowie DXF-Import von Abwicklungen aus HiCAD (z. B.
Alucobond-Kassetten).

## Am eigenen Rechner starten

**Windows:** Doppelklick auf `start_nesting.bat`. Beim ersten Start richtet das
Skript eine eigene Python-Umgebung ein und lädt die benötigten Pakete – das
dauert ein paar Minuten, jeder weitere Start geht sofort. Danach öffnet sich
die Oberfläche im Browser.

Einzige Voraussetzung: Python 3.10 oder neuer von
[python.org](https://www.python.org/downloads/), bei der Installation
**„Add Python to PATH"** ankreuzen.

**macOS / Linux:**

```bash
chmod +x start_nesting.sh    # nur einmal nötig
./start_nesting.sh
```

**Von Hand:**

```bash
pip install -r requirements.txt
streamlit run app_nesting.py
```

**Ohne Installation ausprobieren:** Das Projekt auf GitHub öffnen, oben rechts
*Code → Codespaces → Create codespace* wählen und im Terminal
`streamlit run app_nesting.py` eingeben. Läuft komplett im Browser.

Die Oberfläche läuft nur auf dem eigenen Rechner (`localhost`) – es gehen keine
Daten nach außen.

## Dateien

| Datei | Inhalt |
|---|---|
| `app_nesting.py` | Streamlit-Oberfläche (1D, 2D, DXF-Import, Hilfe) |
| `nesting.py` | Rechenkern 1D und 2D (Bounding-Box), ohne Fremdbibliotheken |
| `kontur_nesting.py` | Echtes Konturnesting (True Shape Nesting), braucht numpy |
| `dxf_import.py` | DXF lesen (HiCAD/Alucobond) und Schachtelplan als DXF schreiben |
| `zeichnung.py` | Schnittpläne als SVG für die Oberfläche |
| `pdf_export.py` | Werkstattdruck als PDF |
| `test_nesting.py` | Tests des Rechenkerns – `python3 test_nesting.py` |
| `test_dxf.py` | Tests des DXF-Wegs – `python3 test_dxf.py` |
| `test_kontur.py` | Tests des Konturnestings – `python3 test_kontur.py` |

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

Drei Schnittarten:

* **Guillotine** – durchgehende Schnitte in Streifen, passend für Tafelschere,
  Plattensäge und Kreissäge.
* **Frei** – dichte Verschachtelung der Außenmaße (MaxRects), nur sinnvoll, wenn
  die Maschine Konturen fährt (Laser, Plasma, CNC-Fräse).
* **Kontur** – echtes Nesting mit der tatsächlichen Teileform (siehe unten).

Schnittfuge (bzw. Fräserdurchmesser) und umlaufende Besäumung werden
mitgerechnet. Teile können um 90° gedreht werden; bei Walz- oder Dekorrichtung
(z. B. Alucobond metallic) den Haken *Drehbar* entfernen.

Ausgabe: Schachtelplan als PDF, Teileliste als Excel/CSV und der komplette
Schachtelplan als DXF (Layer `TAFEL`, `KONTUR`, `FRAESLINIE`, `BESCHRIFTUNG`).

## Konturnesting (True Shape Nesting)

Schachtelt mit der echten Teileform statt mit dem umschreibenden Rechteck.
Teile greifen ineinander, Ausklinkungen werden mitgenutzt und kleine Teile
landen bei Bedarf in den Fensterausschnitten großer Teile.

Was es bringt (gemessen in `test_kontur.py`, Tafel 1250×2500 bzw. 1500×3000):

| Auftrag | Außenmaß-Nesting | Konturnesting |
|---|---|---|
| 16 Dreiecke 600×400 | 2 Tafeln, 31 % | **1 Tafel, 61 %** |
| 10 L-Winkel 800×800 | 4 Tafeln, 22 % | **2 Tafeln, 43 %** |
| Rahmen mit Ausschnitt + Einleger | 2 Tafeln | **1 Tafel** |
| Reine Rechtecke | 2 Tafeln, 57 % | 2 Tafeln, 57 % |
| Kassetten mit 30-mm-Eckausklinkung | 3 Tafeln, 58 % | 3 Tafeln, 58 % |

Kurz: Je stärker die Teile von der Rechteckform abweichen, desto größer der
Gewinn. Bei Rechtecken und bei Kassetten mit nur kleinen Eckausklinkungen
bringt es nichts – dort begrenzt die Tafelbreite, nicht die Teileform.

**So rechnet das Verfahren.** Jede Kontur wird je Drehwinkel in ein Raster
übersetzt (Scanline-Füllung nach der Even-Odd-Regel, dadurch sind Ausschnitte
automatisch frei) und um die halbe Schnittfuge aufgeweitet. Anschließend fällt
jedes Teil an der günstigsten Stelle nach unten und rutscht dabei in vorhandene
Taschen; bewertet wird nach eingeschlossener Restfläche. Teile, die so nicht
mehr unterkommen, werden über eine Kreuzkorrelation (FFT) auf der ganzen Tafel
gesucht – so finden sie auch in Fensterausschnitte hinein.

**Die Schnittfuge ist garantiert.** Gerastert wird nach außen (eine Zelle gilt
als belegt, sobald die Kontur sie berührt), aufgeweitet wird um die halbe
Schnittfuge. Überschneidungsfreie Masken bedeuten deshalb zwingend, dass die
echten Konturen mindestens die volle Schnittfuge auseinanderliegen. Im Zweifel
steht etwas mehr Abstand, nie weniger. `test_kontur.py` rechnet jeden erzeugten
Plan exakt nach – Kantenschnitt, Einschluss und kleinster Abstand.

**Einstellungen:**

* **Rasterweite** – 5 mm ist ein guter Kompromiss; 1–2 mm schachtelt dichter,
  rechnet aber deutlich länger. Bei sehr großen Tafeln vergröbert das Programm
  automatisch und sagt Bescheid.
* **Erlaubte Drehung** – 90°-Schritte (Standard), zusätzlich 45°-Schritte, oder
  keine Drehung. Teile mit Walz- oder Dekorrichtung bleiben über den Haken
  *Drehbar* ohnehin ungedreht (auch 180° würde die Laufrichtung umkehren).
* **Ausschnitte und Taschen mitnutzen** – schaltet die Vollsuche zu.
* **Suchtiefe** – Anzahl durchprobierter Schachtelstrategien (1–5).

**Sicherheitsnetz:** Das Programm rechnet zusätzlich das schnelle
Außenmaß-Verfahren mit und übernimmt dessen Plan, falls er mit weniger Tafeln
auskommt (kommt bei reinen Rechteckaufträgen vor). Konturnesting kann dadurch
nie schlechter ausfallen als *Frei*; der Wechsel wird im Ergebnis angezeigt.

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

* Die Schnittarten *Guillotine* und *Frei* schachteln über die **Außenmaße**.
  Wer die echte Teileform ausnutzen will, nimmt die Schnittart *Kontur*.
* Das Konturnesting rechnet im Raster: die Teile stehen gelegentlich ein paar
  Millimeter weiter auseinander als nötig – nie enger als die Schnittfuge.
* Teile werden von oben eingelegt, nicht seitlich eingeschoben. Eine Tasche,
  die nur seitlich erreichbar wäre, bleibt frei.
* Gedreht wird in 90°- oder 45°-Schritten, nicht in beliebigen Winkeln.
* Die Optimierung ist eine sehr gute Heuristik, kein mathematisches Optimum.
  Bei gemischten Rechteckaufträgen liegt sie erfahrungsgemäß wenige Prozent
  über dem theoretischen Bestwert.
* Der ausgegebene Plan ersetzt die Kontrolle in der Werkstatt nicht.
