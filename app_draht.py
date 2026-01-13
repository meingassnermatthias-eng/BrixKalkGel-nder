import streamlit as st
import pandas as pd
from fpdf import FPDF
import base64
import os
import tempfile
import math
from datetime import datetime # <--- NEU: Für das Datum

# --- 1. SETUP & KONFIGURATION ---
LOGO_DATEI = "Meingassner Metalltechnik 2023.png"
EXCEL_DATEI = "katalog.xlsx"

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
        st.sidebar.warning("Logo Datei nicht gefunden.")

setup_app_icon(LOGO_DATEI)

# --- 2. EXCEL LOGIK ---
def clean_df_columns(df):
    if not df.empty: 
        df.columns = df.columns.str.strip()
        rename_map = {
            'Formel / Info': 'Formel',
            'Formel/Info': 'Formel',
            'Info': 'Formel',
            'Preisfindung': 'Formel'
        }
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
        st.error(f"Fehler beim Speichern: {e}")
        return False

# --- 3. SESSION STATE ---
if 'positionen' not in st.session_state: st.session_state['positionen'] = []
if 'kunden_daten' not in st.session_state: 
    st.session_state['kunden_daten'] = {"Name": "", "Strasse": "", "Ort": "", "Tel": "", "Email": "", "Notiz": ""}
if 'fertiges_pdf' not in st.session_state:
    st.session_state['fertiges_pdf'] = None

# --- 4. PDF ENGINE ---
def clean_text(text):
    if not isinstance(text, str): text = str(text)
    # Euro, Bindestriche und Anführungszeichen ersetzen
    text = text.replace("€", "EUR").replace("–", "-").replace("„", '"').replace("“", '"')
    # latin-1 encoding stellt sicher, dass ä, ö, ü funktionieren
    return text.encode('latin-1', 'replace').decode('latin-1')

class PDF(FPDF):
    def header(self):
        if os.path.exists(LOGO_DATEI):
            self.image(LOGO_DATEI, 10, 8, 60)
        
        self.set_font('Arial', 'B', 16) # Schrift etwas kleiner damit Datum Platz hat
        
        # --- HIER IST DIE ÄNDERUNG: Datum einfügen ---
        heute = datetime.now().strftime("%d.%m.%Y")
        titel = f"Kostenschätzung vom {heute}"
        
        # Titel rechtsbündig
        self.cell(0, 18, clean_text(titel), 0, 1, 'R')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Seite {self.page_no()}', 0, 0, 'C')

def create_pdf(positionen_liste, kunden_dict, fotos):
    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Firmenkopf
    pdf.set_font("Arial", size=10)
    pdf.ln(5)
    
    # --- KUNDENDATEN ---
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 6, "Kundeninformation:", ln=True)
    pdf.set_font("Arial", size=10)
    
    k_text = ""
    if kunden_dict["Name"]: k_text += f"{kunden_dict['Name']}\n"
    if kunden_dict["Strasse"]: k_text += f"{kunden_dict['Strasse']}\n"
    if kunden_dict["Ort"]: k_text += f"{kunden_dict['Ort']}\n"
    k_text += "\n"
    if kunden_dict["Tel"]: k_text += f"Tel: {kunden_dict['Tel']}\n"
    if kunden_dict["Email"]: k_text += f"Email: {kunden_dict['Email']}\n"
    
    pdf.multi_cell(0, 5, clean_text(k_text))
    
    if kunden_dict["Notiz"]:
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 5, "Bemerkung / Notizen:", ln=True)
        pdf.set_font("Arial", size=10)
        pdf.multi_cell(0, 5, clean_text(kunden_dict["Notiz"]))

    pdf.ln(10)
    
    # --- TABELLE ---
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(240, 240, 240)
    
    w_desc, w_menge, w_ep, w_gesamt = 100, 25, 30, 35
    
    pdf.cell(w_desc, 8, "Beschreibung", 1, 0, 'L', True)
    pdf.cell(w_menge, 8, "Menge", 1, 0, 'C', True)
    pdf.cell(w_ep, 8, "EP (EUR)", 1, 0, 'R', True)
    pdf.cell(w_gesamt, 8, "Gesamt", 1, 1, 'R', True)
    
    pdf.set_font("Arial", size=10)
    gesamt_summe = 0
    
    for pos in positionen_liste:
        raw_desc = str(pos['Beschreibung'])
        parts = raw_desc.split("|")
        main_title = parts[0].strip()
        details = ""
        if len(parts) > 1:
            details_raw = parts[1]
            details = "\n" + details_raw.replace(",", "\n -").strip()
            if not details.strip().startswith("-"):
                details = details.replace("\n", "\n - ", 1)

        final_desc_text = clean_text(f"{main_title}{details}")
        
        # Zeilenhöhe berechnen
        x_start, y_start = pdf.get_x(), pdf.get_y()
        pdf.multi_cell(w_desc, 5, final_desc_text, border=1, align='L')
        y_end = pdf.get_y()
        row_height = y_end - y_start
        
        pdf.set_xy(x_start + w_desc, y_start)
        pdf.cell(w_menge, row_height, clean_text(str(pos['Menge'])), 1, 0, 'C')
        pdf.cell(w_ep, row_height, f"{pos['Einzelpreis']:.2f}", 1, 0, 'R')
        pdf.cell(w_gesamt, row_height, f"{pos['Preis']:.2f}", 1, 1, 'R')
        
        gesamt_summe += pos['Preis']

    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(w_desc + w_menge + w_ep, 10, "Gesamtsumme:", 0, 0, 'R')
    pdf.cell(w_gesamt, 10, f"{gesamt_summe:.2f} EUR", 1, 1, 'R')

    # --- FOTOS ---
    if fotos:
        pdf.add_page()
        pdf.cell(0, 10, "Baustellen-Dokumentation / Fotos", 0, 1, 'L')
        for foto_upload in fotos:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
                    tmp_file.write(foto_upload.getvalue())
                    tmp_path = tmp_file.name
                
                if pdf.get_y() > 180: pdf.add_page()
                pdf.image(tmp_path, w=160)
                pdf.ln(10)
                os.unlink(tmp_path)
            except Exception as e:
                pdf.cell(0, 10, f"Fehler beim Bild: {str(e)}", ln=True)

    return pdf.output(dest='S').encode('latin-1')

# --- 5. HAUPT-NAVIGATION ---
st.sidebar.header("Navigation")

index_df = lade_startseite()
katalog_items = []
if not index_df.empty and 'System' in index_df.columns:
    katalog_items = index_df['System'].tolist()

menue_punkt = st.sidebar.radio(
    "Gehe zu:",
    ["📂 Konfigurator / Katalog", "🛒 Warenkorb / Abschluss", "🔐 Admin"]
)

st.sidebar.markdown("---")

# --- TEIL A: KONFIGURATOR ---
if menue_punkt == "📂 Konfigurator / Katalog":
    st.title("Artikel Konfigurator")
    
    if katalog_items:
        auswahl_system = st.selectbox("System wählen:", katalog_items)
    else:
        st.warning("Keine Systeme gefunden. Bitte im Admin oder Excel 'Startseite' anlegen.")
        auswahl_system = None

    if auswahl_system:
        row = index_df[index_df['System'] == auswahl_system]
        if not row.empty:
            blatt = row.iloc[0]['Blattname']
            df_config = lade_blatt(blatt)
            
            col_konfig, col_mini_cart = st.columns([2, 1])
            
            with col_konfig:
                st.subheader(f"Konfiguration: {auswahl_system}")
                
                if df_config.empty:
                    st.warning("Dieses Blatt ist noch leer.")
                elif 'Formel' not in df_config.columns:
                    st.error(f"Fehler: Die Spalte 'Formel' fehlt im Blatt '{blatt}'!")
                else:
                    vars_calc = {}
                    desc_parts = []
                    
                    for index, zeile in df_config.iterrows():
                        typ = str(zeile.get('Typ', '')).strip().lower()
                        label = str(zeile.get('Bezeichnung', 'Unbenannt'))
                        var_name = str(zeile.get('Variable', '')).strip()
                        
                        if typ == 'zahl':
                            val = st.number_input(label, value=0.0, step=0.1, key=f"{blatt}_{index}")
                            vars_calc[var_name] = val
                            if val > 0: desc_parts.append(f"{label}: {val}")
                        
                        elif typ == 'auswahl':
                            raw_opts = str(zeile.get('Optionen', '')).split(',')
                            opts_dict = {}
                            opts_names = []
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
                                    st.session_state['positionen'].append({
                                        "Beschreibung": full_desc, "Menge": 1.0, 
                                        "Einzelpreis": preis, "Preis": preis
                                    })
                                    st.success("Hinzugefügt! Weiter zum Warenkorb.")
                                    
                            except NameError as e:
                                st.error(f"⚠️ Berechnungsfehler: {e}")
                            except Exception as e:
                                st.error(f"⚠️ Fehler: {e}")
            
            with col_mini_cart:
                st.info("🛒 Schnell-Übersicht")
                if st.session_state['positionen']:
                    cnt = len(st.session_state['positionen'])
                    sum_live = sum(p['Preis'] for p in st.session_state['positionen'])
                    st.write(f"**{cnt} Pos.** | **{sum_live:.2f} €**")
                else:
                    st.write("Warenkorb leer")

# --- TEIL B: WARENKORB ---
elif menue_punkt == "🛒 Warenkorb / Abschluss":
    st.title("🛒 Warenkorb & Abschluss")
    col_liste, col_daten = st.columns([1, 1])
    
    with col_liste:
        st.subheader("Artikel Liste")
        if st.session_state['positionen']:
            df_cart = pd.DataFrame(st.session_state['positionen'])
            st.dataframe(df_cart[['Beschreibung', 'Preis']], hide_index=True)
            total = sum(p['Preis'] for p in st.session_state['positionen'])
            st.markdown(f"### Gesamt: {total:.2f} €")
            if st.button("Alles löschen", type="secondary"):
                st.session_state['positionen'] = []
                st.session_state['fertiges_pdf'] = None
                st.rerun()
        else:
            st.info("Warenkorb leer.")

    with col_daten:
        st.subheader("Kundendaten")
        with st.form("abschluss_form"):
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
            submitted = st.form_submit_button("💾 PDF Generieren")
            
        if submitted:
            st.session_state['kunden_daten'] = {
                "Name": name, "Strasse": strasse, "Ort": ort, 
                "Tel": tel, "Email": email, "Notiz": notiz
            }
            if st.session_state['positionen']:
                pdf_bytes = create_pdf(st.session_state['positionen'], st.session_state['kunden_daten'], fotos)
                st.session_state['fertiges_pdf'] = pdf_bytes
                st.success("PDF erstellt!")
            else:
                st.error("Keine Artikel im Korb.")

        if st.session_state['fertiges_pdf']:
            st.download_button("⬇️ PDF Herunterladen", data=st.session_state['fertiges_pdf'], file_name="kostenschaetzung.pdf", mime="application/pdf", type="primary")

# --- TEIL C: ADMIN ---
elif menue_punkt == "🔐 Admin":
    st.title("Admin Bereich")
    pw = st.text_input("Passwort:", type="password")
    if pw == "1234":
        sheets = lade_alle_blattnamen()
        if sheets:
            sh = st.selectbox("Blatt bearbeiten:", sheets)
            df = lade_blatt(sh)
            st.info("Reihenfolge ändern? Bitte Excel am PC bearbeiten.")
            df_new = st.data_editor(df, num_rows="dynamic", use_container_width=True)
            if st.button("Speichern"):
                if speichere_excel(df_new, sh): 
                    st.success("Gespeichert!")
                    st.cache_data.clear()
        else:
            st.warning("Keine Excel-Datei.")
