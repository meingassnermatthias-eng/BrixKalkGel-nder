import streamlit as st
import pandas as pd
from fpdf import FPDF
import base64
import os
import tempfile
import math
from datetime import datetime

# --- 1. SETUP & KONFIGURATION ---
LOGO_DATEI = "Meingassner Metalltechnik 2023.png"
EXCEL_DATEI = "katalog.xlsx"
MWST_SATZ = 0.20  # 20% MwSt

st.set_page_config(page_title="Meingassner App", layout="wide", page_icon=LOGO_DATEI)

def setup_app_icon(image_file):
    if os.path.exists(image_file):
        with open(image_file, "rb") as f:
            data = f.read()
        encoded = base64.b64encode(data).decode()
        icon_html = f"""
        <link rel="apple-touch-icon" href="data:image/png;base64,{encoded}">
        <link rel="icon" type="image/png" href="data:image/png;base64,{encoded}">
        """
        st.markdown(icon_html, unsafe_allow_html=True)
        st.sidebar.image(image_file, width=200)
    else:
        pass

setup_app_icon(LOGO_DATEI)

# --- 2. EXCEL GENERATOR (NEU: MIT FLEXIBLEM ABSTAND) ---
def generiere_neue_excel_datei():
    """Erstellt die katalog.xlsx neu - WIRD NICHT AUTOMATISCH AUSGEFÜHRT"""
    startseite_data = {
        "Kategorie": [
            "Brix Geländer (Alu)", "Brix Geländer (Alu)", "Brix Geländer (Alu)", "Brix Geländer (Alu)",
            "Brix Zäune & Tore", "Brix Zäune & Tore", "Brix Zäune & Tore", "Brix Zäune & Tore", "Brix Zäune & Tore",
            "Drahtgitter & Stein", "Drahtgitter & Stein", "Drahtgitter & Stein",
            "Eigenfertigung", "Eigenfertigung", "Eigenfertigung"
        ],
        "System": [
            "Stab-Optik", "Flächige Optik", "Glas-Geländer", ">> Zubehör Geländer",
            "Zaun Stab & Latten", "Zaun Sichtschutz", "Tore (Drehflügel)", "Schiebetore", ">> Zubehör Zaun",
            "Gittermatten (Smart)", "Geflecht & Steinkorb", ">> Zubehör Draht",
            "Stahl-Wangentreppe", "Edelstahl-Geländer", ">> Montagematerial"
        ],
        "Blattname": [
            "Brix_Gel_Stab", "Brix_Gel_Flaechig", "Brix_Gel_Glas", "Zub_Gel",
            "Brix_Zaun_Stab", "Brix_Zaun_Sicht", "Brix_Tore", "Brix_Schiebe", "Zub_Zaun",
            "Draht_Matten", "Draht_Mix", "Zub_Draht",
            "Stahl_Treppe", "Eigen_Edelstahl", "Zub_Montage"
        ]
    }
    df_start = pd.DataFrame(startseite_data)

    # --- DATEN DEFINITIONEN ---

    # 1. BRIX GELÄNDER
    gel_stab_data = [
        {"Typ": "Zahl", "Bezeichnung": "Länge (m)", "Variable": "L", "Optionen": "", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Modell", "Variable": "P_Modell", "Optionen": "Decor 22:204, Staketen:169", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Farbe", "Variable": "F_Faktor", "Optionen": "Standard:1.0, Sonder:1.10", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Montage Steher", "Variable": "P_Steher", "Optionen": "Aufsatz:125, Seite:161", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Ecken", "Variable": "Ecken", "Optionen": "", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Montage (€/m)", "Variable": "P_Arbeit", "Optionen": "", "Formel": ""},
        {"Typ": "Preis", "Bezeichnung": "Gesamtpreis", "Variable": "Endpreis", "Optionen": "", "Formel": "(P_Modell * L * F_Faktor) + ((math.ceil(L/1.3)+1) * P_Steher * F_Faktor) + (Ecken * 95) + (L * P_Arbeit)"}
    ]
    df_gel_stab = pd.DataFrame(gel_stab_data)
    df_gel_flaechig = df_gel_stab.copy()
    
    gel_glas_data = [
        {"Typ": "Zahl", "Bezeichnung": "Länge (m)", "Variable": "L", "Optionen": "", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "System", "Variable": "P_System", "Optionen": "Glasal:307, Glasalo:284, Glas-Klemmen:180", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Glas-Füllung", "Variable": "P_Glas", "Optionen": "VSG Klar:130, VSG Matt:165", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Farbe", "Variable": "F_Faktor", "Optionen": "Standard:1.0, Sonder:1.10", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Montage Steher", "Variable": "P_Steher", "Optionen": "Aufsatz:125, Seite:161", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Ecken", "Variable": "Ecken", "Optionen": "", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Montage (€/m)", "Variable": "P_Arbeit", "Optionen": "", "Formel": ""},
        {"Typ": "Preis", "Bezeichnung": "Gesamtpreis", "Variable": "Endpreis", "Optionen": "", "Formel": "((P_System + P_Glas) * L * F_Faktor) + ((math.ceil(L/1.3)+1) * P_Steher * F_Faktor) + (Ecken * 110) + (L * P_Arbeit)"}
    ]
    df_gel_glas = pd.DataFrame(gel_glas_data)

    zub_gel_data = [
        {"Typ": "Auswahl", "Bezeichnung": "Artikel", "Variable": "P_Art", "Optionen": "Handlauf SideRail:70, Blumenkasten:135", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Menge / Länge", "Variable": "Menge", "Optionen": "", "Formel": ""},
        {"Typ": "Preis", "Bezeichnung": "Gesamtpreis", "Variable": "Endpreis", "Optionen": "", "Formel": "P_Art * Menge"}
    ]
    df_zub_gel = pd.DataFrame(zub_gel_data)

    # 2. BRIX ZÄUNE
    zaun_stab_data = [
        {"Typ": "Zahl", "Bezeichnung": "Länge (m)", "Variable": "L", "Optionen": "", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Modell", "Variable": "P_Modell", "Optionen": "Decor 22:180, Latten Classic:190, Palisaden:175", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Höhe", "Variable": "H_Faktor", "Optionen": "H 1000:1.0, H 1200:1.2, H 1500:1.4", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Farbe", "Variable": "F_Faktor", "Optionen": "Standard:1.0, Sonder:1.10, Holz:1.4", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Säule", "Variable": "P_Saeule", "Optionen": "Betonieren:85, Dübeln:110", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Montage (€/m)", "Variable": "P_Arbeit", "Optionen": "", "Formel": ""},
        {"Typ": "Preis", "Bezeichnung": "Gesamtpreis", "Variable": "Endpreis", "Optionen": "", "Formel": "(P_Modell * H_Faktor * L * F_Faktor) + ((math.ceil(L/2.0)+1) * P_Saeule * F_Faktor) + (L * P_Arbeit)"}
    ]
    df_zaun_stab = pd.DataFrame(zaun_stab_data)
    
    zaun_sicht_data = [
        {"Typ": "Zahl", "Bezeichnung": "Länge (m)", "Variable": "L", "Optionen": "", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Modell", "Variable": "P_Modell", "Optionen": "Lamello:290, Listello:280, Platten:260", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Höhe", "Variable": "H_Faktor", "Optionen": "H 1000:1.0, H 1500:1.5, H 1800:1.8", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Farbe", "Variable": "F_Faktor", "Optionen": "Standard:1.0, Sonder:1.10", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Säule", "Variable": "P_Saeule", "Optionen": "Betonieren:120, Dübeln:150", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Montage (€/m)", "Variable": "P_Arbeit", "Optionen": "", "Formel": ""},
        {"Typ": "Preis", "Bezeichnung": "Gesamtpreis", "Variable": "Endpreis", "Optionen": "", "Formel": "(P_Modell * H_Faktor * L * F_Faktor) + ((math.ceil(L/1.8)+1) * P_Saeule * F_Faktor) + (L * P_Arbeit)"}
    ]
    df_zaun_sicht = pd.DataFrame(zaun_sicht_data)

    tore_data = [
        {"Typ": "Auswahl", "Bezeichnung": "Typ", "Variable": "P_Basis", "Optionen": "Gehtür (1m):950, 2-Flg Tor (3m):2200", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Füllung", "Variable": "P_Full", "Optionen": "Standard:0, Sichtschutz:350", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Farbe", "Variable": "F_Faktor", "Optionen": "Standard:1.0, Sonder:1.10", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Antrieb", "Variable": "P_Antrieb", "Optionen": "Manuell:0, E-Öffner:150, E-Antrieb:1250", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Anzahl", "Variable": "Menge", "Optionen": "", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Montage (Pauschal)", "Variable": "P_Montage", "Optionen": "", "Formel": ""},
        {"Typ": "Preis", "Bezeichnung": "Gesamtpreis", "Variable": "Endpreis", "Optionen": "", "Formel": "((P_Basis + P_Full) * F_Faktor * Menge) + (P_Antrieb * Menge) + P_Montage"}
    ]
    df_tore = pd.DataFrame(tore_data)

    schiebe_data = [
        {"Typ": "Zahl", "Bezeichnung": "Lichte (m)", "Variable": "L", "Optionen": "", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Modell", "Variable": "P_Modell", "Optionen": "C-Profil Stab:1400, C-Profil Sichtschutz:1600", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Farbe", "Variable": "F_Faktor", "Optionen": "Standard:1.0, Sonder:1.10", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Antrieb", "Variable": "P_Antrieb", "Optionen": "Manuell:0, E-Antrieb Set:1450", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Montage Pauschale", "Variable": "P_Montage", "Optionen": "", "Formel": ""},
        {"Typ": "Preis", "Bezeichnung": "Gesamtpreis", "Variable": "Endpreis", "Optionen": "", "Formel": "(P_Modell * L * F_Faktor) + P_Antrieb + P_Montage"}
    ]
    df_schiebe = pd.DataFrame(schiebe_data)

    zub_zaun_data = [
        {"Typ": "Auswahl", "Bezeichnung": "Artikel", "Variable": "P_Art", "Optionen": "Briefkasten:155, Paketbox:400, Lackspray:25", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Menge", "Variable": "Menge", "Optionen": "", "Formel": ""},
        {"Typ": "Preis", "Bezeichnung": "Gesamt", "Variable": "Endpreis", "Optionen": "", "Formel": "P_Art * Menge"}
    ]
    df_zub_zaun = pd.DataFrame(zub_zaun_data)

    # 3. DRAHTGITTER (Mit Flexiblem Abstand "Dist")
    matten_data = [
        {"Typ": "Zahl", "Bezeichnung": "Länge (m)", "Variable": "L", "Optionen": "", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Preis pro Sack Beton (€)", "Variable": "P_Sack", "Optionen": "", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Konsole Typ (wenn Dübeln)", "Variable": "P_Konsole", "Optionen": "---:0, Leicht:15, Schwer:45", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Montage-Art", "Variable": "Ist_Beton", "Optionen": "Einbetonieren:1, Aufdübeln:0", "Formel": ""},
        
        # NEU: Der variable Abstand
        {"Typ": "Auswahl", "Bezeichnung": "Steher-Abstand", "Variable": "Dist", 
         "Optionen": "Standard (2.5m):2.5, Verkürzt (2.0m):2.0, Eng (1.25m):1.25", 
         "Formel": "Teiler für Steheranzahl"},

        {"Typ": "Auswahl", "Bezeichnung": "Matte Höhe", "Variable": "P_Matte", "Optionen": "H 1030:22, H 1230:26, H 1430:31", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Säulen-Typ", "Variable": "P_Saeule", "Optionen": "Klemmhalter:35, Abdeckleiste:45", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Farbe", "Variable": "F_Faktor", "Optionen": "Verzinkt:1.0, Farbe:1.15", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Montage (€/m)", "Variable": "P_Arbeit", "Optionen": "", "Formel": ""},
        
        # Formel angepasst: Statt 2.5 wird jetzt "Dist" verwendet
        {"Typ": "Preis", "Bezeichnung": "Gesamtpreis", "Variable": "Endpreis", "Optionen": "", 
         "Formel": "(L * P_Matte * F_Faktor) + ((math.ceil(L/Dist)+1) * ((P_Saeule * F_Faktor) + (Ist_Beton * 2 * P_Sack) + ((1-Ist_Beton) * P_Konsole))) + (L * P_Arbeit)"}
    ]
    df_matten = pd.DataFrame(matten_data)
    
    df_draht_mix = df_gel_stab.copy()

    zub_draht_data = [
        {"Typ": "Auswahl", "Bezeichnung": "Artikel", "Variable": "P_Art", "Optionen": "Sichtschutz Rolle:45, Klemmen:2, Spray:18", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Menge", "Variable": "Menge", "Optionen": "", "Formel": ""},
        {"Typ": "Preis", "Bezeichnung": "Gesamt", "Variable": "Endpreis", "Optionen": "", "Formel": "P_Art * Menge"}
    ]
    df_zub_draht = pd.DataFrame(zub_draht_data)

    # 4. EIGENFERTIGUNG
    treppe_data = [
        {"Typ": "Zahl", "Bezeichnung": "Geschoßhöhe (m)", "Variable": "H", "Optionen": "", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Treppenbreite (B)", "Variable": "B", "Optionen": "800mm:0.8, 1000mm:1.0, 1200mm:1.2", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Gitterrost-Stufe", "Variable": "P_Stufe", "Optionen": "MW 30x30:40, MW 30x10:55", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Wangen-Profil (lfm)", "Variable": "P_Wange", "Optionen": "Flachstahl:60, U-Profil:85", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Oberfläche Wangen", "Variable": "F_Faktor", "Optionen": "Verzinkt:1.0, Pulver:1.3", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Podest-Länge (m)", "Variable": "L_Podest", "Optionen": "", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Podest-Belag (€/qm)", "Variable": "P_Rost", "Optionen": "Gitterrost:80, Tränenblech:90", "Formel": ""},
        
        {"Typ": "Zahl", "Bezeichnung": "Montage Rüstzeit Pauschal (h)", "Variable": "T_Basis", "Optionen": "", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Montagezeit pro Meter Höhe (h)", "Variable": "T_Meter", "Optionen": "", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Stundensatz (€)", "Variable": "P_Satz", "Optionen": "", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Montagematerial", "Variable": "P_Mat", "Optionen": "", "Formel": ""},
        
        {"Typ": "Preis", "Bezeichnung": "Gesamtpreis", "Variable": "Endpreis", "Optionen": "", 
         "Formel": "(math.ceil(H/0.18) * P_Stufe) + ((H * 1.8 * 2) * P_Wange * F_Faktor) + (L_Podest * B * P_Rost) + ((T_Basis + (H * T_Meter)) * P_Satz) + P_Mat"}
    ]
    df_treppe = pd.DataFrame(treppe_data)

    edelstahl_data = [
        {"Typ": "Zahl", "Bezeichnung": "Länge (m)", "Variable": "L", "Optionen": "", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Modell", "Variable": "P_Modell", "Optionen": "Reling 5-Stab:240, Glas:450", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Steher-Profil", "Variable": "P_Steher", "Optionen": "Rundrohr:90, Quadratrohr:110", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Montageart", "Variable": "P_Montageart", "Optionen": "Aufgeschraubt:0, Stirnseitig:35", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Ecken", "Variable": "Ecken", "Optionen": "", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Montage (€/m)", "Variable": "P_Arbeit", "Optionen": "", "Formel": ""},
        {"Typ": "Preis", "Bezeichnung": "Gesamtpreis", "Variable": "Endpreis", "Optionen": "", "Formel": "(L * P_Modell) + ((math.ceil(L/1.2)+1) * (P_Steher + P_Montageart)) + (Ecken * 150) + (L * P_Arbeit)"}
    ]
    df_edelstahl = pd.DataFrame(edelstahl_data)

    zub_montage_data = [
        {"Typ": "Auswahl", "Bezeichnung": "Artikel", "Variable": "P_Art", "Optionen": "Anker M10:2.5, Mörtel:25, Gewindestange:8", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Menge", "Variable": "Menge", "Optionen": "", "Formel": ""},
        {"Typ": "Preis", "Bezeichnung": "Gesamt", "Variable": "Endpreis", "Optionen": "", "Formel": "P_Art * Menge"}
    ]
    df_zub_montage = pd.DataFrame(zub_montage_data)

    try:
        with pd.ExcelWriter(EXCEL_DATEI, engine="openpyxl") as writer:
            df_start.to_excel(writer, sheet_name="Startseite", index=False)
            df_gel_stab.to_excel(writer, sheet_name="Brix_Gel_Stab", index=False)
            df_gel_flaechig.to_excel(writer, sheet_name="Brix_Gel_Flaechig", index=False)
            df_gel_glas.to_excel(writer, sheet_name="Brix_Gel_Glas", index=False)
            df_zub_gel.to_excel(writer, sheet_name="Zub_Gel", index=False)
            df_zaun_stab.to_excel(writer, sheet_name="Brix_Zaun_Stab", index=False)
            df_zaun_sicht.to_excel(writer, sheet_name="Brix_Zaun_Sicht", index=False)
            df_tore.to_excel(writer, sheet_name="Brix_Tore", index=False)
            df_schiebe.to_excel(writer, sheet_name="Brix_Schiebe", index=False)
            df_zub_zaun.to_excel(writer, sheet_name="Zub_Zaun", index=False)
            df_matten.to_excel(writer, sheet_name="Draht_Matten", index=False)
            df_draht_mix.to_excel(writer, sheet_name="Draht_Mix", index=False)
            df_zub_draht.to_excel(writer, sheet_name="Zub_Draht", index=False)
            df_treppe.to_excel(writer, sheet_name="Stahl_Treppe", index=False)
            df_edelstahl.to_excel(writer, sheet_name="Eigen_Edelstahl", index=False)
            df_zub_montage.to_excel(writer, sheet_name="Zub_Montage", index=False)
        return True
    except Exception as e: return False

# --- 3. HELPER ---
def clean_df_columns(df):
    if not df.empty: 
        df.columns = df.columns.str.strip()
        rename_map = {'Formel / Info': 'Formel', 'Formel/Info': 'Formel', 'Info': 'Formel'}
        df.rename(columns=rename_map, inplace=True)
    return df

def lade_startseite():
    if not os.path.exists(EXCEL_DATEI): return pd.DataFrame()
    try: return clean_df_columns(pd.read_excel(EXCEL_DATEI, sheet_name="Startseite"))
    except: return pd.DataFrame()

def lade_blatt(blatt_name):
    if not os.path.exists(EXCEL_DATEI): return pd.DataFrame()
    try: return clean_df_columns(pd.read_excel(EXCEL_DATEI, sheet_name=blatt_name))
    except: return pd.DataFrame()

def lade_alle_blattnamen():
    if not os.path.exists(EXCEL_DATEI): return []
    return pd.ExcelFile(EXCEL_DATEI).sheet_names

def speichere_excel(df, blatt_name):
    try:
        mode = "a" if os.path.exists(EXCEL_DATEI) else "w"
        with pd.ExcelWriter(EXCEL_DATEI, engine="openpyxl", mode=mode, if_sheet_exists="replace") as writer:
            df.to_excel(writer, sheet_name=blatt_name, index=False)
        return True
    except Exception as e:
        st.error(f"Fehler: {e}")
        return False

# --- 4. SESSION STATE ---
if 'positionen' not in st.session_state: st.session_state['positionen'] = []
if 'kunden_daten' not in st.session_state: 
    st.session_state['kunden_daten'] = {"Name": "", "Strasse": "", "Ort": "", "Tel": "", "Email": "", "Notiz": ""}
if 'fertiges_pdf' not in st.session_state: st.session_state['fertiges_pdf'] = None
if 'fertiges_intern_pdf' not in st.session_state: st.session_state['fertiges_intern_pdf'] = None

if 'zusatzkosten' not in st.session_state:
    st.session_state['zusatzkosten'] = {
        "kran": 0.0, 
        "montage_mann": 2, 
        "montage_std": 0.0, 
        "montage_satz": 65.0,
        "zuschlag_prozent": 0.0,
        "zuschlag_label": "Normal"
    }

# --- 5. PDF ENGINE 1: KUNDE ---
def clean_text(text):
    if not isinstance(text, str): text = str(text)
    text = text.replace("€", "EUR").replace("–", "-").replace("„", '"').replace("“", '"')
    return text.encode('latin-1', 'replace').decode('latin-1')

class PDF(FPDF):
    def header(self):
        if os.path.exists(LOGO_DATEI): self.image(LOGO_DATEI, 10, 8, 60)
        self.set_font('Arial', 'B', 16)
        heute = datetime.now().strftime("%d.%m.%Y")
        titel = f"Kostenschätzung vom {heute}"
        self.cell(0, 18, clean_text(titel), 0, 1, 'R')
        self.ln(10)
    def footer(self):
        self.set_y(-15); self.set_font('Arial', 'I', 8); self.cell(0, 10, f'Seite {self.page_no()}', 0, 0, 'C')

def create_pdf(positionen_liste, kunden_dict, fotos, montage_summe, kran_summe, zeige_details, zuschlag_prozent, zuschlag_label, zuschlag_transparent):
    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Kundendaten
    pdf.ln(10); pdf.set_font("Arial", 'B', 12); pdf.cell(0, 6, "Kundeninformation:", ln=True); pdf.set_font("Arial", size=10)
    k_text = ""
    if kunden_dict["Name"]: k_text += f"{kunden_dict['Name']}\n"
    if kunden_dict["Strasse"]: k_text += f"{kunden_dict['Strasse']}\n"
    if kunden_dict["Ort"]: k_text += f"{kunden_dict['Ort']}\n"
    k_text += "\n"
    if kunden_dict["Tel"]: k_text += f"Tel: {kunden_dict['Tel']}\n"
    if kunden_dict["Email"]: k_text += f"Email: {kunden_dict['Email']}\n"
    pdf.multi_cell(0, 5, clean_text(k_text))
    if kunden_dict["Notiz"]:
        pdf.ln(5); pdf.set_font("Arial", 'B', 10); pdf.cell(0, 5, "Bemerkung / Notizen:", ln=True); pdf.set_font("Arial", size=10)
        pdf.multi_cell(0, 5, clean_text(kunden_dict["Notiz"]))
    pdf.ln(10)
    
    # Tabelle
    pdf.set_font("Arial", 'B', 10); pdf.set_fill_color(240, 240, 240)
    w_desc, w_menge, w_ep, w_gesamt = 100, 25, 30, 35
    pdf.cell(w_desc, 8, "Beschreibung", 1, 0, 'L', True)
    pdf.cell(w_menge, 8, "Menge", 1, 0, 'C', True)
    pdf.cell(w_ep, 8, "EP (EUR)", 1, 0, 'R', True)
    pdf.cell(w_gesamt, 8, "Gesamt", 1, 1, 'R', True)
    pdf.set_font("Arial", size=10)
    
    subtotal = 0
    for pos in positionen_liste:
        raw_desc = str(pos['Beschreibung'])
        parts = raw_desc.split("|")
        main_title = parts[0].strip()
        details = ""
        if len(parts) > 1:
            details_raw = parts[1]
            details = "\n" + details_raw.replace(",", "\n -").strip()
            if not details.strip().startswith("-"): details = details.replace("\n", "\n - ", 1)
        
        if 'RefMenge' in pos and 'RefEinheit' in pos and pos['RefMenge'] > 0:
            einheit_preis = pos['Einzelpreis'] / float(pos['RefMenge'])
            details += f"\n   (entspricht {einheit_preis:.2f} EUR / {pos['RefEinheit']})"

        final_desc_text = clean_text(f"{main_title}{details}")
        
        x_start, y_start = pdf.get_x(), pdf.get_y()
        pdf.multi_cell(w_desc, 5, final_desc_text, border=1, align='L')
        y_end = pdf.get_y(); row_height = y_end - y_start
        pdf.set_xy(x_start + w_desc, y_start)
        pdf.cell(w_menge, row_height, clean_text(str(pos['Menge'])), 1, 0, 'C')
        pdf.cell(w_ep, row_height, f"{pos['Einzelpreis']:.2f}", 1, 0, 'R')
        pdf.cell(w_gesamt, row_height, f"{pos['Preis']:.2f}", 1, 1, 'R')
        subtotal += pos['Preis']

    # Montage
    zuschlag_wert = 0
    if zuschlag_prozent > 0:
        basis = subtotal + montage_summe + kran_summe
        zuschlag_wert = basis * (zuschlag_prozent / 100.0)

    versteckter_zuschlag_in_montage = 0
    if zuschlag_prozent > 0 and not zuschlag_transparent:
        versteckter_zuschlag_in_montage = zuschlag_wert
        zuschlag_wert = 0

    montage_final = montage_summe + versteckter_zuschlag_in_montage
    if montage_final > 0:
        if zeige_details and not versteckter_zuschlag_in_montage:
            text_montage = "Montagearbeiten (lt. Angabe)"
        else:
            text_montage = "Montage & Regiearbeiten (Pauschal)"
        pdf.cell(w_desc, 8, clean_text(text_montage), 1, 0, 'L')
        pdf.cell(w_menge, 8, "1", 1, 0, 'C')
        pdf.cell(w_ep, 8, f"{montage_final:.2f}", 1, 0, 'R')
        pdf.cell(w_gesamt, 8, f"{montage_final:.2f}", 1, 1, 'R')
        subtotal += montage_final

    if kran_summe > 0:
        pdf.cell(w_desc, 8, clean_text("Kranarbeiten / Hebegerät"), 1, 0, 'L')
        pdf.cell(w_menge, 8, "1", 1, 0, 'C')
        pdf.cell(w_ep, 8, f"{kran_summe:.2f}", 1, 0, 'R')
        pdf.cell(w_gesamt, 8, f"{kran_summe:.2f}", 1, 1, 'R')
        subtotal += kran_summe

    if zuschlag_wert > 0:
        pdf.cell(w_desc + w_menge + w_ep, 8, "Zwischensumme Netto:", 0, 0, 'R')
        pdf.cell(w_gesamt, 8, f"{subtotal:.2f}", 1, 1, 'R')
        label_text = f"Erschwerniszuschlag ({zuschlag_label} - {zuschlag_prozent}%)"
        pdf.set_font("Arial", 'I', 10)
        pdf.cell(w_desc + w_menge + w_ep, 8, clean_text(label_text), 0, 0, 'R')
        pdf.cell(w_gesamt, 8, f"{zuschlag_wert:.2f}", 1, 1, 'R')
        subtotal += zuschlag_wert

    netto = subtotal
    mwst_betrag = netto * MWST_SATZ
    brutto = netto + mwst_betrag

    pdf.ln(2)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(w_desc + w_menge + w_ep, 0, "", 0, 0, 'R')
    pdf.line(pdf.get_x() + w_desc + w_menge + w_ep, pdf.get_y(), pdf.get_x() + w_desc + w_menge + w_ep + w_gesamt, pdf.get_y())
    pdf.ln(2)
    
    pdf.set_font("Arial", '', 11)
    pdf.cell(w_desc + w_menge + w_ep, 6, "Summe Netto:", 0, 0, 'R')
    pdf.cell(w_gesamt, 6, f"{netto:.2f} EUR", 0, 1, 'R')
    
    pdf.cell(w_desc + w_menge + w_ep, 6, f"zzgl. {int(MWST_SATZ*100)}% MwSt:", 0, 0, 'R')
    pdf.cell(w_gesamt, 6, f"{mwst_betrag:.2f} EUR", 0, 1, 'R')
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(w_desc + w_menge + w_ep, 10, "GESAMTSUMME BRUTTO:", 0, 0, 'R')
    pdf.cell(w_gesamt, 10, f"{brutto:.2f} EUR", 1, 1, 'R')

    if fotos:
        pdf.add_page(); pdf.cell(0, 10, "Baustellen-Dokumentation / Fotos", 0, 1, 'L')
        for foto_upload in fotos:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
                    tmp_file.write(foto_upload.getvalue())
                    tmp_path = tmp_file.name
                if pdf.get_y() > 180: pdf.add_page()
                pdf.image(tmp_path, w=160); pdf.ln(10); os.unlink(tmp_path)
            except Exception as e: pdf.cell(0, 10, f"Fehler: {str(e)}", ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- 6. PDF ENGINE 2: INTERN ---
class InternalPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        heute = datetime.now().strftime("%d.%m.%Y")
        self.cell(0, 10, clean_text(f"Fertigungs-Datenblatt / ERP-Import - {heute}"), 0, 1, 'L')
        self.line(10, 20, 200, 20)
        self.ln(10)
    def footer(self):
        self.set_y(-15); self.set_font('Arial', 'I', 8); self.cell(0, 10, f'Seite {self.page_no()}', 0, 0, 'C')

def create_internal_pdf(positionen_liste, kunden_dict, zusatzkosten):
    pdf = InternalPDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 8, f"Kunde: {clean_text(kunden_dict['Name'])} ({clean_text(kunden_dict['Ort'])})", 0, 1, 'L')
    pdf.set_font("Arial", '', 10)
    if kunden_dict['Notiz']:
        pdf.multi_cell(0, 5, clean_text(f"Notiz: {kunden_dict['Notiz']}"))
    pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(10, 8, "#", 1, 0, 'C', True)
    pdf.cell(140, 8, "Artikel & Material-Bedarf", 1, 0, 'L', True)
    pdf.cell(40, 8, "Kalk. Preis", 1, 1, 'R', True)
    
    pdf.set_font("Arial", '', 10)
    
    for i, pos in enumerate(positionen_liste):
        raw_desc = str(pos['Beschreibung'])
        parts = raw_desc.split("|")
        titel = parts[0].strip()
        params = ""
        if len(parts) > 1:
            params = parts[1].replace(", ", "\n  - ").strip()
            if not params.startswith("-"): params = "  - " + params
            
        full_text = f"{titel} (Parameter):\n{params}"
        
        if 'MaterialDetails' in pos and pos['MaterialDetails']:
            full_text += "\n\n  >> MATERIAL-BEDARF (Kalkuliert):"
            for mat_item in pos['MaterialDetails']:
                full_text += f"\n  -> {mat_item}"

        x_start = pdf.get_x()
        y_start = pdf.get_y()
        pdf.set_x(20)
        pdf.multi_cell(140, 5, clean_text(full_text), border=0)
        y_end = pdf.get_y()
        row_height = y_end - y_start
        
        pdf.set_xy(x_start, y_start)
        pdf.cell(10, row_height, str(i+1), 1, 0, 'C')
        pdf.cell(140, row_height, "", 1, 0)
        pdf.cell(40, row_height, f"{pos['Preis']:.2f}", 1, 1, 'R')
        
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 8, "Zusatzkosten-Check:", 0, 1, 'L')
    pdf.set_font("Arial", '', 10)
    
    m_mann = zusatzkosten['montage_mann']
    m_std = zusatzkosten['montage_std']
    m_satz = zusatzkosten['montage_satz']
    kran = zusatzkosten['kran']
    zuschlag = zusatzkosten['zuschlag_prozent']
    z_label = zusatzkosten['zuschlag_label']
    
    text_zusatz = f"- Montage: {m_mann} Mann x {m_std} Std (Satz: {m_satz} EUR)\n"
    text_zusatz += f"- Kran: {kran} EUR\n"
    text_zusatz += f"- Erschwernis: {z_label} ({zuschlag}%)"
    
    pdf.multi_cell(0, 5, clean_text(text_zusatz), 1)
    
    return pdf.output(dest='S').encode('latin-1')

# --- NAVIGATION ---
st.sidebar.header("Navigation")
index_df = lade_startseite()
if not index_df.empty and 'Kategorie' in index_df.columns:
    kategorien = index_df['Kategorie'].unique()
    wahl_kategorie = st.sidebar.selectbox("Filter Kategorie:", kategorien)
    katalog_items = index_df[index_df['Kategorie'] == wahl_kategorie]['System'].tolist()
else:
    katalog_items = index_df['System'].tolist() if not index_df.empty and 'System' in index_df.columns else []

menue_punkt = st.sidebar.radio("Gehe zu:", ["📂 Konfigurator / Katalog", "🛒 Warenkorb / Abschluss", "🔐 Admin"])
st.sidebar.markdown("---")

# TEIL A: KONFIGURATOR
if menue_punkt == "📂 Konfigurator / Katalog":
    st.title("Artikel Konfigurator")
    if katalog_items:
        auswahl_system = st.selectbox("System wählen:", katalog_items)
        if 'Kategorie' in index_df.columns:
            row = index_df[(index_df['System'] == auswahl_system) & (index_df['Kategorie'] == wahl_kategorie)]
        else:
            row = index_df[index_df['System'] == auswahl_system]
            
        if not row.empty:
            blatt = row.iloc[0]['Blattname']
            df_config = lade_blatt(blatt)
            col_konfig, col_mini_cart = st.columns([2, 1])
            with col_konfig:
                st.subheader(f"Konfiguration: {auswahl_system}")
                if df_config.empty: st.warning("Blatt leer.")
                elif 'Formel' not in df_config.columns: st.error("Fehler: 'Formel' fehlt.")
                else:
                    vars_calc = {}; desc_parts = []
                    for index, zeile in df_config.iterrows():
                        typ = str(zeile.get('Typ', '')).strip().lower()
                        label = str(zeile.get('Bezeichnung', 'Unbenannt'))
                        var_name = str(zeile.get('Variable', '')).strip()
                        
                        if typ == 'zahl':
                            val = st.number_input(label, value=0.0, step=1.0, key=f"{blatt}_{index}")
                            vars_calc[var_name] = val
                            if val > 0: desc_parts.append(f"{label}: {val}")
                        elif typ == 'auswahl':
                            raw_opts = str(zeile.get('Optionen', '')).split(',')
                            opts_dict = {}; opts_names = []
                            for opt in raw_opts:
                                if ':' in opt:
                                    n, v = opt.split(':')
                                    opts_dict[n.strip()] = float(v)
                                    opts_names.append(n.strip())
                                else:
                                    opts_dict[opt.strip()] = 0
                                    opts_names.append(opt.strip())
                            wahl = st.selectbox(label, opts_names, key=f"{blatt}_{index}")
                            vars_calc[var_name] = opts_dict.get(wahl, 0)
                            desc_parts.append(f"{label}: {wahl}")
                        elif typ == 'preis':
                            formel = str(zeile.get('Formel', ''))
                            st.markdown("---")
                            try:
                                safe_env = {"__builtins__": None, "math": math, "round": round, "int": int, "float": float}
                                safe_env.update(vars_calc)
                                preis = eval(formel, safe_env)
                                st.subheader(f"Preis: {preis:.2f} €")
                                if st.button("In den Warenkorb", type="primary"):
                                    full_desc = f"{auswahl_system} | " + ", ".join(desc_parts)
                                    
                                    ref_menge = 1.0; ref_einheit = "Stk"
                                    if 'L' in vars_calc and vars_calc['L'] > 0:
                                        ref_menge = vars_calc['L']; ref_einheit = "lfm"
                                    elif 'H' in vars_calc and vars_calc['H'] > 0:
                                        ref_menge = vars_calc['H']; ref_einheit = "lfm Höhe"
                                    elif 'L_Podest' in vars_calc and 'B' in vars_calc and vars_calc['L_Podest'] > 0:
                                        ref_menge = vars_calc['L_Podest'] * vars_calc['B']; ref_einheit = "m²"
                                    
                                    # STÜCKLISTEN LOGIK (Mit flexiblem Abstand Dist)
                                    mat_liste = []
                                    if 'L' in vars_calc and vars_calc['L'] > 0:
                                        l = vars_calc['L']
                                        abstand = 1.3 
                                        
                                        # HIER IST DIE NEUE LOGIK FÜR ABSTAND
                                        if 'Dist' in vars_calc and vars_calc['Dist'] > 0:
                                            abstand = vars_calc['Dist']
                                        elif 'Edelstahl' in auswahl_system: 
                                            abstand = 1.2
                                        elif 'Draht' in auswahl_system:
                                            # Fallback falls jemand Reset nicht gedrückt hat
                                            abstand = 2.5
                                        
                                        anz_steher = math.ceil(l / abstand) + 1
                                        mat_liste.append(f"Steher (alle {abstand}m): {anz_steher} Stk")
                                        
                                        if 'Ist_Beton' in vars_calc:
                                            if vars_calc['Ist_Beton'] == 1:
                                                mat_liste.append(f"Beton (2/Steher): {anz_steher * 2} Säcke")
                                            else:
                                                mat_liste.append(f"Dübelplatten: {anz_steher} Stk")
                                        
                                        if 'Ecken' in vars_calc and vars_calc['Ecken'] > 0:
                                            mat_liste.append(f"Eck-Verbinder: {int(vars_calc['Ecken'])} Stk")

                                    if 'H' in vars_calc and vars_calc['H'] > 0:
                                        h = vars_calc['H']
                                        stufen = math.ceil(h / 0.18)
                                        wangen_lfm = h * 1.8 * 2
                                        mat_liste.append(f"Stufen (H/18cm): {stufen} Stk")
                                        mat_liste.append(f"Wangen-Profil: ca. {wangen_lfm:.2f} lfm")

                                    st.session_state['positionen'].append({
                                        "Beschreibung": full_desc, "Menge": 1.0, 
                                        "Einzelpreis": preis, "Preis": preis,
                                        "RefMenge": ref_menge, "RefEinheit": ref_einheit,
                                        "MaterialDetails": mat_liste
                                    })
                                    st.success("Hinzugefügt!")
                            except Exception as e: st.error(f"Fehler: {e}")
            with col_mini_cart:
                st.info("🛒 Schnell-Check")
                if st.session_state['positionen']:
                    cnt = len(st.session_state['positionen']); sum_live = sum(p['Preis'] for p in st.session_state['positionen'])
                    st.write(f"**{cnt} Pos.** | **{sum_live:.2f} € (netto)**")
                else: st.write("Leer")
    else: st.warning("Keine Daten. Bitte im Admin-Bereich 'Reset' drücken (nur beim ersten Mal)!")

# TEIL B: WARENKORB
elif menue_punkt == "🛒 Warenkorb / Abschluss":
    st.title("🛒 Warenkorb")
    col_liste, col_daten = st.columns([1.2, 0.8])
    with col_liste:
        st.subheader("Positionen")
        if st.session_state['positionen']:
            h1, h2, h3, h4 = st.columns([3, 1, 1, 0.5])
            h1.markdown("**Beschreibung**"); h2.markdown("**Menge**"); h3.markdown("**Preis**"); h4.markdown("**Del**")
            st.markdown("---")
            indices_to_delete = []
            for i, pos in enumerate(st.session_state['positionen']):
                c1, c2, c3, c4 = st.columns([3, 1, 1, 0.5])
                short_desc = pos['Beschreibung'].split("|")[0]
                c1.write(f"**{short_desc}**"); 
                with c1.expander("Details"): st.write(pos['Beschreibung'])
                neue_menge = c2.number_input("Menge", value=float(pos['Menge']), step=1.0, key=f"qty_{i}", label_visibility="collapsed")
                if neue_menge != pos['Menge']:
                    st.session_state['positionen'][i]['Menge'] = neue_menge
                    st.session_state['positionen'][i]['Preis'] = neue_menge * pos['Einzelpreis']
                    st.rerun()
                c3.write(f"{pos['Preis']:.2f} €")
                if c4.button("🗑️", key=f"del_{i}"): indices_to_delete.append(i)
            if indices_to_delete:
                for index in sorted(indices_to_delete, reverse=True): del st.session_state['positionen'][index]
                st.session_state['fertiges_pdf'] = None; st.session_state['fertiges_intern_pdf'] = None; st.rerun()
            st.markdown("---")
            
            total_artikel = sum(p['Preis'] for p in st.session_state['positionen'])
            m_sum = st.session_state['zusatzkosten']['montage_mann'] * st.session_state['zusatzkosten']['montage_std'] * st.session_state['zusatzkosten']['montage_satz']
            k_sum = st.session_state['zusatzkosten']['kran']
            
            zuschlag_prozent = st.session_state['zusatzkosten']['zuschlag_prozent']
            basis = total_artikel + m_sum + k_sum
            zuschlag_wert = basis * (zuschlag_prozent / 100.0)
            end_summe = basis + zuschlag_wert

            if m_sum > 0: st.write(f"➕ Montage: **{m_sum:.2f} €**")
            if k_sum > 0: st.write(f"➕ Kran: **{k_sum:.2f} €**")
            
            if zuschlag_prozent > 0:
                st.write(f"---")
                label = st.session_state['zusatzkosten']['zuschlag_label']
                st.write(f"➕ Erschwernis ({label}): **{zuschlag_wert:.2f} €**")
                
            st.markdown(f"### Netto: {end_summe:.2f} €")
            st.caption(f"Brutto (inkl. {int(MWST_SATZ*100)}%): {(end_summe * (1+MWST_SATZ)):.2f} €")
            
            if st.button("Alles löschen", type="secondary"): st.session_state['positionen'] = []; st.rerun()
        else: st.info("Leer.")

    with col_daten:
        with st.expander("🏗️ Montage & Zusatzkosten", expanded=True):
            st.write("**Montage-Rechner**")
            c_m1, c_m2, c_m3 = st.columns(3)
            st.session_state['zusatzkosten']['montage_mann'] = c_m1.number_input("Mann", value=st.session_state['zusatzkosten']['montage_mann'], step=1)
            st.session_state['zusatzkosten']['montage_std'] = c_m2.number_input("Std", value=st.session_state['zusatzkosten']['montage_std'], step=1.0)
            st.session_state['zusatzkosten']['montage_satz'] = c_m3.number_input("Satz €", value=st.session_state['zusatzkosten']['montage_satz'], step=5.0)
            
            zeige_details = st.checkbox("Details (Stunden/Satz) im PDF anzeigen?", value=True)
            
            st.markdown("---")
            st.session_state['zusatzkosten']['kran'] = st.number_input("Kran Pauschale €", value=st.session_state['zusatzkosten']['kran'], step=50.0)
            
            # --- ZUSCHLAG SCHIEBER ---
            st.markdown("---")
            st.write("**Erschwernis / Risiko**")
            
            stufen = {"Normal": 0.0, "Schwierig": 10.0, "Sehr kompliziert": 20.0}
            wahl_schwierigkeit = st.select_slider("Baustellen-Schwierigkeit:", options=list(stufen.keys()), value="Normal")
            
            st.session_state['zusatzkosten']['zuschlag_prozent'] = stufen[wahl_schwierigkeit]
            st.session_state['zusatzkosten']['zuschlag_label'] = wahl_schwierigkeit
            
            if st.session_state['zusatzkosten']['zuschlag_prozent'] > 0:
                zuschlag_transparent = st.checkbox("Auf PDF ausweisen?", value=True, help="Häkchen WEG = Aufschlag wird unsichtbar in Montage eingerechnet")
            else:
                zuschlag_transparent = True
        
        st.subheader("Kundendaten")
        with st.form("abschluss"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Name", value=st.session_state['kunden_daten']['Name'])
            strasse = c2.text_input("Straße", value=st.session_state['kunden_daten']['Strasse'])
            c3, c4 = st.columns(2)
            ort = c3.text_input("Ort", value=st.session_state['kunden_daten']['Ort'])
            tel = c4.text_input("Tel", value=st.session_state['kunden_daten']['Tel'])
            email = st.text_input("Email", value=st.session_state['kunden_daten']['Email'])
            notiz = st.text_area("Notiz", value=st.session_state['kunden_daten']['Notiz'])
            st.markdown("---")
            fotos = st.file_uploader("Fotos", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])
            submitted = st.form_submit_button("💾 PDFs Generieren")
        if submitted:
            st.session_state['kunden_daten'] = {"Name": name, "Strasse": strasse, "Ort": ort, "Tel": tel, "Email": email, "Notiz": notiz}
            m_sum = st.session_state['zusatzkosten']['montage_mann'] * st.session_state['zusatzkosten']['montage_std'] * st.session_state['zusatzkosten']['montage_satz']
            k_sum = st.session_state['zusatzkosten']['kran']
            z_proz = st.session_state['zusatzkosten']['zuschlag_prozent']
            z_label = st.session_state['zusatzkosten']['zuschlag_label']
            
            if st.session_state['positionen'] or m_sum > 0 or k_sum > 0:
                # 1. KUNDEN PDF
                pdf_bytes = create_pdf(st.session_state['positionen'], st.session_state['kunden_daten'], fotos, m_sum, k_sum, zeige_details, z_proz, z_label, zuschlag_transparent)
                st.session_state['fertiges_pdf'] = pdf_bytes
                
                # 2. INTERNE PDF
                pdf_intern = create_internal_pdf(st.session_state['positionen'], st.session_state['kunden_daten'], st.session_state['zusatzkosten'])
                st.session_state['fertiges_intern_pdf'] = pdf_intern
                
                st.success("Erstellt!")
            else: st.error("Leer.")
            
        c_down1, c_down2 = st.columns(2)
        if st.session_state['fertiges_pdf']:
            c_down1.download_button("⬇️ Kostenschätzung (Kunde)", data=st.session_state['fertiges_pdf'], file_name="kostenschaetzung.pdf", mime="application/pdf", type="primary")
        if st.session_state['fertiges_intern_pdf']:
            c_down2.download_button("⬇️ Fertigungs-Liste (Intern)", data=st.session_state['fertiges_intern_pdf'], file_name="fertigung_erp.pdf", mime="application/pdf", type="secondary")

# TEIL C: ADMIN
elif menue_punkt == "🔐 Admin":
    st.title("Admin")
    pw = st.text_input("Passwort:", type="password")
    if pw == "1234":
        st.error("ACHTUNG: Reset löscht alle manuellen Excel-Änderungen!")
        if st.button("🚀 Katalog-Datei neu erstellen (Reset)", type="primary"):
            if generiere_neue_excel_datei(): st.success("Neu erstellt!"); st.cache_data.clear()
        st.markdown("---")
        sheets = lade_alle_blattnamen()
        if sheets:
            sh = st.selectbox("Blatt:", sheets)
            df = lade_blatt(sh)
            df_new = st.data_editor(df, num_rows="dynamic", use_container_width=True)
            if st.button("💾 Speichern"):
                if speichere_excel(df_new, sh): st.success("Gespeichert!"); st.cache_data.clear()
            st.markdown("---")
            with open(EXCEL_DATEI, "rb") as f: st.download_button("💾 Backup Excel", data=f, file_name="backup.xlsx")
    else: st.warning("Bitte Passwort eingeben.")
