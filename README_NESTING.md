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

## Der Ablauf in drei Schritten

| Schritt | Was dort passiert |
|---|---|
| ① **Teile** | DXF einlesen oder Teile von Hand erfassen; Teileliste mit Sammelaktionen |
| ② **Material & Nesting** | Tafelformate, Schnittfuge, Besäumung, Schnittart – dann schachteln |
| ③ **Plan & Ausgabe** | Pläne ansehen, von Hand nachbessern, als PDF / Excel / CSV / DXF ausgeben |

Der Reiter **Hilfe** erklärt jeden Schritt mit Bildern.

## Schritt ① – Teile

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

## Schritt ② – Material & Nesting

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

Stellschrauben: Rasterweite (5 mm ist ein guter Kompromiss), erlaubte Drehung
(90°- oder 45°-Schritte oder keine), Ausschnitte mitnutzen, Suchtiefe.

## Schritt ③ – Plan & Ausgabe

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
| `zeichnung.py` | Pläne als SVG für den Bildschirm |
| `pdf_export.py` | Werkstattdruck als PDF |
| `hilfe_bilder.py` | Erklärbilder im Hilfe-Reiter |
| `test_*.py` | Tests, ohne pytest ausführbar (`python3 test_nesting.py` usw.) |

## Grenzen

* Geschachtelt wird in der Ebene; Biegeteile werden als Abwicklung behandelt.
* Gedreht wird in 90°- oder 45°-Schritten, nicht in beliebigen Winkeln.
* Das Konturnesting rechnet im Raster – die Teile stehen gelegentlich ein paar
  Millimeter weiter auseinander als nötig, nie enger als die Schnittfuge.
* Teile werden von oben eingelegt, nicht seitlich eingeschoben. Eine Tasche,
  die nur seitlich erreichbar wäre, bleibt frei.
* Die Optimierung ist eine sehr gute Heuristik, kein mathematisches Optimum.
* Der ausgegebene Plan ersetzt die Kontrolle in der Werkstatt nicht.

Die frühere Stangen- und Profiloptimierung (1D) ist entfallen; sie steckt bei
Bedarf noch in der Versionsgeschichte des Projekts.
