"""
raster_editor.py - Felder des Plattenrasters in der Ansicht zuordnen.

Die Fassadenansicht wird anklickbar dargestellt: jedes Feld bekommt mit dem
Pinsel einen Plattentyp (Farbe) oder wird als Oeffnung weggeklickt
(Fenster, Tuer, Entfall). Die Oberflaeche liegt in
komponenten/raster_editor/index.html.
"""

from __future__ import annotations

import os

import streamlit.components.v1 as components

from raster import STANDARDTYP
from zeichnung import FARBEN, farbe_nach_name

_ORDNER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "komponenten", "raster_editor")

_komponente = components.declare_component("nesting_raster_editor", path=_ORDNER)


def typenliste(eintraege) -> list:
    """
    Plattentypen mit Farbe, in der Reihenfolge ihrer Nennung.

    'eintraege' sind entweder Namen oder Angaben der Form
    {"name", "farbe_name", "material"}. Fehlt eine Farbe, wird eine aus der
    Palette vergeben.
    """
    typen, gesehen = [], set()
    for eintrag in list(eintraege) or [STANDARDTYP]:
        if isinstance(eintrag, dict):
            name = str(eintrag.get("name", "")).strip()
            farbe_name = str(eintrag.get("farbe_name", "")).strip()
            material = str(eintrag.get("material", "")).strip()
            tafel_breite = _zahl(eintrag.get("tafel_breite"))
            tafel_hoehe = _zahl(eintrag.get("tafel_hoehe"))
            preis = _zahl(eintrag.get("preis"))
        else:
            name, farbe_name, material = str(eintrag).strip(), "", ""
            tafel_breite = tafel_hoehe = preis = 0.0
        if not name or name in gesehen:
            continue
        gesehen.add(name)
        typen.append({
            "name": name,
            "farbe": farbe_nach_name(farbe_name, FARBEN[len(typen) % len(FARBEN)]),
            "farbe_name": farbe_name,
            "material": material,
            "tafel_breite": tafel_breite,
            "tafel_hoehe": tafel_hoehe,
            "preis": preis,
        })
    if not typen:
        typen = [{"name": STANDARDTYP, "farbe": FARBEN[0], "farbe_name": "",
                  "material": "", "tafel_breite": 0.0, "tafel_hoehe": 0.0,
                  "preis": 0.0}]
    return typen


def _zahl(wert) -> float:
    """Zahl aus der Tabelle; leer oder unbrauchbar ergibt 0."""
    try:
        zahl = float(wert)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if zahl != zahl or zahl < 0 else zahl      # zahl != zahl = NaN


def daten_fuer(felder: list, typen: list) -> dict:
    """Baut die Vorgabe fuer die Oberflaeche."""
    return {
        "typen": typen,
        "felder": [{
            "name": feld.name,
            "rechteckig": bool(feld.rechteckig),
            "polygon": [[round(float(x), 2), round(float(y), 2)]
                        for x, y in feld.polygon],
        } for feld in felder],
        "zuordnung": {feld.name: {"typ": feld.typ, "aus": bool(feld.aus)}
                      for feld in felder},
    }


def raster_editor(felder: list, typen: list, key=None):
    """Zeigt die Zuordnungsansicht. Rueckgabe: None oder die Zuordnung."""
    return _komponente(daten=daten_fuer(felder, typen), key=key, default=None)


def uebernehme_zuordnung(felder: list, rueckgabe: dict) -> dict:
    """
    Schreibt die Zuordnung aus der Ansicht in die Felder zurueck.

    Rueckgabe: Zahlen fuer die Meldung {geaendert, oeffnungen, typen}.
    """
    zuordnung = (rueckgabe or {}).get("zuordnung") or {}
    geaendert = 0
    for feld in felder:
        eintrag = zuordnung.get(feld.name)
        if not isinstance(eintrag, dict):
            continue
        typ = str(eintrag.get("typ") or feld.typ or STANDARDTYP)
        aus = bool(eintrag.get("aus"))
        if typ != feld.typ or aus != feld.aus:
            geaendert += 1
        feld.typ, feld.aus = typ, aus
    return {
        "geaendert": geaendert,
        "oeffnungen": sum(1 for f in felder if f.aus),
        "typen": sorted({f.typ for f in felder if not f.aus}),
    }
