import streamlit as st
import pandas as pd
from fpdf import FPDF
import base64
import os

# --- 1. KONFIGURATION & HANDY ICON ---
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

# --- 2. DATEN LADE-FUNKTION (EXCEL) ---
@st.cache_data # Damit Excel nicht bei jedem Klick neu geladen wird -> schneller
def lade_katalog():
    dateiname = "katalog.xlsx"
    if not os.path.exists(dateiname):
        return None
    try:
        # Lese das Inhaltsverzeichnis (Blatt "Startseite")
        index_df = pd.read_excel(dateiname, sheet_name="Startseite")
        return index_df
    except Exception as e:
        st.error(f"Fehler beim Lesen der 'Startseite': {e}")
        return None

def lade_produkte(blatt_name):
    try:
        df = pd.read_excel("katalog.xlsx", sheet_name=blatt_name)
        return df
    except Exception as e:
        return pd.DataFrame() # Leeres Blatt zurückgeben bei Fehler

# --- 3. SESSION STATE ---
if 'positionen' not in st.session_state:
    st.session_state['positionen'] = []

# --- 4. PDF FUNKTION ---
def create_pdf(positionen_liste):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Angebot - Meingassner Metalltechnik", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 10)
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
        pdf.cell(20, 8, pos.get('Einheit', 'Stk'), 1) # Einheit dazu
        pdf.cell(30, 8, f"{pos['Einzelpreis']:.2f}", 1)
        pdf.cell(30, 8, f"{pos['Preis']:.2f}", 1)
        pdf.ln()
        gesamt += pos['Preis']
        
    pdf.cell(160, 8, "Gesamtsumme:", 1)
    pdf.cell(30, 8, f"{gesamt:.2f}", 1)
    return pdf.output(dest='S').encode('latin-1')

# --- 5. HAUPTNAVIGATION ---
st.sidebar.header("Menü")

modus_haupt = st.sidebar.radio("Modus:", ["Katalog / Systeme", "Eigenfertigung (Kalkulator)"])

st.title("Meingassner Kalkulation")

col_left, col_right = st.columns([2, 1])

# === LINKE SPALTE: AUSWAHL & KALKULATION ===
with col_left:
    
    # ----------------------------------------------------
    # MODUS A: KATALOG (Dynamisch aus Excel)
    # ----------------------------------------------------
    if modus_haupt == "Katalog / Systeme":
        index_data = lade_katalog()
        
        if index_data is None:
            st.error("⚠️ Datei 'katalog.xlsx' nicht gefunden oder fehlerhaft!")
            st.info("Bitte erstelle eine Excel mit Blatt 'Startseite' (Spalten: System, Blattname).")
        else:
            # 1. System wählen (aus Excel Startseite)
            system_list = index_data['System'].tolist()
            wahl_system = st.selectbox("📂 System / Kategorie wählen:", system_list)
            
            # Finde den Blattnamen dazu
            blatt_name = index_data[index_data['System'] == wahl_system]['Blattname'].values[0]
            
            # 2. Lade Produkte dieses Systems
            produkte_df = lade_produkte(blatt_name)
            
            if produkte_df.empty:
                st.warning(f"Keine Produkte im Blatt '{blatt_name}' gefunden.")
            else:
                st.subheader(f"Produkte: {wahl_system}")
                
                # Produkt Dropdown (Wir bauen einen String aus Name + Preis für die Anzeige)
                # Wir gehen davon aus, Excel hat Spalten: Bezeichnung, Einheit, Preis
                produkte_liste = produkte_df.to_dict('records')
                
                formatierte_liste = [f"{p['Bezeichnung']} ({p['Preis']} € / {p['Einheit']})" for p in produkte_liste]
                
                wahl_produkt_str = st.selectbox("Produkt wählen:", formatierte_liste)
                
                # Das ausgewählte Produkt wieder finden
                index_gewaehlt = formatierte_liste.index(wahl_produkt_str)
                produkt_daten = produkte_liste[index_gewaehlt]
                
                # Eingabe Menge
                col_m1, col_m2 = st.columns(2)
                menge = col_m1.number_input(f"Menge ({produkt_daten['Einheit']})", value=1.0, step=0.5)
                
                # Preis berechnen
                preis_gesamt = menge * produkt_daten['Preis']
                col_m2.metric("Preis gesamt", f"{preis_gesamt:.2f} €")
                
                if st.button("In den Warenkorb"):
                    st.session_state['positionen'].append({
                        "Beschreibung": f"{wahl_system}: {produkt_daten['Bezeichnung']}",
                        "Menge": menge,
                        "Einheit": produkt_daten['Einheit'],
                        "Einzelpreis": produkt_daten['Preis'],
                        "Preis": preis_gesamt
                    })
                    st.success("Hinzugefügt!")
                    st.rerun()

    # ----------------------------------------------------
    # MODUS B: EIGENFERTIGUNG (Der alte Kalkulator)
    # ----------------------------------------------------
    elif modus_haupt == "Eigenfertigung (Kalkulator)":
        st.subheader("🛠️ Individuelle Kalkulation")
        
        art = st.selectbox("Was wird gefertigt?", ["Treppe", "Geländer", "Vordach"])
        
        # Einfaches Beispiel für Treppe (wie vorher)
        if art == "Treppe":
            stundensatz = st.number_input("Stundensatz", value=65.0)
            material = st.number_input("Materialkosten", value=500.0)
            stunden = st.number_input("Stunden", value=10.0)
            
            preis = (stunden * stundensatz) + (material * 1.2)
            st.markdown(f"### Preis: {preis:.2f} €")
            
            if st.button("Treppe in Warenkorb"):
                st.session_state['positionen'].append({
                    "Beschreibung": "Indiv. Treppe",
                    "Menge": 1,
                    "Einheit": "Psch",
                    "Einzelpreis": preis,
                    "Preis": preis
                })
                st.rerun()

# === RECHTE SPALTE: WARENKORB ===
with col_right:
    st.write("### 🛒 Aktuelles Angebot")
    if st.session_state['positionen']:
        df_cart = pd.DataFrame(st.session_state['positionen'])
        # Zeige nur wichtige Spalten
        st.dataframe(df_cart[['Beschreibung', 'Menge', 'Preis']], hide_index=True)
        
        summe = sum(p['Preis'] for p in st.session_state['positionen'])
        st.markdown(f"**Summe: {summe:.2f} €**")
        
        # PDF
        pdf_data = create_pdf(st.session_state['positionen'])
        st.download_button("📄 PDF Angebot", pdf_data, "angebot.pdf", "application/pdf")
        
        if st.button("Alles löschen"):
            st.session_state['positionen'] = []
            st.rerun()
    else:
        st.info("Warenkorb leer")
