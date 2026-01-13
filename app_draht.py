import streamlit as st
import pandas as pd
from fpdf import FPDF
import base64
import os
import tempfile

# --- 1. SETUP & HANDY ICON ---
st.set_page_config(page_title="Meingassner App", layout="wide", page_icon="logo.png")

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
        st.sidebar.image(image_file, width=150)

setup_app_icon("logo.png")

# --- 2. EXCEL LOGIK ---
DATEI_NAME = "katalog.xlsx"

def clean_df_columns(df):
    if not df.empty: 
        df.columns = df.columns.str.strip()
        # --- FIX: Automatische Umbenennung, falls die Spalte "Formel / Info" heißt ---
        rename_map = {
            'Formel / Info': 'Formel',
            'Formel/Info': 'Formel',
            'Info': 'Formel'
        }
        df.rename(columns=rename_map, inplace=True)
    return df

def lade_startseite():
    if not os.path.exists(DATEI_NAME): return pd.DataFrame()
    try: return clean_df_columns(pd.read_excel(DATEI_NAME, sheet_name="Startseite"))
    except: return pd.DataFrame()

def lade_blatt(blatt_name):
    if not os.path.exists(DATEI_NAME): return pd.DataFrame()
    try: return clean_df_columns(pd.read_excel(DATEI_NAME, sheet_name=blatt_name))
    except: return pd.DataFrame()

def lade_alle_blattnamen():
    if not os.path.exists(DATEI_NAME): return []
    return pd.ExcelFile(DATEI_NAME).sheet_names

def speichere_excel(df, blatt_name):
    try:
        with pd.ExcelWriter(DATEI_NAME, engine="openpyxl", mode="a" if os.path.exists(DATEI_NAME) else "w", if_sheet_exists="replace") as writer:
            df.to_excel(writer, sheet_name=blatt_name, index=False)
        return True
    except Exception as e:
        st.error(f"Fehler: {e}")
        return False

# --- 3. SESSION STATE ---
if 'positionen' not in st.session_state: st.session_state['positionen'] = []
if 'kunden_daten' not in st.session_state: 
    st.session_state['kunden_daten'] = {"Name": "", "Strasse": "", "Ort": "", "Tel": "", "Email": "", "Notiz": ""}
if 'fertiges_pdf' not in st.session_state:
    st.session_state['fertiges_pdf'] = None

# --- 4. PDF ENGINE ---
class PDF(FPDF):
    def header(self):
        if os.path.exists("logo.png"):
            self.image("logo.png", 10, 8, 40)
        self.set_font('Arial', 'B', 20)
        self.cell(0, 10, 'Angebot', 0, 1, 'C')
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Seite {self.page_no()}', 0, 0, 'C')

def clean_text(text):
    if not isinstance(text, str): text = str(text)
    # WICHTIG: Ersetzt Euro und Bindestriche, damit PDF nicht abstürzt
    text = text.replace("€", "EUR").replace("–", "-")
    return text.encode('latin-1', 'replace').decode('latin-1')

def create_pdf(positionen_liste, kunden_dict, fotos):
    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Firmenkopf
    pdf.set_font("Arial", size=10)
    pdf.ln(5)
    pdf.cell(0, 5, clean_text("Meingassner Metalltechnik"), ln=True)
    pdf.cell(0, 5, clean_text("Ihr Spezialist für Metallbau"), ln=True)
    
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
        # Layout Text
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
        
        # Cursor zurücksetzen
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
                
                if pdf.get_y() > 200: pdf.add_page()
                pdf.image(tmp_path, w=150)
                pdf.ln(10)
                os.unlink(tmp_path)
            except Exception as e:
                pdf.cell(0, 10, f"Fehler beim Bild: {str(e)}", ln=True)

    return pdf.output(dest='S').encode('latin-1')

# --- 5. MENÜ STRUKTUR ---
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
        auswahl_system = st.selectbox("Wähle System:", katalog_items)
    else:
        st.warning("Keine Systeme gefunden (Excel leer?).")
        auswahl_system = None

    if auswahl_system:
        row = index_df[index_df['System'] == auswahl_system]
        if not row.empty:
            blatt = row.iloc[0]['Blattname']
            df_config = lade_blatt(blatt)
            
            col_konfig, col_mini_cart = st.columns([2, 1])
            
            with col_konfig:
                st.subheader(f"Konfiguration: {auswahl_system}")
                
                # Prüfen auf Pflichtfelder (Formel Spalte wird durch clean_df_columns repariert)
                if df_config.empty:
                    st.error("Blatt ist leer.")
                elif 'Formel' not in df_config.columns:
                    st.error(f"Spalte 'Formel' fehlt! (Gefunden: {list(df_config.columns)})")
                else:
                    vars_calc = {}
                    desc_parts = []
                    
                    for index, zeile in df_config.iterrows():
                        typ = str(zeile['Typ']).strip().lower()
                        label = str(zeile['Bezeichnung'])
                        var_name = str(zeile['Variable'])
                        
                        if typ == 'zahl':
                            val = st.number_input(label, value=0.0, step=0.1, key=f"{blatt}_{index}")
                            vars_calc[var_name] = val
                            if val > 0: desc_parts.append(f"{label}: {val}")
                        
                        elif typ == 'auswahl':
                            raw_opts = str(zeile['Optionen']).split(',')
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
                            vars_calc[var_name] = opts_dict[wahl]
                            desc_parts.append(f"{label}: {wahl}")

                        elif typ == 'preis':
                            formel = str(zeile['Formel'])
                            st.markdown("---")
                            try:
                                preis = eval(formel, {"__builtins__": None}, vars_calc)
                                st.subheader(f"Preis: {preis:.2f} €")
                                if st.button("In den Warenkorb", type="primary"):
                                    full_desc = f"{auswahl_system} | " + ", ".join(desc_parts)
                                    st.session_state['positionen'].append({
                                        "Beschreibung": full_desc,
                                        "Menge": 1.0, "Einzelpreis": preis, "Preis": preis
                                    })
                                    st.success("Hinzugefügt! Weiter zum Warenkorb.")
                            except Exception as e:
                                st.error("Fehler in der Formel.")
                                st.write(f"Details: {e}")
            
            with col_mini_cart:
                st.info("Aktuelle Positionen:")
                if st.session_state['positionen']:
                    cnt = len(st.session_state['positionen'])
                    sum_live = sum(p['Preis'] for p in st.session_state['positionen'])
                    st.write(f"**{cnt} Artikel** | Summe: **{sum_live:.2f} €**")
                else:
                    st.write("(Leer)")

# --- TEIL B: WARENKORB ---
elif menue_punkt == "🛒 Warenkorb / Abschluss":
    st.title("🛒 Warenkorb & Abschluss")
    
    col_liste, col_daten = st.columns([1, 1])
    
    with col_liste:
        st.subheader("Artikel")
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
            st.info("Leer.")

    with col_daten:
        st.subheader("Kundendaten & Fotos")
        
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
            fotos = st.file_uploader("Fotos anhängen", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])
            
            submitted = st.form_submit_button("💾 PDF Generieren")
            
        if submitted:
            st.session_state['kunden_daten'] = {
                "Name": name, "Strasse": strasse, "Ort": ort, 
                "Tel": tel, "Email": email, "Notiz": notiz
            }
            if st.session_state['positionen']:
                pdf_bytes = create_pdf(
                    st.session_state['positionen'], 
                    st.session_state['kunden_daten'],
                    fotos
                )
                st.session_state['fertiges_pdf'] = pdf_bytes
                st.success("PDF erstellt!")
            else:
                st.error("Warenkorb leer.")

        if st.session_state['fertiges_pdf']:
            st.download_button(
                "⬇️ PDF Herunterladen", 
                data=st.session_state['fertiges_pdf'], 
                file_name="angebot.pdf", 
                mime="application/pdf"
            )

# --- TEIL C: ADMIN ---
elif menue_punkt == "🔐 Admin":
    st.title("Admin")
    pw = st.text_input("PW:", type="password")
    if pw == "1234":
        sheets = lade_alle_blattnamen()
        if sheets:
            sh = st.selectbox("Blatt:", sheets)
            df = lade_blatt(sh)
            df_new = st.data_editor(df, num_rows="dynamic", use_container_width=True)
            if st.button("Speichern"):
                if speichere_excel(df_new, sh): 
                    st.success("Gespeichert!")
                    st.cache_data.clear()
