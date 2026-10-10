"""
app_nesting.py - Verschnittoptimierung (Nesting) fuer Meingassner Metalltechnik

Start:  streamlit run app_nesting.py

Aufbau in drei Schritten:

  1  Teile      DXF einlesen (HiCAD / Alucobond) oder von Hand erfassen
  2  Material   Tafeln und Schnittparameter, dann schachteln
  3  Plan       Ergebnis ansehen, von Hand nachbessern, ausgeben
"""

import datetime
import inspect
import io
import os

import pandas as pd
import streamlit as st

from nesting import Tafel, Zuschnitt2D, optimize_2d, parse_2d_eingabe
from zeichnung import farbkarte, legende, namen_aus_plan, svg_tafel, svg_teil
import hilfe_bilder

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
# 6. DIE DREI SCHRITTE
# ==========================================================

schritt1, schritt2, schritt3, hilfe = st.tabs([
    "① Teile", "② Material & Nesting", "③ Plan & Ausgabe", "❔ Hilfe"])


# ---------------------------------------------------------
# Schritt 1: Teile
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
# Schritt 2: Material und Nesting
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
            st.warning("Keine Teile erfasst – bitte zuerst Schritt 1.")
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
                f"– weiter in Schritt ③ Plan & Ausgabe.")
            st.rerun()


# ---------------------------------------------------------
# Schritt 3: Plan und Ausgabe
# ---------------------------------------------------------
with schritt3:
    erg = st.session_state.ergebnis
    if erg is None:
        st.markdown('<div class="schritt">Noch kein Plan gerechnet</div>',
                    unsafe_allow_html=True)
        st.info("Erst Teile erfassen (Schritt ①), dann Tafeln wählen und "
                "**Nesting starten** (Schritt ②).")
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

    st.markdown("#### Schritt ① – Teile")
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

    st.markdown("#### Schritt ② – Material & Nesting")
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

    st.markdown("#### Schritt ③ – Plan & Ausgabe")
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
