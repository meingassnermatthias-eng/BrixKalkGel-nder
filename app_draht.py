import streamlit as st

# --- Seitenkonfiguration ---
st.set_page_config(page_title="Meingassner Kalkulation", layout="wide")

# --- TITEL & LOGO (oben) ---
st.title("Meingassner Metalltechnik - Kalkulation")

# --- SIDEBAR (Die saubere Navigation) ---
st.sidebar.header("Menü")

# 1. Hauptauswahl: Eigenfertigung oder Zukauf/Systeme
bereich = st.sidebar.radio(
    "Bereich wählen:",
    ["Eigenfertigung", "Handel & Systeme"],
    index=0
)

st.sidebar.markdown("---") # Trennlinie

# 2. Untermenü (ändert sich je nach Bereich)
if bereich == "Eigenfertigung":
    # Deine gefertigten Produkte
    modus = st.sidebar.radio(
        "Produkt:",
        ["Individuell (Treppen/Geländer)", "Gitterstabmattenzäune", "Vordächer"]
    )
    
else: # Handel & Systeme
    # Deine Zukauf-Produkte
    modus = st.sidebar.radio(
        "System:",
        ["Brix Zaun", "Terrassendach / Sommergarten", "Alu Fenster & Türen"]
    )

# --- HAUPTBEREICH (Rechts) ---

# ---------------------------------------------------------
# MODUS: INDIVIDUELL (Treppen & Geländer) - Dein Screenshot
# ---------------------------------------------------------
if modus == "Individuell (Treppen/Geländer)":
    st.subheader("🛠️ Metallbau Individual Kalkulation")

    # Parameter Block (wie im Screenshot)
    with st.expander("Grundeinstellungen & Parameter", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            stundensatz = st.number_input("Stundensatz (€)", value=65.00, step=1.0)
        with col2:
            material_faktor = st.number_input("Material Faktor", value=1.20, step=0.05)
            
        c1, c2 = st.columns(2)
        with c1:
            kategorie = st.selectbox("Kategorie", ["Treppe", "Geländer Edelstahl", "Geländer Stahl verzinkt"])
        with c2:
            modell = st.selectbox("Modell", ["Stahltreppe Gerade", "Stahltreppe Gewendelt", "Individual"])

    # Maße
    st.markdown("### Maße")
    m1, m2, m3 = st.columns(3)
    with m1:
        anzahl = st.number_input("Anzahl (Stufen/Lfm)", value=1.0, step=1.0)
    with m2:
        laenge = st.number_input("Länge (m)", value=0.0, step=0.1)
    with m3:
        breite = st.number_input("Breite (m)", value=0.0, step=0.1)

    # Optionen (Checkboxen aus Screenshot)
    st.markdown("### Optionen")
    opt_wangen = st.checkbox("Wangen aus Flachstahl (40.00€ Pauschal)")
    opt_gitterrost = st.checkbox("Stufen Gitterrost (35.0€ Pauschal)")
    opt_gelaender = st.checkbox("Geländer einseitig (140.0€ pro lfm)")
    opt_pulver = st.checkbox("Pulverbeschichtung (80.0€ pro lfm)")

    # Einfache Dummy-Berechnung (damit du ein Ergebnis siehst)
    # Hier musst du später deine echten Formeln hinterlegen
    material_kosten = (laenge * breite * 100) * material_faktor
    arbeits_kosten = (anzahl * 2) * stundensatz
    zusatz_kosten = 0
    
    if opt_wangen: zusatz_kosten += 40
    if opt_gitterrost: zusatz_kosten += 35
    if opt_gelaender: zusatz_kosten += (140 * laenge)
    if opt_pulver: zusatz_kosten += (80 * laenge)

    gesamtpreis = material_kosten + arbeits_kosten + zusatz_kosten

    st.markdown("---")
    # Ergebnis Box
    st.info(f"💰 Kalkulierter Preis: **{gesamtpreis:.2f} €**")
    
    if st.button("In den Warenkorb / Angebot erstellen"):
        st.success("Position zum Angebot hinzugefügt!")

# ---------------------------------------------------------
# MODUS: BRIX ZAUN
# ---------------------------------------------------------
elif modus == "Brix Zaun":
    st.subheader("🧱 Brix Zaun Konfigurator")
    st.write("Hier folgt die Eingabemaske für Brix Zäune.")
    # Platzhalter für Brix Logik
    modell_brix = st.selectbox("Brix Modell", ["Lattenzaun", "Palisaden", "Sichtschutz"])
    lfm_brix = st.number_input("Laufmeter", value=10.0)
    st.info(f"Geschätzter Preis für {lfm_brix}m {modell_brix}: (Formel einfügen)")

# ---------------------------------------------------------
# MODUS: VORDÄCHER
# ---------------------------------------------------------
elif modus == "Vordächer":
    st.subheader("☔ Vordächer")
    st.write("Planung für Vordächer.")

# ---------------------------------------------------------
# MODUS: GITTERSTABMATTEN
# ---------------------------------------------------------
elif modus == "Gitterstabmattenzäune":
    st.subheader("🚧 Gitterstabmatten")
    st.write("Kalkulation für Standard-Zäune.")

# ---------------------------------------------------------
# MODUS: TERRASSENDACH
# ---------------------------------------------------------
elif modus == "Terrassendach / Sommergarten":
    st.subheader("☀️ Terrassendach & Sommergarten")
    st.write("Konfigurator für Überdachungen.")

# ---------------------------------------------------------
# MODUS: FENSTER & TÜREN
# ---------------------------------------------------------
elif modus == "Alu Fenster & Türen":
    st.subheader("🚪 Aluminium Fenster & Türen (Montage)")
    st.write("Erfassung für Zukaufteile und Montageaufwand.")
