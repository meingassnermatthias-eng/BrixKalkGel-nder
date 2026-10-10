# Nesting – Verschnittoptimierung

Blech- und Plattenzuschnitt für die Werkstatt, mit DXF-Import aus HiCAD
(z. B. Alucobond-Kassetten). Alle Maße in Millimeter.

## Am eigenen Rechner starten

**Windows:** Ordner entpacken (nicht aus der ZIP heraus starten), dann
Doppelklick auf `start_nesting.bat`. Das Skript sucht Python, bietet die
Installation über `winget` an, falls es fehlt, richtet beim ersten Start eine
eigene Umgebung ein und öffnet die Oberfläche im Browser. Beim ersten Start
wird außerdem angeboten, einen **Startknopf auf dem Desktop** anzulegen;
nachträglich geht das über `Desktop-Verknuepfung.bat`.

**macOS / Linux:** `chmod +x start_nesting.sh` (einmalig), dann
`./start_nesting.sh`.

**Von Hand:** `pip install -r requirements.txt` und
`streamlit run app_nesting.py`.

Die Oberfläche läuft nur auf dem eigenen Rechner (`localhost`) – es gehen keine
Daten nach außen.

## Der Ablauf in vier Schritten

| Schritt | Was dort passiert |
|---|---|
| ① **Raster (Fassade)** | Plattenraster zeichnen oder aus DXF holen, Felder zuordnen, Gleichteile suchen – *freiwillig* |
| ② **Teile** | DXF einlesen oder Teile von Hand erfassen; Teileliste mit Sammelaktionen |
| ③ **Material & Nesting** | Tafelformate, Schnittfuge, Besäumung, Schnittart – dann schachteln |
| ④ **Plan & Ausgabe** | Pläne ansehen, von Hand nachbessern, als PDF / Excel / CSV / DXF ausgeben |

Der Reiter **Hilfe** erklärt jeden Schritt mit Bildern.

## Schritt ① – Raster (Fassade)

Aus dem Plattenraster einer Fassade entstehen die Platten von selbst. Wer die
Teile schon hat, überspringt diesen Schritt.

**Raster zeichnen.** Spaltenbreiten und Zeilenhöhen eintippen – `3x1250 900`
heißt dreimal 1250 mm, dann 900 mm. Oder das Gesamtmaß angeben und in gleiche
Felder teilen lassen.

**Raster aus DXF.** Eine beliebige Ansicht einlesen. Die Linien werden
**layerweise** gelesen; angekreuzt wird, was zum Raster gehört. Vorgewählt ist
alles außer Bemaßung, Text und Schraffur – **der Umriss muss dabei sein**, und
er liegt oft auf einem anderen Layer als die Teilung.

Das Programm zerlegt die ausgewählten Linien an ihren Kreuzungspunkten und
sucht alle Maschen – jede rundum geschlossene Fläche wird ein Feld. Deshalb
funktionieren auch:

* unregelmäßige Raster und Felder, die über mehrere Rasterzellen gehen
  (fehlende Trennlinie), L-förmige Felder;
* **schiefwinklige und perspektivisch gezeichnete Ansichten** – Parallelogramme,
  Dreiecke (Giebel), beliebige Vielecke;
* geschlossene Polylinien als Feld, in beliebiger Form;
* über den Umriss hinausstehende Linienenden – sie stören nicht;
* Fenster und Türen aus den Texten (`Fenster`, `Aussparung`, `Entfall` …),
  wenn der Haken gesetzt ist.

Flächen, deren Rand nicht vollständig gezeichnet ist, entstehen gar nicht erst:
eine L-förmige Fassade bekommt in der offenen Ecke kein Scheinfeld. Die
**Toleranz** überbrückt kleine Lücken und Ungenauigkeiten zwischen den Linien
(typisch 1–3 mm); damit werden auch Linien verbunden, die sich nur fast
berühren.

Bei einem rechtwinkligen Raster heißen die Felder `Z2/S3` (Zeile/Spalte), bei
schiefwinkligen Ansichten gibt es keine Zeilen und Spalten – dort werden sie
von links oben nach rechts unten durchnumeriert (`F01`). Bei nicht
rechteckigen Feldern ist das angezeigte Maß das **Hüllmaß**, nicht die
Plattenkante; geschnitten wird die echte Form.

**Fuge und Zugabe.** Die Rasterlinie gilt als **Fugenmitte**: zwischen zwei
Platten geht die ganze Fugenbreite ab, je Seite die Hälfte. Am Außenrand geht
die Platte bis zur Linie, umstellbar mit *Fuge auch am Rand*. Zur
Fensteröffnung hin bleibt die Fuge erhalten. Die **Zugabe je Seite** schlägt
danach wieder auf – zum Beispiel die Aufkantung einer Kassette:
Sichtmaß + 2 × Zugabe = Zuschnitt.

**Plattentypen.** Eine Tabelle mit einer Zeile je Plattenart – meist je Farbe:
*Plattentyp* (Name, z. B. „RAL 7016 anthrazit“), *Farbe im Plan* (nur die
Darstellung) und *Material* (kommt in die Teileliste).

**Felder zuordnen.** Jedes Feld bekommt mit dem Pinsel einen dieser Typen oder
wird als **Öffnung** weggeklickt. Anklicken oder mit gedrückter Maustaste über
mehrere Felder ziehen; Zifferntasten wählen den Pinsel, Strg+Z nimmt zurück.
Erst *Zuordnung übernehmen* schreibt sie ins Raster. Ändert sich auf der
Baustelle eine Farbe, wird einfach das betroffene Feld umgemalt.

Gleich große Platten verschiedener Typen werden **nie zusammengefasst**. Die
Position heißt dann `P03 RAL 9006 silber` und bekommt das Material ihres Typs.
Die Ansicht lässt sich wahlweise nach Position oder nach Plattentyp einfärben,
der Montageplan legt jeden Typ auf einen eigenen DXF-Layer (`TYP_...`), und die
Excel-Liste bekommt ein Blatt *Plattentypen* mit Stück und m² je Farbe.

**Gleichteilsuche.** Deckungsgleiche Platten werden zu Positionen
(P01, P02 …) gebündelt:

| Einstellung | Wann |
|---|---|
| nur gleich ausgerichtet | Regelfall bei Walz- oder Dekorrichtung |
| auch gedreht | wenn 90/180/270° gedreht eingebaut werden darf |
| auch gespiegelt | nur bei beidseitig gleichem Material – die Sichtseite dreht sich |

Zum Schluss gehen die Positionen mit Stückzahl und echter Kontur in die
Teileliste. Dazu gibt es die **Positionsliste** als Excel (mit Feldliste und
Blatt *Plattentypen*) und den **Montageplan als DXF**: Rasterfelder,
Plattenkonturen, Positionsnummern und Plattentyp – die Zeichnung für die
Baustelle.

## Schritt ② – Teile

**DXF-Import.** Eine oder mehrere Dateien hochladen. Erkannt werden
Außenkontur, Ausschnitte (Löcher) und Fräs-/Falzlinien; identische Teile
werden zu einer Position mit Stückzahl gebündelt, ein Text innerhalb der
Kontur wird als Positionsbezeichnung übernommen.

| Layername enthält | Bedeutung |
|---|---|
| Kontur, Außen, Innen, Ausschnitt, Schnitt, Cut | wird geschnitten |
| Fräs, Falz, Biege, Nut, Kant, Knick, Fold, Bend | Fräs-/Falzlinie, kein Schnitt |
| Bemaßung, Maß, Text, Beschriftung, Achse, Defpoints | wird ignoriert |

Unbekannte Layer gelten im Zweifel als Kontur; jede Zuordnung lässt sich unter
*Einleseoptionen* von Hand ändern. Meldet das Programm offene Konturzüge, hilft
eine größere **Konturtoleranz** (typisch 0,1 bis 1 mm). Mit *Erkannte Teile als
DXF* lässt sich vor dem Nesting prüfen, was gelesen wurde.

**Von Hand erfassen:** eine Zeile je Position, `Breite x Höhe x Anzahl` oder
`Breite;Höhe;Anzahl;Bezeichnung;Material`.

**Sammelaktionen** wirken auf alle Zeilen der Teileliste: Material setzen,
alle/keine Teile drehbar, Stückzahlen verdoppeln, Liste leeren. Teile mit Walz-
oder Dekorrichtung (Alucobond metallic) bekommen *Keines drehbar*.

## Schritt ③ – Material & Nesting

Tafelformate aus der Vorlagenliste übernehmen oder eintragen. **Anzahl** leer
lassen heißt unbegrenzt verfügbar, **Material** leer lassen heißt „passt für
alle Teile". Dazu Schnittfuge (Sägeblatt oder Fräser), Besäumung des
Tafelrands und die Schnittart:

* **Guillotine** – jeder Schnitt geht durch die ganze Tafel. Tafelschere,
  Plattensäge, Kreissäge.
* **Frei** – Rechtecke dicht gepackt (MaxRects). Für Laser, Plasma, CNC-Fräse.
* **Kontur** – echtes Nesting mit der tatsächlichen Teileform.

### Konturnesting

Teile greifen ineinander, Ausklinkungen werden mitgenutzt und kleine Teile
landen bei Bedarf in den Fensterausschnitten großer Teile. Gemessen in
`test_kontur.py`:

| Auftrag | Außenmaß-Nesting | Konturnesting |
|---|---|---|
| 16 Dreiecke 600×400 | 2 Tafeln, 31 % | **1 Tafel, 61 %** |
| 10 L-Winkel 800×800 | 4 Tafeln, 22 % | **2 Tafeln, 43 %** |
| Rahmen mit Ausschnitt + Einleger | 2 Tafeln | **1 Tafel** |
| Reine Rechtecke | 2 Tafeln, 57 % | 2 Tafeln, 57 % |

Je stärker die Teile von der Rechteckform abweichen, desto größer der Gewinn.
Bei Rechtecken bringt es nichts – dort rechnet das Programm zusätzlich das
schnelle Verfahren mit und übernimmt automatisch den besseren Plan.

**So rechnet es:** Jede Kontur wird je Drehwinkel gerastert (Scanline,
Even-Odd-Regel, dadurch sind Ausschnitte automatisch frei) und um die halbe
Schnittfuge aufgeweitet. Jedes Teil fällt an der günstigsten Stelle nach unten
und rutscht in vorhandene Taschen; Teile, die so nicht unterkommen, werden über
eine Kreuzkorrelation (FFT) auf der ganzen Tafel gesucht. Weil nach außen
gerundet wird, ist die eingestellte **Schnittfuge garantiert** eingehalten – im
Zweifel steht etwas mehr Abstand, nie weniger.

#### Erlaubte Drehung

Voreingestellt ist **beliebig – an den Teilekanten**. Jedes Teil wird dann
zusätzlich so gedreht, dass eine seiner eigenen Kanten waagrecht liegt. Das
entscheidet bei schiefen Teilen alles: ungedreht liegen sie schräg in ihrem
Hüllrechteck und verschenken die halbe Fläche.

| Auftrag | 90°-Schritte | an den Teilekanten |
|---|---|---|
| 10 Diagonalstreifen (Hülle 1400×1100, echte Breite 200) | 2 Tafeln, 24 % | **1 Tafel, 49 %** |
| 12 Giebelschenkel (langes Dreieck) | 2 Tafeln, 21 % | **1 Tafel, 43 %** |
| 20 Rechtecke 700×500 | 2 Tafeln, 78 % | 2 Tafeln, 78 % |

Die Winkel stammen aus der konvexen Hülle des Teils: je Kante eine Drehung, die
sie waagrecht legt, davon die drei mit der kleinsten Hüllfläche, jeweils in vier
Vierteldrehungen. Bei reinen Rechtecken kommt dabei nichts Neues heraus – dort
kostet es nur Rechenzeit, und die 90°-Schritte genügen. Teile mit *Drehbar =
aus* (Walz- oder Dekorrichtung) bleiben in jedem Fall stehen.

Stellschrauben: Rasterweite (5 mm ist ein guter Kompromiss), erlaubte Drehung,
Ausschnitte mitnutzen, Suchtiefe (1–6 Bewertungsstrategien; mehr ist genauer
und langsamer).

## Schritt ④ – Plan & Ausgabe

**Von Hand anpassen.** Jedes Teil lässt sich mit der Maus verschieben, drehen,
ablegen und wieder einsetzen – auch von einer Tafel auf die andere. Wählbar
ist, wie viele Tafeln gleichzeitig zu sehen sind (1 bis alle).

| Bedienung | Wirkung |
|---|---|
| Teil anklicken und ziehen | verschieben, auch auf eine andere Tafel |
| **R** oder die Drehknöpfe | 90° drehen (Winkelfeld für beliebige Grad) |
| Pfeiltasten | 1 mm schieben, mit Umschalt 10 mm |
| **Entf** oder *Ablegen* | Teil neben die Tafel legen |
| Knopf in der Ablage | Teil auf die aktive Tafel einsetzen |
| **Strg+Z** / *Verwerfen* | Schritt zurück bzw. auf den gerechneten Plan |

Beim Ziehen fangen sich die Teile an der Tafelkante und an den Nachbarn – genau
im Abstand der Schnittfuge – und an einem einstellbaren Raster. Überschneidungen
werden rot markiert; ein rot losgelassenes Teil **rückt selbst auf die nächste
freie Stelle** (abschaltbar über *Einrücken*). Erst **Änderungen übernehmen**
schreibt den Plan um; PDF, Excel und DXF nutzen danach den angepassten Plan.

**Ausgabe:** Schachtelplan als PDF (mit Zeichnung je Tafel), Teile- und
Tafelliste als Excel und CSV, kompletter Plan als DXF (Layer `TAFEL`,
`KONTUR`, `FRAESLINIE`, `BESCHRIFTUNG`).

## Dateien

| Datei | Inhalt |
|---|---|
| `app_nesting.py` | Oberfläche (die Datei wird gestartet) |
| `nesting.py` | Rechenkern über die Außenmaße, ohne Fremdbibliotheken |
| `kontur_nesting.py` | Echtes Konturnesting, braucht numpy |
| `dxf_import.py` | DXF lesen (HiCAD/Alucobond) und Schachtelplan schreiben |
| `plan_editor.py` + `komponenten/plan_editor/` | Plan von Hand nachbessern |
| `raster.py` | Plattenraster, Fugen, Gleichteilsuche, Montageplan |
| `raster_editor.py` + `komponenten/raster_editor/` | Felder in der Ansicht zuordnen |
| `zeichnung.py` | Pläne als SVG für den Bildschirm |
| `pdf_export.py` | Werkstattdruck als PDF |
| `hilfe_bilder.py` | Erklärbilder im Hilfe-Reiter |
| `test_*.py` | Tests, ohne pytest ausführbar (`python3 test_nesting.py` usw.) |

## Grenzen

* Geschachtelt wird in der Ebene; Biegeteile werden als Abwicklung behandelt.
* Gedreht wird in 90°- oder 45°-Schritten oder in den Winkeln, die sich aus den
  Kanten des Teils ergeben – nicht in völlig freien Winkeln.
* Das Konturnesting rechnet im Raster – die Teile stehen gelegentlich ein paar
  Millimeter weiter auseinander als nötig, nie enger als die Schnittfuge.
* Teile werden von oben eingelegt, nicht seitlich eingeschoben. Eine Tasche,
  die nur seitlich erreichbar wäre, bleibt frei.
* Die Optimierung ist eine sehr gute Heuristik, kein mathematisches Optimum.
* Der ausgegebene Plan ersetzt die Kontrolle in der Werkstatt nicht.
* Das Fassadenraster wird als ebene Ansicht behandelt: eine perspektivisch
  verzerrte Zeichnung liefert die Maße, die darin stehen – nicht die wahren
  Maße am Bau.
* Bögen und Kreise im Rasterplan werden in kurze Strecken zerlegt; ein Feld
  mit runder Kante bekommt dadurch viele Eckpunkte.
* Gerechnet wird die Abwicklung in der Ebene – Gehrungen, Kantungen und
  Befestigungen bleiben Sache der Konstruktion.

Die frühere Stangen- und Profiloptimierung (1D) ist entfallen; sie steckt bei
Bedarf noch in der Versionsgeschichte des Projekts.
