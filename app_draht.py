import streamlit as st
import pandas as pd
from fpdf import FPDF
import base64
import os

# --- 1. KONFIGURATION ---
st.set_page_config(page_title="Meingassner App", layout="wide", page_icon="logo.png")

# Handy-Icon laden
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

# --- 2. DATEN LOGIK (EXCEL) ---
DATEI_NAME = "katalog.xlsx"

def lade_startseite():
    if not os.path.exists(DATEI_NAME):
        return pd.DataFrame() # Leer
    try:
        return pd.read_excel(DATEI_NAME, sheet_name="Startseite")
    except:
        return pd.DataFrame()

def lade_blatt(blatt_name):
    if not os.path.exists(DATEI_NAME):
        return pd.DataFrame()
    try:
        return pd.read_excel(DATEI_NAME, sheet_name=blatt_name)
    except:
        return pd.DataFrame()

def lade_alle_blattnamen():
    if not os.path.exists(DATEI_NAME):
        return []
    xl = pd.ExcelFile(DATEI_NAME)
    return xl.sheet_names

def speichere_excel(df, blatt_name):
    try:
        if os.path.exists(DATEI_NAME):
            with pd.ExcelWriter(DATEI_NAME, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
                df.to_excel(writer, sheet_name=blatt_name, index=False)
        else:
            with pd.ExcelWriter(DATEI_NAME, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name=blatt_name, index=False)
        return True
    except Exception as e:
        st.error(f"Fehler: {e}")
        return False

# --- 3. SESSION STATE (Warenkorb) ---
if 'positionen' not in st.session_state:
    st.session_state['positionen'] = []

# --- 4. PDF ERSTELLEN ---
def create_pdf(positionen_liste):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Angebot - Meingassner Metalltechnik", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 10)
    
    # Kopfzeile
    pdf.cell(90, 8, "Beschreibung", 1)
    pdf.cell(20, 8, "Menge", 1)
    pdf.cell(20, 8, "Einh.", 1)
    pdf.cell(30, 8, "EP", 1)
    pdf.cell(30, 8, "Gesamt", 1)
    pdf.ln()
    
    pdf.set_font("Arial", size=10)
    gesamt = 0
    for pos in positionen_liste:
        txt = pos['Beschreibung'].encode('latin-1', 'replace').decode('latin-1')
        pdf.cell(90, 8, txt, 1)
        pdf.cell(20, 8, str(pos['Menge']), 1)
        pdf.cell(20, 8, pos.get('Einheit', 'Stk'), 1)
        pdf.cell(30, 8, f"{pos['Einzelpreis']:.2f}", 1)
        pdf.cell(30, 8, f"{pos['Preis']:.2f}", 1)
        pdf.ln()
        gesamt += pos['Preis']
        
    pdf.cell(160, 8, "Gesamtsumme:", 1)
    pdf.cell(30, 8, f"{gesamt:.2f}", 1)
    return pdf.output(dest='S').encode('latin-1')

# --- 5. SIDEBAR MENÜ AUFBAU ---
st.sidebar.header("Katalog Auswahl")

# 1. Lade die Kategorien aus der Excel Startseite
index_df = lade_startseite()
menue_optionen = []

if not index_df.empty and 'System' in index_df.columns:
    # Nimm alle Systeme aus der Spalte "System"
    menue_optionen = index_df['System'].tolist()
else:
    st.sidebar.warning("Excel 'Startseite' leer oder fehlt.")

# 2. Füge Admin fix hinzu
menue_optionen.append("🔐 Admin / Datenpflege")

# 3. Das Menü
auswahl = st.sidebar.radio("Bitte wählen:", menue_optionen)

# --- 6. HAUPTBEREICH ---
st.title("Meingassner App")

# Layout: 2/3 Links (Produkte/Admin), 1/3 Rechts (Warenkorb)
# Außer bei Admin, da brauchen wir Platz
if auswahl == "🔐 Admin / Datenpflege":
    col_content, col_cart = st.columns([1, 0.01]) 
else:
    col_content, col_cart = st.columns([2, 1])

with col_content:
    
    # === FALL A: ADMIN ===
    if auswahl == "🔐 Admin / Datenpflege":
        st.subheader("Datenverwaltung")
        pw = st.text_input("Passwort:", type="password")
        if pw == "1234":
            alle_sheets = lade_alle_blattnamen()
            if alle_sheets:
                sheet_wahl = st.selectbox("Blatt bearbeiten:", alle_sheets)
                df_edit = lade_blatt(sheet_wahl)
                st.info("Tabelle bearbeiten (Zeilen hinzufügen mit + unten):")
                df_neu = st.data_editor(df_edit, num_rows="dynamic", use_container_width=True)
                
                if st.button("💾 Speichern"):
                    if speichere_excel(df_neu, sheet_wahl):
                        st.success("Gespeichert! Bitte App neu laden (Rerun) für Menü-Updates.")
            else:
                st.warning("Keine Excel-Datei gefunden.")
    
    # === FALL B: KATALOG ITEM (Alles andere) ===
    else:
        # Wir müssen herausfinden, welches Excel-Blatt zu diesem Menüpunkt gehört
        # Wir filtern die Startseite nach dem gewählten Namen
        row = index_df[index_df['System'] == auswahl]
        
        if not row.empty:
            blatt_name = row.iloc[0]['Blattname'] # Hole den Blattnamen
            st.subheader(f"Kategorie: {auswahl}")
            
            # Produkte laden
            produkte_df = lade_blatt(blatt_name)
            
            if not produkte_df.empty:
                # Prüfen ob die Spalten da sind
                if not set(['Bezeichnung', 'Preis', 'Einheit']).issubset(produkte_df.columns):
                    st.error(f"Fehler im Blatt '{blatt_name}': Spalten 'Bezeichnung', 'Preis', 'Einheit' fehlen.")
                else:
                    # Dropdown vorbereiten
                    prod_liste = produkte_df.to_dict('records')
                    # Label für Dropdown: "Name (Preis / Einh)"
                    optionen_str = [f"{p['Bezeichnung']} ({p['Preis']} € / {p['Einheit']})" for p in prod_liste]
                    
                    wahl_str = st.selectbox("Artikel wählen:", optionen_str)
                    
                    # Passenden Datensatz finden
                    index_wahl = optionen_str.index(wahl_str)
                    produkt = prod_liste[index_wahl]
                    
                    st.markdown("---")
                    
                    # Eingabe Menge
                    c1, c2 = st.columns(2)
                    menge = c1.number_input(f"Menge ({produkt['Einheit']})", value=1.0, step=0.1)
                    
                    # Preis berechnen
                    preis_pos = menge * produkt['Preis']
                    c2.metric("Gesamtpreis Position", f"{preis_pos:.2f} €")
                    
                    if st.button("In den Warenkorb legen", type="primary"):
                        st.session_state['positionen'].append({
                            "Beschreibung": f"{produkt['Bezeichnung']}", # System-Name evtl. weglassen für saubere Liste?
                            "Menge": menge,
                            "Einheit": produkt['Einheit'],
                            "Einzelpreis": produkt['Preis'],
                            "Preis": preis_pos
                        })
                        st.success("Hinzugefügt!")
                        st.rerun()
            else:
                st.warning(f"Das Blatt '{blatt_name}' ist leer.")
        else:
            st.error("Zuordnung in Startseite nicht gefunden.")

# === WARENKORB (RECHTS) ===
if auswahl != "🔐 Admin / Datenpflege":
    with col_cart:
        st.markdown("### 🛒 Angebot")
        if st.session_state['positionen']:
            df_cart = pd.DataFrame(st.session_state['positionen'])
            
            # Schöne Tabelle für Warenkorb
            st.dataframe(
                df_cart[['Beschreibung', 'Menge', 'Preis']], 
                hide_index=True, 
                use_container_width=True
            )
            
            total = sum(p['Preis'] for p in st.session_state['positionen'])
            st.markdown(f"### Summe: {total:.2f} €")
            
            pdf_data = create_pdf(st.session_state['positionen'])
            st.download_button("📄 PDF Angebot", pdf_data, "angebot_meingassner.pdf", "application/pdf")
            
            if st.button("🗑️ Leeren"):
                st.session_state['positionen'] = []
                st.rerun()
        else:
            st.info("Noch leer.")
