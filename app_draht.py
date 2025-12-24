import streamlit as st
import math
import pandas as pd
from fpdf import FPDF
import datetime
import base64
import os
from streamlit_pdf_viewer import pdf_viewer

# --- 1. DATENBANK (Drahtgitter & Tore) ---
class ZaunDatabase:
    def __init__(self, preisfaktor=1.0):
        self.faktor = preisfaktor

        # A. MATTEN (Doppelstabmatten) - Preise pro Stück (Breite 2500mm)
        # Preise exemplarisch - Bitte mit PDF abgleichen!
        self.matten_preise = {
            "Leicht (6/5/6)": {
                830: 35.00, 1030: 42.00, 1230: 49.00, 1430: 58.00, 
                1630: 65.00, 1830: 75.00, 2030: 85.00
            },
            "Schwer (8/6/8)": {
                830: 48.00, 1030: 58.00, 1230: 69.00, 1430: 79.00, 
                1630: 89.00, 1830: 99.00, 2030: 110.00
            }
        }

        # B. SÄULEN (Rechteckrohr 60x40) - Preise pro Stück
        self.saeulen_preise = {
            "Zum Einbetonieren": {
                830: 25.00, 1030: 29.00, 1230: 34.00, 1430: 39.00, 
                1630: 45.00, 1830: 49.00, 2030: 55.00
            },
            "Mit Fußplatte (Dübel)": {
                830: 45.00, 1030: 49.00, 1230: 54.00, 1430: 59.00, 
                1630: 65.00, 1830: 69.00, 2030: 75.00
            }
        }

        # C. TORE
        self.tore = {
            "Keines": 0.00,
            "Gehtür 1-flg (1000mm)": 450.00,
            "Einfahrtstor 2-flg (3000mm)": 1200.00,
            "Einfahrtstor 2-flg (4000mm)": 1500.00
        }

        # D. FARBZUSCHLÄGE
        self.farben = {
            "Verzinkt (Silber)": 1.00,
            "RAL 6005 (Moosgrün)": 1.15,
            "RAL 7016 (Anthrazit)": 1.15,
            "Sonderfarbe": 1.30
        }

        # E. ZUBEHÖR
        self.extras = {
            "Eck-Schelle (Aufpreis)": 15.00,
            "Sichtschutzstreifen (Rolle 35m)": 59.00,
            "Montage-Set (Schrauben/Bit)": 25.00
        }

    def get_matte_preis(self, typ, hoehe):
        # Nächste verfügbare Höhe finden
        verfuegbare = sorted(self.matten_preise[typ].keys())
        passende_h = min(verfuegbare, key=lambda x: abs(x - hoehe))
        return self.matten_preise[typ][passende_h] * self.faktor, passende_h

    def get_saeule_preis(self, montage, hoehe):
        verfuegbare = sorted(self.saeulen_preise[montage].keys())
        passende_h = min(verfuegbare, key=lambda x: abs(x - hoehe))
        return self.saeulen_preise[montage][passende_h] * self.faktor


def berechne_zaun(d, db):
    # 1. Matten (2500mm)
    matten_breite = 2.50
    anzahl_matten = math.ceil(d['laenge'] / matten_breite)
    
    preis_matte_stk, h_real = db.get_matte_preis(d['typ'], d['hoehe'])
    k_matten = anzahl_matten * preis_matte_stk

    # 2. Säulen (Matten + 1 + Ecken)
    anzahl_saeulen = anzahl_matten + 1 + d['ecken']
    
    preis_saeule_stk = db.get_saeule_preis(d['montage'], d['hoehe'])
    k_saeulen = anzahl_saeulen * preis_saeule_stk

    # 3. Tore
    k_tore = db.tore[d['tor_typ']] * d['tor_anzahl']

    # 4. Extras
    k_extras = (d['ecken'] * db.extras["Eck-Schelle (Aufpreis)"]) + \
               (d['sichtschutz_rollen'] * db.extras["Sichtschutzstreifen (Rolle 35m)"])

    # 5. Summen
    summe_material = k_matten + k_saeulen + k_tore + k_extras
    faktor_farbe = db.farben[d['farbe']]
    
    netto_mat = summe_material * faktor_farbe
    rabatt_wert = netto_mat * (d['rabatt'] / 100)
    netto_mat_final = netto_mat - rabatt_wert

    # 6. Montage
    montage = d['montage_stunden'] * d['montage_satz']
    
    total_netto = netto_mat_final + montage
    
    return {
        "detail": {
            "matten_anz": anzahl_matten, "matten_h": h_real, "matten_p_stk": preis_matte_stk * faktor_farbe,
            "saeulen_anz": anzahl_saeulen, "saeulen_p_stk": preis_saeule_stk * faktor_farbe,
        },
        "k_matten": k_matten * faktor_farbe,
        "k_saeulen": k_saeulen * faktor_farbe,
        "k_tore": k_tore * faktor_farbe,
        "k_extras": k_extras * faktor_farbe,
        "rabatt": rabatt_wert,
        "k_montage": montage,
        "netto": total_netto,
        "mwst": total_netto * 0.20,
        "brutto": total_netto * 1.20,
        "input": d
    }

# --- PDF ---
def create_zaun_pdf(res, db):
    pdf = FPDF()
    pdf.add_page()
    def txt(s): return str(s).encode('latin-1', 'replace').decode('latin-1')

    # Header
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt("ZAUN-ANGEBOT (Drahtgitter)"), ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 10, txt(f"Datum: {datetime.date.today().strftime('%d.%m.%Y')}"), ln=True, align='R')
    pdf.ln(5)
    
    # Projekt
    d = res['input']
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, txt(f"Modell: {d['typ']} | Farbe: {d['farbe']}"), ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 6, txt(f"Länge: {d['laenge']}m | Höhe: {res['detail']['matten_h']}mm"), ln=True)
    pdf.cell(0, 6, txt(f"Montage: {d['montage']}"), ln=True)
    pdf.ln(10)
    
    # Tabelle
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(130, 8, txt("Position"), 1, 0, 'L', 1)
    pdf.cell(60, 8, txt("Gesamt (Netto)"), 1, 1, 'R', 1)
    pdf.set_font("Arial", '', 10)

    def row(text, val):
        pdf.cell(130, 8, txt(text), 1)
        pdf.cell(60, 8, txt(f"{val:,.2f} EUR"), 1, 1, 'R')

    row(f"Gittermatten {d['typ']} ({res['detail']['matten_anz']} Stk)", res['k_matten'])
    row(f"Säulen & Befestigung ({res['detail']['saeulen_anz']} Stk)", res['k_saeulen'])
    
    if res['k_tore'] > 0: row(f"Tor: {d['tor_typ']} ({d['tor_anzahl']}x)", res['k_tore'])
    if res['k_extras'] > 0: row("Zubehör (Ecken, Sichtschutz)", res['k_extras'])
    
    if d['rabatt'] > 0:
        pdf.set_text_color(200,0,0)
        row(f"Rabatt ({d['rabatt']}%)", -res['rabatt'])
        pdf.set_text_color(0,0,0)

    if d['montage_stunden'] > 0:
        row(f"Montage ({d['montage_stunden']}h)", res['k_montage'])

    # Summen
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(130, 10, txt("NETTO SUMME"), 0, 0, 'R')
    pdf.cell(60, 10, txt(f"{res['netto']:,.2f} EUR"), 1, 1, 'R')
    pdf.cell(130, 10, txt("MwSt (20%)"), 0, 0, 'R')
    pdf.cell(60, 10, txt(f"{res['mwst']:,.2f} EUR"), 1, 1, 'R')
    
    pdf.set_fill_color(200, 255, 200)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(130, 10, txt("BRUTTO SUMME"), 0, 0, 'R')
    pdf.cell(60, 10, txt(f"{res['brutto']:,.2f} EUR"), 1, 1, 'R', 1)

    return pdf.output(dest='S').encode('latin-1')

# --- MAIN APP ---
def main():
    st.set_page_config(page_title="Brix Zaun Kalkulator", page_icon="🚧", layout="wide")
    
    with st.sidebar:
        st.header("⚙️ Admin")
        preisfaktor = st.number_input("Preisfaktor:", 0.5, 2.0, 1.0, 0.01)
        st.info("Bitte 'preisliste_draht.pdf' auf GitHub hochladen.")

    db = ZaunDatabase(preisfaktor)
    st.title("🚧 Brix Drahtgitter Kalkulator")

    col_app, col_pdf = st.columns([1, 1])

    with col_app:
        tab1, tab2, tab3, tab4 = st.tabs(["📏 Zaun", "🚪 Tore", "🛠️ Extras", "💰 Setup"])
        
        with tab1:
            typ = st.selectbox("Matten-Typ:", ["Leicht (6/5/6)", "Schwer (8/6/8)"])
            montage = st.selectbox("Säulen-Montage:", ["Zum Einbetonieren", "Mit Fußplatte (Dübel)"])
            
            c1, c2 = st.columns(2)
            laenge = c1.number_input("Zaunlänge (m):", 1.0, 500.0, 10.0, 0.5)
            hoehe = c2.select_slider("Höhe (mm):", options=[830, 1030, 1230, 1430, 1630, 1830, 2030], value=1230)
            
            ecken = st.number_input("Anzahl Ecken:", 0, 50, 0)
            st.caption(f"Benötigte Matten: {math.ceil(laenge/2.5)} Stück (à 2500mm)")

        with tab2:
            tor_typ = st.selectbox("Tor Modell:", list(db.tore.keys()))
            tor_anz = st.number_input("Anzahl Tore:", 0, 10, 0 if tor_typ=="Keines" else 1)

        with tab3:
            sichtschutz = st.number_input("Sichtschutz (Rollen à 35m):", 0, 50, 0)
            st.divider()
            std = st.number_input("Montage Stunden:", 0.0, 500.0, 0.0, 1.0)
            satz = st.number_input("Satz €/h:", 0.0, 200.0, 65.0, 5.0)

        with tab4:
            farbe = st.selectbox("Farbe / Oberfläche:", list(db.farben.keys()))
            rabatt = st.slider("Rabatt %:", 0, 50, 0)

        # Berechnen
        input_d = {
            "typ": typ, "montage": montage, "laenge": laenge, "hoehe": hoehe, "ecken": ecken,
            "tor_typ": tor_typ, "tor_anzahl": tor_anz, "sichtschutz_rollen": sichtschutz,
            "montage_stunden": std, "montage_satz": satz, "farbe": farbe, "rabatt": rabatt
        }
        res = berechne_zaun(input_d, db)

        # Ergebnis
        st.markdown("---")
        k1, k2 = st.columns(2)
        k1.metric("Netto", f"€ {res['netto']:,.2f}")
        k2.metric("Brutto", f"€ {res['brutto']:,.2f}")

        with st.expander("Details"):
            df = pd.DataFrame([
                ["Matten", f"{res['detail']['matten_anz']} Stk", f"€ {res['k_matten']:,.2f}"],
                ["Säulen", f"{res['detail']['saeulen_anz']} Stk", f"€ {res['k_saeulen']:,.2f}"],
                ["Tore", f"{tor_anz} Stk", f"€ {res['k_tore']:,.2f}"],
                ["Extras", "Pausch.", f"€ {res['k_extras']:,.2f}"],
                ["Montage", f"{std} h", f"€ {res['k_montage']:,.2f}"],
            ], columns=["Posten", "Menge", "Summe"])
            st.dataframe(df, hide_index=True, use_container_width=True)

        pdf_bytes = create_zaun_pdf(res, db)
        st.download_button("📄 PDF Angebot speichern", pdf_bytes, f"Zaun_Angebot_{datetime.date.today()}.pdf", "application/pdf", type="primary")

    with col_pdf:
        st.subheader("📋 Preisliste (Draht)")
        if os.path.exists("preisliste_draht.pdf"):
            pdf_viewer("preisliste_draht.pdf", height=800)
        else:
            st.warning("⚠️ 'preisliste_draht.pdf' fehlt. Bitte auf GitHub hochladen!")

if __name__ == "__main__":
    main()
