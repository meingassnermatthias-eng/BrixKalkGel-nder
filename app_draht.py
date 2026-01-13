import streamlit as st
import pandas as pd
from fpdf import FPDF
import base64
import os

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
    """Entfernt Leerzeichen aus Spaltennamen"""
    if not df.empty:
        df.columns = df.columns.str.strip()
    return df

def lade_startseite():
    if not os.path.exists(DATEI_NAME): return pd.DataFrame()
    try: 
        df = pd.read_excel(DATEI_NAME, sheet_name="Startseite")
        return clean_df_columns(df)
    except: return pd.DataFrame()

def lade_blatt(blatt_name):
    if not os.path.exists(DATEI_NAME): return pd.DataFrame()
    try: 
        df = pd.read_excel(DATEI_NAME, sheet_name=blatt_name)
        return clean_df_columns(df)
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

# --- 3. WARENKORB ---
if 'positionen' not in st.session_state: st.session_state['positionen'] = []

# --- 4. PDF ENGINE (PROFESSIONELL) ---
class PDF(FPDF):
    def header(self):
        # Logo einfügen (oben rechts oder links)
        if os.path.exists("logo.png"):
            # x=10, y=8, breite=40
            self.image("logo.png", 10, 8, 40)
        
        self.set_font('Arial', 'B', 20)
        # Titel mittig aber nicht im Logo
        self.cell(0, 10, 'Angebot', 0, 1, 'C')
        self.ln(20) # Abstand nach unten

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Seite {self.page_no()}', 0, 0, 'C')

def clean_text(text):
    """Reinigt Text für PDF (keine Euro-Zeichen, Latin-1 kompatibel)"""
    if not isinstance(text, str):
        text = str(text)
    # Ersetzungen für Stabilität
    text = text.replace("€", "EUR")
    text = text.replace("–", "-")
    # Erzwinge Latin-1 encoding, ersetze unbekannte Zeichen durch ?
    return text.encode('latin-1', 'replace').decode('latin-1')

def create_pdf(positionen_liste):
    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Firmeninfo unter Logo
    pdf.set_font("Arial", size=10)
    pdf.ln(5)
    pdf.cell(0, 5, clean_text("Meingassner Metalltechnik"), ln=True)
    pdf.cell(0, 5, clean_text("Ihr Spezialist für Metallbau"), ln=True)
    pdf.ln(10)
    
    # Tabellen-Einstellungen
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(240, 240, 240) # Hellgrau
    
    # Spaltenbreiten
    w_desc = 100
    w_menge = 25
    w_ep = 30
    w_gesamt = 35
    
    # Kopfzeile
    pdf.cell(w_desc, 8, "Beschreibung", 1, 0, 'L', True)
    pdf.cell(w_menge, 8, "Menge", 1, 0, 'C', True)
    pdf.cell(w_ep, 8, "EP (EUR)", 1, 0, 'R', True)
    pdf.cell(w_gesamt, 8, "Gesamt", 1, 1, 'R', True)
    
    pdf.set_font("Arial", size=10)
    
    gesamt_summe = 0
    
    for pos in positionen_liste:
        # Text formatieren: Wir machen aus dem langen String eine schöne Liste
        # Ursprung: "Carport | Länge: 6, Breite: 5"
        # Ziel: "Carport\n - Länge: 6\n - Breite: 5"
        
        # 1. Haupttitel trennen (vor dem ersten |)
        raw_desc = str(pos['Beschreibung'])
        parts = raw_desc.split("|")
        
        main_title = parts[0].strip()
        details = ""
        
        if len(parts) > 1:
            # Der Rest sind Details, durch Komma getrennt
            details_raw = parts[1]
            # Ersetze Kommas durch neue Zeilen mit Strich
            details = "\n" + details_raw.replace(",", "\n -").strip()
            # Falls das erste Element noch keinen Strich hat
            if not details.strip().startswith("-"):
                details = details.replace("\n", "\n - ", 1)

        final_desc_text = clean_text(f"{main_title}{details}")
        
        # Werte bereinigen
        menge_str = clean_text(str(pos['Menge']))
        ep_str = f"{pos['Einzelpreis']:.2f}"
        gesamt_str = f"{pos['Preis']:.2f}"
        
        # --- HÖHENBERECHNUNG (Der Trick für saubere Tabellen) ---
        # 1. Wir speichern die aktuelle X und Y Position
        x_start = pdf.get_x()
        y_start = pdf.get_y()
        
        # 2. Wir drucken die Beschreibung (MultiCell) um zu sehen, wie hoch sie wird
        pdf.multi_cell(w_desc, 5, final_desc_text, border=1, align='L')
        
        # 3. Wo sind wir jetzt?
        y_end = pdf.get_y()
        row_height = y_end - y_start
        
        # 4. Cursor zurücksetzen nach rechts oben neben die Beschreibung
        pdf.set_xy(x_start + w_desc, y_start)
        
        # 5. Die anderen Zellen mit genau dieser Höhe drucken
        pdf.cell(w_menge, row_height, menge_str, 1, 0, 'C')
        pdf.cell(w_ep, row_height, ep_str, 1, 0, 'R')
        pdf.cell(w_gesamt, row_height, gesamt_str, 1, 1, 'R') # Zeilenumbruch
        
        gesamt_summe += pos['Preis']

    # Summenblock
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(w_desc + w_menge + w_ep, 10, "Gesamtsumme:", 0, 0, 'R')
    pdf.cell(w_gesamt, 10, f"{gesamt_summe:.2f} EUR", 1, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')

# --- 5. MENÜ ---
st.sidebar.header("Menü")
index_df = lade_startseite()

if not index_df.empty and 'System' in index_df.columns:
    menue_items = index_df['System'].tolist()
else:
    menue_items = []
    
menue_items.append("🔐 Admin")
auswahl = st.sidebar.radio("Wähle Bereich:", menue_items)

# --- 6. HAUPTBEREICH ---
st.title("Meingassner Konfigurator")

if auswahl == "🔐 Admin":
    # --- ADMIN BEREICH ---
    pw = st.text_input("Passwort:", type="password")
    if pw == "1234":
        sheets = lade_alle_blattnamen()
        if sheets:
            sh = st.selectbox("Blatt:", sheets)
            df = lade_blatt(sh)
            st.info("Benötigte Spalten: Typ, Bezeichnung, Variable, Optionen, Formel")
            df_new = st.data_editor(df, num_rows="dynamic", use_container_width=True)
            if st.button("Speichern"):
                if speichere_excel(df_new, sh): 
                    st.success("Gespeichert! Bitte Seite neu laden.")
                    st.cache_data.clear()
        else:
            st.warning("Keine Excel-Datei gefunden.")

else:
    # --- KONFIGURATOR ---
    if not index_df.empty and 'System' in index_df.columns:
        row = index_df[index_df['System'] == auswahl]
        if not row.empty:
            blatt = row.iloc[0]['Blattname']
            df_config = lade_blatt(blatt)
            
            # Check: Formel Spalte da?
            if df_config.empty:
                st.warning("Blatt ist leer.")
            elif 'Formel' not in df_config.columns:
                 st.error(f"Fehler: Spalte 'Formel' fehlt im Blatt '{blatt}'!")
            else:
                st.subheader(f"Konfiguration: {auswahl}")
                
                col_l, col_r = st.columns([2, 1])
                
                with col_l:
                    vars_calc = {}
                    desc_parts = [] 
                    
                    for index, zeile in df_config.iterrows():
                        typ = str(zeile['Typ']).strip().lower()
                        label = str(zeile['Bezeichnung'])
                        var_name = str(zeile['Variable'])
                        
                        if typ == 'zahl':
                            val = st.number_input(label, value=0.0, step=0.1, key=f"{blatt}_{index}")
                            vars_calc[var_name] = val
                            # Nur anzeigen wenn Wert > 0
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
                                    # Fallback
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
                                    # Wir bauen den Text so, dass wir ihn im PDF wieder zerlegen können
                                    full_desc = f"{auswahl} | " + ", ".join(desc_parts)
                                    
                                    st.session_state['positionen'].append({
                                        "Beschreibung": full_desc,
                                        "Menge": 1.0,
                                        "Einzelpreis": preis,
                                        "Preis": preis
                                    })
                                    st.success("Hinzugefügt!")
                                    st.rerun()
                            except Exception as e:
                                st.error("Fehler in der Berechnung!")
                                st.caption(f"Details: {e}")
                                
                with col_r:
                    st.write("### 🛒 Angebot")
                    if st.session_state['positionen']:
                        df_cart = pd.DataFrame(st.session_state['positionen'])
                        # Zeige vereinfachte Tabelle im Web
                        st.dataframe(df_cart[['Beschreibung', 'Preis']], hide_index=True)
                        
                        summe = sum(p['Preis'] for p in st.session_state['positionen'])
                        st.markdown(f"**Total: {summe:.2f} €**")
                        
                        # PDF GENERIERUNG
                        pdf_data = create_pdf(st.session_state['positionen'])
                        
                        st.download_button(
                            label="📄 PDF Angebot laden", 
                            data=pdf_data, 
                            file_name="angebot.pdf", 
                            mime="application/pdf"
                        )
                        
                        if st.button("Löschen"):
                            st.session_state['positionen'] = []
                            st.rerun()
