"""
app_nesting.py - Verschnittoptimierung (Nesting) fuer Meingassner Metalltechnik

Start:  streamlit run app_nesting.py

Aufbau in vier Schritten:

  1  Raster     Plattenraster der Fassade zeichnen oder aus DXF holen,
                Felder zuordnen, Gleichteile suchen   (freiwillig)
  2  Teile      DXF einlesen (HiCAD / Alucobond) oder von Hand erfassen
  3  Material   Tafeln und Schnittparameter, dann schachteln
  4  Plan       Ergebnis ansehen, von Hand nachbessern, ausgeben
"""

import datetime
import inspect
import io
import os

import pandas as pd
import streamlit as st

from nesting import Tafel, Zuschnitt2D, optimize_2d, parse_2d_eingabe
from zeichnung import farbkarte, legende, namen_aus_plan, svg_fassade, svg_tafel, svg_teil
import hilfe_bilder

try:
    import raster
    import raster_editor
    RASTER_OK = True
except Exception as exc:
    RASTER_OK = False
    RASTER_FEHLER = str(exc)

try:
    from kontur_nesting import FEINE_WINKEL, STANDARD_WINKEL, optimize_2d_kontur
    KONTUR_OK = True
except Exception as exc:                      # numpy fehlt
    KONTUR_OK = False
    KONTUR_FEHLER = str(exc)

try:
    import dxf_import as dxf
    DXF_OK = True
except Exception as exc:
    DXF_OK = False
    DXF_FEHLER = str(exc)

try:
    from pdf_export import pdf_2d
    PDF_OK = True
except Exception as exc:
    PDF_OK = False
    PDF_FEHLER = str(exc)

try:
    from plan_editor import kontur_karte, plan_editor, uebernehme, vorrat_fuer
    EDITOR_OK = True
except Exception as exc:
    EDITOR_OK = False
    EDITOR_FEHLER = str(exc)


# ==========================================================
# 0. STREAMLIT-KOMPATIBILITAET
# ==========================================================
# Neuere Streamlit-Versionen ersetzen use_container_width durch width="stretch".
try:
    _NEUE_BREITE = "width" in inspect.signature(st.dataframe).parameters
except (TypeError, ValueError):               # pragma: no cover
    _NEUE_BREITE = False

BREITE = {"width": "stretch"} if _NEUE_BREITE else {"use_container_width": True}


# ==========================================================
# 1. SEITE UND STIL
# ==========================================================

LOGO = next((d for d in ("Meingassner Metalltechnik 2023.png", "logo_firma.png",
                         "logo.png") if os.path.exists(d)), None)

st.set_page_config(page_title="Nesting - Verschnittoptimierung",
                   page_icon=LOGO or "🪚", layout="wide")

st.markdown("""
    <style>
    .kopf { font-size: 1.9rem; font-weight: 700; color: #1E3A8A; margin-bottom: 2px; }
    .unterkopf { color: #6B7280; font-size: 0.95rem; margin-bottom: 10px; }
    .schritt { font-size: 1.15rem; font-weight: 700; color: #1E3A8A;
               margin: 2px 0 2px 0; }
    .merk { color: #6B7280; font-size: 0.88rem; margin-bottom: 10px; }
    div.stButton > button { min-height: 42px; border-radius: 8px; }
    div[data-testid="stMetricValue"] { font-size: 1.45rem; }
    section[data-testid="stSidebar"] { width: 300px !important; }
    </style>
""", unsafe_allow_html=True)


# ==========================================================
# 2. TABELLEN OHNE RUECKSCHREIBEN
# ==========================================================
# st.data_editor darf sein eigenes Ergebnis nicht in seine Datenquelle
# zurueckschreiben - sonst wird die Tabelle bei jedem Lauf neu aufgesetzt und
# die erste Aenderung (z. B. ein Haken) geht verloren. Darum: die Quelle bleibt
# liegen, Bearbeitungen werden nur gelesen. Aendert das Programm die Quelle
# selbst, bekommt die Tabelle ueber die Version einen neuen Schluessel.


def tabelle(name: str, **argumente) -> pd.DataFrame:
    """Zeigt eine bearbeitbare Tabelle und liefert den aktuellen Stand."""
    version = st.session_state.get(f"{name}_version", 0)
    bearbeitet = st.data_editor(st.session_state[name],
                                key=f"ed_{name}_{version}", **argumente)
    st.session_state[f"{name}_aktuell"] = bearbeitet
    return bearbeitet


def setze_tabelle(name: str, daten: pd.DataFrame) -> None:
    """Ersetzt den Inhalt einer Tabelle (durch das Programm, nicht den Benutzer)."""
    st.session_state[name] = daten.reset_index(drop=True)
    st.session_state[f"{name}_version"] = st.session_state.get(f"{name}_version", 0) + 1
    st.session_state[f"{name}_aktuell"] = st.session_state[name]


def stand(name: str) -> pd.DataFrame:
    """Aktueller Stand einer Tabelle, auch wenn sie gerade nicht sichtbar ist."""
    return st.session_state.get(f"{name}_aktuell", st.session_state[name])


# ==========================================================
# 3. VORGABEN UND SITZUNG
# ==========================================================

TAFEL_VORLAGEN = {
    "Alucobond 1250 x 3200": (1250, 3200),
    "Alucobond 1500 x 3200": (1500, 3200),
    "Alucobond 1500 x 4000": (1500, 4000),
    "Alucobond 2000 x 3200": (2000, 3200),
    "Blech 1000 x 2000": (1000, 2000),
    "Blech 1250 x 2500": (1250, 2500),
    "Blech 1500 x 3000": (1500, 3000),
    "Blech 2000 x 1000": (2000, 1000),
}

SPALTEN_TEILE = ["Bezeichnung", "Breite (mm)", "Höhe (mm)", "Anzahl", "Material",
                 "Drehbar", "Kontur"]
SPALTEN_TAFELN = ["Bezeichnung", "Breite (mm)", "Höhe (mm)", "Anzahl", "Material",
                  "Preis (€)"]

BEISPIEL_TEILE = pd.DataFrame([
    {"Bezeichnung": "Wange", "Breite (mm)": 1200.0, "Höhe (mm)": 300.0, "Anzahl": 4,
     "Material": "Blech 3 mm", "Drehbar": True, "Kontur": "—"},
    {"Bezeichnung": "Deckblech", "Breite (mm)": 800.0, "Höhe (mm)": 400.0, "Anzahl": 6,
     "Material": "Blech 3 mm", "Drehbar": True, "Kontur": "—"},
], columns=SPALTEN_TEILE)

BEISPIEL_TAFELN = pd.DataFrame([
    {"Bezeichnung": "Blech 1250 x 2500", "Breite (mm)": 1250.0, "Höhe (mm)": 2500.0,
     "Anzahl": float("nan"), "Material": "Blech 3 mm", "Preis (€)": 145.0},
], columns=SPALTEN_TAFELN)


def init():
    vorgaben = {
        "teile": BEISPIEL_TEILE.copy(),
        "tafeln": BEISPIEL_TAFELN.copy(),
        "teile_version": 0,
        "tafeln_version": 0,
        "ergebnis": None,
        "konturen": {},
        "dxf_teile": [],
        "dxf_hinweise": [],
        "dxf_layer": {},
        "projekt": "",
        "raster_felder": [],
        "raster_linien": {},
        "raster_texte": [],
        "raster_hinweise": [],
        "raster_quelle": "",
        "raster_material": {},
    }
    for schluessel, wert in vorgaben.items():
        if schluessel not in st.session_state:
            st.session_state[schluessel] = wert


init()


def zahl(wert, standard=0.0) -> float:
    if wert is None or (isinstance(wert, float) and pd.isna(wert)):
        return standard
    try:
        return float(str(wert).replace(",", "."))
    except (TypeError, ValueError):
        return standard


def ganzzahl_oder_none(wert):
    """Leeres Feld = unbegrenzt verfuegbar."""
    if wert is None or (isinstance(wert, float) and pd.isna(wert)):
        return None
    try:
        n = int(float(wert))
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def excel_bytes(blaetter: dict) -> bytes | None:
    try:
        puffer = io.BytesIO()
        with pd.ExcelWriter(puffer, engine="openpyxl") as schreiber:
            for name, df in blaetter.items():
                df.to_excel(schreiber, sheet_name=name[:31], index=False)
        return puffer.getvalue()
    except ImportError:
        return None


def dateiname(basis: str, endung: str) -> str:
    projekt = "".join(c for c in st.session_state.projekt if c.isalnum() or c in " -_").strip()
    teil = f"_{projekt.replace(' ', '_')}" if projekt else ""
    return f"{basis}{teil}_{datetime.date.today():%Y%m%d}.{endung}"


def teile_aus_tabelle(df: pd.DataFrame) -> list:
    """Baut aus der Teiletabelle die Rechenobjekte."""
    teile = []
    for _, zeile in df.iterrows():
        breite, hoehe = zahl(zeile["Breite (mm)"]), zahl(zeile["Höhe (mm)"])
        anzahl = int(zahl(zeile["Anzahl"], 0))
        if breite <= 0 or hoehe <= 0 or anzahl <= 0:
            continue
        bezeichnung = str(zeile["Bezeichnung"] or "Teil")
        gespeichert = st.session_state.konturen.get(bezeichnung, {})
        teile.append(Zuschnitt2D(
            breite, hoehe, anzahl, bezeichnung, str(zeile.get("Material") or ""),
            bool(zeile.get("Drehbar", True)),
            kontur=gespeichert.get("kontur", []),
            stichlinien=gespeichert.get("stichlinien", [])))
    return teile


def tafeln_aus_tabelle(df: pd.DataFrame) -> list:
    return [Tafel(zahl(z["Breite (mm)"]), zahl(z["Höhe (mm)"]),
                  ganzzahl_oder_none(z.get("Anzahl")),
                  str(z["Bezeichnung"] or "Tafel"), str(z.get("Material") or ""),
                  zahl(z.get("Preis (€)")))
            for _, z in df.iterrows()
            if zahl(z["Breite (mm)"]) > 0 and zahl(z["Höhe (mm)"]) > 0]


# ==========================================================
# 4. KOPF UND SEITENLEISTE
# ==========================================================

kopf_links, kopf_rechts = st.columns([1, 6])
with kopf_links:
    if LOGO:
        st.image(LOGO, width=130)
with kopf_rechts:
    st.markdown('<div class="kopf">Nesting &ndash; Verschnittoptimierung</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="unterkopf">Blech- und Plattenzuschnitt mit DXF-Import '
                'aus HiCAD / Alucobond</div>', unsafe_allow_html=True)

with st.sidebar:
    if LOGO:
        st.image(LOGO, **BREITE)
    st.session_state.projekt = st.text_input(
        "Projekt / Auftrag", st.session_state.projekt,
        placeholder="z. B. BV Musterhaus, Fassade Nord")

    st.markdown("---")
    st.markdown("**Stand**")
    if st.session_state.get("raster_felder"):
        felder_jetzt = st.session_state.raster_felder
        offen = sum(1 for f in felder_jetzt if f.aus)
        st.write(f"Raster: **{len(felder_jetzt)}** Felder"
                 + (f", {offen} Öffnungen" if offen else ""))
    teile_jetzt = stand("teile")
    anzahl_positionen = int((teile_jetzt["Anzahl"].fillna(0) > 0).sum()) \
        if "Anzahl" in teile_jetzt else 0
    anzahl_stueck = int(teile_jetzt["Anzahl"].fillna(0).sum()) if len(teile_jetzt) else 0
    st.write(f"Teile: **{anzahl_positionen}** Positionen, **{anzahl_stueck}** Stück")
    st.write(f"Tafelformate: **{len(stand('tafeln'))}**")
    if st.session_state.ergebnis is not None:
        erg = st.session_state.ergebnis
        st.write(f"Plan: **{erg.anzahl_tafeln}** Tafeln, "
                 f"**{erg.ausnutzung_echt_prozent:.0f} %** Ausnutzung")
    else:
        st.write("Plan: _noch nicht gerechnet_")

    st.markdown("---")
    st.caption("Alle Maße in Millimeter. Preise netto.")


# ==========================================================
# 5. ERGEBNISDARSTELLUNG
# ==========================================================


def teileliste_2d(erg) -> pd.DataFrame:
    zeilen = []
    for nr, plan in enumerate(erg.plaene, start=1):
        for i, p in enumerate(plan.platzierungen, start=1):
            zeilen.append({
                "Tafel": nr, "Material": plan.material, "Tafeltyp": plan.tafel,
                "Pos": i, "Teil": p.bezeichnung,
                "Breite (mm)": round(p.breite, 1), "Höhe (mm)": round(p.hoehe, 1),
                "X (mm)": round(p.x, 1), "Y (mm)": round(p.y, 1),
                "Drehung": f"{p.winkel:.0f}°",
            })
    return pd.DataFrame(zeilen)


def tafelliste_2d(erg) -> pd.DataFrame:
    return pd.DataFrame([{
        "Tafel": nr, "Material": plan.material, "Tafeltyp": plan.tafel,
        "Breite (mm)": round(plan.breite), "Höhe (mm)": round(plan.hoehe),
        "Teile": len(plan.platzierungen),
        "Ausnutzung (%)": round(plan.ausnutzung * 100, 1),
        "Preis (€)": round(plan.preis, 2),
    } for nr, plan in enumerate(erg.plaene, start=1)])


def zeige_kennzahlen(erg):
    mit_kontur = abs(erg.echte_flaeche - erg.genutzte_flaeche) > 1.0
    k = st.columns(5)
    k[0].metric("Tafeln", erg.anzahl_tafeln)
    k[1].metric("Tafelfläche", f"{erg.gesamt_flaeche / 1e6:.2f} m²")
    k[2].metric("Ausnutzung", f"{erg.ausnutzung_echt_prozent:.1f} %",
                help="Echte Teilefläche bezogen auf die Tafelfläche"
                if mit_kontur else None)
    k[3].metric("Abfall", f"{100 - erg.ausnutzung_echt_prozent:.1f} %",
                f"{(erg.gesamt_flaeche - erg.echte_flaeche) / 1e6:.2f} m²",
                delta_color="inverse")
    k[4].metric("Materialkosten", f"{erg.gesamt_kosten:,.2f} €".replace(",", "."))


def zeige_plaene(erg, farben):
    st.markdown(legende(farben.keys(), farben), unsafe_allow_html=True)
    st.caption("Rot gestrichelt = Fräs-/Falzlinie aus dem DXF (kein Trennschnitt).")
    spalten = st.columns(2)
    for i, plan in enumerate(erg.plaene):
        with spalten[i % 2]:
            st.markdown(svg_tafel(plan, i + 1, farben=farben), unsafe_allow_html=True)


def zeige_editor(erg, farben):
    """Schachtelplan von Hand nachbessern - eine, mehrere oder alle Tafeln."""
    st.caption(
        "Teil anklicken und ziehen – auch von einer Tafel auf die andere. "
        "**R** dreht um 90°, **Entf** legt es neben die Tafel, die **Pfeiltasten** "
        "schieben millimeterweise. Wer ein Teil rot loslässt, bekommt es automatisch "
        "auf die nächste freie Stelle gerückt. Erst **Änderungen übernehmen** "
        "schreibt den Plan um.")

    gesamt = len(erg.plaene)
    nummern = [1]
    if gesamt > 1:
        stufen = [z for z in (1, 2, 4, 6, 10, 15) if z < gesamt]
        optionen = stufen + ["Alle"]
        vorgabe = "Alle" if gesamt <= 6 else 6
        s1, s2 = st.columns([2, 3])
        wahl = s1.selectbox(
            "Tafeln gleichzeitig anzeigen", optionen,
            index=optionen.index(vorgabe) if vorgabe in optionen else len(optionen) - 1,
            key="editor_anzahl",
            help="Mehrere Tafeln nebeneinander: dann lassen sich Teile auch "
                 "zwischen den Tafeln hin- und herziehen.")
        if wahl == "Alle":
            nummern = list(range(1, gesamt + 1))
        else:
            hoechste = gesamt - wahl + 1
            ab = 1 if hoechste <= 1 else s2.slider("ab Tafel", 1, hoechste, 1,
                                                   key="editor_ab")
            nummern = list(range(ab, ab + wahl))

    plaene = [erg.plaene[nummer - 1] for nummer in nummern]
    karte = kontur_karte(erg, st.session_state.konturen)
    vorrat = vorrat_fuer(erg, plaene[0], karte, farben)

    rueckgabe = plan_editor(
        plaene, nummern, saegeblatt=st.session_state.get("schnittfuge", 5.0),
        besaeumung=st.session_state.get("besaeumung", 10.0),
        farben=farben, vorrat=vorrat, raster=5.0,
        key=f"plan_editor_{nummern[0]}_{len(nummern)}")

    # Meldung erst nach dem Neuaufbau zeigen - st.rerun() verwirft sie sonst
    if st.session_state.get("editor_meldung"):
        art, text = st.session_state.pop("editor_meldung")
        (st.warning if art == "warnung" else st.success)(text)

    # Jeden Stand nur einmal anwenden; beim Umschalten der Ansicht liefert die
    # Komponente sonst einen aelteren Stand erneut.
    angewandt = st.session_state.setdefault("editor_staende", set())
    zeitstempel = rueckgabe.get("stand") if rueckgabe else None
    if zeitstempel is not None and zeitstempel not in angewandt:
        angewandt.add(zeitstempel)
        meldungen = uebernehme(erg, nummern, rueckgabe, karte)
        text = ("Plan aktualisiert: "
                + ("; ".join(meldungen) if meldungen else "keine Änderung"))
        if rueckgabe.get("fehlerhaft"):
            st.session_state.editor_meldung = (
                "warnung",
                f"{text}. Achtung: {rueckgabe['fehlerhaft']} Teil(e) liegen falsch "
                f"(Überschneidung oder außerhalb der Tafel) – vor dem Zuschnitt prüfen.")
        else:
            st.session_state.editor_meldung = ("erfolg", text)
        st.rerun()


# ==========================================================
# 6. DIE VIER SCHRITTE
# ==========================================================

schritt_raster, schritt1, schritt2, schritt3, hilfe = st.tabs([
    "① Raster (Fassade)", "② Teile", "③ Material & Nesting",
    "④ Plan & Ausgabe", "❔ Hilfe"])


# ---------------------------------------------------------
# Schritt 1: Plattenraster der Fassade
# ---------------------------------------------------------
with schritt_raster:
    st.markdown('<div class="schritt">Plattenraster der Fassade</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="merk">Raster zeichnen oder aus einem DXF holen, '
                'Felder zuordnen, Fenster wegklicken – das Programm sucht die '
                'Gleichteile und legt die Positionen in die Teileliste. '
                'Wer seine Teile schon hat, überspringt diesen Schritt.</div>',
                unsafe_allow_html=True)

    if not RASTER_OK:
        st.error(f"Rastermodul nicht verfügbar: {RASTER_FEHLER}")
    else:
        hand, aus_dxf = st.columns(2)

        # ---------------- Raster zeichnen ----------------
        with hand:
            st.markdown("##### Raster zeichnen")
            art = st.radio("Eingabeart", ["Einzelmaße", "Gesamtmaß teilen"],
                           horizontal=True, key="raster_art",
                           label_visibility="collapsed")
            if art == "Einzelmaße":
                spalten_text = st.text_input(
                    "Spaltenbreiten (links → rechts)", "3x1250 900",
                    key="raster_spalten",
                    help="Achsmaße, durch Leerzeichen getrennt. "
                         "`3x1250` heißt dreimal 1250 mm.")
                zeilen_text = st.text_input(
                    "Zeilenhöhen (oben → unten)", "4x1100", key="raster_zeilen")
                spalten = raster.masse_lesen(spalten_text)
                zeilen = raster.masse_lesen(zeilen_text)
            else:
                g1, g2 = st.columns(2)
                gesamt_b = g1.number_input("Gesamtbreite (mm)", 100.0, 200000.0,
                                           4700.0, 100.0, key="raster_gb")
                anzahl_s = g2.number_input("Spalten", 1, 200, 4, 1, key="raster_as")
                gesamt_h = g1.number_input("Gesamthöhe (mm)", 100.0, 200000.0,
                                           4400.0, 100.0, key="raster_gh")
                anzahl_z = g2.number_input("Zeilen", 1, 200, 4, 1, key="raster_az")
                spalten = raster.gleiche_teilung(gesamt_b, anzahl_s)
                zeilen = raster.gleiche_teilung(gesamt_h, anzahl_z)

            if spalten and zeilen:
                st.caption(f"{len(spalten)} × {len(zeilen)} = "
                           f"**{len(spalten) * len(zeilen)} Felder**, "
                           f"Gesamtmaß {sum(spalten):.0f} × {sum(zeilen):.0f} mm")
            else:
                st.caption("Noch keine gültigen Maße.")

            if st.button("▦ Raster erzeugen", type="primary", key="btn_raster_hand",
                         disabled=not (spalten and zeilen)):
                st.session_state.raster_felder = raster.felder_aus_raster(spalten, zeilen)
                st.session_state.raster_hinweise = []
                st.session_state.raster_quelle = (
                    f"von Hand, {len(spalten)} × {len(zeilen)} Felder")
                st.session_state.raster_meldung = (
                    "erfolg", f"{len(spalten) * len(zeilen)} Felder erzeugt.")
                st.rerun()

        # ---------------- Raster aus DXF ----------------
        with aus_dxf:
            st.markdown("##### Rasterplan aus DXF")
            if not DXF_OK:
                st.error(f"DXF-Modul nicht verfügbar: {DXF_FEHLER}")
            else:
                plan_datei = st.file_uploader(
                    "Ansicht mit dem Plattenraster", type=["dxf"],
                    key="raster_datei", label_visibility="collapsed",
                    help="Beliebige Ansicht – das Programm liest die Linien "
                         "layerweise ein.")
                if plan_datei is not None and st.button(
                        "📥 Linien einlesen", key="btn_raster_lesen"):
                    try:
                        gelesen = dxf.lade_linien(plan_datei.getvalue(), plan_datei.name)
                        st.session_state.raster_linien = gelesen["linien"]
                        st.session_state.raster_texte = gelesen["texte"]
                        st.session_state.raster_hinweise = gelesen["hinweise"]
                        st.session_state.raster_datei_name = plan_datei.name
                    except Exception as exc:
                        st.session_state.raster_linien = {}
                        st.session_state.raster_hinweise = [
                            f"{plan_datei.name}: Fehler beim Lesen – {exc}"]
                    st.rerun()

                linien = st.session_state.raster_linien
                if linien:
                    # Layer mit Linien, die meisten zuerst. Vorgewaehlt ist alles,
                    # was nicht nach Bemassung, Text oder Schraffur aussieht -
                    # Umriss und Teilung liegen oft auf verschiedenen Layern.
                    reihenfolge = [name for name in
                                   sorted(linien, key=lambda n: -len(linien[n]))
                                   if linien[name]]
                    beschriftet = {name: f"{name}  ({len(linien[name])} Linien)"
                                   for name in reihenfolge}
                    vorgabe = [beschriftet[name] for name in reihenfolge
                               if dxf.klassifiziere_layer(name) != "ignorieren"]
                    st.caption("Layer der Datei "
                               f"**{st.session_state.get('raster_datei_name', '')}** – "
                               "ankreuzen, was zum Raster gehört. **Der Umriss muss "
                               "dabei sein**, auch wenn er auf einem anderen Layer "
                               "liegt:")
                    gewaehlt = st.multiselect(
                        "Rasterlayer", [beschriftet[name] for name in reihenfolge],
                        default=vorgabe or [beschriftet[reihenfolge[0]]],
                        key="raster_layer", label_visibility="collapsed")
                    namen = [eintrag.rsplit("  (", 1)[0] for eintrag in gewaehlt]
                    d1, d2 = st.columns(2)
                    tol_raster = d1.number_input(
                        "Toleranz (mm)", 0.1, 50.0, 2.0, 0.5, key="raster_toleranz",
                        help="Überbrückt kleine Lücken und Ungenauigkeiten "
                             "zwischen den Rasterlinien")
                    min_feld = d2.number_input(
                        "Kleinstes Feld (m²)", 0.001, 10.0, 0.01, 0.01,
                        format="%.3f", key="raster_minflaeche",
                        help="Kleinere Flächen gelten als Hilfslinien")
                    fenster_auto = st.checkbox(
                        "Fenster und Türen aus den Texten erkennen", True,
                        key="raster_fenster_auto",
                        help="Felder mit Texten wie „Fenster“ oder „Aussparung“ "
                             "werden gleich als Öffnung markiert")

                    if st.button("▦ Raster erkennen", type="primary",
                                 key="btn_raster_dxf", disabled=not namen):
                        zuege = [zug for name in namen for zug in linien.get(name, [])]
                        felder_neu, hinweise_neu = raster.felder_aus_linien(
                            zuege, toleranz=tol_raster,
                            min_flaeche=min_feld * 1e6)
                        treffer = 0
                        if fenster_auto and felder_neu:
                            treffer = raster.oeffnungen_aus_texten(
                                felder_neu, st.session_state.raster_texte)
                        st.session_state.raster_felder = felder_neu
                        st.session_state.raster_hinweise = hinweise_neu
                        st.session_state.raster_quelle = (
                            f"DXF {st.session_state.get('raster_datei_name', '')}, "
                            f"Layer {', '.join(namen)}")
                        if felder_neu:
                            text = f"{len(felder_neu)} Felder erkannt."
                            if treffer:
                                text += f" {treffer} davon als Öffnung markiert."
                            st.session_state.raster_meldung = ("erfolg", text)
                        else:
                            st.session_state.raster_meldung = (
                                "warnung", "Keine Felder erkannt – anderen Layer "
                                "wählen oder die Toleranz erhöhen.")
                        st.rerun()

        if st.session_state.get("raster_meldung"):
            art_meldung, text = st.session_state.pop("raster_meldung")
            (st.warning if art_meldung == "warnung" else st.success)(text)
        for hinweis in st.session_state.raster_hinweise:
            st.warning(hinweis)

        # ---------------- Felder zuordnen und rechnen ----------------
        felder = st.session_state.raster_felder
        if felder:
            st.markdown("---")
            st.markdown("##### Fugen und Plattentypen")
            p1, p2, p3 = st.columns(3)
            fuge = p1.number_input(
                "Fugenbreite (mm)", 0.0, 500.0, 15.0, 1.0, key="raster_fuge",
                help="Die Rasterlinie ist die Fugenmitte: je Seite wird die "
                     "halbe Fuge abgezogen.")
            zugabe = p2.number_input(
                "Zugabe je Seite (mm)", 0.0, 500.0, 0.0, 1.0, key="raster_zugabe",
                help="Aufkantung oder Falz der Kassette – wird auf das "
                     "Sichtmaß aufgeschlagen (Abwicklung).")
            rand_fuge = p3.checkbox(
                "Fuge auch am Rand", False, key="raster_randfuge",
                help="Aus: am Außenrand geht die Platte bis zur Rasterlinie. "
                     "Ein: auch dort die halbe Fuge abziehen.")

            t1, t2 = st.columns([3, 2])
            typ_text = t1.text_input(
                "Plattentypen (durch Komma getrennt)",
                st.session_state.get("raster_typ_text", "Standard"),
                key="raster_typ_text",
                help="Je Typ eine Farbe und ein eigenes Material, z. B. "
                     "`Anthrazit, Silber`. Gleich große Platten verschiedener "
                     "Typen bleiben getrennte Positionen.")
            modus = t2.selectbox(
                "Gleichteile erkennen", list(raster.MODI),
                format_func=lambda m: raster.MODI[m], key="raster_modus",
                help="Gedreht und gespiegelt nur, wenn Sichtseite und "
                     "Walzrichtung es zulassen.")
            typen = raster_editor.typenliste(
                [t.strip() for t in typ_text.split(",") if t.strip()])
            # Wer die Typen umbenennt, soll nicht mit Feldern dastehen, die auf
            # einen Typ zeigen, den es nicht mehr gibt: die bekommen den ersten.
            bekannt = {t["name"] for t in typen}
            for feld_eintrag in felder:
                if feld_eintrag.typ not in bekannt:
                    feld_eintrag.typ = typen[0]["name"]

            st.markdown("##### Felder zuordnen")
            st.caption("Pinsel wählen, dann Felder anklicken oder mit gedrückter "
                       "Maustaste darüberziehen. Erst **Zuordnung übernehmen** "
                       "schreibt sie in das Raster.")
            rueckgabe = raster_editor.raster_editor(
                felder, typen, key=f"raster_editor_{len(felder)}")

            angewandt = st.session_state.setdefault("raster_staende", set())
            stempel = rueckgabe.get("stand") if rueckgabe else None
            if stempel is not None and stempel not in angewandt:
                angewandt.add(stempel)
                zahlen = raster_editor.uebernehme_zuordnung(felder, rueckgabe)
                st.session_state.raster_meldung = (
                    "erfolg",
                    f"Zuordnung übernommen: {zahlen['geaendert']} Feld(er) geändert, "
                    f"{zahlen['oeffnungen']} Öffnung(en).")
                st.rerun()

            # ---------------- Rechnen ----------------
            platten, platten_hinweise = raster.platten_aus_feldern(
                felder, fuge=fuge, zugabe=zugabe, rand_fuge=rand_fuge)
            positionen = raster.gleichteile(platten, modus=modus)
            for hinweis in platten_hinweise[:5]:
                st.warning(hinweis)

            zahlen = raster.kennzahlen(felder, platten, positionen)
            k = st.columns(5)
            k[0].metric("Felder", zahlen["felder"])
            k[1].metric("Öffnungen", zahlen["oeffnungen"])
            k[2].metric("Platten", zahlen["platten"])
            k[3].metric("Positionen", zahlen["positionen"],
                        help="Verschiedene Plattenformen – das ist das Ergebnis "
                             "der Gleichteilsuche")
            k[4].metric("Plattenfläche", f"{zahlen['flaeche']:.2f} m²")

            nummern = raster.position_je_feld(positionen)
            farben_pos = farbkarte([p.nummer for p in positionen])
            ansicht, liste = st.columns([3, 2])
            with ansicht:
                st.markdown(svg_fassade(
                    felder, nummern, farben_pos,
                    titel=f"Fassadenansicht – {st.session_state.raster_quelle}"),
                    unsafe_allow_html=True)
            with liste:
                st.markdown("**Positionen**")
                st.dataframe(pd.DataFrame(raster.positionsliste(positionen)),
                             hide_index=True, **BREITE)

            with st.expander("Feldliste (welches Feld bekommt welche Position?)"):
                st.dataframe(pd.DataFrame(raster.feldliste(positionen)),
                             hide_index=True, **BREITE)

            # ---------------- Uebergabe und Ausgabe ----------------
            st.markdown("##### Positionen ins Nesting übernehmen")
            vorhandene = {p.typ for p in positionen}
            material = dict(st.session_state.get("raster_material", {}))
            spalten_material = st.columns(max(len(vorhandene), 1))
            for i, typ in enumerate(sorted(vorhandene)):
                material[typ] = spalten_material[i].text_input(
                    f"Material für {typ}", material.get(typ, ""),
                    key=f"raster_mat_{typ}", placeholder="z. B. Alucobond 4 mm")
            st.session_state.raster_material = material

            u1, u2 = st.columns([3, 2])
            ersetzen = u2.checkbox("Teileliste vorher leeren", True,
                                   key="raster_ersetzen")
            if u1.button("➡️ Positionen in die Teileliste", type="primary",
                         key="btn_raster_uebernehmen", disabled=not positionen):
                zeilen, konturen = [], dict(st.session_state.konturen)
                for position in positionen:
                    kontur = [[(float(x), float(y))
                               for x, y in raster.in_nullpunkt(position.polygon)]]
                    konturen[position.nummer] = {"kontur": kontur, "stichlinien": []}
                    zeilen.append({
                        "Bezeichnung": position.nummer,
                        "Breite (mm)": round(position.breite, 1),
                        "Höhe (mm)": round(position.hoehe, 1),
                        "Anzahl": position.anzahl,
                        "Material": material.get(position.typ, ""),
                        "Drehbar": modus != "gleich",
                        "Kontur": "ja"})
                st.session_state.konturen = konturen
                alt = pd.DataFrame(columns=SPALTEN_TEILE) if ersetzen else stand("teile")
                setze_tabelle("teile", pd.concat(
                    [alt, pd.DataFrame(zeilen, columns=SPALTEN_TEILE)],
                    ignore_index=True))
                # Die Meldung steht beim Knopf, nicht oben am Seitenanfang:
                # nach dem Neuaufbau bleibt die Seite stehen, wo sie war.
                st.session_state.raster_uebergabe = (
                    f"{len(zeilen)} Positionen mit {sum(p.anzahl for p in positionen)} "
                    f"Platten in die Teileliste übernommen – weiter mit Schritt "
                    f"② Teile bzw. ③ Material & Nesting.")
                st.rerun()

            if st.session_state.get("raster_uebergabe"):
                st.success(st.session_state.pop("raster_uebergabe"))

            a1, a2, a3 = st.columns(3)
            daten_excel = excel_bytes({
                "Positionen": pd.DataFrame(raster.positionsliste(positionen)),
                "Felder": pd.DataFrame(raster.feldliste(positionen))})
            if daten_excel:
                a1.download_button("📊 Positionsliste als Excel", daten_excel,
                                   dateiname("Positionsliste", "xlsx"),
                                   "application/vnd.openxmlformats-officedocument."
                                   "spreadsheetml.sheet", **BREITE)
            if DXF_OK:
                a2.download_button(
                    "📐 Montageplan als DXF",
                    raster.montageplan_als_dxf(felder, positionen).encode("utf-8"),
                    dateiname("Montageplan", "dxf"), "image/vnd.dxf", **BREITE)
                a3.download_button(
                    "📐 Positionen als DXF",
                    raster.positionen_als_dxf(positionen).encode("utf-8"),
                    dateiname("Positionen", "dxf"), "image/vnd.dxf", **BREITE)

            if st.button("Raster verwerfen", key="btn_raster_weg"):
                st.session_state.raster_felder = []
                st.session_state.raster_quelle = ""
                st.rerun()


# ---------------------------------------------------------
# Schritt 2: Teile
# ---------------------------------------------------------
with schritt1:
    st.markdown('<div class="schritt">Woraus soll geschnitten werden?</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="merk">DXF-Dateien einlesen oder Teile von Hand '
                'erfassen. Beides landet in derselben Teileliste.</div>',
                unsafe_allow_html=True)

    quelle_dxf, quelle_hand = st.columns([3, 2])

    # ---------------- DXF ----------------
    with quelle_dxf:
        st.markdown("##### DXF einlesen (HiCAD / Alucobond)")
        if not DXF_OK:
            st.error(f"DXF-Modul nicht verfügbar: {DXF_FEHLER}")
        else:
            dateien = st.file_uploader("DXF-Dateien auswählen", type=["dxf"],
                                       accept_multiple_files=True,
                                       label_visibility="collapsed")
            with st.expander("Einleseoptionen"):
                e1, e2, e3 = st.columns(3)
                toleranz = e1.number_input(
                    "Konturtoleranz (mm)", 0.001, 10.0, 0.1, 0.05,
                    help="Größte Lücke, die noch als geschlossene Kontur gilt")
                min_flaeche = e2.number_input(
                    "Kleinste Teilefläche (mm²)", 1.0, 100000.0, 500.0, 100.0,
                    help="Kleinere Konturen werden ignoriert")
                buendeln = e3.checkbox("Gleiche Teile bündeln", True)
                if st.session_state.dxf_layer:
                    st.markdown("**Layer-Zuordnung**")
                    st.caption("kontur = wird geschnitten · stich = Fräs-/Falzlinie · "
                               "ignorieren = Bemaßung, Text, Hilfslinien")
                    override = {}
                    for name, (klasse, anzahl) in sorted(st.session_state.dxf_layer.items()):
                        override[name] = st.selectbox(
                            f"{name}  ({anzahl} Elemente)",
                            ["kontur", "stich", "ignorieren"],
                            index=["kontur", "stich", "ignorieren"].index(klasse),
                            key=f"layer_{name}")
                    st.session_state.layer_override = override

            if st.button("📥 DXF einlesen", type="primary", key="btn_dxf",
                         disabled=not dateien):
                gelesen, hinweise, layer = [], [], {}
                for datei in dateien:
                    try:
                        ergebnis = dxf.lade_dxf(
                            datei.getvalue(), datei.name, toleranz=toleranz,
                            min_flaeche=min_flaeche, zusammenfassen=buendeln,
                            layer_override=st.session_state.get("layer_override"))
                        gelesen.extend(ergebnis.teile)
                        layer.update(ergebnis.layer)
                        hinweise.extend(f"{datei.name}: {h}" for h in ergebnis.hinweise)
                    except Exception as exc:
                        hinweise.append(f"{datei.name}: Fehler beim Lesen – {exc}")
                st.session_state.dxf_teile = gelesen
                st.session_state.dxf_hinweise = hinweise
                st.session_state.dxf_layer = layer
                st.rerun()

    # ---------------- Von Hand ----------------
    with quelle_hand:
        st.markdown("##### Von Hand erfassen")
        eingabe = st.text_area(
            "Eine Zeile je Position",
            placeholder="1000 x 500 x 3\n800;600;2;Wange;Blech 2 mm",
            height=120, label_visibility="collapsed",
            help="Format: `Breite x Höhe x Anzahl` oder "
                 "`Breite;Höhe;Anzahl;Bezeichnung;Material`")
        if st.button("Zur Teileliste hinzufügen", key="btn_schnell"):
            neue = parse_2d_eingabe(eingabe)
            if neue:
                zusatz = pd.DataFrame([{
                    "Bezeichnung": t.bezeichnung, "Breite (mm)": t.breite,
                    "Höhe (mm)": t.hoehe, "Anzahl": t.anzahl,
                    "Material": t.material, "Drehbar": True, "Kontur": "—"}
                    for t in neue], columns=SPALTEN_TEILE)
                setze_tabelle("teile", pd.concat([stand("teile"), zusatz],
                                                 ignore_index=True))
                st.rerun()
            else:
                st.warning("Keine gültige Zeile erkannt.")

    for hinweis in st.session_state.dxf_hinweise:
        st.warning(hinweis)

    # ---------------- Erkannte DXF-Teile ----------------
    erkannt = st.session_state.dxf_teile
    if erkannt:
        st.markdown("---")
        gesamt = sum(t.anzahl for t in erkannt)
        st.success(f"{len(erkannt)} Positionen mit insgesamt {gesamt} Teilen erkannt.")
        farben_dxf = farbkarte([t.bezeichnung for t in erkannt])
        spalten = st.columns(min(len(erkannt), 5))
        for i, teil in enumerate(erkannt):
            with spalten[i % len(spalten)]:
                st.markdown(svg_teil(teil, 170, farben_dxf), unsafe_allow_html=True)
                st.caption(f"**{teil.bezeichnung}**  \n"
                           f"{teil.breite:.0f} × {teil.hoehe:.0f} mm · {teil.anzahl}×  \n"
                           f"{len(teil.stichlinien)} Fräs-/Falzlinien")

        u1, u2, u3 = st.columns([2, 2, 3])
        material_dxf = u1.text_input("Material für diese Teile", "",
                                     placeholder="z. B. Alucobond 4 mm")
        drehbar_dxf = u2.checkbox("Drehbar", value=False,
                                  help="Bei Walz- oder Dekorrichtung ausgeschaltet lassen")
        if u3.button("➡️ Alle erkannten Teile in die Teileliste", type="primary"):
            zeilen, konturen = [], dict(st.session_state.konturen)
            for teil in erkannt:
                konturen[teil.bezeichnung] = {"kontur": teil.kontur,
                                              "stichlinien": teil.stichlinien}
                zeilen.append({
                    "Bezeichnung": teil.bezeichnung,
                    "Breite (mm)": float(teil.breite), "Höhe (mm)": float(teil.hoehe),
                    "Anzahl": int(teil.anzahl), "Material": material_dxf,
                    "Drehbar": bool(drehbar_dxf), "Kontur": "ja"})
            st.session_state.konturen = konturen
            setze_tabelle("teile", pd.concat(
                [stand("teile"), pd.DataFrame(zeilen, columns=SPALTEN_TEILE)],
                ignore_index=True))
            st.session_state.dxf_teile = []
            st.rerun()

        if DXF_OK:
            st.download_button(
                "📐 Erkannte Teile als DXF (zur Kontrolle)",
                dxf.teile_als_dxf(erkannt).encode("utf-8"),
                dateiname("DXF_Teilepruefung", "dxf"), "image/vnd.dxf")

    # ---------------- Teileliste ----------------
    st.markdown("---")
    st.markdown("##### Teileliste")

    st.caption("Sammelaktionen – wirken auf **alle** Zeilen der Teileliste:")
    s1, s2 = st.columns([4, 2])
    sammel_material = s1.text_input("Material für alle Teile", "",
                                    placeholder="z. B. Alucobond 4 mm",
                                    key="sammel_material", label_visibility="collapsed")
    if s2.button("Material auf alle anwenden", key="btn_material_alle", **BREITE):
        df = stand("teile").copy()
        df["Material"] = sammel_material
        setze_tabelle("teile", df)
        st.rerun()

    s3, s4, s5, s6 = st.columns(4)
    if s3.button("Alle drehbar", key="btn_drehbar_an", **BREITE):
        df = stand("teile").copy()
        df["Drehbar"] = True
        setze_tabelle("teile", df)
        st.rerun()
    if s4.button("Keines drehbar", key="btn_drehbar_aus", **BREITE,
                 help="Bei Walz- oder Dekorrichtung, z. B. Alucobond metallic"):
        df = stand("teile").copy()
        df["Drehbar"] = False
        setze_tabelle("teile", df)
        st.rerun()
    if s5.button("Stückzahlen verdoppeln", key="btn_doppelt", **BREITE):
        df = stand("teile").copy()
        df["Anzahl"] = (df["Anzahl"].fillna(0) * 2).astype(int)
        setze_tabelle("teile", df)
        st.rerun()
    if s6.button("Liste leeren", key="btn_leeren", **BREITE):
        setze_tabelle("teile", pd.DataFrame(columns=SPALTEN_TEILE))
        st.session_state.konturen = {}
        st.rerun()

    tabelle("teile", num_rows="dynamic", hide_index=True, **BREITE,
            column_config={
                "Bezeichnung": st.column_config.TextColumn(width="medium"),
                "Breite (mm)": st.column_config.NumberColumn(min_value=0.0, step=1.0,
                                                             format="%.1f"),
                "Höhe (mm)": st.column_config.NumberColumn(min_value=0.0, step=1.0,
                                                           format="%.1f"),
                "Anzahl": st.column_config.NumberColumn(min_value=0, step=1),
                "Drehbar": st.column_config.CheckboxColumn(
                    help="Aus bei Walz- oder Dekorrichtung"),
                "Kontur": st.column_config.TextColumn(
                    disabled=True, width="small",
                    help="ja = echte Kontur aus dem DXF vorhanden"),
            })
    st.caption("Zeile anhängen: in die letzte, leere Zeile schreiben. "
               "Zeile löschen: links markieren und Entf drücken.")


# ---------------------------------------------------------
# Schritt 3: Material und Nesting
# ---------------------------------------------------------
with schritt2:
    st.markdown('<div class="schritt">Worauf wird geschnitten?</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="merk">Tafelformate und Schnittparameter festlegen, '
                'dann schachteln.</div>', unsafe_allow_html=True)

    links, rechts = st.columns([5, 3])

    with links:
        st.markdown("##### Tafeln / Rohmaterial")
        v1, v2 = st.columns([4, 2])
        vorlage = v1.selectbox("Format übernehmen", ["–"] + list(TAFEL_VORLAGEN))
        v2.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        if v2.button("Hinzufügen", key="btn_tafel", **BREITE) and vorlage != "–":
            b, h = TAFEL_VORLAGEN[vorlage]
            zusatz = pd.DataFrame([{
                "Bezeichnung": vorlage, "Breite (mm)": float(b), "Höhe (mm)": float(h),
                "Anzahl": float("nan"), "Material": "", "Preis (€)": 0.0}],
                columns=SPALTEN_TAFELN)
            setze_tabelle("tafeln", pd.concat([stand("tafeln"), zusatz],
                                              ignore_index=True))
            st.rerun()
        m1, m2 = st.columns([4, 2])
        sammel_tafelmaterial = m1.text_input(
            "Material für alle Tafeln", "", key="sammel_tafelmaterial",
            placeholder="Material für alle Tafeln", label_visibility="collapsed")
        if m2.button("Auf alle anwenden", key="btn_tafelmaterial", **BREITE):
            df = stand("tafeln").copy()
            df["Material"] = sammel_tafelmaterial
            setze_tabelle("tafeln", df)
            st.rerun()

        tabelle("tafeln", num_rows="dynamic", hide_index=True, **BREITE,
                column_config={
                    "Breite (mm)": st.column_config.NumberColumn(min_value=0.0,
                                                                 step=10.0, format="%.0f"),
                    "Höhe (mm)": st.column_config.NumberColumn(min_value=0.0,
                                                               step=10.0, format="%.0f"),
                    "Anzahl": st.column_config.NumberColumn(
                        min_value=0, step=1, help="leer = unbegrenzt verfügbar"),
                    "Preis (€)": st.column_config.NumberColumn(min_value=0.0, step=1.0,
                                                               format="%.2f"),
                })
        st.caption("**Anzahl** leer lassen = unbegrenzt verfügbar. "
                   "**Material** leer lassen = passt für alle Teile.")

    with rechts:
        st.markdown("##### Schnittparameter")
        st.session_state.schnittfuge = st.number_input(
            "Schnittfuge / Fräserdurchmesser (mm)", 0.0, 50.0,
            st.session_state.get("schnittfuge", 5.0), 0.5,
            help="Mindestabstand zwischen zwei Teilen")
        st.session_state.besaeumung = st.number_input(
            "Besäumung Tafelrand (mm)", 0.0, 200.0,
            st.session_state.get("besaeumung", 10.0), 5.0)

        schnittarten = ["Guillotine – durchgehende Schnitte",
                        "Frei – Laser, Plasma, CNC-Fräse"]
        if KONTUR_OK:
            schnittarten.append("Kontur – echtes Nesting")
        modus_text = st.radio("Schnittart", schnittarten,
                              help="Siehe Reiter Hilfe – dort stehen die Unterschiede "
                                   "mit Bildern.")
        modus = ("guillotine" if modus_text.startswith("Guillotine")
                 else "frei" if modus_text.startswith("Frei") else "kontur")

        raster, winkel, nachverdichten, versuche = 5.0, STANDARD_WINKEL if KONTUR_OK else (), True, 3
        if modus == "kontur":
            with st.expander("Einstellungen Konturnesting"):
                raster = st.select_slider(
                    "Rasterweite (mm)", options=[1.0, 2.0, 3.0, 5.0, 8.0, 10.0],
                    value=5.0,
                    help="Kleiner = dichter geschachtelt, aber deutlich langsamer")
                drehung = st.radio("Erlaubte Drehung",
                                   ["90°-Schritte", "auch 45°-Schritte", "keine Drehung"])
                winkel = {"90°-Schritte": STANDARD_WINKEL,
                          "auch 45°-Schritte": FEINE_WINKEL,
                          "keine Drehung": (0.0,)}[drehung]
                nachverdichten = st.checkbox("Ausschnitte und Taschen mitnutzen", True)
                versuche = st.slider("Suchtiefe", 1, 5, 3)

    st.markdown("")
    if st.session_state.get("nesting_meldung"):
        st.success(st.session_state.pop("nesting_meldung"))
    if st.button("🔧 Nesting starten", type="primary", key="btn_nesting", **BREITE):
        teile = teile_aus_tabelle(stand("teile"))
        tafeln = tafeln_aus_tabelle(stand("tafeln"))
        if not teile:
            st.warning("Keine Teile erfasst – bitte zuerst Schritt ② Teile.")
        elif not tafeln:
            st.warning("Keine Tafel erfasst.")
        else:
            with st.spinner("Schachtele ..."):
                if modus == "kontur":
                    st.session_state.ergebnis = optimize_2d_kontur(
                        teile, tafeln, saegeblatt=st.session_state.schnittfuge,
                        besaeumung=st.session_state.besaeumung, raster=raster,
                        winkel=winkel, versuche=versuche,
                        nachverdichten=nachverdichten)
                else:
                    st.session_state.ergebnis = optimize_2d(
                        teile, tafeln, saegeblatt=st.session_state.schnittfuge,
                        besaeumung=st.session_state.besaeumung, modus=modus)
            st.session_state.modus = modus
            # Neu aufbauen, damit der Stand in der Seitenleiste stimmt
            st.session_state.nesting_meldung = (
                f"Fertig: {st.session_state.ergebnis.anzahl_tafeln} Tafeln, "
                f"{st.session_state.ergebnis.ausnutzung_echt_prozent:.1f} % Ausnutzung "
                f"– weiter in Schritt ④ Plan & Ausgabe.")
            st.rerun()


# ---------------------------------------------------------
# Schritt 4: Plan und Ausgabe
# ---------------------------------------------------------
with schritt3:
    erg = st.session_state.ergebnis
    if erg is None:
        st.markdown('<div class="schritt">Noch kein Plan gerechnet</div>',
                    unsafe_allow_html=True)
        st.info("Erst Teile erfassen (Schritt ②), dann Tafeln wählen und "
                "**Nesting starten** (Schritt ③).")
        st.markdown(hilfe_bilder.bild_ablauf(), unsafe_allow_html=True)
    else:
        st.markdown('<div class="schritt">Schachtelplan</div>', unsafe_allow_html=True)
        zeige_kennzahlen(erg)

        for hinweis in getattr(erg, "hinweise", []):
            st.info(hinweis)
        if erg.fehlende:
            zeilen = ", ".join(f"{a}× {b} ({x:.0f}×{y:.0f} mm)"
                               for b, x, y, a in erg.fehlende)
            st.error(f"Nicht eingeplant: {zeilen}")
            st.caption("Mögliche Ursachen: Teil größer als jede Tafel (auch gedreht), "
                       "Tafelbestand aufgebraucht, oder das **Material** des Teils "
                       "kommt bei den Tafeln nicht vor.")

        farben = farbkarte(namen_aus_plan(erg))
        plan_tab, editor_tab, ausgabe_tab = st.tabs(
            ["Pläne", "✏️ Von Hand anpassen", "⬇️ Ausgabe"])

        with plan_tab:
            zeige_plaene(erg, farben)
            with st.expander("Teileliste (Tabelle)"):
                st.dataframe(teileliste_2d(erg), **BREITE, hide_index=True)
            with st.expander("Tafelliste"):
                st.dataframe(tafelliste_2d(erg), **BREITE, hide_index=True)

        with editor_tab:
            if EDITOR_OK and erg.plaene:
                zeige_editor(erg, farben)
            else:
                st.info("Editor nicht verfügbar.")

        with ausgabe_tab:
            knoepfe = st.columns(4)
            if PDF_OK:
                try:
                    knoepfe[0].download_button(
                        "📄 Schachtelplan als PDF",
                        pdf_2d(erg, st.session_state.projekt,
                               {"saegeblatt": st.session_state.get("schnittfuge", 5.0),
                                "besaeumung": st.session_state.get("besaeumung", 10.0),
                                "modus": st.session_state.get("modus", "guillotine")}),
                        dateiname("Schachtelplan", "pdf"), "application/pdf", **BREITE)
                except Exception as exc:
                    knoepfe[0].error(f"PDF-Fehler: {exc}")
            else:
                knoepfe[0].info("PDF nicht verfügbar (fpdf fehlt).")

            mappe = excel_bytes({"Teileliste": teileliste_2d(erg),
                                 "Tafeln": tafelliste_2d(erg)})
            if mappe:
                knoepfe[1].download_button(
                    "📊 Listen als Excel", mappe, dateiname("Schachtelplan", "xlsx"),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    **BREITE)
            else:
                knoepfe[1].info("Excel nicht verfügbar (openpyxl fehlt).")

            knoepfe[2].download_button(
                "📋 Teileliste als CSV",
                teileliste_2d(erg).to_csv(index=False, sep=";").encode("utf-8-sig"),
                dateiname("Teileliste", "csv"), "text/csv", **BREITE)

            if DXF_OK:
                knoepfe[3].download_button(
                    "📐 Schachtelplan als DXF",
                    dxf.plan_als_dxf(erg).encode("utf-8"),
                    dateiname("Schachtelplan", "dxf"), "image/vnd.dxf", **BREITE,
                    help="Layer TAFEL / KONTUR / FRAESLINIE / BESCHRIFTUNG")
            st.caption("Alle Ausgaben verwenden den aktuellen Plan – auch die von "
                       "Hand angepasste Fassung.")


# ---------------------------------------------------------
# Hilfe
# ---------------------------------------------------------
with hilfe:
    st.markdown('<div class="schritt">So arbeitet das Programm</div>',
                unsafe_allow_html=True)
    st.markdown(hilfe_bilder.bild_ablauf(), unsafe_allow_html=True)

    st.markdown("#### Schritt ① – Raster (Fassade)")
    st.markdown("""
Dieser Schritt ist **freiwillig**: Wer die Teile schon hat, fängt bei Schritt ②
an. Für eine Fassade spart er dagegen das halbe Aufmaß – aus dem Plattenraster
entstehen die Platten von selbst.

**Woher kommt das Raster?**

* **Von Hand gezeichnet** – Spaltenbreiten und Zeilenhöhen eintippen.
  `3x1250 900` heißt: dreimal 1250 mm, dann 900 mm. Oder das Gesamtmaß
  angeben und in gleiche Felder teilen lassen.
* **Aus einem DXF** – eine beliebige Ansicht einlesen. Das Programm liest die
  Linien **layerweise**; vorgewählt ist alles außer Bemaßung, Text und
  Schraffur. **Der Umriss muss angekreuzt sein** – er liegt oft auf einem
  anderen Layer als die Teilung, und ohne ihn ist kein Feld geschlossen.

Die Linien werden an ihren Kreuzungspunkten zerlegt; jede rundum geschlossene
Masche wird ein Feld. Deshalb gehen auch Felder über mehrere Rasterzellen
(fehlende Trennlinie), L-Formen, **schiefwinklige und perspektivisch
gezeichnete Ansichten**, Giebeldreiecke und beliebige Vielecke. Flächen, deren
Rand nicht vollständig gezeichnet ist, entstehen gar nicht erst, und
überstehende Linienenden stören nicht. Die **Toleranz** überbrückt Lücken und
Ungenauigkeiten (typisch 1–3 mm).

Felder heißen `Z2/S3` (Zeile/Spalte), solange das Raster rechtwinklig ist –
sonst `F01`, `F02` … von links oben nach rechts unten. Bei schiefen Feldern
ist das angezeigte Maß das **Hüllmaß**; geschnitten wird die echte Form.
    """)
    st.markdown(hilfe_bilder.bild_raster(), unsafe_allow_html=True)
    st.markdown("""
**Fuge und Zugabe.** Die Rasterlinie gilt als **Fugenmitte**: zwischen zwei
Platten wird die ganze Fugenbreite abgezogen, je Seite die Hälfte. Am
Außenrand geht die Platte bis zur Linie – das lässt sich mit *Fuge auch am
Rand* umstellen. Zur Fensteröffnung hin bleibt die Fuge erhalten. Die
**Zugabe** schlägt danach wieder auf, z. B. die Aufkantung einer Kassette:
Sichtmaß + 2 × Zugabe = Zuschnitt.

**Felder zuordnen.** Jedes Feld bekommt mit dem Pinsel einen Plattentyp
(= Farbe und Material) oder wird als **Öffnung** weggeklickt. Anklicken oder
mit gedrückter Maustaste über mehrere Felder ziehen; die Zifferntasten wählen
den Pinsel, Strg+Z nimmt zurück.
    """)
    st.markdown(hilfe_bilder.bild_felder(), unsafe_allow_html=True)
    st.markdown("""
**Gleichteilsuche.** Zum Schluss sucht das Programm die deckungsgleichen
Platten und fasst sie zu Positionen zusammen (P01, P02 …):
    """)
    st.markdown(hilfe_bilder.bild_gleichteile(), unsafe_allow_html=True)
    st.markdown("""
| Einstellung | Wann |
|---|---|
| nur gleich ausgerichtet | Regelfall bei Walz- oder Dekorrichtung |
| auch gedreht | wenn die Platte um 90/180/270° gedreht eingebaut werden darf |
| auch gespiegelt | nur bei beidseitig gleichem Material – die Sichtseite dreht sich |

Platten verschiedener Typen werden nie zusammengefasst, auch wenn sie gleich
groß sind. Zum Schluss gehen die Positionen mit Stückzahl und echter Kontur in
die **Teileliste** – dort läuft alles weiter wie gewohnt. Zusätzlich gibt es
die Positionsliste als Excel und den **Montageplan als DXF**: er zeigt, welche
Position in welches Feld gehört.
    """)

    st.markdown("#### Schritt ② – Teile")
    st.markdown("""
Die Teile kommen entweder aus **DXF-Dateien** (Abwicklungen aus HiCAD, z. B.
Alucobond-Kassetten) oder werden **von Hand** erfasst. Beim DXF-Import erkennt
das Programm die Außenkontur, die Ausschnitte und die Fräs- oder Falzlinien
anhand der Layernamen:
    """)
    st.markdown(hilfe_bilder.bild_dxf_layer(), unsafe_allow_html=True)
    st.markdown("""
| Layername enthält | Bedeutung |
|---|---|
| Kontur, Außen, Innen, Ausschnitt, Schnitt, Cut | wird geschnitten |
| Fräs, Falz, Biege, Nut, Kant, Knick, Fold, Bend | Fräs-/Falzlinie, kein Schnitt |
| Bemaßung, Maß, Text, Beschriftung, Achse, Defpoints | wird ignoriert |

Unbekannte Layer gelten im Zweifel als Kontur. Jede Zuordnung lässt sich unter
*Einleseoptionen* von Hand ändern. Meldet das Programm offene Konturzüge, hilft
eine größere **Konturtoleranz** (typisch 0,1 bis 1 mm).

**Sammelaktionen:** Material, Drehbar und das Leeren der Liste wirken auf
*alle* Teile auf einmal – das spart das Tippen in jeder Zeile. Teile mit
Walz- oder Dekorrichtung (Alucobond metallic) bekommen *Keines drehbar*.
    """)

    st.markdown("#### Schritt ③ – Material & Nesting")
    st.markdown(hilfe_bilder.bild_schnittfuge(), unsafe_allow_html=True)
    st.markdown("Die drei Schnittarten unterscheiden sich so:")
    st.markdown(hilfe_bilder.bild_schnittarten(), unsafe_allow_html=True)
    st.markdown("""
* **Guillotine** – jeder Schnitt geht durch die ganze Tafel. Passt zu
  Tafelschere, Plattensäge und Kreissäge.
* **Frei** – die Teile werden als Rechtecke dicht gepackt. Nur sinnvoll, wenn
  die Maschine Konturen fährt (Laser, Plasma, CNC-Fräse).
* **Kontur** – echtes Nesting mit der tatsächlichen Teileform. Lohnt sich bei
  L-Formen, Dreiecken, Trapezen und Teilen mit großen Ausschnitten; bei reinen
  Rechtecken bringt es nichts. Das Programm rechnet dann zusätzlich das
  einfache Verfahren mit und nimmt automatisch den besseren Plan.
    """)

    st.markdown("#### Schritt ④ – Plan & Ausgabe")
    st.markdown(hilfe_bilder.bild_editor(), unsafe_allow_html=True)
    st.markdown("""
Unter *Von Hand anpassen* lässt sich jedes Teil mit der Maus verschieben,
drehen, ablegen und wieder einsetzen – auch von einer Tafel auf die andere.
Wählbar ist, wie viele Tafeln gleichzeitig zu sehen sind.

| Bedienung | Wirkung |
|---|---|
| Teil anklicken und ziehen | verschieben, auch auf eine andere Tafel |
| **R** oder die Drehknöpfe | 90° drehen (Winkelfeld für beliebige Grad) |
| Pfeiltasten | 1 mm schieben, mit Umschalt 10 mm |
| **Entf** oder *Ablegen* | Teil neben die Tafel legen |
| Knopf in der Ablage | Teil auf die aktive Tafel einsetzen |
| **Strg+Z** / *Verwerfen* | Schritt zurück bzw. auf den gerechneten Plan |

Erst **Änderungen übernehmen** schreibt den Plan um. Danach nutzen PDF, Excel
und DXF-Export den angepassten Plan.

#### Grenzen
* Geschachtelt wird in der Ebene; Biegeteile werden als Abwicklung behandelt.
* Gedreht wird in 90°- oder 45°-Schritten, nicht in beliebigen Winkeln.
* Das Konturnesting rechnet im Raster – die Teile stehen gelegentlich ein paar
  Millimeter weiter auseinander als nötig, nie enger als die Schnittfuge.
* Der ausgegebene Plan ersetzt die Kontrolle in der Werkstatt nicht.
    """)
    st.markdown("---")
    st.caption("Meingassner Metalltechnik · Nesting · alle Maße in Millimeter")
