"""
app_nesting.py - Verschnittoptimierung (Nesting) fuer Meingassner Metalltechnik

Start:  streamlit run app_nesting.py

  1D   Stangen- und Profilzuschnitt (Rohre, Flachstahl, Handlauf, ...)
  2D   Blech- und Plattenzuschnitt (Tafeln, Alucobond, Glas, ...)
  DXF  Import von Abwicklungen aus HiCAD / Alucobond inkl. Fraeslinien
"""

import datetime
import inspect
import io
import os

import pandas as pd
import streamlit as st

from nesting import (
    Stange, Tafel, Teil, Zuschnitt2D,
    optimize_1d, optimize_2d, parse_1d_eingabe, parse_2d_eingabe,
)

try:
    from kontur_nesting import FEINE_WINKEL, STANDARD_WINKEL, optimize_2d_kontur
    KONTUR_OK = True
except Exception as exc:                      # numpy fehlt
    KONTUR_OK = False
    KONTUR_FEHLER = str(exc)
from zeichnung import farbkarte, legende, namen_aus_plan, svg_stange, svg_tafel, svg_teil

try:
    import dxf_import as dxf
    DXF_OK = True
except Exception as exc:                      # pragma: no cover
    DXF_OK = False
    DXF_FEHLER = str(exc)

try:
    from pdf_export import pdf_1d, pdf_2d
    PDF_OK = True
except Exception as exc:                      # pragma: no cover
    PDF_OK = False
    PDF_FEHLER = str(exc)


# ==========================================================
# 0. STREAMLIT-KOMPATIBILITAET
# ==========================================================
# Neuere Streamlit-Versionen ersetzen use_container_width durch width="stretch".
try:
    _NEUE_BREITE = "width" in inspect.signature(st.dataframe).parameters
except (TypeError, ValueError):     # pragma: no cover
    _NEUE_BREITE = False

BREITE = {"width": "stretch"} if _NEUE_BREITE else {"use_container_width": True}


# ==========================================================
# 1. SEITE & STIL
# ==========================================================

LOGO = next((d for d in ("Meingassner Metalltechnik 2023.png", "logo_firma.png", "logo.png")
             if os.path.exists(d)), None)

st.set_page_config(page_title="Nesting - Verschnittoptimierung",
                   page_icon=LOGO or "🪚", layout="wide")

st.markdown("""
    <style>
    .main-header { font-size: 2.0rem; font-weight: 700; color: #1E3A8A; margin-bottom: 4px; }
    .sub { color:#6B7280; font-size:0.95rem; margin-bottom:14px; }
    .karte { background:#F9FAFB; padding:14px 16px; border-radius:10px;
             border:1px solid #E5E7EB; margin-bottom:14px; }
    div.stButton > button { min-height: 46px; font-size: 16px !important; border-radius: 8px; }
    div[data-testid="stMetricValue"] { font-size: 1.5rem; }
    </style>
""", unsafe_allow_html=True)


# ==========================================================
# 2. VORGABEN & SESSION
# ==========================================================

LAGERLAENGEN = [6000, 6500, 3000, 2000, 12000]

TAFEL_VORLAGEN = {
    "Alucobond 1250 x 3200": (1250, 3200),
    "Alucobond 1500 x 3200": (1500, 3200),
    "Alucobond 1500 x 4000": (1500, 4000),
    "Alucobond 2000 x 3200": (2000, 3200),
    "Blech 1000 x 2000": (1000, 2000),
    "Blech 1250 x 2500": (1250, 2500),
    "Blech 1500 x 3000": (1500, 3000),
    "Blech 2000 x 1000": (2000, 1000),
    "Lochblech 1000 x 2000": (1000, 2000),
}

BEISPIEL_1D = pd.DataFrame([
    {"Bezeichnung": "Pfosten", "Länge (mm)": 1050.0, "Anzahl": 9, "Profil": "Rohr 40x40x2"},
    {"Bezeichnung": "Handlauf", "Länge (mm)": 1980.0, "Anzahl": 6, "Profil": "Rohr 42,4x2"},
    {"Bezeichnung": "Füllstab", "Länge (mm)": 940.0, "Anzahl": 24, "Profil": "Rundstahl 12"},
])

BEISPIEL_LAGER = pd.DataFrame([
    {"Bezeichnung": "Rohr 40x40x2 - 6 m", "Länge (mm)": 6000.0, "Anzahl": float("nan"),
     "Profil": "Rohr 40x40x2", "Preis (€)": 48.0, "Reststück": False},
    {"Bezeichnung": "Rohr 42,4x2 - 6 m", "Länge (mm)": 6000.0, "Anzahl": float("nan"),
     "Profil": "Rohr 42,4x2", "Preis (€)": 39.0, "Reststück": False},
    {"Bezeichnung": "Rundstahl 12 - 6 m", "Länge (mm)": 6000.0, "Anzahl": float("nan"),
     "Profil": "Rundstahl 12", "Preis (€)": 12.5, "Reststück": False},
])

BEISPIEL_2D = pd.DataFrame([
    {"Bezeichnung": "Wange", "Breite (mm)": 1200.0, "Höhe (mm)": 300.0, "Anzahl": 4,
     "Material": "Blech 3 mm", "Drehbar": True},
    {"Bezeichnung": "Deckblech", "Breite (mm)": 800.0, "Höhe (mm)": 400.0, "Anzahl": 6,
     "Material": "Blech 3 mm", "Drehbar": True},
])

BEISPIEL_TAFELN = pd.DataFrame([
    {"Bezeichnung": "Blech 1250 x 2500", "Breite (mm)": 1250.0, "Höhe (mm)": 2500.0,
     "Anzahl": float("nan"), "Material": "Blech 3 mm", "Preis (€)": 145.0},
])


def init():
    vorgaben = {
        "teile_1d": BEISPIEL_1D.copy(),
        "lager_1d": BEISPIEL_LAGER.copy(),
        "teile_2d": BEISPIEL_2D.copy(),
        "tafeln_2d": BEISPIEL_TAFELN.copy(),
        "erg_1d": None,
        "erg_2d": None,
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
    """Excel-Mappe erzeugen; None, wenn openpyxl fehlt."""
    try:
        puffer = io.BytesIO()
        with pd.ExcelWriter(puffer, engine="openpyxl") as writer:
            for name, df in blaetter.items():
                df.to_excel(writer, sheet_name=name[:31], index=False)
        return puffer.getvalue()
    except ImportError:
        return None


def dateiname(basis: str, endung: str) -> str:
    projekt = "".join(c for c in st.session_state.projekt if c.isalnum() or c in " -_").strip()
    teil = f"_{projekt.replace(' ', '_')}" if projekt else ""
    return f"{basis}{teil}_{datetime.date.today():%Y%m%d}.{endung}"


# ==========================================================
# 3. KOPF & SEITENLEISTE
# ==========================================================

kopf_links, kopf_rechts = st.columns([1, 6])
with kopf_links:
    if LOGO:
        st.image(LOGO, width=140)
with kopf_rechts:
    st.markdown('<div class="main-header">Nesting &ndash; Verschnittoptimierung</div>',
                unsafe_allow_html=True)
    st.markdown('<div class="sub">Stangen- und Blechzuschnitt mit minimalem Verschnitt &ndash; '
                'inklusive DXF-Import aus HiCAD / Alucobond</div>', unsafe_allow_html=True)

with st.sidebar:
    if LOGO:
        st.image(LOGO, **BREITE)
    st.session_state.projekt = st.text_input("Projekt / Auftrag", st.session_state.projekt,
                                             placeholder="z. B. BV Musterhaus, Geländer OG")

    st.markdown("### Schnittparameter 1D")
    saegeblatt = st.number_input("Sägeblattstärke (mm)", 0.0, 20.0, 3.0, 0.5,
                                 help="Materialverlust je Schnitt")
    anschnitt = st.number_input("Anschnitt am Stangenanfang (mm)", 0.0, 500.0, 10.0, 5.0,
                                help="Besäumung, z. B. wegen Stauchung oder Rost")
    endschnitt = st.number_input("Reserve am Stangenende (mm)", 0.0, 500.0, 10.0, 5.0)
    min_rest = st.number_input("Reststück verwertbar ab (mm)", 0.0, 6000.0, 400.0, 50.0,
                               help="Kürzere Reste gelten als Verschnitt")
    reste_zuerst = st.checkbox("Reststücke aus dem Lager zuerst verbrauchen", True)

    st.markdown("### Schnittparameter 2D")
    schnittfuge = st.number_input("Schnittfuge / Fräserdurchmesser (mm)", 0.0, 50.0, 5.0, 0.5,
                                  help="Abstand zwischen zwei Teilen")
    besaeumung = st.number_input("Besäumung Tafelrand (mm)", 0.0, 200.0, 10.0, 5.0)
    schnittarten = ["Guillotine (durchgehende Schnitte)",
                    "Frei (Laser / Plasma / CNC-Fräse)"]
    if KONTUR_OK:
        schnittarten.append("Kontur (echtes Nesting)")
    modus_text = st.radio(
        "Schnittart", schnittarten,
        help="Guillotine für Tafelschere und Plattensäge, frei für Konturschneiden, "
             "Kontur für ineinandergreifende Teile (Ausklinkungen, L-Formen, "
             "Dreiecke, Ausschnitte)")
    if modus_text.startswith("Guillotine"):
        modus = "guillotine"
    elif modus_text.startswith("Frei"):
        modus = "frei"
    else:
        modus = "kontur"

    raster = 5.0
    winkel = STANDARD_WINKEL if KONTUR_OK else ()
    nachverdichten = True
    versuche = 3
    if modus == "kontur":
        raster = st.select_slider(
            "Rasterweite (mm)", options=[1.0, 2.0, 3.0, 5.0, 8.0, 10.0], value=5.0,
            help="Genauigkeit der Konturrechnung. Kleiner = dichter geschachtelt, "
                 "aber deutlich langsamer.")
        drehung = st.radio("Erlaubte Drehung",
                           ["90°-Schritte", "auch 45°-Schritte", "keine Drehung"],
                           help="45°-Schritte lohnen bei schrägen Teilen, "
                                "brauchen aber die doppelte Rechenzeit.")
        winkel = {"90°-Schritte": STANDARD_WINKEL,
                  "auch 45°-Schritte": FEINE_WINKEL,
                  "keine Drehung": (0.0,)}[drehung]
        nachverdichten = st.checkbox(
            "Ausschnitte und Taschen mitnutzen", True,
            help="Sucht für die übrigen Teile auf der ganzen Tafel nach Platz, "
                 "also auch innerhalb von Fensterausschnitten.")
        versuche = st.slider("Suchtiefe", 1, 5, 3,
                             help="Anzahl durchprobierter Schachtelstrategien. "
                                  "Mehr = etwas besser, aber langsamer.")

    st.markdown("---")
    st.caption("Alle Maße in Millimeter. Preise netto.")

parameter_1d = {"saegeblatt": saegeblatt, "anschnitt": anschnitt, "endschnitt": endschnitt,
                "min_reststueck": min_rest, "reste_zuerst": reste_zuerst}
parameter_2d = {"saegeblatt": schnittfuge, "besaeumung": besaeumung, "modus": modus}
if modus == "kontur":
    parameter_2d["raster"] = raster


# ==========================================================
# 4. ERGEBNISDARSTELLUNG
# ==========================================================


def zeige_ergebnis_1d(erg):
    k = st.columns(5)
    k[0].metric("Stangen", erg.anzahl_stangen)
    k[1].metric("Material", f"{erg.gesamt_material / 1000:.2f} m")
    k[2].metric("Ausnutzung", f"{erg.ausnutzung_prozent:.1f} %")
    k[3].metric("Verschnitt", f"{erg.verschnitt_prozent:.1f} %",
                f"{erg.verschnitt / 1000:.2f} m", delta_color="inverse")
    k[4].metric("Materialkosten", f"{erg.gesamt_kosten:,.2f} €".replace(",", "."))

    if erg.verwertbare_reste > 0:
        st.success(f"Verwertbare Reststücke: {erg.verwertbare_reste / 1000:.2f} m "
                   f"(ab {min_rest:.0f} mm) &ndash; zurück ins Lager.")
    if erg.fehlende:
        zeilen = ", ".join(f"{a}× {b} ({l:.0f} mm)" for b, l, a in erg.fehlende)
        st.error(f"Nicht eingeplant: {zeilen}")
        st.caption("Mögliche Ursachen: Teil länger als jede Lagerstange, Lagerbestand "
                   "aufgebraucht, oder das **Profil** des Teils kommt im Lager nicht vor "
                   "(Schreibweise vergleichen oder Profilfeld leer lassen).")

    farben = farbkarte(namen_aus_plan(erg))
    st.markdown(legende(farben.keys(), farben), unsafe_allow_html=True)

    aktuelles_profil = None
    for nr, plan in enumerate(erg.plaene, start=1):
        if plan.profil != aktuelles_profil:
            aktuelles_profil = plan.profil
            st.markdown(f"**Profil: {aktuelles_profil or 'ohne Zuordnung'}**")
        st.markdown(svg_stange(plan, nr, farben=farben), unsafe_allow_html=True)

    with st.expander("Schnittliste (Tabelle)"):
        st.dataframe(schnittliste_1d(erg), **BREITE, hide_index=True)


def schnittliste_1d(erg) -> pd.DataFrame:
    zeilen = []
    for nr, plan in enumerate(erg.plaene, start=1):
        for p in plan.platzierungen:
            zeilen.append({
                "Stange": nr,
                "Profil": plan.profil,
                "Lagerstange": plan.stange,
                "Lagerlänge (mm)": round(plan.stangen_laenge),
                "Teil": p.bezeichnung,
                "Länge (mm)": round(p.laenge, 1),
                "Position ab (mm)": round(p.start, 1),
                "Rest (mm)": round(plan.rest, 1),
                "Rest verwertbar": "ja" if plan.rest_verwertbar else "nein",
            })
    return pd.DataFrame(zeilen)


def stangenliste_1d(erg) -> pd.DataFrame:
    zeilen = []
    for nr, plan in enumerate(erg.plaene, start=1):
        zeilen.append({
            "Stange": nr, "Profil": plan.profil, "Lagerstange": plan.stange,
            "Lagerlänge (mm)": round(plan.stangen_laenge),
            "Teile": plan.anzahl_teile, "Belegt (mm)": round(plan.belegt, 1),
            "Rest (mm)": round(plan.rest, 1),
            "Rest verwertbar": "ja" if plan.rest_verwertbar else "nein",
            "Ausnutzung (%)": round(plan.ausnutzung * 100, 1),
            "Preis (€)": round(plan.preis, 2),
        })
    return pd.DataFrame(zeilen)


def bestellliste_1d(erg) -> pd.DataFrame:
    zusammen = {}
    for plan in erg.plaene:
        schluessel = (plan.profil, plan.stange, plan.stangen_laenge, plan.preis)
        zusammen[schluessel] = zusammen.get(schluessel, 0) + 1
    zeilen = [{"Profil": p, "Lagerstange": s, "Länge (mm)": round(l), "Anzahl": n,
               "Einzelpreis (€)": round(pr, 2), "Summe (€)": round(pr * n, 2)}
              for (p, s, l, pr), n in zusammen.items()]
    return pd.DataFrame(zeilen)


def zeige_ergebnis_2d(erg):
    # Bei echten Konturen weicht die Teilefläche von der Bounding-Box ab
    mit_kontur = abs(erg.echte_flaeche - erg.genutzte_flaeche) > 1.0
    k = st.columns(6 if mit_kontur else 5)
    k[0].metric("Tafeln", erg.anzahl_tafeln)
    k[1].metric("Tafelfläche", f"{erg.gesamt_flaeche / 1e6:.2f} m²")
    if mit_kontur:
        k[2].metric("Ausnutzung Kontur", f"{erg.ausnutzung_echt_prozent:.1f} %",
                    help="Echte Teilefläche bezogen auf die Tafelfläche")
        k[3].metric("Ausnutzung Außenmaß", f"{erg.ausnutzung_prozent:.1f} %",
                    help="Bounding-Box der Teile bezogen auf die Tafelfläche")
        k[4].metric("Abfall", f"{100 - erg.ausnutzung_echt_prozent:.1f} %",
                    f"{(erg.gesamt_flaeche - erg.echte_flaeche) / 1e6:.2f} m²",
                    delta_color="inverse")
        k[5].metric("Materialkosten", f"{erg.gesamt_kosten:,.2f} €".replace(",", "."))
    else:
        k[2].metric("Ausnutzung", f"{erg.ausnutzung_prozent:.1f} %")
        k[3].metric("Verschnitt", f"{erg.verschnitt_prozent:.1f} %",
                    f"{(erg.gesamt_flaeche - erg.genutzte_flaeche) / 1e6:.2f} m²",
                    delta_color="inverse")
        k[4].metric("Materialkosten", f"{erg.gesamt_kosten:,.2f} €".replace(",", "."))

    for hinweis in getattr(erg, "hinweise", []):
        st.info(hinweis)

    if erg.fehlende:
        zeilen = ", ".join(f"{a}× {b} ({x:.0f}×{y:.0f} mm)" for b, x, y, a in erg.fehlende)
        st.error(f"Nicht eingeplant: {zeilen}")
        st.caption("Mögliche Ursachen: Teil größer als jede Tafel (auch gedreht), "
                   "Tafelbestand aufgebraucht, oder das **Material** des Teils kommt bei "
                   "den Tafeln nicht vor (Schreibweise vergleichen oder Materialfeld "
                   "leer lassen).")

    farben = farbkarte(namen_aus_plan(erg))
    st.markdown(legende(farben.keys(), farben), unsafe_allow_html=True)
    st.caption("Rot gestrichelt = Fräs-/Falzlinie aus dem DXF (kein Trennschnitt).")

    spalten = st.columns(2)
    for i, plan in enumerate(erg.plaene):
        with spalten[i % 2]:
            st.markdown(svg_tafel(plan, i + 1, farben=farben), unsafe_allow_html=True)

    with st.expander("Teileliste (Tabelle)"):
        st.dataframe(teileliste_2d(erg), **BREITE, hide_index=True)


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
    zeilen = []
    for nr, plan in enumerate(erg.plaene, start=1):
        zeilen.append({
            "Tafel": nr, "Material": plan.material, "Tafeltyp": plan.tafel,
            "Breite (mm)": round(plan.breite), "Höhe (mm)": round(plan.hoehe),
            "Teile": len(plan.platzierungen),
            "Ausnutzung (%)": round(plan.ausnutzung * 100, 1),
            "Preis (€)": round(plan.preis, 2),
        })
    return pd.DataFrame(zeilen)


# ==========================================================
# 5. REGISTERKARTEN
# ==========================================================

tab_1d, tab_2d, tab_dxf, tab_hilfe = st.tabs([
    "📏 Stangen & Profile (1D)",
    "▦ Bleche & Platten (2D)",
    "📐 DXF-Import (HiCAD / Alucobond)",
    "❔ Hilfe",
])


# ---------------------------------------------------------
# 5.1 1D
# ---------------------------------------------------------
with tab_1d:
    links, rechts = st.columns([3, 2])

    with links:
        st.markdown("#### Zuschnittliste")
        st.session_state.teile_1d = st.data_editor(
            st.session_state.teile_1d, num_rows="dynamic", **BREITE,
            key="editor_teile_1d",
            column_config={
                "Bezeichnung": st.column_config.TextColumn(width="medium"),
                "Länge (mm)": st.column_config.NumberColumn(min_value=0.0, step=1.0,
                                                            format="%.1f"),
                "Anzahl": st.column_config.NumberColumn(min_value=0, step=1),
                "Profil": st.column_config.TextColumn(
                    help="Teile mit demselben Profil werden gemeinsam geschachtelt"),
            })

        with st.expander("Schnellerfassung (eine Zeile je Position)"):
            eingabe = st.text_area(
                "Format: `Länge x Anzahl Bezeichnung` oder "
                "`Länge;Anzahl;Bezeichnung;Profil`",
                placeholder="1050 x 9 Pfosten\n1980;6;Handlauf;Rohr 42,4x2",
                height=110, key="schnell_1d")
            if st.button("Zur Liste hinzufügen", key="btn_schnell_1d"):
                neue = parse_1d_eingabe(eingabe)
                if neue:
                    zusatz = pd.DataFrame([{"Bezeichnung": t.bezeichnung,
                                            "Länge (mm)": t.laenge, "Anzahl": t.anzahl,
                                            "Profil": t.profil} for t in neue])
                    st.session_state.teile_1d = pd.concat(
                        [st.session_state.teile_1d, zusatz], ignore_index=True)
                    st.rerun()
                else:
                    st.warning("Keine gültige Zeile erkannt.")

    with rechts:
        st.markdown("#### Lager / Rohmaterial")
        st.session_state.lager_1d = st.data_editor(
            st.session_state.lager_1d, num_rows="dynamic", **BREITE,
            key="editor_lager_1d",
            column_config={
                "Länge (mm)": st.column_config.NumberColumn(min_value=0.0, step=100.0,
                                                            format="%.0f"),
                "Anzahl": st.column_config.NumberColumn(
                    min_value=0, step=1, help="leer = unbegrenzt verfügbar"),
                "Preis (€)": st.column_config.NumberColumn(min_value=0.0, step=1.0,
                                                           format="%.2f"),
                "Reststück": st.column_config.CheckboxColumn(
                    help="Reste aus dem Lager werden bevorzugt verbraucht"),
            })
        st.caption("Spalte **Anzahl** leer lassen = unbegrenzt verfügbar. "
                   "Profil leer lassen = passt für alle Teile.")

    if st.button("🔧 Zuschnitt optimieren", type="primary", key="btn_opt_1d"):
        teile = [Teil(zahl(r["Länge (mm)"]), int(zahl(r["Anzahl"], 0)),
                      str(r["Bezeichnung"] or "Teil"), str(r.get("Profil") or ""))
                 for _, r in st.session_state.teile_1d.iterrows()
                 if zahl(r["Länge (mm)"]) > 0 and zahl(r["Anzahl"], 0) > 0]
        lager = [Stange(zahl(r["Länge (mm)"]), ganzzahl_oder_none(r.get("Anzahl")),
                        str(r["Bezeichnung"] or "Stange"), str(r.get("Profil") or ""),
                        zahl(r.get("Preis (€)")), bool(r.get("Reststück")))
                 for _, r in st.session_state.lager_1d.iterrows()
                 if zahl(r["Länge (mm)"]) > 0]
        if not teile:
            st.warning("Bitte zuerst Teile erfassen.")
        elif not lager:
            st.warning("Bitte mindestens eine Lagerlänge erfassen.")
        else:
            with st.spinner("Optimiere ..."):
                st.session_state.erg_1d = optimize_1d(
                    teile, lager, saegeblatt=saegeblatt, anschnitt=anschnitt,
                    endschnitt=endschnitt, min_reststueck=min_rest,
                    reste_zuerst=reste_zuerst)

    if st.session_state.erg_1d is not None:
        erg = st.session_state.erg_1d
        st.markdown("---")
        zeige_ergebnis_1d(erg)

        st.markdown("#### Ausgabe")
        knoepfe = st.columns(3)
        if PDF_OK:
            try:
                knoepfe[0].download_button(
                    "📄 Schnittplan als PDF",
                    pdf_1d(erg, st.session_state.projekt, parameter_1d),
                    dateiname("Zuschnittplan", "pdf"), "application/pdf",
                    **BREITE)
            except Exception as exc:
                knoepfe[0].error(f"PDF-Fehler: {exc}")
        else:
            knoepfe[0].info("PDF nicht verfügbar (fpdf fehlt).")

        mappe = excel_bytes({"Schnittliste": schnittliste_1d(erg),
                             "Stangen": stangenliste_1d(erg),
                             "Bestellliste": bestellliste_1d(erg)})
        if mappe:
            knoepfe[1].download_button(
                "📊 Listen als Excel", mappe, dateiname("Zuschnittliste", "xlsx"),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                **BREITE)
        else:
            knoepfe[1].info("Excel nicht verfügbar (openpyxl fehlt).")

        knoepfe[2].download_button(
            "📋 Schnittliste als CSV",
            schnittliste_1d(erg).to_csv(index=False, sep=";").encode("utf-8-sig"),
            dateiname("Schnittliste", "csv"), "text/csv", **BREITE)

        with st.expander("Bestellliste"):
            st.dataframe(bestellliste_1d(erg), **BREITE, hide_index=True)


# ---------------------------------------------------------
# 5.2 2D
# ---------------------------------------------------------
with tab_2d:
    links, rechts = st.columns([3, 2])

    with links:
        st.markdown("#### Teileliste")
        st.session_state.teile_2d = st.data_editor(
            st.session_state.teile_2d, num_rows="dynamic", **BREITE,
            key="editor_teile_2d",
            column_config={
                "Breite (mm)": st.column_config.NumberColumn(min_value=0.0, step=1.0,
                                                             format="%.1f"),
                "Höhe (mm)": st.column_config.NumberColumn(min_value=0.0, step=1.0,
                                                           format="%.1f"),
                "Anzahl": st.column_config.NumberColumn(min_value=0, step=1),
                "Drehbar": st.column_config.CheckboxColumn(
                    help="Aus bei Walz-/Dekorrichtung (z. B. Alucobond metallic)"),
            })
        if modus == "kontur":
            st.caption("Schnittart **Kontur**: aus dem DXF übernommene Teile werden mit "
                       "ihrer echten Form geschachtelt und greifen ineinander. "
                       "Teile ohne DXF-Kontur gelten als Rechteck.")
        else:
            st.caption("Aus dem DXF-Import übernommene Teile behalten ihre echte Kontur, "
                       "geschachtelt wird bei dieser Schnittart aber über die Außenmaße. "
                       "Für echtes Konturnesting die Schnittart *Kontur* wählen.")

        with st.expander("Schnellerfassung (eine Zeile je Position)"):
            eingabe2 = st.text_area(
                "Format: `Breite x Höhe x Anzahl` oder "
                "`Breite;Höhe;Anzahl;Bezeichnung;Material`",
                placeholder="1000 x 500 x 3\n800;600;2;Wange;Blech 2 mm",
                height=110, key="schnell_2d")
            if st.button("Zur Liste hinzufügen", key="btn_schnell_2d"):
                neue = parse_2d_eingabe(eingabe2)
                if neue:
                    zusatz = pd.DataFrame([{"Bezeichnung": t.bezeichnung,
                                            "Breite (mm)": t.breite, "Höhe (mm)": t.hoehe,
                                            "Anzahl": t.anzahl, "Material": t.material,
                                            "Drehbar": True} for t in neue])
                    st.session_state.teile_2d = pd.concat(
                        [st.session_state.teile_2d, zusatz], ignore_index=True)
                    st.rerun()
                else:
                    st.warning("Keine gültige Zeile erkannt.")

    with rechts:
        st.markdown("#### Tafeln / Rohmaterial")
        vorlage = st.selectbox("Tafelformat übernehmen", ["-"] + list(TAFEL_VORLAGEN.keys()))
        if st.button("Tafel hinzufügen", key="btn_tafel") and vorlage != "-":
            b, h = TAFEL_VORLAGEN[vorlage]
            zusatz = pd.DataFrame([{"Bezeichnung": vorlage, "Breite (mm)": float(b),
                                    "Höhe (mm)": float(h), "Anzahl": float("nan"),
                                    "Material": "", "Preis (€)": 0.0}])
            st.session_state.tafeln_2d = pd.concat(
                [st.session_state.tafeln_2d, zusatz], ignore_index=True)
            st.rerun()

        st.session_state.tafeln_2d = st.data_editor(
            st.session_state.tafeln_2d, num_rows="dynamic", **BREITE,
            key="editor_tafeln_2d",
            column_config={
                "Breite (mm)": st.column_config.NumberColumn(min_value=0.0, step=10.0,
                                                             format="%.0f"),
                "Höhe (mm)": st.column_config.NumberColumn(min_value=0.0, step=10.0,
                                                           format="%.0f"),
                "Anzahl": st.column_config.NumberColumn(
                    min_value=0, step=1, help="leer = unbegrenzt verfügbar"),
                "Preis (€)": st.column_config.NumberColumn(min_value=0.0, step=1.0,
                                                           format="%.2f"),
            })

    if st.button("🔧 Tafeln schachteln", type="primary", key="btn_opt_2d"):
        teile = []
        for _, r in st.session_state.teile_2d.iterrows():
            b, h, n = zahl(r["Breite (mm)"]), zahl(r["Höhe (mm)"]), int(zahl(r["Anzahl"], 0))
            if b <= 0 or h <= 0 or n <= 0:
                continue
            bezeichnung = str(r["Bezeichnung"] or "Teil")
            gespeichert = st.session_state.get("konturen", {}).get(bezeichnung, {})
            teile.append(Zuschnitt2D(
                b, h, n, bezeichnung, str(r.get("Material") or ""),
                bool(r.get("Drehbar", True)),
                kontur=gespeichert.get("kontur", []),
                stichlinien=gespeichert.get("stichlinien", [])))
        tafeln = [Tafel(zahl(r["Breite (mm)"]), zahl(r["Höhe (mm)"]),
                        ganzzahl_oder_none(r.get("Anzahl")),
                        str(r["Bezeichnung"] or "Tafel"), str(r.get("Material") or ""),
                        zahl(r.get("Preis (€)")))
                  for _, r in st.session_state.tafeln_2d.iterrows()
                  if zahl(r["Breite (mm)"]) > 0 and zahl(r["Höhe (mm)"]) > 0]
        if not teile:
            st.warning("Bitte zuerst Teile erfassen.")
        elif not tafeln:
            st.warning("Bitte mindestens eine Tafel erfassen.")
        else:
            with st.spinner("Schachtele ..."):
                if modus == "kontur":
                    st.session_state.erg_2d = optimize_2d_kontur(
                        teile, tafeln, saegeblatt=schnittfuge, besaeumung=besaeumung,
                        raster=raster, winkel=winkel, versuche=versuche,
                        nachverdichten=nachverdichten)
                else:
                    st.session_state.erg_2d = optimize_2d(
                        teile, tafeln, saegeblatt=schnittfuge, besaeumung=besaeumung,
                        modus=modus)

    if st.session_state.erg_2d is not None:
        erg = st.session_state.erg_2d
        st.markdown("---")
        zeige_ergebnis_2d(erg)

        st.markdown("#### Ausgabe")
        knoepfe = st.columns(4)
        if PDF_OK:
            try:
                knoepfe[0].download_button(
                    "📄 Schachtelplan als PDF",
                    pdf_2d(erg, st.session_state.projekt, parameter_2d),
                    dateiname("Schachtelplan", "pdf"), "application/pdf",
                    **BREITE)
            except Exception as exc:
                knoepfe[0].error(f"PDF-Fehler: {exc}")
        else:
            knoepfe[0].info("PDF nicht verfügbar (fpdf fehlt).")

        mappe = excel_bytes({"Teileliste": teileliste_2d(erg), "Tafeln": tafelliste_2d(erg)})
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
                dateiname("Schachtelplan", "dxf"), "image/vnd.dxf",
                **BREITE,
                help="Tafeln nebeneinander, Layer TAFEL / KONTUR / FRAESLINIE / BESCHRIFTUNG")


# ---------------------------------------------------------
# 5.3 DXF-Import
# ---------------------------------------------------------
with tab_dxf:
    if not DXF_OK:
        st.error(f"DXF-Modul nicht verfügbar: {DXF_FEHLER}")
    else:
        st.markdown("#### DXF-Dateien einlesen")
        st.caption("Abwicklungen aus HiCAD (z. B. Alucobond-Kassetten) oder beliebige "
                   "2D-Konturen. Mehrere Dateien gleichzeitig möglich.")

        dateien = st.file_uploader("DXF-Dateien auswählen", type=["dxf"],
                                   accept_multiple_files=True)

        e1, e2, e3 = st.columns(3)
        toleranz = e1.number_input("Konturtoleranz (mm)", 0.001, 10.0, 0.1, 0.05,
                                   help="Maximale Lücke, die noch als geschlossene "
                                        "Kontur gilt")
        min_flaeche = e2.number_input("Kleinste Teilefläche (mm²)", 1.0, 100000.0, 500.0,
                                      100.0, help="Kleinere Konturen werden ignoriert")
        buendeln = e3.checkbox("Gleiche Teile bündeln", True)

        if st.session_state.dxf_layer:
            with st.expander("Layer-Zuordnung anpassen"):
                st.caption("kontur = wird geschnitten &middot; stich = Fräs-/Falzlinie "
                           "&middot; ignorieren = Bemaßung, Text, Hilfslinien")
                override = {}
                for name, (klasse, anzahl) in sorted(st.session_state.dxf_layer.items()):
                    wahl = st.selectbox(f"{name}  ({anzahl} Elemente)",
                                        ["kontur", "stich", "ignorieren"],
                                        index=["kontur", "stich", "ignorieren"].index(klasse),
                                        key=f"layer_{name}")
                    override[name] = wahl
                st.session_state.layer_override = override

        if st.button("📥 DXF einlesen", type="primary", key="btn_dxf") and dateien:
            teile, hinweise, layer = [], [], {}
            for datei in dateien:
                try:
                    ergebnis = dxf.lade_dxf(
                        datei.getvalue(), datei.name, toleranz=toleranz,
                        min_flaeche=min_flaeche, zusammenfassen=buendeln,
                        layer_override=st.session_state.get("layer_override"))
                    teile.extend(ergebnis.teile)
                    layer.update(ergebnis.layer)
                    hinweise.extend(f"{datei.name}: {h}" for h in ergebnis.hinweise)
                except Exception as exc:
                    hinweise.append(f"{datei.name}: Fehler beim Lesen &ndash; {exc}")
            st.session_state.dxf_teile = teile
            st.session_state.dxf_hinweise = hinweise
            st.session_state.dxf_layer = layer
            st.rerun()

        for hinweis in st.session_state.dxf_hinweise:
            st.warning(hinweis)

        teile = st.session_state.dxf_teile
        if teile:
            gesamt = sum(t.anzahl for t in teile)
            st.success(f"{len(teile)} Positionen mit insgesamt {gesamt} Teilen erkannt.")

            st.markdown("#### Erkannte Teile")
            farben_dxf = farbkarte([t.bezeichnung for t in teile])
            spalten = st.columns(4)
            for i, teil in enumerate(teile):
                with spalten[i % 4]:
                    st.markdown(svg_teil(teil, 200, farben_dxf), unsafe_allow_html=True)
                    st.caption(f"**{teil.bezeichnung}**  \n"
                               f"{teil.breite:.0f} × {teil.hoehe:.0f} mm &middot; "
                               f"{teil.anzahl}×  \n"
                               f"Fläche {teil.flaeche / 1e6:.3f} m² "
                               f"({teil.ausnutzung_bbox * 100:.0f} % der Außenmaße)  \n"
                               f"{len(teil.stichlinien)} Fräs-/Falzlinien")

            st.markdown("#### Übernahme ins Nesting")
            uebersicht = pd.DataFrame([{
                "Übernehmen": True,
                "Bezeichnung": t.bezeichnung,
                "Breite (mm)": round(t.breite, 1),
                "Höhe (mm)": round(t.hoehe, 1),
                "Anzahl": t.anzahl,
                "Material": "",
                "Drehbar": False,
            } for t in teile])
            bearbeitet = st.data_editor(
                uebersicht, **BREITE, hide_index=True, key="editor_dxf",
                column_config={
                    "Übernehmen": st.column_config.CheckboxColumn(),
                    "Drehbar": st.column_config.CheckboxColumn(
                        help="Bei Alucobond mit Laufrichtung ausgeschaltet lassen"),
                    "Breite (mm)": st.column_config.NumberColumn(disabled=True,
                                                                 format="%.1f"),
                    "Höhe (mm)": st.column_config.NumberColumn(disabled=True,
                                                               format="%.1f"),
                })

            aktion = st.columns(2)
            if aktion[0].button("➡️ Teile ins 2D-Nesting übernehmen", type="primary",
                                key="btn_uebernahme"):
                neue_zeilen, konturen = [], st.session_state.get("konturen", {})
                for teil, (_, zeile) in zip(teile, bearbeitet.iterrows()):
                    if not zeile["Übernehmen"]:
                        continue
                    bezeichnung = str(zeile["Bezeichnung"])
                    konturen[bezeichnung] = {"kontur": teil.kontur,
                                             "stichlinien": teil.stichlinien}
                    neue_zeilen.append({
                        "Bezeichnung": bezeichnung,
                        "Breite (mm)": float(teil.breite),
                        "Höhe (mm)": float(teil.hoehe),
                        "Anzahl": int(zeile["Anzahl"]),
                        "Material": str(zeile["Material"] or ""),
                        "Drehbar": bool(zeile["Drehbar"]),
                    })
                if neue_zeilen:
                    st.session_state.konturen = konturen
                    st.session_state.teile_2d = pd.concat(
                        [st.session_state.teile_2d, pd.DataFrame(neue_zeilen)],
                        ignore_index=True)
                    st.success(f"{len(neue_zeilen)} Positionen übernommen &ndash; "
                               f"weiter im Reiter „Bleche & Platten (2D)“.")
                else:
                    st.warning("Keine Position ausgewählt.")

            aktion[1].download_button(
                "📐 Erkannte Teile als DXF (Kontrolle)",
                dxf.teile_als_dxf(teile).encode("utf-8"),
                dateiname("DXF_Teilepruefung", "dxf"), "image/vnd.dxf",
                **BREITE)

        if st.session_state.dxf_layer:
            with st.expander("Gefundene Layer"):
                st.dataframe(pd.DataFrame(
                    [{"Layer": name, "Zuordnung": klasse, "Elemente": anzahl}
                     for name, (klasse, anzahl) in sorted(st.session_state.dxf_layer.items())]),
                    **BREITE, hide_index=True)


# ---------------------------------------------------------
# 5.4 Hilfe
# ---------------------------------------------------------
with tab_hilfe:
    st.markdown("""
### Was das Programm macht

**1D &ndash; Stangen und Profile.** Für jede Stange wird die bestmögliche Belegung
gerechnet (vollständige Kombinationssuche je Stange), danach die nächste Stange.
Die Sägeblattstärke, ein Anschnitt am Anfang und eine Reserve am Ende werden
mitgerechnet. Teile werden nur mit Teilen desselben **Profils** kombiniert.

**2D &ndash; Bleche und Platten.** Drei Schnittarten:

* **Guillotine** &ndash; durchgehende Schnitte in Streifen. Passt zu Tafelschere,
  Plattensäge und Kreissäge.
* **Frei** &ndash; die Teile werden als Rechtecke dicht verschachtelt (MaxRects).
  Nur sinnvoll, wenn die Maschine Konturen fährt (Laser, Plasma, CNC-Fräse).
* **Kontur** &ndash; echtes Nesting mit der tatsächlichen Teileform: Teile greifen
  ineinander, Ausklinkungen und Fensterausschnitte werden mitgenutzt.

**Wann lohnt sich Kontur-Nesting?** Immer dann, wenn die Teile nicht rechteckig
sind &ndash; L-Formen, Dreiecke, Trapeze, Kassetten mit tiefen Ausklinkungen. In
den Tests halbiert es dort den Tafelbedarf (Dreiecke 2 &rarr; 1 Tafel, L-Winkel
4 &rarr; 2 Tafeln). Bei reinen Rechtecken bringt es dagegen nichts; das Programm
rechnet dann zusätzlich das einfache Verfahren mit und übernimmt automatisch
den besseren Plan &ndash; schlechter als *Frei* kann Kontur also nie werden.

So arbeitet das Verfahren: jede Kontur wird in ein Raster übersetzt und um die
halbe Schnittfuge aufgeweitet; anschließend fällt jedes Teil an der günstigsten
Stelle nach unten und rutscht dabei in vorhandene Taschen. Weil nach außen
gerundet wird, ist die eingestellte Schnittfuge garantiert eingehalten &ndash;
im Zweifel steht etwas mehr Abstand, nie weniger.

Stellschrauben:

* **Rasterweite** &ndash; 5 mm ist ein guter Kompromiss. 1&ndash;2 mm schachtelt
  dichter, rechnet aber deutlich länger.
* **Erlaubte Drehung** &ndash; 90°-Schritte reichen meist. 45°-Schritte lohnen
  bei schrägen Teilen. Teile mit Walz- oder Dekorrichtung bleiben über den
  Haken *Drehbar* ohnehin ungedreht.
* **Ausschnitte und Taschen mitnutzen** &ndash; legt kleine Teile in
  Fensterausschnitte großer Teile.
* **Suchtiefe** &ndash; probiert mehrere Schachtelstrategien durch.

**DXF &ndash; HiCAD / Alucobond.** Die Abwicklungen werden eingelesen, die
Außenkontur und die Ausschnitte werden erkannt, Fräs- und Falzlinien getrennt
geführt und nicht als Schnitt gewertet. Der fertige Schachtelplan lässt sich
wieder als DXF ausgeben.

### Layer-Erkennung beim DXF-Import

| Layername enthält | Bedeutung |
|---|---|
| Kontur, Außen, Innen, Ausschnitt, Schnitt, Cut | wird geschnitten |
| Fräs, Falz, Biege, Nut, Kant, Knick, Fold, Bend | Fräs-/Falzlinie (kein Schnitt) |
| Bemaßung, Maß, Text, Beschriftung, Achse, Defpoints | wird ignoriert |

Unbekannte Layer werden im Zweifel als Kontur behandelt. Jede Zuordnung lässt
sich im Reiter *DXF-Import* von Hand ändern.

### Grenzen, die man kennen sollte

* Bei den Schnittarten *Guillotine* und *Frei* wird über die **Außenmaße
  (Bounding-Box)** geschachtelt. Wer die echte Teileform ausnutzen will, nimmt
  die Schnittart **Kontur**.
* Das Konturnesting rechnet im Raster (Standard 5 mm). Die Teile stehen dadurch
  gelegentlich ein paar Millimeter weiter auseinander als nötig &ndash; nie
  enger als die eingestellte Schnittfuge.
* Gedreht wird in 90°- oder 45°-Schritten, nicht in beliebigen Winkeln.
* Teile werden nicht ineinander verschoben, sondern von oben eingelegt. Eine
  Tasche, die nur seitlich erreichbar wäre, bleibt frei.
* Die Optimierung ist eine sehr gute Heuristik, kein mathematisches Optimum.
  Bei üblichen Werkstattaufgaben liegt der Verschnitt erfahrungsgemäß nur
  wenige Prozent über dem theoretischen Bestwert.
* Prüfen Sie vor dem Zuschnitt immer den ausgegebenen Plan &ndash; die Software
  ersetzt die Kontrolle in der Werkstatt nicht.

### Reststücke

Alles, was länger als die eingestellte Grenze ist, gilt als **verwertbarer Rest**
und wird nicht als Verschnitt gezählt. Solche Reste können im Lager als eigene
Zeile mit Haken bei *Reststück* erfasst werden &ndash; sie werden dann zuerst
verbraucht.
    """)

    st.markdown("---")
    st.caption("Meingassner Metalltechnik &middot; Nesting-Modul &middot; "
               "alle Maße in Millimeter")
