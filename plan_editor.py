"""
plan_editor.py - Schachtelplan von Hand nachbessern.

Stellt den Plan einer Tafel als bedienbare Zeichnung dar: Teile lassen sich
mit der Maus verschieben, drehen, ablegen und wieder einsetzen. Die Komponente
prueft dabei laufend, ob sich Teile ueberschneiden oder die Schnittfuge
unterschreiten.

Die Oberflaeche liegt in komponenten/plan_editor/index.html und spricht ueber
das Streamlit-Komponentenprotokoll mit diesem Modul.
"""

from __future__ import annotations

import os

import streamlit.components.v1 as components

from nesting import Platzierung2D, drehe_polygone, versatz_fuer

_ORDNER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "komponenten", "plan_editor")

_komponente = components.declare_component("nesting_plan_editor", path=_ORDNER)


# ==========================================================
# 1. DATEN FUER DIE OBERFLAECHE
# ==========================================================


def _rechteck(breite: float, hoehe: float) -> list:
    return [[(0.0, 0.0), (breite, 0.0), (breite, hoehe), (0.0, hoehe)]]


def sichere_kontur(platzierung) -> list:
    """
    Kontur einer Platzierung; bei Rechteckteilen ohne DXF-Kontur wird eine
    erzeugt und am Teil hinterlegt.

    Ohne Kontur liesse sich ein Teil nach dem Drehen nicht mehr vermessen -
    Breite und Hoehe wuerden zu null und das Teil verschwaende aus dem Plan.
    """
    if platzierung.kontur:
        return platzierung.kontur
    winkel = (platzierung.winkel or 0.0) % 360.0
    if abs(winkel - 90.0) < 1e-9 or abs(winkel - 270.0) < 1e-9:
        breite, hoehe = platzierung.hoehe, platzierung.breite
    else:
        breite, hoehe = platzierung.breite, platzierung.hoehe
    platzierung.kontur = _rechteck(float(breite), float(hoehe))
    return platzierung.kontur


def kontur_karte(ergebnis, zusatz: dict | None = None) -> dict:
    """
    Nachschlagewerk Bezeichnung -> (Kontur, Stichlinien).

    Gesammelt wird aus allen platzierten Teilen; 'zusatz' ergaenzt Konturen,
    die nur beim DXF-Import bekannt sind.
    """
    karte: dict = {}
    for plan in ergebnis.plaene:
        for p in plan.platzierungen:
            if p.bezeichnung not in karte and p.kontur:
                karte[p.bezeichnung] = (p.kontur, p.stichlinien)
    for name, eintrag in (zusatz or {}).items():
        if name not in karte:
            kontur = eintrag.get("kontur") if isinstance(eintrag, dict) else None
            stich = eintrag.get("stichlinien", []) if isinstance(eintrag, dict) else []
            if kontur:
                karte[name] = (kontur, stich)
    return karte


def _punkte(ringe) -> list:
    return [[[float(x), float(y)] for x, y in ring] for ring in ringe]


def daten_fuer(plaene, nummern, saegeblatt: float, besaeumung: float,
               farben: dict, vorrat: list, raster: float = 5.0) -> dict:
    """
    Baut die Vorgabe fuer die Oberflaeche.

    plaene/nummern  die gezeigten Tafeln und ihre Nummern im Gesamtplan.
    Die Teile kommen als eine Liste mit Feld "tafel" (Index innerhalb der
    gezeigten Tafeln) - so kann die Oberflaeche sie zwischen Tafeln ziehen.
    """
    tafeln, teile = [], []
    for index, (plan, nummer) in enumerate(zip(plaene, nummern)):
        tafeln.append({
            "nummer": int(nummer),
            "name": plan.tafel,
            "breite": float(plan.breite),
            "hoehe": float(plan.hoehe),
            "besaeumung": float(besaeumung),
        })
        for i, p in enumerate(plan.platzierungen):
            teile.append({
                "id": f"t{index}_{i}",
                "tafel": index,
                "sorte": p.bezeichnung,
                "x": round(float(p.x), 3),
                "y": round(float(p.y), 3),
                "winkel": float(p.winkel or 0.0),
                "kontur": _punkte(sichere_kontur(p)),
                "stich": _punkte(p.stichlinien or []),
                "farbe": farben.get(p.bezeichnung, "#1E3A8A"),
            })
    return {
        "tafeln": tafeln,
        "saegeblatt": float(saegeblatt),
        "raster": float(raster),
        "teile": teile,
        "vorrat": vorrat,
    }


def vorrat_fuer(ergebnis, plan, karte: dict, farben: dict) -> list:
    """
    Teile, die auf keiner Tafel liegen und zum Material dieser Tafel passen -
    sie koennen im Editor von Hand eingesetzt werden.
    """
    posten = []
    for bezeichnung, breite, hoehe, anzahl in ergebnis.fehlende:
        kontur, stich = karte.get(bezeichnung, (None, []))
        if kontur is None:
            kontur = _rechteck(float(breite), float(hoehe))
        posten.append({
            "sorte": bezeichnung,
            "anzahl": int(anzahl),
            "kontur": _punkte(kontur),
            "stich": _punkte(stich or []),
            "farbe": farben.get(bezeichnung, "#6B7280"),
        })
    return posten


def plan_editor(plaene, nummern, saegeblatt: float, besaeumung: float,
                farben: dict, vorrat: list, raster: float = 5.0, key=None):
    """Zeigt den Editor an. Rueckgabe: None oder die uebernommenen Aenderungen."""
    daten = daten_fuer(plaene, nummern, saegeblatt, besaeumung, farben, vorrat, raster)
    return _komponente(daten=daten, key=key, default=None)


# ==========================================================
# 2. AENDERUNGEN UEBERNEHMEN
# ==========================================================


def uebernehme(ergebnis, nummern, rueckgabe: dict, karte: dict) -> list[str]:
    """
    Schreibt die Aenderungen aus dem Editor in die gezeigten Tafeln zurueck.

    Teile koennen dabei die Tafel gewechselt haben. Entfernte Teile wandern in
    die Liste der nicht eingeplanten Teile, eingesetzte werden von dort
    abgezogen.

    Rueckgabe: Meldungen fuer die Oberflaeche.
    """
    plaene = [ergebnis.plaene[nummer - 1] for nummer in nummern]
    alt = [list(plan.platzierungen) for plan in plaene]

    vorher: dict = {}
    for liste in alt:
        for p in liste:
            vorher[p.bezeichnung] = vorher.get(p.bezeichnung, 0) + 1

    neu: list[list[Platzierung2D]] = [[] for _ in plaene]
    verschoben = 0
    gewechselt = 0

    for eintrag in rueckgabe.get("teile", []):
        ziel = int(eintrag.get("tafel", 0))
        if not 0 <= ziel < len(plaene):
            continue
        kennung = str(eintrag.get("id", ""))
        bezeichnung = str(eintrag.get("sorte", "Teil"))
        winkel = float(eintrag.get("winkel", 0.0)) % 360.0
        quelle = _quelle_zu(kennung, alt)

        if quelle is not None:
            herkunft, p = quelle
            kontur, stich = sichere_kontur(p), p.stichlinien
            bezeichnung = p.bezeichnung
            if herkunft != ziel:
                gewechselt += 1
            elif (abs(p.x - float(eintrag.get("x", 0.0))) > 0.01
                    or abs(p.y - float(eintrag.get("y", 0.0))) > 0.01
                    or abs((p.winkel or 0.0) - winkel) > 0.01):
                verschoben += 1
        else:
            kontur, stich = karte.get(bezeichnung, (None, []))
            if kontur is None:
                continue

        _, breite, hoehe = drehe_polygone(kontur, winkel)
        if breite <= 0 or hoehe <= 0:
            continue                      # ohne brauchbare Kontur nicht platzierbar
        neu[ziel].append(Platzierung2D(
            bezeichnung=bezeichnung,
            x=float(eintrag.get("x", 0.0)),
            y=float(eintrag.get("y", 0.0)),
            breite=breite, hoehe=hoehe,
            gedreht=abs(winkel - 90.0) < 1e-9,
            kontur=kontur, stichlinien=stich,
            winkel=winkel,
            versatz=versatz_fuer(kontur, winkel),
        ))

    for plan, liste in zip(plaene, neu):
        plan.platzierungen = liste

    nachher: dict = {}
    for liste in neu:
        for p in liste:
            nachher[p.bezeichnung] = nachher.get(p.bezeichnung, 0) + 1

    meldungen = []
    if verschoben:
        meldungen.append(f"{verschoben} Teil(e) verschoben oder gedreht")
    if gewechselt:
        meldungen.append(f"{gewechselt} Teil(e) auf eine andere Tafel gelegt")
    for bezeichnung in sorted(set(vorher) | set(nachher)):
        unterschied = nachher.get(bezeichnung, 0) - vorher.get(bezeichnung, 0)
        if unterschied == 0:
            continue
        # Was von der Tafel genommen wurde, fehlt wieder; was eingesetzt wurde,
        # ist nicht mehr offen.
        _fehlende_aendern(ergebnis, bezeichnung, -unterschied, karte)
        if unterschied < 0:
            meldungen.append(f"{-unterschied}× {bezeichnung} abgelegt")
        else:
            meldungen.append(f"{unterschied}× {bezeichnung} eingesetzt")
    return meldungen


def _quelle_zu(kennung: str, alt: list):
    """Findet die urspruengliche Platzierung zu einer Kennung 't<tafel>_<pos>'."""
    if not kennung.startswith("t") or "_" not in kennung:
        return None
    tafel, _, pos = kennung[1:].partition("_")
    if not tafel.isdigit() or not pos.isdigit():
        return None
    tafel, pos = int(tafel), int(pos)
    if tafel >= len(alt) or pos >= len(alt[tafel]):
        return None
    return tafel, alt[tafel][pos]


def _fehlende_aendern(ergebnis, bezeichnung: str, anzahl: int, karte: dict) -> None:
    """Erhoeht (anzahl > 0) oder senkt (anzahl < 0) die Zahl der offenen Teile."""
    if anzahl == 0:
        return
    rest = anzahl
    neue_liste = []
    for eintrag in ergebnis.fehlende:
        name, breite, hoehe, menge = eintrag
        if name == bezeichnung and rest != 0:
            menge += rest
            rest = 0
            if menge > 0:
                neue_liste.append((name, breite, hoehe, menge))
            continue
        neue_liste.append(eintrag)

    if rest > 0:
        kontur = karte.get(bezeichnung, (None, []))[0]
        if kontur:
            _, breite, hoehe = drehe_polygone(kontur, 0.0)
        else:
            breite = hoehe = 0.0
        neue_liste.append((bezeichnung, breite, hoehe, rest))

    ergebnis.fehlende = neue_liste
