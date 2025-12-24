import streamlit as st
import math
import pandas as pd
from fpdf import FPDF
import datetime
import os
from streamlit_pdf_viewer import pdf_viewer

# --- 1. DATENBANK ---
class ZaunDatabase:
    def __init__(self, preisfaktor=1.0):
        self.faktor = preisfaktor

        # PREISE (Bitte mit PDF abgleichen)
        self.matten_preise = {
            "Leicht 6/5/6": {830: 35.00, 1030: 42.00, 1230: 49.00, 1430: 58.00, 1630: 65.00, 1830: 75.00, 2030: 85.00},
            "Schwer 8/6/8": {830: 48.00, 1030: 58.00, 1230: 69.00, 1430: 79.00, 1630: 89.00, 1830: 99.00, 2030: 110.00}
        }

        self.steher_basis = {
            "Rechteck 60x40": 30.00, "Rundrohr 60mm": 35.00, "Typ SL 60": 45.00, "Typ 70k": 55.00
        }

        self.tore_db = {
            "Gehtür 1-flg": [
                {'max_b': 1000, 'max_h': 1250, 'preis': 450.00}, {'max_b': 1000, 'max_h': 2000, 'preis': 550.00},
                {'max_b': 1250, 'max_h': 1250, 'preis': 520.00}, {'max_b': 1250, 'max_h': 2000, 'preis': 620.00}
            ],
            "Einfahrtstor 2-flg": [
                {'max_b': 3000, 'max_h': 1250, 'preis': 1200.00}, {'max_b': 3000, 'max_h': 2000, 'preis': 1400.00},
                {'max_b': 4000, 'max_h': 1250, 'preis': 1500.00}, {'max_b': 4000, 'max_h': 2000, 'preis': 1800.00}
            ],
            "Schiebetor": [{'max_b': 3500, 'max_h': 1400, 'preis': 2800.00}, {'max_b': 4500, 'max_h': 1400, 'preis': 3500.00}]
        }

        self.torsaeulen = {"Standard": 150.00, "Verstärkt": 300.00, "Alu-Design": 400.00}

        self.beton_sack_preis = 9.00
        self.konsole_preis = 25.00
        self.montagemat_preis = 8.00

        self.sichtschutz = {"Keiner": 0.00, "Rolle (Weich-PVC)": 59.00, "Hart-PVC Streifen": 110.00}
        self.tor_zubehoer = {"Schloss": 80.00, "E-Öffner": 45.00, "Bodenriegel": 30.00, "Zackenleiste": 25.00}
        self.farben = {"Verzinkt": 1.0, "Anthrazit (7016)": 1.15, "Moosgrün (6005)": 1.15, "Sonderfarbe": 1.30}

    def get_matte_preis(self, typ, hoehe):
        verf = sorted(self.matten_preise[typ].keys())
        passende_h = min(verf, key=lambda x: abs(x - hoehe))
        return self.matten_preise[typ][passende_h] * self.faktor

    def get_tor_preis(self, modell, b, h):
        moegliche = self.tore_db.get(modell, [])
        passende = [t for t in moegliche if t['max_b'] >= b and t['max_h'] >= h]
        if not passende: return max(moegliche, key=lambda x: x['preis'])['preis'] * 1.20 * self.faktor
        return min(passende, key=lambda x: x['preis'])['preis'] * self.faktor

# --- STATE ---
if 'zauene' not in st.session_state: st.session_state['zauene'] = []
if 'tore' not in st.session_state: st.session_state['tore'] = []

def add_zaun(bez, typ, farbe, laenge, hoehe, steher, ecken, sicht, montage, beton):
    st.session_state['zauene'].append({
        "bezeichnung": bez, "typ": typ, "farbe": farbe, "laenge": laenge, "hoehe": hoehe,
        "steher": steher, "ecken": ecken, "sicht": sicht, "montage": montage, "beton_stk": beton
    })

def delete_zaun(idx): st.session_state['zauene'].pop(idx)
def add_tor(modell, sl, th, saeule, zub, farbe):
    st.session_state['tore'].append({
        "modell": modell, "sl": sl, "th": th, "saeule": saeule, "zub": zub, "farbe": farbe
    })
def delete_tor(idx): st.session_state['tore'].pop(idx)

# --- RECHNER ---
def calculate_project(db, montage_std, montage_satz, rabatt):
    pos_liste = []
    total_netto = 0
    total_saecke_projekt = 0
    
    # 1. ZÄUNE
    for i, z in enumerate(st.session_state['zauene']):
        # Berechnungen
        anz_matten = math.ceil(z['laenge'] / 2.5)
        p_matte = db.get_matte_preis(z['typ'], z['hoehe'])
        farbfaktor = db.farben[z['farbe']]
        k_matten = anz_matten * p_matte * farbfaktor
        
        anz_steher = anz_matten + 1 + z['ecken']
        p_steher_base = db.steher_basis[z['steher']] * (z['hoehe']/1000) * db.faktor * farbfaktor
        k_steher = anz_steher * p_steher_base
        
        # Details für PDF vorbereiten
        details = []
        details.append(f"- Gitter: {anz_matten} Stk {z['typ']} (H={z['hoehe']}mm), {z['farbe']}")
        
        # Steher Länge Logik
        # Wenn einbetoniert: Zaunhöhe + ca 600mm. Wenn Fundament: Zaunhöhe + ca 100mm
        l_steher_mm = z['hoehe'] + 600 if z['montage'] == "Einbetonieren" else z['hoehe'] + 100
        details.append(f"- Steher: {anz_steher} Stk '{z['steher']}' (Länge ca. {l_steher_mm}mm)")

        k_mont_mat = 0
        if z['montage'] == "Einbetonieren":
            beton_fuer_pos = anz_steher * z['beton_stk']
            k_beton = beton_fuer_pos * db.beton_sack_preis
            k_mont_mat += k_beton
            total_saecke_projekt += beton_fuer_pos
            details.append(f"- Fundament: {beton_fuer_pos} Säcke Fertigbeton (bei {z['beton_stk']} Sack/Steher)")
        else:
            k_kons = anz_steher * (db.konsole_preis + db.montagemat_preis) * db.faktor
            k_mont_mat += k_kons
            details.append(f"- Montage: auf Fundament ({anz_steher} Konsolen + Anker)")

        if z['sicht'] != "Keiner":
            menge = math.ceil(z['laenge'] / 35) if "Rolle" in z['sicht'] else anz_matten
            k_sicht = menge * db.sichtschutz[z['sicht']] * farbfaktor
            einheit = "Rollen" if "Rolle" in z['sicht'] else "Sets"
            details.append(f"- Sichtschutz: {menge} {einheit} ({z['sicht']})")
            sum_pos = k_matten + k_steher + k_mont_mat + k_sicht
        else:
            sum_pos = k_matten + k_steher + k_mont_mat

        pos_liste.append({
            "titel": f"Zaun: {z['bezeichnung']} ({z['laenge']}m)",
            "details": details,
            "preis": sum_pos
        })
        total_netto += sum_pos

    # 2. TORE
    for i, t in enumerate(st.session_state['tore']):
        farbfaktor = db.farben[t['farbe']]
        p_basis = db.get_tor_preis(t['modell'], t['sl'], t['th']) * farbfaktor
        p_saeule = db.torsaeulen[t['saeule']] * db.faktor
        p_zub = sum([db.tor_zubehoer[x] for x in t['zub']]) * db.faktor
        sum_tor = p_basis + p_saeule + p_zub
        
        details = [
            f"- Maß: SL {t['sl']}mm x TH {t['th']}mm",
            f"- Farbe: {t['farbe']}",
            f"- Säulen: {t['saeule']}",
        ]
        if t['zub']: details.append(f"- Zubehör: {', '.join(t['zub'])}")

        pos_liste.append({
            "titel": f"Tor: {t['modell']}",
            "details": details,
            "preis": sum_tor
        })
        total_netto += sum_tor

    # 3. GESAMT
    rabatt_wert = total_netto * (rabatt / 100)
    netto_rabattiert = total_netto - rabatt_wert
    montage_kosten = montage_std * montage_satz
    final_netto = netto_rabattiert + montage_kosten
    
    return {
        "positionen": pos_liste,
        "rabatt": rabatt_wert,
        "montage": montage_kosten,
        "total_netto": final_netto,
        "mwst": final_netto * 0.20,
        "brutto": final_netto * 1.20,
        "beton_total": total_saecke_projekt
    }

# --- PDF (OPTIMIERT) ---
def create_pdf(res):
    pdf = FPDF()
    pdf.add_page()
    def txt(s): return str(s).encode('latin-1', 'replace').decode('latin-1')

    # Header
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt("ANGEBOT - ZAUNBAU"), ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 10, txt(f"Datum: {datetime.date.today().strftime('%d.%m.%Y')}"), ln=True, align='R')
    pdf.ln(10)

    # Tabellenkopf
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(10, 8, "#", 1, 0, 'C', 1)
    pdf.cell(120, 8, "Position / Details", 1, 0, 'L', 1)
    pdf.cell(60, 8, "Gesamt (Netto)", 1, 1, 'R', 1)
    
    # Positionen Loop
    for idx, pos in enumerate(res['positionen']):
        # Zeile 1: Titel und Preis (Fett)
        pdf.set_font("Arial", 'B', 10)
        # Wir merken uns die Y-Position
        start_y = pdf.get_y()
        
        pdf.cell(10, 8, str(idx+1), "LRT", 0, 'C') 
        pdf.cell(120, 8, txt(pos['titel']), "LRT", 0, 'L')
        pdf.cell(60, 8, txt(f"{pos['preis']:,.2f} EUR"), "LRT", 1, 'R')
        
        # Zeile 2ff: Details (Normal, eingerückt)
        pdf.set_font("Arial", '', 9)
        for detail in pos['details']:
            pdf.cell(10, 5, "", "LR", 0) # Leerer Rand links
            pdf.cell(120, 5, txt(f"  {detail}"), "LR", 0, 'L') # Detail Text
            pdf.cell(60, 5, "", "LR", 1) # Leerer Rand rechts
        
        # Abschlusslinie der Position
        pdf.cell(190, 1, "", "T", 1) 

    # Summenblock
    pdf.ln(5)
    
    # Funktion für Summenzeilen
    def sum_row(lab, val, bold=False, color=False):
        if bold: pdf.set_font("Arial", 'B', 11)
        else: pdf.set_font("Arial", '', 10)
        
        if color: pdf.set_fill_color(200, 255, 200)
        fill = 1 if color else 0
        
        pdf.cell(130, 8, txt(lab), 0, 0, 'R', fill)
        pdf.cell(60, 8, txt(f"{val:,.2f} EUR"), 1, 1, 'R', fill)

    if res['rabatt'] > 0:
        sum_row(f"Abzüglich Rabatt", -res['rabatt'])

    if res['montage'] > 0:
        sum_row(f"Montageleistung", res['montage'])

    pdf.ln(2)
    pdf.cell(190, 0, "", "T", 1) # Trennlinie
    pdf.ln(2)

    sum_row("GESAMT NETTO", res['total_netto'], bold=True)
    sum_row("MwSt (20%)", res['mwst'])
    sum_row("GESAMT BRUTTO", res['brutto'], bold=True, color=True)

    # Footer Info
    if res['beton_total'] > 0:
        pdf.ln(10)
        pdf.set_font("Arial", 'I', 9)
        pdf.multi_cell(0, 5, txt(f"Hinweis zur Montage: Für dieses Projekt werden gesamt ca. {res['beton_total']} Sack Fertigbeton benötigt."))

    return pdf.output(dest='S').encode('latin-1')

# --- GUI ---
def main():
    st.set_page_config(page_title="Profi Zaun-Kalkulator V2.1", page_icon="🏗️", layout="wide")
    
    with st.sidebar:
        st.header("Admin")
        faktor = st.number_input("Preisfaktor:", 0.5, 2.0, 1.0, 0.01)
        st.info("Rechnet mit 'preisliste_draht.pdf'")
    
    db = ZaunDatabase(faktor)
    st.title("🏗️ Multi-Zaun Projektierung")

    col_L, col_R = st.columns([1.2, 1])

    with col_L:
        tab1, tab2, tab3 = st.tabs(["1️⃣ Zäune", "2️⃣ Tore", "3️⃣ Global"])
        
        # TAB 1: ZÄUNE
        with tab1:
            st.subheader("Neuen Zaunabschnitt hinzufügen")
            with st.form("zaun_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                bez = c1.text_input("Bezeichnung (z.B. Vorgarten):", "Zaun 1")
                typ = c2.selectbox("Typ:", list(db.matten_preise.keys()))
                
                c3, c4 = st.columns(2)
                laenge = c3.number_input("Länge (m):", 1.0, 500.0, 10.0)
                hoehe = c4.select_slider("Höhe (mm):", options=[830,1030,1230,1430,1630,1830,2030], value=1230)
                
                c5, c6 = st.columns(2)
                farbe = c5.selectbox("Farbe:", list(db.farben.keys()))
                sicht = c6.selectbox("Sichtschutz:", list(db.sichtschutz.keys()))
                
                st.divider()
                c7, c8 = st.columns(2)
                mont = c7.radio("Montage:", ["Einbetonieren", "Auf Fundament"])
                steher = c8.selectbox("Steher:", list(db.steher_basis.keys()))
                ecken = st.number_input("Ecken:", 0, 20, 0)
                
                beton = 2
                if mont == "Einbetonieren":
                    beton = st.number_input("Säcke Beton/Steher:", 1, 10, 2)

                if st.form_submit_button("➕ Zaun hinzufügen"):
                    add_zaun(bez, typ, farbe, laenge, hoehe, steher, ecken, sicht, mont, beton)
                    st.rerun()

            if st.session_state['zauene']:
                st.divider()
                st.write("📋 **Liste:**")
                for i, z in enumerate(st.session_state['zauene']):
                    with st.expander(f"{i+1}. {z['bezeichnung']} ({z['laenge']}m)", expanded=True):
                        st.caption(f"{z['typ']} | H:{z['hoehe']}mm | {z['montage']}")
                        if st.button("Entfernen", key=f"d{i}"): delete_zaun(i); st.rerun()

        # TAB 2: TORE
        with tab2:
            st.subheader("Tore")
            with st.form("tor_form"):
                mod = st.selectbox("Modell:", list(db.tore_db.keys()))
                c1, c2 = st.columns(2)
                sl = c1.number_input("Lichte (mm):", 800, 5000, 1000, 50)
                th = c2.number_input("Höhe (mm):", 800, 2500, 1200, 50)
                ts = st.selectbox("Säulen:", list(db.torsaeulen.keys()))
                tf = st.selectbox("Farbe:", list(db.farben.keys()))
                tz = st.multiselect("Zubehör:", list(db.tor_zubehoer.keys()))
                if st.form_submit_button("➕ Tor hinzufügen"):
                    add_tor(mod, sl, th, ts, tz, tf)
                    st.rerun()
            
            if st.session_state['tore']:
                st.divider()
                for i, t in enumerate(st.session_state['tore']):
                    with st.expander(f"{i+1}. {t['modell']} ({t['sl']}x{t['th']})", expanded=True):
                        if st.button("Entfernen", key=f"dt{i}"): delete_tor(i); st.rerun()

        # TAB 3: GLOBAL
        with tab3:
            st.subheader("Montage & Rabatt")
            h_std = st.number_input("Montage (h):", 0.0, 500.0, 0.0)
            h_satz = st.number_input("Satz (€):", 0.0, 200.0, 65.0)
            rabatt = st.slider("Rabatt (%):", 0, 50, 0)

    # RECHTS
    with col_R:
        res = calculate_project(db, h_std, h_satz, rabatt)
        
        st.subheader("Gesamt")
        k1, k2 = st.columns(2)
        k1.metric("Netto", f"€ {res['total_netto']:,.2f}")
        k2.metric("Brutto", f"€ {res['brutto']:,.2f}")
        
        st.write("##### Vorschau:")
        for p in res['positionen']:
            st.text(f"{p['titel']}: € {p['preis']:,.2f}")
        
        pdf_bytes = create_pdf(res)
        st.download_button("📄 PDF Angebot (Detailliert)", pdf_bytes, "Angebot.pdf", "application/pdf", type="primary")
        
        if os.path.exists("preisliste_draht.pdf"):
            with st.expander("Katalog anzeigen"):
                pdf_viewer("preisliste_draht.pdf", height=500)

if __name__ == "__main__":
    main()
