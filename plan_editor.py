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


def daten_fuer(plan, nummer: int, saegeblatt: float, besaeumung: float,
               farben: dict, vorrat: list, raster: float = 5.0) -> dict:
    """Baut die Vorgabe fuer die Oberflaeche."""
    teile = []
    for i, p in enumerate(plan.platzierungen):
        kontur = sichere_kontur(p)
        teile.append({
            "id": f"t{i}",
            "sorte": p.bezeichnung,
            "x": round(float(p.x), 3),
            "y": round(float(p.y), 3),
            "winkel": float(p.winkel or 0.0),
            "kontur": _punkte(kontur),
            "stich": _punkte(p.stichlinien or []),
            "farbe": farben.get(p.bezeichnung, "#1E3A8A"),
        })
    return {
        "tafel": {
            "nummer": nummer,
            "name": plan.tafel,
            "breite": float(plan.breite),
            "hoehe": float(plan.hoehe),
            "besaeumung": float(besaeumung),
        },
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


def plan_editor(plan, nummer: int, saegeblatt: float, besaeumung: float,
                farben: dict, vorrat: list, raster: float = 5.0, key=None):
    """Zeigt den Editor an. Rueckgabe: None oder die uebernommenen Aenderungen."""
    daten = daten_fuer(plan, nummer, saegeblatt, besaeumung, farben, vorrat, raster)
    return _komponente(daten=daten, key=key, default=None)


# ==========================================================
# 2. AENDERUNGEN UEBERNEHMEN
# ==========================================================


def uebernehme(ergebnis, index: int, rueckgabe: dict, karte: dict) -> list[str]:
    """
    Schreibt die Aenderungen aus dem Editor in den Plan zurueck.

    Entfernte Teile wandern in die Liste der nicht eingeplanten Teile,
    eingesetzte Teile werden von dort abgezogen.

    Rueckgabe: Meldungen fuer die Oberflaeche.
    """
    plan = ergebnis.plaene[index]
    alt = list(plan.platzierungen)
    vorher: dict = {}
    for p in alt:
        vorher[p.bezeichnung] = vorher.get(p.bezeichnung, 0) + 1

    neu: list[Platzierung2D] = []
    verschoben = 0
    for eintrag in rueckgabe.get("teile", []):
        kennung = str(eintrag.get("id", ""))
        bezeichnung = str(eintrag.get("sorte", "Teil"))
        winkel = float(eintrag.get("winkel", 0.0)) % 360.0

        if kennung.startswith("t") and kennung[1:].isdigit() and int(kennung[1:]) < len(alt):
            quelle = alt[int(kennung[1:])]
            kontur, stich = sichere_kontur(quelle), quelle.stichlinien
            bezeichnung = quelle.bezeichnung
            if (abs(quelle.x - float(eintrag.get("x", 0.0))) > 0.01
                    or abs(quelle.y - float(eintrag.get("y", 0.0))) > 0.01
                    or abs((quelle.winkel or 0.0) - winkel) > 0.01):
                verschoben += 1
        else:
            kontur, stich = karte.get(bezeichnung, (None, []))
            if kontur is None:
                continue

        _, breite, hoehe = drehe_polygone(kontur, winkel)
        if breite <= 0 or hoehe <= 0:
            continue                      # ohne brauchbare Kontur nicht platzierbar
        neu.append(Platzierung2D(
            bezeichnung=bezeichnung,
            x=float(eintrag.get("x", 0.0)),
            y=float(eintrag.get("y", 0.0)),
            breite=breite, hoehe=hoehe,
            gedreht=abs(winkel - 90.0) < 1e-9,
            kontur=kontur, stichlinien=stich,
            winkel=winkel,
            versatz=versatz_fuer(kontur, winkel),
        ))

    plan.platzierungen = neu

    nachher: dict = {}
    for p in neu:
        nachher[p.bezeichnung] = nachher.get(p.bezeichnung, 0) + 1

    meldungen = []
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

    if verschoben:
        meldungen.insert(0, f"{verschoben} Teil(e) verschoben oder gedreht")
    return meldungen


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
