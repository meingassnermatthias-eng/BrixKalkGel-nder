import streamlit as st
import math
import pandas as pd
from fpdf import FPDF
import datetime

# --- DATENBANK & PREISLOGIK ---
class BrixDatabase:
    def __init__(self):
        # 1. MODELLE (Preise exkl. MwSt, Basis 1000mm Höhe)
        self.modelle = {
            "--- STAB-GELÄNDER ---": None,
            "DECOR 22 (Stäbe 22mm)": {"preis": 204.00, "schraeg_plus": 30.00, "kat": "L", "seite": 6},
            "DECOR 60 (Breite Stäbe)": {"preis": 204.00, "schraeg_plus": 30.00, "kat": "L", "seite": 7},
            "STAKETEN 40 (Standard)": {"preis": 169.00, "schraeg_plus": 30.00, "kat": "L", "seite": 10},
            "STAKETEN 60 (Breit)": {"preis": 169.00, "schraeg_plus": 30.00, "kat": "L", "seite": 10},
            "STAKETEN 22 (Fein)": {"preis": 169.00, "schraeg_plus": 30.00, "kat": "L", "seite": 10},
            "VERTI.SIGN (40/60/100)": {"preis": 207.00, "schraeg_plus": 30.00, "kat": "L", "seite": 16},
            "INQUER (Querstäbe)": {"preis": 190.00, "schraeg_plus": 30.00, "kat": "L", "seite": 16},
            
            "--- LATTEN & PALISADEN ---": None,
            "LATTEN-Classic (45mm)": {"preis": 206.00, "schraeg_plus": 30.00, "kat": "S", "seite": 14},
            "LATTEN-Füllung (Vertikal)": {"preis": 210.00, "schraeg_plus": 60.00, "kat": "S", "seite": 12},
            "PALISADEN (Rund 25mm)": {"preis": 180.00, "schraeg_plus": 30.00, "kat": "L", "seite": 15},
            "PALIQUADRA (Eckig 22mm)": {"preis": 218.00, "schraeg_plus": 30.00, "kat": "L", "seite": 15},
            
            "--- GLAS & FLÄCHIG ---": None,
            "GLASAL (Rahmen + VSG)": {"preis": 307.00, "schraeg_plus": 45.00, "kat": "S", "seite": 17},
            "GLASALO (Rahmen 10mm)": {"preis": 284.00, "schraeg_plus": 45.00, "kat": "S", "seite": 17},
            "DECOR-PERFORÉE (Lochblech)": {"preis": 250.00, "schraeg_plus": 32.00, "kat": "S", "seite": 8},
            "STAKET ON FLAT": {"preis": 255.00, "schraeg_plus": 32.00, "kat": "S", "seite": 9},
            "FLAT-DESIGN": {"preis": 265.00, "schraeg_plus": 32.00, "kat": "S", "seite": 11},
            
            "--- HORIZONTAL & SICHTSCHUTZ ---": None,
            "LAMELLO (Sichtschutz)": {"preis": 221.00, "schraeg_plus": 35.00, "kat": "S", "seite": 22},
            "FRONTLINE (Quer VOR Steher)": {"preis": 210.00, "schraeg_plus": 35.00, "kat": "S", "seite": 21},
            "STAKETTO (Quer IM Rahmen)": {"preis": 221.00, "schraeg_plus": 35.00, "kat": "S", "seite": 20},
        }

        # 2. STEHER VARIANTEN
        self.steher_varianten = {
            "66x66mm Standard": {
                "AM (Boden)": 125.00, 
                "SM (Wand)": 161.00, 
                "SM (Wand) - 90° Eck": 203.00
            },
            "100x66mm Verstärkt": {
                "AM (Boden)": 151.00, 
                "SM (Wand)": 179.00,
                "SM (Wand) - Spezial": 264.00
            },
            "32x66mm Slim (nur Glas/Flat)": {
                "AM (Boden)": 86.00, 
                "SM (Wand)": 121.00
            }
        }

        # 3. EXTRAS & FARBEN
        self.verblendungen = {
            "Keine": 0.00,
            "BV 160 (2 Latten)": 33.00,
            "BV 240 (3 Latten)": 41.00,
            "BV 320 (4 Latten)": 50.00,
            "BV 400 (5 Latten)": 58.00,
        }

        self.ornamente = {
            "Keine": 0.00,
            "Karo (Raute)": 30.00,
            "Trigon (Dreieck)": 30.00,
            "Trio (3 Streifen)": 30.00,
            "Kreis / Ring": 40.00, 
            "Zierleiste (für Staketen)": 45.00
        }

        self.statik = {"L": 1.90, "S": 1.30} 
        
        self.farben = {
            "STF (Standard)": 1.00,
            "SOF (Sonderfarbe +10%)": 1.10,
            "SPF (Spezialfarbe +30%)": 1.30,
            "HD (Holzdekor ~+25%)": 1.25
        }
        
        self.eck_preis = 95.00
        self.aufpreis_hoehe_pro_m = 30.00 

# --- RECHENLOGIK ---
def berechne_projekt(d, db):
    m_info = db.modelle[d['modell']]
    total_laenge = d['laenge_gerade'] + d['laenge_schraeg']
    
    # 1. Felder Kosten (inkl. Höhenaufschlag)
    preis_basis_m = m_info['preis']
    aufpreis_hoehe_ges = 0
    
    if d['hoehe'] > 1000:
        preis_basis_m += db.aufpreis_hoehe_pro_m
        aufpreis_hoehe_ges = total_laenge * db.aufpreis_hoehe_pro_m

    preis_gerade = d['laenge_gerade'] * preis_basis_m
    preis_schraeg = d['laenge_schraeg'] * (preis_basis_m + m_info['schraeg_plus'])
    kosten_felder = preis_gerade + preis_schraeg
    
    # 2. Steher
    max_abstand = db.statik[m_info['kat']]
    if total_laenge > 0:
        anzahl_felder = math.ceil(total_laenge / max_abstand)
        anzahl_steher = anzahl_felder + 1 + d['ecken']
    else:
        anzahl_steher = 0
        
    preis_pro_steher = db.steher_varianten[d['steher_typ']][d['montage_typ']]
    kosten_steher = anzahl_steher * preis_pro_steher
    
    # 3. Extras
    kosten_ecken = d['ecken'] * db.eck_preis
    kosten_verblendung = d['laenge_verblendung'] * db.verblendungen[d['verblendung_typ']]
    kosten_ornamente = d['ornamente_anzahl'] * db.ornamente[d['ornamente_typ']]
    
    kosten_zubehoer = 0
    if d['blumenkasten'] > 0: kosten_zubehoer += d['blumenkasten'] * 135.00
    if d['handlauf_wand'] > 0: kosten_zubehoer += d['handlauf_wand'] * 70.00
    
    # 4. Rabatte
    summe_material = kosten_felder + kosten_steher + kosten_ecken + kosten_verblendung + kosten_ornamente + kosten_zubehoer
    faktor = db.farben[d['farbe']]
    
    material_farbig = summe_material * faktor
    rabatt_wert = material_farbig * (d['rabatt'] / 100)
    material_netto = material_farbig - rabatt_wert
    
    # 5. Montage
    kosten_montage = d['montage_stunden'] * d['montage_satz']
    
    # 6. Endsummen
    netto_total = material_netto + kosten_montage
    mwst = netto_total * 0.20
    brutto = netto_total + mwst
    
    return {
        "steher_anz": anzahl_steher,
        "k_felder": kosten_felder * faktor,
        "k_steher": kosten_steher * faktor,
        "k_ecken": kosten_ecken * faktor,
        "k_verblendung": kosten_verblendung * faktor,
        "k_ornamente": kosten_ornamente * faktor,
        "k_zubehoer": kosten_zubehoer * faktor,
        "k_montage": kosten_montage,
        "rabatt": rabatt_wert,
        "netto": netto_total,
        "mwst": mwst,
        "brutto": brutto,
        "input_data": d # Für PDF benötigt
    }

# --- PDF GENERATOR (FPDF) ---
def create_pdf(res, db):
    pdf = FPDF()
    pdf.add_page()
    
    # HACK: Unicode Zeichen in FPDF (Standard-Fonts unterstützen kein €)
    # Wir nutzen Latin-1 und schreiben EUR statt € um Fehler zu vermeiden
    def txt(s):
        return str(s).encode('latin-1', 'replace').decode('latin-1')

    # --- Header ---
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt("BRIX GELÄNDER - KOSTENSCHÄTZUNG"), ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 10, txt(f"Datum: {datetime.date.today().strftime('%d.%m.%Y')}"), ln=True, align='R')
    pdf.ln(10)

    # --- Projekt Infos ---
    d = res['input_data']
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, txt("Projektdaten:"), ln=True)
    pdf.set_font("Arial", '', 10)
    
    # Datenblock
    infos = [
        f"Modell: {d['modell']}",
        f"Höhe: {d['hoehe']} mm",
        f"Farbe: {d['farbe']}",
        f"Steher: {d['steher_typ']} ({d['montage_typ']})",
        f"Länge: {d['laenge_gerade'] + d['laenge_schraeg']} m (Gerade: {d['laenge_gerade']}m / Schräg: {d['laenge_schraeg']}m)"
    ]
    
    for info in infos:
        pdf.cell(0, 6, txt(info), ln=True)
    pdf.ln(10)

    # --- Tabelle ---
    pdf.set_font("Arial", 'B', 10)
    # Header: Position, Menge, Gesamt
    pdf.cell(110, 8, txt("Position"), 1)
    pdf.cell(30, 8, txt("Menge"), 1, 0, 'C')
    pdf.cell(50, 8, txt("Preis (Netto)"), 1, 0, 'R')
    pdf.ln()

    # Inhalt
    pdf.set_font("Arial", '', 10)

    def add_row(pos, menge, preis):
        pdf.cell(110, 8, txt(pos), 1)
        pdf.cell(30, 8, txt(menge), 1, 0, 'C')
        pdf.cell(50, 8, txt(f"{preis:,.2f} EUR"), 1, 0, 'R')
        pdf.ln()

    # 1. Felder
    total_l = d['laenge_gerade'] + d['laenge_schraeg']
    h_text = f" (H={d['hoehe']}mm)" if d['hoehe'] > 1000 else ""
    add_row(f"Geländer-Felder{h_text}", f"{total_l} m", res['k_felder'])
    
    # 2. Steher
    add_row(f"Steher & Befestigung ({d['steher_typ']})", f"{res['steher_anz']} Stk", res['k_steher'])
    
    # 3. Ecken
    if d['ecken'] > 0:
        add_row("Eckverbinder / Ausbildung", f"{d['ecken']} Stk", res['k_ecken'])
        
    # 4. Verblendung
    if d['laenge_verblendung'] > 0:
        add_row(f"Balkonverblendung ({d['verblendung_typ']})", f"{d['laenge_verblendung']} m", res['k_verblendung'])
        
    # 5. Ornamente
    if d['ornamente_anzahl'] > 0:
        add_row(f"Zierelemente: {d['ornamente_typ']}", f"{d['ornamente_anzahl']} Stk", res['k_ornamente'])
        
    # 6. Zubehör
    if res['k_zubehoer'] > 0:
        add_row("Zubehör (Blumenk./Handlauf)", "Pausch.", res['k_zubehoer'])
        
    # 7. Rabatt
    if d['rabatt'] > 0:
        pdf.set_text_color(200, 0, 0) # Rot für Rabatt
        add_row(f"Rabatt auf Material ({d['rabatt']}%)", "1 x", -res['rabatt'])
        pdf.set_text_color(0, 0, 0) # Schwarz zurück
        
    # 8. Montage
    if d['montage_stunden'] > 0:
        add_row("Montageleistung", f"{d['montage_stunden']} Std", res['k_montage'])

    # --- Summenblock ---
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 10)
    
    # Funktion für Summenzeile rechtsbündig
    def add_total(label, value, is_bold=False):
        if is_bold: pdf.set_font("Arial", 'B', 12)
        else: pdf.set_font("Arial", '', 10)
        
        pdf.cell(140, 8, txt(label), 0, 0, 'R')
        pdf.cell(50, 8, txt(f"{value:,.2f} EUR"), 1, 1, 'R')

    add_total("Netto Summe:", res['netto'])
    add_total("MwSt (20%):", res['mwst'])
    add_total("GESAMT BRUTTO:", res['brutto'], is_bold=True)

    # --- Footer ---
    pdf.ln(20)
    pdf.set_font("Arial", 'I', 8)
    pdf.multi_cell(0, 5, txt("Dies ist eine automatische Kostenschätzung basierend auf der Brix Preisliste 2025. "
                             "Angaben ohne Gewähr. Für eine exakte Bestellung ist eine Naturmaßnahme vor Ort erforderlich. "
                             "Preise verstehen sich exkl. allfälliger Frachtkosten."))

    return pdf.output(dest='S').encode('latin-1')

# --- MAIN APP ---
def main():
    st.set_page_config(page_title="Brix Kalkulator V4", page_icon="🏗️", layout="wide")
    db = BrixDatabase()
    
    st.title("🏗️ Brix Profi-Kalkulator (V4.0 - PDF)")
    
    col_nav, col_calc = st.columns([1, 1.5])
    
    with col_nav:
        tab1, tab2, tab3, tab4 = st.tabs(["📏 Maße", "🔩 Montage", "✨ Extras", "💰 Setup"])
        
        with tab1:
            st.subheader("Modell & Dimensionen")
            opts = [k for k in db.modelle.keys() if db.modelle[k] is not None]
            modell = st.selectbox("Modell:", opts)
            
            hoehe = st.number_input("Geländerhöhe (mm):", 800, 1200, 1000, step=50)
            if hoehe > 1000:
                st.warning(f"⚠️ Überhöhe: Aufpreis berücksichtigt.")

            c1, c2 = st.columns(2)
            l_gerade = c1.number_input("Gerade (m):", 0.0, 100.0, 10.0, step=0.5)
            l_schraeg = c2.number_input("Schräg (m):", 0.0, 50.0, 0.0, step=0.5)
            ecken = st.number_input("Anzahl Ecken:", 0, 20, 0)

        with tab2:
            st.subheader("Konstruktion")
            s_typ = st.selectbox("Steher:", list(db.steher_varianten.keys()))
            m_typ = st.selectbox("Montage:", list(db.steher_varianten[s_typ].keys()))
            st.divider()
            std = st.number_input("Montage Stunden:", 0.0, 500.0, 0.0, step=1.0)
            satz = st.number_input("Stundensatz (€):", 0.0, 200.0, 65.0, step=5.0)

        with tab3:
            st.subheader("Extras")
            verb_typ = st.selectbox("Verblendung:", list(db.verblendungen.keys()))
            verb_l = st.number_input("Länge Verbl. (m):", 0.0, 100.0, 0.0)
            st.divider()
            orn_typ = st.selectbox("Ornament:", list(db.ornamente.keys()))
            orn_anz = st.number_input("Anzahl Orn.:", 0, 100, 0)
            st.divider()
            bk = st.number_input("Blumenkästen:", 0, 20, 0)
            wh = st.number_input("Wandhandlauf (m):", 0.0, 50.0, 0.0)

        with tab4:
            st.subheader("Konditionen")
            farbe = st.selectbox("Farbe:", list(db.farben.keys()))
            rabatt = st.slider("Rabatt Material (%):", 0, 50, 0)

    # Calculate
    data = {
        "modell": modell, "hoehe": hoehe, "laenge_gerade": l_gerade, "laenge_schraeg": l_schraeg,
        "ecken": ecken, "steher_typ": s_typ, "montage_typ": m_typ, "montage_stunden": std,
        "montage_satz": satz, "verblendung_typ": verb_typ, "laenge_verblendung": verb_l,
        "ornamente_typ": orn_typ, "ornamente_anzahl": orn_anz, "blumenkasten": bk,
        "handlauf_wand": wh, "farbe": farbe, "rabatt": rabatt
    }
    res = berechne_projekt(data, db)
    
    with col_calc:
        st.container()
        k1, k2, k3 = st.columns(3)
        k1.metric("Netto", f"€ {res['netto']:,.2f}")
        k2.metric("MwSt", f"€ {res['mwst']:,.2f}")
        k3.metric("Brutto", f"€ {res['brutto']:,.2f}", delta="Final")
        
        st.divider()
        
        # Vorschau Tabelle
        df_rows = [
            ["Felder", f"{l_gerade+l_schraeg} m", f"€ {res['k_felder']:,.2f}"],
            ["Steher", f"{res['steher_anz']} Stk", f"€ {res['k_steher']:,.2f}"],
            ["Montage", f"{std} h", f"€ {res['k_montage']:,.2f}"]
        ]
        st.dataframe(pd.DataFrame(df_rows, columns=["Posten", "Menge", "Netto"]), hide_index=True, use_container_width=True)
        
        # PDF Button
        pdf_bytes = create_pdf(res, db)
        st.download_button(
            label="📄 PDF Angebot herunterladen",
            data=pdf_bytes,
            file_name=f"Angebot_Brix_{datetime.date.today()}.pdf",
            mime="application/pdf",
            type="primary"
        )

if __name__ == "__main__":
    main()