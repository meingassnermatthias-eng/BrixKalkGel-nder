import streamlit as st
import pandas as pd
from fpdf import FPDF
import base64

# --- SEITEN KONFIGURATION ---
# --- SEITEN KONFIGURATION ---
# Das Bild "logo.png" muss im gleichen Ordner liegen wie diese Datei!
st.set_page_config(
    page_title="Meingassner App",    # <--- Der Name der App
    page_icon="logo.png",            # <--- Dein Logo als App-Icon
    layout="wide"
)
# Logo oben links in der Sidebar anzeigen
st.logo("logo.png")
# --- SESSION STATE (Hier speichern wir die Positionen) ---
if 'positionen' not in st.session_state:
    st.session_state['positionen'] = []

# --- HILFSFUNKTION: PDF ERSTELLEN ---
def create_pdf(positionen_liste):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    
    # Kopfzeile
    pdf.cell(0, 10, "Angebot - Meingassner Metalltechnik", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, "Spezialist für Geländer, Treppen, Zäune & Überdachungen", ln=True, align='C')
    pdf.ln(10)
    
    # Tabellenkopf
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(80, 10, "Beschreibung", 1)
    pdf.cell(30, 10, "Menge", 1)
    pdf.cell(40, 10, "Einzelpreis", 1)
    pdf.cell(40, 10, "Gesamt", 1)
    pdf.ln()
    
    # Inhalt
    pdf.set_font("Arial", size=12)
    gesamt_netto = 0
    
    for pos in positionen_liste:
        # Umlaute fixen für FPDF (einfache Methode)
        beschreibung = pos['Beschreibung'].encode('latin-1', 'replace').decode('latin-1')
        menge = str(pos['Menge'])
        preis = f"{pos['Preis']:.2f}"
        
        pdf.cell(80, 10, beschreibung, 1)
        pdf.cell(30, 10, menge, 1)
        pdf.cell(40, 10, "", 1) # Einzelpreis hier vereinfacht leer oder berechnen
        pdf.cell(40, 10, preis + " EUR", 1)
        pdf.ln()
        
        gesamt_netto += pos['Preis']
        
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(110, 10, "", 0)
    pdf.cell(40, 10, "Gesamtsumme:", 1)
    pdf.cell(40, 10, f"{gesamt_netto:.2f} EUR", 1)
    
    # Rückgabe als String (latin-1 encoding für PDF byte stream)
    return pdf.output(dest='S').encode('latin-1')

# --- SIDEBAR NAVIGATION ---
st.sidebar.header("Menü Auswahl")
bereich = st.sidebar.radio("Hauptbereich:", ["Eigenfertigung", "Handel & Systeme"], index=0)
st.sidebar.markdown("---")

if bereich == "Eigenfertigung":
    modus = st.sidebar.radio("Produkt:", ["Individuell (Treppen/Geländer)", "Gitterstabmatten", "Vordächer"])
else:
    modus = st.sidebar.radio("System:", ["Brix Zaun", "Terrassendach", "Fenster & Türen"])

# --- HAUPTBEREICH ---
st.title(f"Kalkulation: {modus}")

# Variablen initialisieren (damit sie später verfügbar sind)
preis_dieser_position = 0.0
beschreibung_text = ""
menge_text = 1.0

# === 1. EINGABEMASKE ===
col_input, col_summary = st.columns([2, 1])

with col_input:
    # ---------------------------------------------------------
    # MODUS: INDIVIDUELL (Treppen & Geländer)
    # ---------------------------------------------------------
    if modus == "Individuell (Treppen/Geländer)":
        with st.expander("Parameter", expanded=True):
            c1, c2 = st.columns(2)
            stundensatz = c1.number_input("Stundensatz (€)", value=65.0)
            mat_faktor = c2.number_input("Material Faktor", value=1.2)
            modell = st.selectbox("Modell", ["Stahltreppe Gerade", "Geländer Edelstahl", "Geländer Verzinkt"])

        m1, m2, m3 = st.columns(3)
        anzahl = m1.number_input("Anzahl / Stk.", value=1.0)
        laenge = m2.number_input("Länge (m)", value=3.0)
        breite = m3.number_input("Breite (m)", value=1.0)
        
        # Checkboxen
        opt_wangen = st.checkbox("Wangen (40€)")
        opt_rost = st.checkbox("Gitterrost (35€)")
        
        # Berechnung (Dummy Logik)
        material = (laenge * breite * 50) * mat_faktor
        arbeit = (anzahl * 5) * stundensatz
        extras = 0
        if opt_wangen: extras += 40
        if opt_rost: extras += 35
        
        preis_dieser_position = material + arbeit + extras
        beschreibung_text = f"{modell} ({laenge}x{breite}m)"
        menge_text = anzahl

    # ---------------------------------------------------------
    # MODUS: BRIX ZAUN (Beispiel)
    # ---------------------------------------------------------
    elif modus == "Brix Zaun":
        modell = st.selectbox("Brix Modell", ["Lattenzaun", "Palisaden"])
        lfm = st.number_input("Laufmeter", value=10.0)
        preis_pro_m = 150.0 # Beispielpreis
        
        preis_dieser_position = lfm * preis_pro_m
        beschreibung_text = f"Brix {modell} ({lfm} lfm)"
        menge_text = lfm

    # ---------------------------------------------------------
    # Andere Modi (Platzhalter)
    # ---------------------------------------------------------
    else:
        st.info("Für diesen Bereich ist noch keine Formel hinterlegt.")
        preis_dieser_position = 0.0
        beschreibung_text = modus

    # === PREIS ANZEIGE & BUTTON ===
    st.markdown("---")
    st.subheader(f"Positionspreis: {preis_dieser_position:.2f} €")
    
    if st.button("➕ Position zum Angebot hinzufügen", type="primary"):
        if preis_dieser_position > 0:
            neue_pos = {
                "Beschreibung": beschreibung_text,
                "Menge": menge_text,
                "Preis": preis_dieser_position
            }
            st.session_state['positionen'].append(neue_pos)
            st.success("Hinzugefügt!")
            st.rerun()
        else:
            st.warning("Preis ist 0, kann nicht hinzugefügt werden.")

# === 2. ANGEBOTS-ZUSAMMENFASSUNG (Rechts oder Unten) ===
with col_summary:
    st.write("### 📝 Aktuelles Angebot")
    
    if len(st.session_state['positionen']) > 0:
        # Tabelle anzeigen
        df = pd.DataFrame(st.session_state['positionen'])
        st.dataframe(df, hide_index=True)
        
        # Gesamtsumme
        total = sum(item['Preis'] for item in st.session_state['positionen'])
        st.markdown(f"### Summe: {total:.2f} €")
        
        # PDF DOWNLOAD BUTTON
        pdf_bytes = create_pdf(st.session_state['positionen'])
        
        st.download_button(
            label="📄 Angebot als PDF herunterladen",
            data=pdf_bytes,
            file_name="angebot_meingassner.pdf",
            mime="application/pdf"
        )
        
        # Liste löschen Button
        if st.button("🗑️ Angebot leeren"):
            st.session_state['positionen'] = []
            st.rerun()
            
    else:
        st.info("Noch keine Positionen im Angebot.")
