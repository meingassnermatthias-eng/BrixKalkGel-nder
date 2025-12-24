import streamlit as st
import math
import pandas as pd
from fpdf import FPDF
import datetime
import base64
import os

# --- 1. DATENBANK & LOGIK ---
class BrixDatabase:
    def __init__(self, preisfaktor=1.0):
        self.faktor = preisfaktor # Globaler Preisfaktor

        # MODELLE (Basispreis pro lfm für 1000mm Höhe, exkl. MwSt)
        # Quelle: PDF Preisliste 2025
        self.raw_modelle = {
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

        # STEHER VARIANTEN
        self.raw_steher = {
            "66x66mm Standard": {"AM (Boden)": 125.00, "SM (Wand)": 161.00},
            "100x66mm Verstärkt": {"AM (Boden)": 151.00, "SM (Wand)": 179.00},
            "32x66mm Slim (nur Glas/Flat)": {"AM (Boden)": 86.00, "SM (Wand)": 121.00}
        }

        # Dynamische Preisanpassung (Faktor) anwenden
        self.modelle = {}
        for name, data in self.raw_modelle.items():
            if data is None:
                self.modelle[name] = None
            else:
                self.modelle[name] = data.copy()
                self.modelle[name]['preis'] *= self.faktor
                self.modelle[name]['schraeg_plus'] *= self.faktor

        self.steher_varianten = {}
        for typ, variants in self.raw_steher.items():
            self.steher_varianten[typ] = {k: v * self.faktor for k, v in variants.items()}

        # EXTRAS & ZUBEHÖR (auch mit Faktor)
        self.verblendungen = {k: v * self.faktor for k, v in {
            "Keine": 0.00, "BV 160 (2 Latten)": 33.00, "BV 240 (3 Latten)": 41.00,
            "BV 320 (4 Latten)": 50.00, "BV 400 (5 Latten)": 58.00}.items()}

        self.ornamente = {k: v * self.faktor for k, v in {
            "Keine": 0.00, "Karo (Raute)": 30.00, "Trigon (Dreieck)": 30.00,
            "Trio (3 Streifen)": 30.00, "Kreis / Ring": 40.00}.items()}

        self.statik = {"L": 1.90, "S": 1.30}
        self.farben = {"STF (Standard)": 1.00, "SOF (+10%)": 1.10, "SPF (+30%)": 1.30, "HD (+25%)": 1.25}
        
        self.eck_preis = 95.00 * self.faktor
        self.aufpreis_hoehe_pro_m = 30.00 * self.faktor # Aufpreis ab 1001mm Höhe
        self.blumenkasten_preis = 135.00 * self.faktor
        self.wandhandlauf_preis = 70.00 * self.faktor

def berechne_projekt(d, db):
    m_info = db.modelle[d['modell']]
    total_laenge = d['laenge_gerade'] + d['laenge_schraeg']
    
    # 1. Felder Kosten
    preis_basis = m_info['preis']
    # Höhenaufschlag prüfen (Seite 30)
    if d['hoehe'] > 1000: 
        preis_basis += db.aufpreis_hoehe_pro_m

    k_felder = (d['laenge_gerade'] * preis_basis) + \
               (d['laenge_schraeg'] * (preis_basis + m_info['schraeg_plus']))
    
    # 2. Steher Kosten
    if total_laenge > 0:
        anzahl_steher = math.ceil(total_laenge / db.statik[m_info['kat']]) + 1 + d['ecken']
    else:
        anzahl_steher = 0
    k_steher = anzahl_steher * db.steher_varianten[d['steher_typ']][d['montage_typ']]
    
    # 3. Extras Kosten
    k_extras = (d['ecken'] * db.eck_preis) + \
               (d['laenge_verblendung'] * db.verblendungen[d['verblendung_typ']]) + \
               (d['ornamente_anzahl'] * db.ornamente[d['ornamente_typ']]) + \
               (d['blumenkasten'] * db.blumenkasten_preis) + \
               (d['handlauf_wand'] * db.wandhandlauf_preis)
    
    # 4. Rabatt & Summen
    mat_netto = (k_felder + k_steher + k_extras) * db.farben[d['farbe']]
    rabatt_wert = mat_netto * (d['rabatt'] / 100)
    mat_final = mat_netto - rabatt_wert
    
    # 5. Montage
    montage = d['montage_stunden'] * d['montage_satz']
    
    # 6. Endergebnis
    total_netto = mat_final + montage
    return {
        "steher_anz": anzahl_steher, "k_felder": k_felder * db.farben[d['farbe']],
        "k_steher": k_steher * db.farben[d['farbe']], "k_extras": k_extras * db.farben[d['farbe']],
        "rabatt": rabatt_wert, "k_montage": montage,
        "netto": total_netto, "mwst": total_netto * 0.20, "brutto": total_netto * 1.20,
        "input": d
    }

# --- 2. PDF VIEWER (Mit Edge Fix) ---
def display_pdf(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
        
        # Sicherer Button (funktioniert immer)
        st.download_button(
            label="📖 Preisliste in neuem Fenster öffnen (PDF)",
            data=base64.b64decode(base64_pdf),
            file_name="Brix_Preisliste.pdf",
            mime="application/pdf",
            use_container_width=True
        )

        # Vorschau-Versuch (Object Tag ist besser für Edge als Iframe)
        pdf_display = f"""
            <object data="data:application/pdf;base64,{base64_pdf}" type="application/pdf" width="100%" height="800px">
                <p style="text-align:center; margin-top:20px;">
                Vorschau nicht verfügbar? Klicke einfach auf den Button oben! 👆</p>
            </object>
        """
        st.markdown(pdf_display, unsafe_allow_html=True)
    else:
        st.warning("⚠️ Keine Datei 'preisliste.pdf' gefunden.")
        st.info("Lade deine PDF als 'preisliste.pdf' auf GitHub hoch, damit sie hier erscheint.")

# --- 3. ANGEBOT ERSTELLEN (PDF Download) ---
def create_sales_pdf(res, db):
    pdf = FPDF()
    pdf.add_page()
    # Hilfsfunktion für Sonderzeichen (UTF-8 zu Latin-1 Mapping)
    def txt(s): return str(s).encode('latin-1', 'replace').decode('latin-1')

    # Header
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt("ANGEBOT - KOSTENSCHÄTZUNG"), ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 10, txt(f"Datum: {datetime.date.today().strftime('%d.%m.%Y')}"), ln=True, align='R')
    
    # Projekt Infos
    d = res['input']
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, txt(f"Projekt: {d['modell']} ({d['farbe']})"), ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 6, txt(f"Länge: {d['laenge_gerade']+d['laenge_schraeg']}m | Höhe: {d['hoehe']}mm"), ln=True)
    pdf.cell(0, 6, txt(f"Montageart: {d['steher_typ']} - {d['montage_typ']}"), ln=True)
    pdf.ln(10)
    
    # Tabelle Header
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(130, 8, txt("Position / Leistung"), 1, 0, 'L', 1)
    pdf.cell(60, 8, txt("Betrag (Netto)"), 1, 1, 'R', 1)
    
    pdf.set_font("Arial", '', 10)
    def row(label, val):
        pdf.cell(130, 8, txt(label), 1)
        pdf.cell(60, 8, txt(f"{val:,.2f} EUR"), 1, 1, 'R')

    # Positionen
    h_text = f" (H={d['hoehe']}mm)" if d['hoehe'] > 1000 else ""
    row(f"Material Geländer-Felder{h_text}", res['k_felder'])
    row(f"Steher ({res['steher_anz']} Stk) & Befestigung", res['k_steher'])
    
    if res['k_extras'] > 0: 
        row("Extras (Ecken, Zier, Zubehör)", res['k_extras'])
    
    if d['rabatt'] > 0: 
        pdf.set_text_color(200,0,0) # Rot
        row(f"Abzüglich Rabatt ({d['rabatt']}%)", -res['rabatt'])
        pdf.set_text_color(0,0,0)
    
    if d['montage_stunden'] > 0: 
        row(f"Montageleistung ({d['montage_stunden']} Std)", res['k_montage'])
    
    # Summenblock
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(130, 10, txt("GESAMT NETTO"), 0, 0, 'R')
    pdf.cell(60, 10, txt(f"{res['netto']:,.2f} EUR"), 1, 1, 'R')
    
    pdf.cell(130, 10, txt("MwSt (20%)"), 0, 0, 'R')
    pdf.cell(60, 10, txt(f"{res['mwst']:,.2f} EUR"), 1, 1, 'R')
    
    pdf.set_fill_color(200, 255, 200) # Hellgrün
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(130, 10, txt("GESAMT BRUTTO"), 0, 0, 'R')
    pdf.cell(60, 10, txt(f"{res['brutto']:,.2f} EUR"), 1, 1, 'R', 1)
    
    # Footer
    pdf.ln(20)
    pdf.set_font("Arial", 'I', 8)
    pdf.multi_cell(0, 5, txt("Dies ist eine unverbindliche Kostenschätzung basierend auf der Brix Preisliste 2025. "
                             "Für eine exakte Bestellung ist eine Naturmaßnahme erforderlich."))
    
    return pdf.output(dest='S').encode('latin-1')

# --- 4. HAUPTPROGRAMM (GUI) ---
def main():
    st.set_page_config(page_title="Brix Kalkulator V5.1", page_icon="🏗️", layout="wide")
    
    # SIDEBAR: Admin & Preisfaktor
    with st.sidebar:
        st.header("⚙️ Einstellungen")
        st.write("Preis-Anpassung (Global):")
        preisfaktor = st.number_input("Faktor (1.00 = Original):", 0.50, 2.00, 1.00, 0.01)
        if preisfaktor != 1.0:
            st.warning(f"⚠️ Preise x {preisfaktor} aktiv!")
        
        st.divider()
        st.caption("ℹ️ 'preisliste.pdf' auf GitHub hochladen für Vorschau.")

    db = BrixDatabase(preisfaktor)
    st.title("🏗️ Brix Kalkulator & Katalog Viewer")

    # LAYOUT: Links App, Rechts PDF
    col_app, col_pdf = st.columns([1, 1])

    with col_app:
        # Eingabe Tabs
        tab1, tab2, tab3, tab4 = st.tabs(["📏 Maße", "🔩 Bau", "✨ Extras", "💰 Setup"])
        
        with tab1:
            opts = [k for k in db.modelle.keys() if db.modelle[k] is not None]
            modell = st.selectbox("Modellwahl:", opts)
            
            hoehe = st.number_input("Höhe (mm):", 800, 1200, 1000, 50, help="Standard 1000mm. Ab 1001mm Aufpreis!")
            if hoehe > 1000: st.caption("⚠️ Überhöhe (>1m) +30€/m")
            
            c1, c2 = st.columns(2)
            l_ger = c1.number_input("Gerade (m):", 0.0, 100.0, 10.0, 0.5)
            l_schr = c2.number_input("Schräg (m):", 0.0, 50.0, 0.0, 0.5)
            ecken = st.number_input("Anzahl Ecken:", 0, 20, 0)

        with tab2:
            s_typ = st.selectbox("Steher:", list(db.steher_varianten.keys()))
            m_typ = st.selectbox("Montage:", list(db.steher_varianten[s_typ].keys()))
            st.divider()
            std = st.number_input("Montage Stunden:", 0.0, 500.0, 0.0, 1.0)
            satz = st.number_input("Stundensatz (€):", 0.0, 200.0, 65.0, 5.0)

        with tab3:
            verb_typ = st.selectbox("Verblendung:", list(db.verblendungen.keys()))
            verb_l = st.number_input("Länge Verblendung (m):", 0.0, 100.0, 0.0)
            st.divider()
            orn_typ = st.selectbox("Ornament:", list(db.ornamente.keys()))
            orn_anz = st.number_input("Anzahl Orn.:", 0, 100, 0)
            st.divider()
            bk = st.number_input("Blumenkästen (Stk):", 0, 20, 0)
            wh = st.number_input("Wandhandlauf (m):", 0.0, 50.0, 0.0)

        with tab4:
            farbe = st.selectbox("Farbe:", list(db.farben.keys()))
            rabatt = st.slider("Rabatt Material (%):", 0, 50, 0)

        # Berechnen
        input_d = {
            "modell": modell, "hoehe": hoehe, "laenge_gerade": l_ger, "laenge_schraeg": l_schr,
            "ecken": ecken, "steher_typ": s_typ, "montage_typ": m_typ, "montage_stunden": std,
            "montage_satz": satz, "verblendung_typ": verb_typ, "laenge_verblendung": verb_l,
            "ornamente_typ": orn_typ, "ornamente_anzahl": orn_anz, "blumenkasten": bk,
            "handlauf_wand": wh, "farbe": farbe, "rabatt": rabatt
        }
        res = berechne_projekt(input_d, db)

        # Ergebnis Anzeige
        st.markdown("---")
        k1, k2 = st.columns(2)
        k1.metric("Netto", f"€ {res['netto']:,.2f}")
        k2.metric("Brutto (inkl. 20%)", f"€ {res['brutto']:,.2f}")
        
        with st.expander("Details anzeigen"):
            rows = [
                ["Material", f"€ {res['k_felder']:,.2f}"],
                ["Steher", f"€ {res['k_steher']:,.2f}"],
                ["Extras", f"€ {res['k_extras']:,.2f}"],
                ["Rabatt", f"- € {res['rabatt']:,.2f}"],
                ["Montage", f"€ {res['k_montage']:,.2f}"]
            ]
            st.dataframe(pd.DataFrame(rows, columns=["Posten", "Wert"]), hide_index=True, use_container_width=True)

        # PDF Download Button
        pdf_bytes = create_sales_pdf(res, db)
        st.download_button(
            label="📄 Angebot als PDF speichern",
            data=pdf_bytes,
            file_name=f"Angebot_{datetime.date.today()}.pdf",
            mime="application/pdf",
            type="primary"
        )

    # RECHTE SPALTE: PDF KATALOG
    with col_pdf:
        st.subheader("📋 Preisliste / Katalog")
        display_pdf("preisliste.pdf")

if __name__ == "__main__":
    main()
