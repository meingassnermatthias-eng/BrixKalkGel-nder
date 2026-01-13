import streamlit as st
import pandas as pd
from fpdf import FPDF
import base64
import os

# --- 1. SEITEN KONFIGURATION (Muss als allererstes stehen) ---
st.set_page_config(
    page_title="Meingassner App", 
    layout="wide", 
    page_icon="logo.png" # Standard Favicon für PC
)

# --- 2. FUNKTION: MOBILE APP ICON (Der "Trick" für Handys) ---
def setup_app_icon(image_file):
    """
    Versucht, das Bild als Apple-Touch-Icon und Android-Icon 
    in den HTML-Header zu schmuggeln.
    """
    if os.path.exists(image_file):
        try:
            with open(image_file, "rb") as f:
                data = f.read()
            encoded = base64.b64encode(data).decode()
            
            # HTML Injection für iOS und Android Homescreen
            icon_html = f"""
            <style>
            </style>
            <link rel="apple-touch-icon" href="data:image/png;base64,{encoded}">
            <link rel="icon" type="image/png" href="data:image/png;base64,{encoded}">
            """
            st.markdown(icon_html, unsafe_allow_html=True)
            # Optional: Logo auch in der Sidebar anzeigen
            st.sidebar.image(image_file, width=150)
        except Exception as e:
            st.warning(f"Fehler beim Laden des Logos: {e}")
    else:
        # Falls kein Logo da ist, kein Fehler, nur Hinweis
        st.sidebar.warning("⚠️ 'logo.png' nicht gefunden. Bitte in den Ordner legen.")

# Logo-Funktion aufrufen
setup_app_icon("logo.png")

# --- 3. SESSION STATE (Warenkorb Speicher) ---
if 'positionen' not in st.session_state:
    st.session_state['positionen'] = []

# --- 4. FUNKTION: PDF ERSTELLEN ---
def create_pdf(positionen_liste):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    
    # Kopfzeile
    pdf.cell(0, 10, "Angebot - Meingassner Metalltechnik", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, "Geländer | Treppen | Zäune | Überdachungen", ln=True, align='C')
    pdf.ln(10)
    
    # Tabellenkopf
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(90, 10, "Beschreibung", 1)
    pdf.cell(20, 10, "Menge", 1)
    pdf.cell(40, 10, "Einzelpreis", 1)
    pdf.cell(40, 10, "Gesamt", 1)
    pdf.ln()
    
    # Inhalt
    pdf.set_font("Arial", size=12)
    gesamt_netto = 0
    
    for pos in positionen_liste:
        # Text bereinigen (latin-1 encoding fix)
        beschreibung = pos['Beschreibung'].encode('latin-1', 'replace').decode('latin-1')
        menge = str(pos['Menge'])
        preis = f"{pos['Preis']:.2f}"
        
        pdf.cell(90, 10, beschreibung, 1)
        pdf.cell(20, 10, menge, 1)
        pdf.cell(40, 10, "", 1) 
        pdf.cell(40, 10, preis + " EUR", 1)
        pdf.ln()
        
        gesamt_netto += pos['Preis']
        
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(110, 10, "", 0)
    pdf.cell(40, 10, "Gesamtsumme:", 1)
    pdf.cell(40, 10, f"{gesamt_netto:.2f} EUR", 1)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 5. SIDEBAR NAVIGATION ---
st.sidebar.header("Menü")

# Hauptkategorie
bereich = st.sidebar.radio(
    "Bereich wählen:",
    ["Eigenfertigung", "Handel & Systeme"],
    index=0
)

st.sidebar.markdown("---")

# Untermenü je nach Hauptkategorie
if bereich == "Eigenfertigung":
    modus = st.sidebar.radio(
        "Produkt:",
        ["Individuell (Treppen/Geländer)", "Gitterstabmattenzäune", "Vordächer"]
    )
else: # Handel & Systeme
    modus = st.sidebar.radio(
        "System:",
        ["Brix Zaun", "Terrassendach / Sommergarten", "Alu Fenster & Türen"]
    )

# --- 6. HAUPTBEREICH (KALKULATION) ---
st.title(f"Kalkulation: {modus}")

# Layout: Links Eingabe, Rechts (oder unten) Warenkorb
col_input, col_cart = st.columns([2, 1])

# Variablen initialisieren
preis_pos = 0.0
text_pos = ""
menge_pos = 1.0

with col_input:
    # --- MODUS A: EIGENFERTIGUNG INDIVIDUELL ---
    if modus == "Individuell (Treppen/Geländer)":
        with st.expander("Grundeinstellungen", expanded=True):
            c1, c2 = st.columns(2)
            stundensatz = c1.number_input("Stundensatz (€)", value=65.0, step=1.0)
            mat_faktor = c2.number_input("Material Faktor", value=1.20, step=0.05)
            
            kategorie = st.selectbox("Kategorie", ["Treppe", "Geländer Edelstahl", "Geländer Verzinkt"])
            modell = st.text_input("Modellbezeichnung", value="Stahltreppe Gerade")

        st.markdown("### Maße & Menge")
        m1, m2, m3 = st.columns(3)
        anzahl = m1.number_input("Anzahl", value=1.0, step=1.0)
        laenge = m2.number_input("Länge (m)", value=0.0, step=0.1)
        breite = m3.number_input("Breite (m)", value=0.0, step=0.1)

        st.markdown("### Optionen")
        opt_wangen = st.checkbox("Wangen Flachstahl (40€ pauschal)")
        opt_rost = st.checkbox("Stufen Gitterrost (35€ pauschal)")
        opt_gelaender = st.checkbox("Geländer einseitig (140€/lfm)")
        opt_pulver = st.checkbox("Pulverbeschichtung (80€/lfm)")

        # Berechnung
        material_basis = (laenge * breite * 100) * mat_faktor # Beispielformel
        arbeits_kosten = (anzahl * 3) * stundensatz           # Beispielformel
        
        zusatz = 0
        if opt_wangen: zusatz += 40
        if opt_rost: zusatz += 35
        if opt_gelaender: zusatz += (140 * laenge)
        if opt_pulver: zusatz += (80 * laenge)
        
        preis_pos = (material_basis + arbeits_kosten + zusatz) * anzahl
        text_pos = f"{kategorie}: {modell} ({laenge}x{breite}m)"
        menge_pos = anzahl

    # --- MODUS B: BRIX ZAUN ---
    elif modus == "Brix Zaun":
        st.subheader("Brix Konfigurator")
        brix_modell = st.selectbox("Modell", ["Brix Alu-Latten", "Brix Palisaden", "Brix Sichtschutz"])
        lfm = st.number_input("Laufmeter", value=10.0)
        preis_pro_m = st.number_input("Preis pro lfm (€)", value=180.0)
        
        preis_pos = lfm * preis_pro_m
        text_pos = f"{brix_modell} ({lfm}m)"
        menge_pos = lfm

    # --- ANDERE MODI (PLATZHALTER) ---
    else:
        st.info("Kalkulationsmaske wird noch erstellt.")
        text_pos = modus
        preis_pos = st.number_input("Manueller Preis (€)", value=0.0)

    # --- BUTTON: HINZUFÜGEN ---
    st.markdown("---")
    st.markdown(f"### Aktueller Preis: **{preis_pos:.2f} €**")
    
    if st.button("In den Warenkorb legen", type="primary"):
        if preis_pos > 0:
            st.session_state['positionen'].append({
                "Beschreibung": text_pos,
                "Menge": menge_pos,
                "Preis": preis_pos
            })
            st.success("Hinzugefügt!")
            st.rerun()
        else:
            st.error("Preis ist 0 €.")

# --- 7. RECHTE SPALTE: WARENKORB & PDF ---
with col_cart:
    st.markdown("### 🛒 Warenkorb")
    
    if st.session_state['positionen']:
        # Tabelle anzeigen
        df = pd.DataFrame(st.session_state['positionen'])
        st.dataframe(df, hide_index=True, use_container_width=True)
        
        # Summe
        total = sum(p['Preis'] for p in st.session_state['positionen'])
        st.markdown(f"### Gesamt: {total:.2f} €")
        
        # PDF Download
        pdf_data = create_pdf(st.session_state['positionen'])
        st.download_button(
            label="📄 PDF Angebot laden",
            data=pdf_data,
            file_name="angebot_meingassner.pdf",
            mime="application/pdf"
        )
        
        # Leeren
        if st.button("Warenkorb leeren"):
            st.session_state['positionen'] = []
            st.rerun()
    else:
        st.info("Noch keine Positionen.")
