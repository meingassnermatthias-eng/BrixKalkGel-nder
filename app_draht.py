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

# --- 2. PASSWORT SCHUTZ (Der Türsteher) ---
def check_password():
    """Returns `True` if the user had the correct password."""

    # Prüfen ob überhaupt ein Passwort im System hinterlegt ist
    if "password" not in st.secrets:
        st.error("⚠️ ACHTUNG: Es wurde noch kein Passwort in den Streamlit 'Secrets' hinterlegt.")
        st.info("Gehe auf share.streamlit.io -> App Settings -> Secrets und trage ein: password = \"DeinPasswort\"")
        return False

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Passwort aus dem Cache löschen
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # Erste Anzeige: Eingabefeld
        st.text_input(
            "🔒 Bitte Passwort eingeben:", 
            type="password", 
            on_change=password_entered, 
            key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        # Passwort war falsch
        st.text_input(
            "🔒 Bitte Passwort eingeben:", 
            type="password", 
            on_change=password_entered, 
            key="password"
        )
        st.error("😕 Passwort falsch")
        return False
    else:
        # Passwort war korrekt
        return True

# --- ZUGRIFFSPRÜFUNG ---
if not check_password():
    st.stop()  # HIER STOPPT DIE APP WENN PASSWORT FALSCH/FEHLT

# ---------------------------------------------------------
# AB HIER LÄUFT DIE NORMALE APP (NUR NACH LOGIN)
# ---------------------------------------------------------

# NOTFALL RESET
st.sidebar.header("Hilfe")
if st.sidebar.button("⚠️ Speicher leeren (Reset)", help="Klicken bei hartnäckigen Fehlern"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def setup_app_icon(image_file):
    if os.path.exists(image_file):
        try:
            with open(image_file, "rb") as f:
                data = f.read()
            encoded = base64.b64encode(data).decode()
            icon_html = f"""
            <link rel="apple-touch-icon" href="data:image/png;base64,{encoded}">
            <link rel="icon" type="image/png" href="data:image/png;base64,{encoded}">
            """
            st.markdown(icon_html, unsafe_allow_html=True)
            st.sidebar.image(image_file, width=200)
        except: pass

setup_app_icon(LOGO_DATEI)

# --- HELPER (Robust & Komma-Fixer) ---
def safe_float(value):
    """Wandelt Text sicher in Zahl um, egal ob Komma oder Punkt"""
    if pd.isna(value): return 0.0
    s_val = str(value).replace(',', '.').strip()
    try:
        return float(s_val)
    except:
        return 0.0

def clean_df_columns(df):
    if df is None: return pd.DataFrame()
    if not df.empty: 
        df.columns = df.columns.str.strip()
        rename_map = {'Formel / Info': 'Formel', 'Formel/Info': 'Formel', 'Info': 'Formel'}
        df.rename(columns=rename_map, inplace=True)
        if 'Variable' in df.columns:
            df = df.dropna(subset=['Variable'])
    return df

def lade_startseite():
    if not os.path.exists(EXCEL_DATEI): return pd.DataFrame()
    try: 
        df = pd.read_excel(EXCEL_DATEI, sheet_name="Startseite")
        return clean_df_columns(df)
    except: return pd.DataFrame()

def lade_blatt(blatt_name):
    if not os.path.exists(EXCEL_DATEI): return pd.DataFrame()
    try: 
        df = pd.read_excel(EXCEL_DATEI, sheet_name=blatt_name)
        return clean_df_columns(df)
    except: return pd.DataFrame()

def lade_alle_blattnamen():
    if not os.path.exists(EXCEL_DATEI): return []
    return pd.ExcelFile(EXCEL_DATEI).sheet_names

def speichere_excel(df, blatt_name):
    try:
        with pd.ExcelWriter(EXCEL_DATEI, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            df.to_excel(writer, sheet_name=blatt_name, index=False)
        return True
    except: return False

# --- SESSION STATE ---
def init_state():
    if 'positionen' not in st.session_state or st.session_state['positionen'] is None: 
        st.session_state['positionen'] = []
    if 'kunden_daten' not in st.session_state or st.session_state['kunden_daten'] is None: 
        st.session_state['kunden_daten'] = {"Name": "", "Strasse": "", "Ort": "", "Tel": "", "Email": "", "Notiz": ""}
    if 'fertiges_pdf' not in st.session_state: st.session_state['fertiges_pdf'] = None
    if 'fertiges_intern_pdf' not in st.session_state: st.session_state['fertiges_intern_pdf'] = None

    default_zk = {
        "kran": 0.0, "montage_mann": 2, "montage_std": 0.0, "montage_satz": 65.0,
        "zuschlag_prozent": 0.0, "zuschlag_label": "Normal"
    }
    if 'zusatzkosten' not in st.session_state or st.session_state['zusatzkosten'] is None:
        st.session_state['zusatzkosten'] = default_zk.copy()
    else:
        for k, v in default_zk.items():
            if k not in st.session_state['zusatzkosten']:
                st.session_state['zusatzkosten'][k] = v

init_state()

# --- PDF ENGINES ---
def clean_text(text):
    if text is None: return ""
    if not isinstance(text, str): text = str(text)
    text = text.replace("€", "EUR").replace("–", "-").replace("„", '"').replace("“", '"')
    try: return text.encode('latin-1', 'replace').decode('latin-1')
    except: return text

class PDF(FPDF):
    def header(self):
        if os.path.exists(LOGO_DATEI): 
            try: self.image(LOGO_DATEI, 10, 8, 60)
            except: pass
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
    
    if not kunden_dict: kunden_dict = {}
    
    pdf.ln(10); pdf.set_font("Arial", 'B', 12); pdf.cell(0, 6, "Kundeninformation:", ln=True); pdf.set_font("Arial", size=10)
    k_text = ""
    if kunden_dict.get("Name"): k_text += f"{kunden_dict['Name']}\n"
    if kunden_dict.get("Strasse"): k_text += f"{kunden_dict['Strasse']}\n"
    if kunden_dict.get("Ort"): k_text += f"{kunden_dict['Ort']}\n"
    k_text += "\n"
    if kunden_dict.get("Tel"): k_text += f"Tel: {kunden_dict['Tel']}\n"
    if kunden_dict.get("Email"): k_text += f"Email: {kunden_dict['Email']}\n"
    pdf.multi_cell(0, 5, clean_text(k_text))
    
    if kunden_dict.get("Notiz"):
        pdf.ln(5); pdf.set_font("Arial", 'B', 10); pdf.cell(0, 5, "Bemerkung / Notizen:", ln=True); pdf.set_font("Arial", size=10)
        pdf.multi_cell(0, 5, clean_text(kunden_dict["Notiz"]))
    pdf.ln(10)
    
    pdf.set_font("Arial", 'B', 10); pdf.set_fill_color(240, 240, 240)
    w_desc, w_menge, w_ep, w_gesamt = 100, 25, 30, 35
    pdf.cell(w_desc, 8, "Beschreibung", 1, 0, 'L', True)
    pdf.cell(w_menge, 8, "Menge", 1, 0, 'C', True)
    pdf.cell(w_ep, 8, "EP (EUR)", 1, 0, 'R', True)
    pdf.cell(w_gesamt, 8, "Gesamt", 1, 1, 'R', True)
    pdf.set_font("Arial", size=10)
    
    subtotal = 0
    for pos in positionen_liste:
        if not pos: continue
        raw_desc = str(pos.get('Beschreibung', ''))
        parts = raw_desc.split("|")
        main_title = parts[0].strip()
        details = ""
        if len(parts) > 1:
            details_raw = parts[1]
            details = "\n" + details_raw.replace(",", "\n -").strip()
            if not details.strip().startswith("-"): details = details.replace("\n", "\n - ", 1)
        
        if pos.get('RefMenge', 0) > 0:
            einheit_preis = pos['Einzelpreis'] / float(pos['RefMenge'])
            details += f"\n   (entspricht {einheit_preis:.2f} EUR / {pos.get('RefEinheit', 'Stk')})"

        final_desc_text = clean_text(f"{main_title}{details}")
        x_start, y_start = pdf.get_x(), pdf.get_y()
        pdf.multi_cell(w_desc, 5, final_desc_text, border=1, align='L')
        y_end = pdf.get_y(); row_height = y_end - y_start
        pdf.set_xy(x_start + w_desc, y_start)
        pdf.cell(w_menge, row_height, clean_text(str(pos.get('Menge', 0))), 1, 0, 'C')
        pdf.cell(w_ep, row_height, f"{pos.get('Einzelpreis', 0):.2f}", 1, 0, 'R')
        pdf.cell(w_gesamt, row_height, f"{pos.get('Preis', 0):.2f}", 1, 1, 'R')
        subtotal += pos.get('Preis', 0)

    zuschlag_wert = 0
    if zuschlag_prozent > 0:
        basis = subtotal + montage_summe + kran_summe
        zuschlag_wert = basis * (zuschlag_prozent / 100.0)

    versteckter_zuschlag = 0
    if zuschlag_prozent > 0 and not zuschlag_transparent:
        versteckter_zuschlag = zuschlag_wert
        zuschlag_wert = 0

    montage_final = montage_summe + versteckter_zuschlag
    if montage_final > 0:
        if zeige_details and not versteckter_zuschlag:
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
            except: pass
    return pdf.output(dest='S').encode('latin-1')

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
    
    if not kunden_dict: kunden_dict = {}
    if not zusatzkosten: zusatzkosten = {}

    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 8, f"Kunde: {clean_text(kunden_dict.get('Name', ''))} ({clean_text(kunden_dict.get('Ort', ''))})", 0, 1, 'L')
    pdf.set_font("Arial", '', 10)
    if kunden_dict.get('Notiz'):
        pdf.multi_cell(0, 5, clean_text(f"Notiz: {kunden_dict['Notiz']}"))
    pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(10, 8, "#", 1, 0, 'C', True)
    pdf.cell(140, 8, "Artikel & Material-Bedarf", 1, 0, 'L', True)
    pdf.cell(40, 8, "Kalk. Preis", 1, 1, 'R', True)
    pdf.set_font("Arial", '', 10)
    
    for i, pos in enumerate(positionen_liste):
        if not pos: continue
        raw_desc = str(pos.get('Beschreibung', ''))
        parts = raw_desc.split("|")
        titel = parts[0].strip()
        params = ""
        if len(parts) > 1:
            params = parts[1].replace(", ", "\n  - ").strip()
            if not params.startswith("-"): params = "  - " + params
            
        full_text = f"{titel} (Parameter):\n{params}"
        if pos.get('MaterialDetails'):
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
        pdf.cell(40, row_height, f"{pos.get('Preis', 0):.2f}", 1, 1, 'R')
        
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 8, "Zusatzkosten-Check:", 0, 1, 'L')
    pdf.set_font("Arial", '', 10)
    
    text_zusatz = f"- Montage: {zusatzkosten.get('montage_mann',0)} Mann x {zusatzkosten.get('montage_std',0)} Std (Satz: {zusatzkosten.get('montage_satz',0)} EUR)\n"
    text_zusatz += f"- Kran: {zusatzkosten.get('kran',0)} EUR\n"
    text_zusatz += f"- Erschwernis: {zusatzkosten.get('zuschlag_label','')} ({zusatzkosten.get('zuschlag_prozent',0)}%)"
    
    pdf.multi_cell(0, 5, clean_text(text_zusatz), 1)
    return pdf.output(dest='S').encode('latin-1')

# --- NAVIGATION ---
st.sidebar.header("Navigation")
index_df = lade_startseite()

katalog_items = []
if index_df is not None and not index_df.empty and 'Kategorie' in index_df.columns:
    kategorien = index_df['Kategorie'].unique()
    wahl_kategorie = st.sidebar.selectbox("Filter Kategorie:", kategorien)
    katalog_items = index_df[index_df['Kategorie'] == wahl_kategorie]['System'].tolist()

menue_punkt = st.sidebar.radio("Gehe zu:", ["📂 Konfigurator / Katalog", "🛒 Warenkorb / Abschluss", "🔐 Admin"])
st.sidebar.markdown("---")

# TEIL A: KONFIGURATOR
if menue_punkt == "📂 Konfigurator / Katalog":
    st.title("Artikel Konfigurator")
    if katalog_items:
        auswahl_system = st.selectbox("System wählen:", katalog_items)
        
        row = pd.DataFrame()
        if index_df is not None and not index_df.empty:
            row = index_df[(index_df['System'] == auswahl_system)]
            if 'Kategorie' in index_df.columns and 'wahl_kategorie' in locals():
                row = row[row['Kategorie'] == wahl_kategorie]
            
        if not row.empty:
            blatt = row.iloc[0]['Blattname']
            df_config = lade_blatt(blatt)
            col_konfig, col_mini_cart = st.columns([2, 1])
            with col_konfig:
                st.subheader(f"Konfiguration: {auswahl_system}")
                
                if df_config is None or df_config.empty: 
                    st.warning("Katalog-Blatt ist leer oder nicht gefunden.")
                elif 'Formel' not in df_config.columns: 
                    st.error("Fehler: Spalte 'Formel' fehlt in Excel.")
                else:
                    try:
                        vars_calc = {}; desc_parts = []
                        for index, zeile in df_config.iterrows():
                            if pd.isna(zeile.get('Typ')): continue 
                            
                            typ = str(zeile.get('Typ', '')).strip().lower()
                            label = str(zeile.get('Bezeichnung', 'Unbenannt'))
                            var_name = str(zeile.get('Variable', '')).strip()
                            
                            if typ == 'zahl':
                                raw_val = str(zeile.get('Optionen', '')).strip()
                                std_val = safe_float(raw_val)
                                
                                val = st.number_input(label, value=std_val, step=1.0, key=f"{blatt}_{index}")
                                vars_calc[var_name] = val
                                if val != 0: desc_parts.append(f"{label}: {val}")
                            
                            elif typ == 'auswahl':
                                raw_opts = str(zeile.get('Optionen', '')).split(',')
                                opts_dict = {}; opts_names = []
                                
                                if not raw_opts or (len(raw_opts) == 1 and raw_opts[0] == ''):
                                    st.error(f"❌ FEHLER in Zeile '{label}': Keine Optionen gefunden!")
                                    st.code(f"Gelesener Wert im Excel: '{zeile.get('Optionen', '')}'", language="text")
                                else:
                                    for opt in raw_opts:
                                        if ':' in opt:
                                            n, v = opt.split(':')
                                            opts_dict[n.strip()] = safe_float(v)
                                            opts_names.append(n.strip())
                                        else:
                                            opts_dict[opt.strip()] = 0
                                            opts_names.append(opt.strip())
                                    
                                    if opts_names:
                                        wahl = st.selectbox(label, opts_names, key=f"{blatt}_{index}")
                                        vars_calc[var_name] = opts_dict.get(wahl, 0)
                                        desc_parts.append(f"{label}: {wahl}")
                                    else:
                                        st.warning(f"Dropdown '{label}' ist leer. Prüfe Syntax 'Text:Preis, Text:Preis'")
                            
                            elif typ == 'mehrfach':
                                raw_opts = str(zeile.get('Optionen', '')).split(',')
                                opts_dict = {}; opts_names = []
                                for opt in raw_opts:
                                    if ':' in opt:
                                        n, v = opt.split(':')
                                        opts_dict[n.strip()] = safe_float(v)
                                        opts_names.append(n.strip())
                                    else:
                                        opts_dict[opt.strip()] = 0
                                        opts_names.append(opt.strip())
                                wahl_liste = st.multiselect(label, opts_names, key=f"{blatt}_{index}")
                                summe_wahl = sum(opts_dict.get(x, 0) for x in wahl_liste)
                                vars_calc[var_name] = summe_wahl
                                if wahl_liste: desc_parts.append(f"{label}: {', '.join(wahl_liste)}")

                            elif typ == 'berechnung':
                                formel = str(zeile.get('Formel', ''))
                                try:
                                    safe_env = {"__builtins__": None, "math": math, "round": round, "int": int, "float": float}
                                    safe_env.update(vars_calc)
                                    calc_val = eval(formel, safe_env)
                                    vars_calc[var_name] = calc_val
                                except Exception as e:
                                    vars_calc[var_name] = 0

                            elif typ == 'preis':
                                formel = str(zeile.get('Formel', ''))
                                st.markdown("---")
                                safe_env = {"__builtins__": None, "math": math, "round": round, "int": int, "float": float}
                                safe_env.update(vars_calc)
                                try:
                                    preis = eval(formel, safe_env)
                                    st.subheader(f"Preis: {preis:.2f} €")
                                    
                                    with st.expander("ℹ️ Details zur Berechnung (Debug)", expanded=False):
                                        st.write("Variablen:")
                                        st.json(vars_calc)

                                    if st.button("In den Warenkorb", type="primary"):
                                        full_desc = f"{auswahl_system} | " + ", ".join(desc_parts)
                                        
                                        ref_menge = 1.0; ref_einheit = "Stk"
                                        if 'L' in vars_calc and vars_calc['L'] > 0:
                                            ref_menge = vars_calc['L']; ref_einheit = "lfm"
                                        elif 'H' in vars_calc and vars_calc['H'] > 0:
                                            ref_menge = vars_calc['H']; ref_einheit = "lfm Höhe"
                                        elif 'L_Podest' in vars_calc and 'B' in vars_calc and vars_calc['L_Podest'] > 0:
                                            ref_menge = vars_calc['L_Podest'] * vars_calc['B']; ref_einheit = "m²"
                                        
                                        mat_liste = []
                                        # --- INTELLIGENTE MATERIAL-LISTE ---
                                        if 'L' in vars_calc and vars_calc['L'] > 0:
                                            l = vars_calc['L']
                                            
                                            # Fall 1: Terrassenüberdachung
                                            if 'N_Spar' in vars_calc:
                                                b = vars_calc.get('B', 0)
                                                h = vars_calc.get('H', 0)
                                                n_col = int(vars_calc.get('N_Col', 0))
                                                n_spar = int(vars_calc.get('N_Spar', 0))
                                                
                                                dachflaeche = l * b
                                                stahl_lfm = (n_col * h) + (n_spar * b) + l
                                                stahl_flaeche = stahl_lfm * 0.4
                                                
                                                mat_liste.append(f"Dachfläche (Glas/Folie): {dachflaeche:.2f} m²")
                                                mat_liste.append(f"Säulen: {n_col} Stk | Sparren: {n_spar} Stk")
                                                mat_liste.append(f"Laufmeter Stahlprofile (Gesamt): {stahl_lfm:.2f} m")
                                                mat_liste.append(f"Oberfläche Stahl (ca. Beschichtung): {stahl_flaeche:.2f} m²")

                                            # Fall 2: Horizontal Geländer
                                            elif 'N_Rows' in vars_calc:
                                                h = vars_calc.get('H', 0)
                                                n_steher = int(vars_calc.get('N_Steher', 0))
                                                n_rows = int(vars_calc.get('N_Rows', 0))
                                                
                                                mat_liste.append(f"Steher: {n_steher} Stk")
                                                mat_liste.append(f"Füllung: {n_rows} Reihen")
                                                mat_liste.append(f"Laufmeter Füllung: {(l * n_rows):.2f} m")
                                                mat_liste.append(f"Ansichtsfläche: {(l * h):.2f} m²")

                                            # Fall 3: Standard Zäune/Geländer
                                            elif 'Treppe' not in str(auswahl_system) and 'N_Col' not in vars_calc:
                                                abstand = 1.3 
                                                if 'Dist' in vars_calc and vars_calc['Dist'] > 0: abstand = vars_calc['Dist']
                                                elif 'Edelstahl' in auswahl_system: abstand = 1.2
                                                elif 'Draht' in auswahl_system: abstand = 2.5
                                                anz_steher = math.ceil(l / abstand) + 1
                                                mat_liste.append(f"Steher (kalkuliert): {anz_steher} Stk")
                                                if 'H' in vars_calc:
                                                    mat_liste.append(f"Ansichtsfläche: {(l * vars_calc['H']):.2f} m²")

                                        # Fall 4: Treppen (Nur wenn explizit H da und keine anderen Indikatoren)
                                        if 'H' in vars_calc and vars_calc['H'] > 0:
                                            if 'N_Spar' not in vars_calc and 'N_Rows' not in vars_calc and 'Treppe' in str(auswahl_system):
                                                h = vars_calc['H']
                                                stufen = math.ceil(h / 0.18)
                                                mat_liste.append(f"Stufen (H/18cm): {stufen} Stk")

                                        # Beton / Ecken (Immer prüfen)
                                        if 'Ist_Beton' in vars_calc:
                                            if vars_calc['Ist_Beton'] == 1:
                                                mat_liste.append(f"Beton (2/Steher): {anz_steher * 2} Säcke")
                                            else:
                                                mat_liste.append(f"Dübelplatten: {anz_steher} Stk")
                                        if 'Ecken' in vars_calc and vars_calc['Ecken'] > 0:
                                            mat_liste.append(f"Eck-Verbinder: {int(vars_calc['Ecken'])} Stk")

                                        st.session_state['positionen'].append({
                                            "Beschreibung": full_desc, "Menge": 1.0, 
                                            "Einzelpreis": preis, "Preis": preis,
                                            "RefMenge": ref_menge, "RefEinheit": ref_einheit,
                                            "MaterialDetails": mat_liste
                                        })
                                        st.success("Hinzugefügt!")
                                except NameError as ne:
                                    st.error(f"⚠️ FEHLER IN EXCEL-FORMEL: {str(ne)}")
                                    st.info(f"Variablen-Namen prüfen! Groß-/Kleinschreibung beachten.")
                                except Exception as calc_err:
                                    st.error(f"Berechnungsfehler: {str(calc_err)}")

                    except Exception as e:
                        st.error(f"⚠️ Allgemeiner Fehler im Blatt '{blatt}': {str(e)}")

            with col_mini_cart:
                st.info("🛒 Schnell-Check")
                if st.session_state['positionen']:
                    cnt = len(st.session_state['positionen']); sum_live = sum(p.get('Preis',0) for p in st.session_state['positionen'])
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
                short_desc = pos.get('Beschreibung', 'Artikel').split("|")[0]
                c1.write(f"**{short_desc}**"); 
                with c1.expander("Details"): st.write(pos.get('Beschreibung', ''))
                neue_menge = c2.number_input("Menge", value=float(pos.get('Menge', 1.0)), step=1.0, key=f"qty_{i}", label_visibility="collapsed")
                if neue_menge != pos.get('Menge'):
                    st.session_state['positionen'][i]['Menge'] = neue_menge
                    st.session_state['positionen'][i]['Preis'] = neue_menge * pos.get('Einzelpreis', 0)
                    st.rerun()
                c3.write(f"{pos.get('Preis', 0):.2f} €")
                if c4.button("🗑️", key=f"del_{i}"): indices_to_delete.append(i)
            if indices_to_delete:
                for index in sorted(indices_to_delete, reverse=True): del st.session_state['positionen'][index]
                st.session_state['fertiges_pdf'] = None; st.session_state['fertiges_intern_pdf'] = None; st.rerun()
            st.markdown("---")
            
            total_artikel = sum(p.get('Preis',0) for p in st.session_state['positionen'])
            zk = st.session_state.get('zusatzkosten', {})
            if zk is None: zk = {}
            
            m_sum = zk.get('montage_mann',0) * zk.get('montage_std',0) * zk.get('montage_satz',0)
            k_sum = zk.get('kran',0)
            z_proz = zk.get('zuschlag_prozent',0)
            
            basis = total_artikel + m_sum + k_sum
            zuschlag_wert = basis * (z_proz / 100.0)
            end_summe = basis + zuschlag_wert

            if m_sum > 0: st.write(f"➕ Montage: **{m_sum:.2f} €**")
            if k_sum > 0: st.write(f"➕ Kran: **{k_sum:.2f} €**")
            
            if z_proz > 0:
                st.write(f"---")
                label = zk.get('zuschlag_label', 'Normal')
                st.write(f"➕ Erschwernis ({label}): **{zuschlag_wert:.2f} €**")
                
            st.markdown(f"### Netto: {end_summe:.2f} €")
            st.caption(f"Brutto (inkl. {int(MWST_SATZ*100)}%): {(end_summe * (1+MWST_SATZ)):.2f} €")
            
            if st.button("Alles löschen", type="secondary"): st.session_state['positionen'] = []; st.rerun()
        else: st.info("Leer.")

    with col_daten:
        with st.expander("🏗️ Montage & Zusatzkosten", expanded=True):
            st.write("**Montage-Rechner**")
            c_m1, c_m2, c_m3 = st.columns(3)
            if 'zusatzkosten' not in st.session_state or st.session_state['zusatzkosten'] is None: st.session_state['zusatzkosten'] = {}
            zk = st.session_state['zusatzkosten']
            
            st.session_state['zusatzkosten']['montage_mann'] = c_m1.number_input("Mann", value=int(zk.get('montage_mann', 2)), step=1)
            st.session_state['zusatzkosten']['montage_std'] = c_m2.number_input("Std", value=float(zk.get('montage_std', 0.0)), step=1.0)
            st.session_state['zusatzkosten']['montage_satz'] = c_m3.number_input("Satz €", value=float(zk.get('montage_satz', 65.0)), step=5.0)
            
            zeige_details = st.checkbox("Details (Stunden/Satz) im PDF anzeigen?", value=True)
            
            st.markdown("---")
            st.session_state['zusatzkosten']['kran'] = st.number_input("Kran Pauschale €", value=float(zk.get('kran', 0.0)), step=50.0)
            
            # --- ZUSCHLAG SCHIEBER ---
            st.markdown("---")
            st.write("**Erschwernis / Risiko**")
            
            stufen = {"Normal": 0.0, "Schwierig": 10.0, "Sehr kompliziert": 20.0}
            current_label = zk.get('zuschlag_label', "Normal")
            if current_label not in stufen: current_label = "Normal"
            
            wahl_schwierigkeit = st.select_slider("Baustellen-Schwierigkeit:", options=list(stufen.keys()), value=current_label)
            
            st.session_state['zusatzkosten']['zuschlag_prozent'] = stufen[wahl_schwierigkeit]
            st.session_state['zusatzkosten']['zuschlag_label'] = wahl_schwierigkeit
            
            if st.session_state['zusatzkosten']['zuschlag_prozent'] > 0:
                zuschlag_transparent = st.checkbox("Auf PDF ausweisen?", value=True, help="Häkchen WEG = Aufschlag wird unsichtbar in Montage eingerechnet")
            else:
                zuschlag_transparent = True
        
        st.subheader("Kundendaten")
        with st.form("abschluss"):
            kd = st.session_state.get('kunden_daten', {})
            c1, c2 = st.columns(2)
            name = c1.text_input("Name", value=kd.get('Name', ''))
            strasse = c2.text_input("Straße", value=kd.get('Strasse', ''))
            c3, c4 = st.columns(2)
            ort = c3.text_input("Ort", value=kd.get('Ort', ''))
            tel = c4.text_input("Tel", value=kd.get('Tel', ''))
            email = st.text_input("Email", value=kd.get('Email', ''))
            notiz = st.text_area("Notiz", value=kd.get('Notiz', ''))
            st.markdown("---")
            fotos = st.file_uploader("Fotos", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])
            submitted = st.form_submit_button("💾 PDFs Generieren")
        if submitted:
            st.session_state['kunden_daten'] = {"Name": name, "Strasse": strasse, "Ort": ort, "Tel": tel, "Email": email, "Notiz": notiz}
            # Calc sums
            zk = st.session_state['zusatzkosten']
            m_sum = zk.get('montage_mann',0) * zk.get('montage_std',0) * zk.get('montage_satz',0)
            k_sum = zk.get('kran',0)
            z_proz = zk.get('zuschlag_prozent',0)
            z_label = zk.get('zuschlag_label','Normal')
            
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
