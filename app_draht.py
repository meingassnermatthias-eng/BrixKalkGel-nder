import streamlit as st
import pandas as pd
from fpdf import FPDF
import base64
import os

# --- 1. SETUP ---
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

def lade_startseite():
    if not os.path.exists(DATEI_NAME): return pd.DataFrame()
    try: return pd.read_excel(DATEI_NAME, sheet_name="Startseite")
    except: return pd.DataFrame()

def lade_blatt(blatt_name):
    if not os.path.exists(DATEI_NAME): return pd.DataFrame()
    try: return pd.read_excel(DATEI_NAME, sheet_name=blatt_name)
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

# --- 4. PDF ---
def create_pdf(positionen_liste):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Angebot - Meingassner Metalltechnik", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(90, 8, "Beschreibung", 1)
    pdf.cell(20, 8, "Menge", 1)
    pdf.cell(30, 8, "EP", 1)
    pdf.cell(30, 8, "Gesamt", 1)
    pdf.ln()
    pdf.set_font("Arial", size=10)
    gesamt = 0
    for pos in positionen_liste:
        txt = pos['Beschreibung'].encode('latin-1', 'replace').decode('latin-1')
        pdf.cell(90, 8, txt, 1)
        pdf.cell(20, 8, str(pos['Menge']), 1)
        pdf.cell(30, 8, f"{pos['Einzelpreis']:.2f}", 1)
        pdf.cell(30, 8, f"{pos['Preis']:.2f}", 1)
        pdf.ln()
        gesamt += pos['Preis']
    pdf.cell(140, 8, "Gesamtsumme:", 1)
    pdf.cell(30, 8, f"{gesamt:.2f}", 1)
    return pdf.output(dest='S').encode('latin-1')

# --- 5. MENÜ ---
st.sidebar.header("Menü")
index_df = lade_startseite()
menue_items = index_df['System'].tolist() if not index_df.empty else []
menue_items.append("🔐 Admin")
auswahl = st.sidebar.radio("Wähle Bereich:", menue_items)

# --- 6. HAUPTBEREICH ---
st.title("Meingassner Konfigurator")

if auswahl == "🔐 Admin":
    # --- ADMIN BEREICH (Gleich wie vorher) ---
    pw = st.text_input("Passwort:", type="password")
    if pw == "1234":
        sheets = lade_alle_blattnamen()
        if sheets:
            sh = st.selectbox("Blatt:", sheets)
            df = lade_blatt(sh)
            st.info("Spalten müssen sein: Typ, Bezeichnung, Variable, Optionen, Formel")
            df_new = st.data_editor(df, num_rows="dynamic", use_container_width=True)
            if st.button("Speichern"):
                if speichere_excel(df_new, sh): st.success("Gespeichert!")

else:
    # --- DER INTELLIGENTE KONFIGURATOR ---
    col_l, col_r = st.columns([2, 1])
    
    with col_l:
        row = index_df[index_df['System'] == auswahl]
        if not row.empty:
            blatt = row.iloc[0]['Blattname']
            df_config = lade_blatt(blatt)
            
            if df_config.empty:
                st.warning("Blatt ist leer.")
            else:
                st.subheader(f"Konfiguration: {auswahl}")
                
                # Hier speichern wir die Werte deiner Inputs (L, B, H...)
                berechnungs_variablen = {}
                beschreibung_parts = [] # Für den Angebotstext
                
                # Wir gehen Zeile für Zeile durch dein Excel
                for index, zeile in df_config.iterrows():
                    
                    typ = str(zeile['Typ']).strip().lower()
                    label = str(zeile['Bezeichnung'])
                    var_name = str(zeile['Variable'])
                    
                    # 1. ZAHLEINGABE (z.B. Länge)
                    if typ == 'zahl':
                        val = st.number_input(label, value=0.0, step=0.1, key=f"{blatt}_{index}")
                        berechnungs_variablen[var_name] = val
                        if val > 0: beschreibung_parts.append(f"{label}: {val}")
                    
                    # 2. AUSWAHL (z.B. Oberfläche)
                    elif typ == 'auswahl':
                        # Optionen parsen: "Rund:0, Quadrat:25"
                        raw_opts = str(zeile['Optionen']).split(',')
                        opts_dict = {} # Name -> Wert
                        opts_names = []
                        
                        for opt in raw_opts:
                            if ':' in opt:
                                name, wert = opt.split(':')
                                opts_dict[name.strip()] = float(wert)
                                opts_names.append(name.strip())
                            else:
                                # Fallback falls kein Wert dabei steht
                                opts_dict[opt.strip()] = 0
                                opts_names.append(opt.strip())
                        
                        wahl = st.selectbox(label, opts_names, key=f"{blatt}_{index}")
                        wert_der_wahl = opts_dict[wahl]
                        
                        # Wir speichern den WERT in die Variable für die Rechnung
                        berechnungs_variablen[var_name] = wert_der_wahl
                        beschreibung_parts.append(f"{label}: {wahl}")

                    # 3. PREIS BERECHNUNG
                    elif typ == 'preis':
                        formel = str(zeile['Formel'])
                        st.markdown("---")
                        
                        try:
                            # Sicherheit: eval ist mächtig, wir nutzen es für Mathe
                            # Wir übergeben unser Wörterbuch mit Variablen (L=3, B=4...)
                            preis_ergebnis = eval(formel, {"__builtins__": None}, berechnungs_variablen)
                            
                            st.subheader(f"Preis: {preis_ergebnis:.2f} €")
                            
                            if st.button("In den Warenkorb", type="primary"):
                                beschreibung_text = f"{auswahl} | " + ", ".join(beschreibung_parts)
                                st.session_state['positionen'].append({
                                    "Beschreibung": beschreibung_text,
                                    "Menge": 1.0, # Ist bei Konfigurator meist 1 Stk
                                    "Einzelpreis": preis_ergebnis,
                                    "Preis": preis_ergebnis
                                })
                                st.success("Hinzugefügt!")
                                st.rerun()
                                
                        except Exception as e:
                            st.error(f"Fehler in der Formel: {formel}")
                            st.caption(f"Details: {e}")
                            st.caption(f"Aktuelle Werte: {berechnungs_variablen}")

    # --- WARENKORB RECHTS ---
    with col_r:
        st.write("### 🛒 Angebot")
        if st.session_state['positionen']:
            df_cart = pd.DataFrame(st.session_state['positionen'])
            st.dataframe(df_cart[['Beschreibung', 'Preis']], hide_index=True, use_container_width=True)
            summe = sum(p['Preis'] for p in st.session_state['positionen'])
            st.markdown(f"**Total: {summe:.2f} €**")
            
            pdf_data = create_pdf(st.session_state['positionen'])
            st.download_button("📄 PDF", pdf_data, "angebot.pdf", "application/pdf")
            
            if st.button("Löschen"):
                st.session_state['positionen'] = []
                st.rerun()
