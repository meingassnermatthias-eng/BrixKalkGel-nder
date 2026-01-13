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
DATEI_NAME = "katalog.xlsx"

def lade_excel_blatt(blatt_name):
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
    # Vorsicht: Das ist ein einfacher Speicher-Mechanismus.
    # Um bestehende Blätter nicht zu löschen, laden wir erst alles.
    try:
        # Lade existierende Datei komplett
        if os.path.exists(DATEI_NAME):
            with pd.ExcelWriter(DATEI_NAME, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
                df.to_excel(writer, sheet_name=blatt_name, index=False)
        else:
            # Neue Datei
            with pd.ExcelWriter(DATEI_NAME, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name=blatt_name, index=False)
        return True
    except Exception as e:
        st.error(f"Fehler beim Speichern: {e}")
        return False

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
        pdf.cell(20, 8, pos.get('Einheit', 'Stk'), 1)
        pdf.cell(30, 8, f"{pos['Einzelpreis']:.2f}", 1)
        pdf.cell(30, 8, f"{pos['Preis']:.2f}", 1)
        pdf.ln()
        gesamt += pos['Preis']
        
    pdf.cell(160, 8, "Gesamtsumme:", 1)
    pdf.cell(30, 8, f"{gesamt:.2f}", 1)
    return pdf.output(dest='S').encode('latin-1')

# --- 5. HAUPTNAVIGATION ---
st.sidebar.header("Menü")

modus_haupt = st.sidebar.radio(
    "Bereich:", 
    ["Katalog / Systeme", "Eigenfertigung (Kalkulator)", "🔒 Admin / Datenpflege"]
)

st.title("Meingassner App")

# Layout Aufteilung
if modus_haupt == "🔒 Admin / Datenpflege":
    col_left, col_right = st.columns([1, 0.1]) # Admin braucht volle Breite
else:
    col_left, col_right = st.columns([2, 1])   # Normaler Modus

# === INHALT LINKER BEREICH ===
with col_left:
    
    # ----------------------------------------------------
    # MODUS A: KATALOG (Dynamisch)
    # ----------------------------------------------------
    if modus_haupt == "Katalog / Systeme":
        st.subheader("📂 System Auswahl")
        
        index_df = lade_excel_blatt("Startseite")
        
        if index_df.empty:
            st.warning("Excel 'katalog.xlsx' fehlt oder Blatt 'Startseite' leer.")
        else:
            # System wählen
            systeme = index_df['System'].tolist()
            wahl_system = st.selectbox("Kategorie wählen:", systeme)
            
            # Blatt dazu finden
            blatt = index_df[index_df['System'] == wahl_system]['Blattname'].values[0]
            
            # Produkte laden
            produkte_df = lade_excel_blatt(blatt)
            
            if not produkte_df.empty:
                st.write(f"### {wahl_system}")
                
                # Dictionary für Dropdown erstellen
                prod_dict = produkte_df.to_dict('records')
                # Anzeige String formatieren
                optionen = [f"{p['Bezeichnung']} | {p['Preis']}€" for p in prod_dict]
                
                wahl_prod_str = st.selectbox("Artikel wählen:", optionen)
                
                # Daten zurückholen
                idx = optionen.index(wahl_prod_str)
                gewaehlt = prod_dict[idx]
                
                c1, c2 = st.columns(2)
                menge = c1.number_input(f"Menge ({gewaehlt['Einheit']})", value=1.0)
                preis_pos = menge * gewaehlt['Preis']
                c2.metric("Preis", f"{preis_pos:.2f} €")
                
                if st.button("In den Warenkorb"):
                    st.session_state['positionen'].append({
                        "Beschreibung": f"{wahl_system}: {gewaehlt['Bezeichnung']}",
                        "Menge": menge,
                        "Einheit": gewaehlt['Einheit'],
                        "Einzelpreis": gewaehlt['Preis'],
                        "Preis": preis_pos
                    })
                    st.success("Ok!")
                    st.rerun()

    # ----------------------------------------------------
    # MODUS B: EIGENFERTIGUNG
    # ----------------------------------------------------
    elif modus_haupt == "Eigenfertigung (Kalkulator)":
        st.subheader("🛠️ Individuelle Kalkulation")
        # (Dein Code für Treppen hier - gekürzt für Übersicht)
        st.info("Hier ist der Platz für den Treppen/Geländer Rechner (siehe vorheriger Code).")
        
        # Beispiel Dummy
        if st.button("Dummy Treppe hinzufügen"):
             st.session_state['positionen'].append({
                "Beschreibung": "Stahltreppe Individual",
                "Menge": 1,
                "Einheit": "Psch",
                "Einzelpreis": 1500.0,
                "Preis": 1500.0
            })
             st.rerun()

    # ----------------------------------------------------
    # MODUS C: ADMIN (DATENPFLEGE) - NEU!
    # ----------------------------------------------------
    elif modus_haupt == "🔒 Admin / Datenpflege":
        st.subheader("Excel Datenverwaltung")
        
        passwort = st.text_input("Admin Passwort", type="password")
        
        if passwort == "1234": # <--- HIER DEIN PASSWORT ÄNDERN
            st.success("Eingeloggt")
            
            # 1. Welches Blatt bearbeiten?
            alle_blaetter = lade_alle_blattnamen()
            if not alle_blaetter:
                st.error("Keine Excel Datei gefunden. Bitte lade eine hoch oder erstelle 'katalog.xlsx'.")
            else:
                blatt_wahl = st.selectbox("Welches Blatt bearbeiten?", alle_blaetter)
                
                # 2. Daten laden
                df_edit = lade_excel_blatt(blatt_wahl)
                
                # 3. Editor anzeigen (Hier kannst du tippen wie in Excel!)
                st.info("Tipp: Klicke in die Tabelle, um Werte zu ändern. Unten neue Zeilen anfügen.")
                df_geaendert = st.data_editor(df_edit, num_rows="dynamic")
                
                # 4. Speichern Button
                if st.button("💾 Änderungen in Excel speichern"):
                    erfolg = speichere_excel(df_geaendert, blatt_wahl)
                    if erfolg:
                        st.success(f"Blatt '{blatt_wahl}' wurde gespeichert!")
                        # Cache leeren damit Änderungen sofort sichtbar sind
                        st.cache_data.clear()
        
        elif passwort:
            st.error("Falsches Passwort")

# === INHALT RECHTER BEREICH (WARENKORB) ===
# Nur anzeigen wenn NICHT im Admin Modus
if modus_haupt != "🔒 Admin / Datenpflege":
    with col_right:
        st.write("### 🛒 Angebot")
        if st.session_state['positionen']:
            df_cart = pd.DataFrame(st.session_state['positionen'])
            st.dataframe(df_cart[['Beschreibung', 'Menge', 'Preis']], hide_index=True)
            
            total = sum(p['Preis'] for p in st.session_state['positionen'])
            st.markdown(f"**Summe: {total:.2f} €**")
            
            pdf_data = create_pdf(st.session_state['positionen'])
            st.download_button("📄 PDF laden", pdf_data, "angebot.pdf", "application/pdf")
            
            if st.button("Löschen"):
                st.session_state['positionen'] = []
                st.rerun()
