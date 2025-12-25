import streamlit as st
import math
import pandas as pd
from fpdf import FPDF
import datetime
import os
from streamlit_pdf_viewer import pdf_viewer

# ==========================================
# 1. DATENBANK & PREIS-LOGIK
# ==========================================
class ZaunDatabase:
    def __init__(self, preisfaktor=1.0):
        self.faktor = preisfaktor

        # --- A. GITTERMATTEN ---
        self.matten_preise = {
            "Leicht 6/5/6": {830: 35.00, 1030: 42.00, 1230: 49.00, 1430: 58.00, 1630: 65.00, 1830: 75.00, 2030: 85.00},
            "Schwer 8/6/8": {830: 48.00, 1030: 58.00, 1230: 69.00, 1430: 79.00, 1630: 89.00, 1830: 99.00, 2030: 110.00}
        }

        # --- B. STEHER ---
        self.steher_basis = {
            "Rechteck 60x40": 30.00, 
            "Rundrohr 60mm": 35.00, 
            "Typ SL 60 (Klemm)": 45.00, 
            "Typ 70k (Design)": 55.00
        }

        # --- C. TORE (Grundpreise) ---
        self.tore_db = {
            "Gehtür 1-flg": [
                {'max_b': 1000, 'max_h': 1250, 'preis': 450.00}, {'max_b': 1000, 'max_h': 2000, 'preis': 550.00},
                {'max_b': 1250, 'max_h': 1250, 'preis': 520.00}, {'max_b': 1250, 'max_h': 2000, 'preis': 620.00}
            ],
            "Einfahrtstor 2-flg": [
                {'max_b': 3000, 'max_h': 1250, 'preis': 1200.00}, {'max_b': 3000, 'max_h': 2000, 'preis': 1400.00},
                {'max_b': 4000, 'max_h': 1250, 'preis': 1500.00}, {'max_b': 4000, 'max_h': 2000, 'preis': 1800.00}
            ],
            "Schiebetor": [
                {'max_b': 3500, 'max_h': 1400, 'preis': 2800.00}, {'max_b': 4500, 'max_h': 1400, 'preis': 3500.00}
            ]
        }

        # --- D. ZUBEHÖR & MONTAGEMATERIAL ---
        self.torsaeulen = {"Standard": 150.00, "Verstärkt": 300.00, "Alu-Design": 400.00}
        self.beton_sack_preis = 9.00
        self.konsole_preis = 25.00
        self.montagemat_preis = 8.00

        # Sichtschutz: Unterscheidung Einheit (Rolle vs Streifen)
        self.sichtschutz_daten = {
            "Keiner": {"preis": 0.00, "einheit": ""},
            "Rolle (Weich 30m)": {"preis": 49.00, "einheit": "Rollen", "laenge": 30.0},
            "Hart-PVC (Streifen 2,5m)": {"preis": 6.50, "einheit": "Streifen", "laenge": 2.5}
        }
        
        # Erweitertes Tor-Zubehör
        self.tor_zubehoer = {
            "Profilzylinder (inkl. 3 Schl.)": 35.00,
            "Drückergarnitur ALU": 45.00,
            "Drückergarnitur NIRO": 75.00,
            "Locinox-Schloss (Industrie)": 110.00,
            "E-Öffner Modul (Lose)": 85.00,
            "Bodenanschlag (Mitte)": 40.00,
            "Bodenriegel (Stangenriegel)": 55.00,
            "Tor-Feststeller (Schnapper)": 65.00,
            "Türschließer (z.B. Samson)": 350.00,
            "Zackenleiste (Übersteigschutz)": 35.00
        }
        
        self.farben = {"Verzinkt": 1.0, "Anthrazit (7016)": 1.15, "Moosgrün (6005)": 1.15, "Sonderfarbe": 1.30}

    # --- Preisfinder Funktionen ---
    def get_matte_preis(self, typ, hoehe):
        verf = sorted(self.matten_preise[typ].keys())
        passende_h = min(verf, key=lambda x: abs(x - hoehe))
        return self.matten_preise[typ][passende_h] * self.faktor

    def get_tor_preis(self, modell, b, h):
        moegliche = self.tore_db.get(modell, [])
        passende = [t for t in moegliche if t['max_b'] >= b and t['max_h'] >= h]
        if not passende: return max(moegliche, key=lambda x: x['preis'])['preis'] * 1.20 * self.faktor
        return min(passende, key=lambda x: x['preis'])['preis'] * self.faktor


# ==========================================
# 2. SESSION STATE & HELPER
# ==========================================
if 'zauene' not in st.session_state: st.session_state['zauene'] = []
if 'tore' not in st.session_state: st.session_state['tore'] = []

def add_zaun(bez, typ, farbe, laenge, hoehe, steher, ecken, sicht, reihen, montage, beton):
    st.session_state['zauene'].append({
        "bezeichnung": bez, "typ": typ, "farbe": farbe, "laenge": laenge, "hoehe": hoehe,
        "steher": steher, "ecken": ecken, "sicht": sicht, "reihen": reihen, "montage": montage, "beton_stk": beton
    })

def delete_zaun(idx): st.session_state['zauene'].pop(idx)

def add_tor(modell, sl, th, saeule, zub, farbe):
    st.session_state['tore'].append({
        "modell": modell, "sl": sl, "th": th, "saeule": saeule, "zub": zub, "farbe": farbe
    })

def delete_tor(idx): st.session_state['tore'].pop(idx)


# ==========================================
# 3. KALKULATIONS-ENGINE
# ==========================================
def calculate_project(db, montage_std, montage_satz, rabatt):
    pos_liste = []
    total_netto_material = 0
    total_saecke_projekt = 0
    
    # Vorab: Montagekosten pro Meter ermitteln (für Kennzahl)
    total_zaun_laenge = sum([z['laenge'] for z in st.session_state['zauene']])
    total_montage_kosten = montage_std * montage_satz
    montage_anteil_pro_m = (total_montage_kosten / total_zaun_laenge) if total_zaun_laenge > 0 else 0

    # --- A. ZÄUNE ---
    for i, z in enumerate(st.session_state['zauene']):
        details = []
        farbfaktor = db.farben[z['farbe']]
        sum_pos_material = 0

        # 1. Matten
        anz_matten = math.ceil(z['laenge'] / 2.5)
        p_matte_einzel = db.get_matte_preis(z['typ'], z['hoehe']) * farbfaktor
        k_matten = anz_matten * p_matte_einzel
        details.append({
            "txt": f"Gittermatten: {anz_matten} Stk {z['typ']} ({z['farbe']}, H={z['hoehe']})", 
            "ep": p_matte_einzel, 
            "sum": k_matten
        })
        sum_pos_material += k_matten
        
        # 2. Steher
        anz_steher = anz_matten + 1 + z['ecken']
        p_steher_raw = db.steher_basis[z['steher']] * (z['hoehe']/1000) * db.faktor * farbfaktor
        k_steher = anz_steher * p_steher_raw
        
        # Steherlänge Logik
        l_steher_mm = z['hoehe'] + 600 if z['montage'] == "Einbetonieren" else z['hoehe'] + 100
        details.append({
            "txt": f"Steher: {anz_steher} Stk '{z['steher']}' (L={l_steher_mm}mm)", 
            "ep": p_steher_raw, 
            "sum": k_steher
        })
        sum_pos_material += k_steher

        # 3. Montage Material (Fundament/Konsole)
        if z['montage'] == "Einbetonieren":
            beton_anz = anz_steher * z['beton_stk']
            k_beton = beton_anz * db.beton_sack_preis
            details.append({
                "txt": f"Fundament: {beton_anz} Säcke Fertigbeton", 
                "ep": db.beton_sack_preis, 
                "sum": k_beton
            })
            sum_pos_material += k_beton
            total_saecke_projekt += beton_anz
        else:
            p_kons_set = (db.konsole_preis + db.montagemat_preis) * db.faktor
            k_kons = anz_steher * p_kons_set
            details.append({
                "txt": f"Montage-Set: {anz_steher}x Konsole & Anker", 
                "ep": p_kons_set, 
                "sum": k_kons
            })
            sum_pos_material += k_kons

        # 4. Sichtschutz (Komplexe Logik)
        if z['sicht'] != "Keiner":
            info = db.sichtschutz_daten[z['sicht']]
            reihen = z['reihen']
            
            if "Rolle" in z['sicht']:
                # Rollenware berechnen
                total_bahnen_m = z['laenge'] * reihen
                anz_einheiten = math.ceil(total_bahnen_m / info['laenge'])
                calc_txt = f"{reihen} Reihen à {z['laenge']}m"
            else:
                # Streifenware berechnen
                anz_einheiten = anz_matten * reihen
                calc_txt = f"{reihen} Reihen für {anz_matten} Matten"

            p_sicht_einzel = info['preis'] 
            k_sicht = anz_einheiten * p_sicht_einzel
            
            details.append({
                "txt": f"Sichtschutz: {anz_einheiten} {info['einheit']} ({z['sicht']})", 
                "ep": p_sicht_einzel, 
                "sum": k_sicht
            })
            # Infozeile (ohne Preis)
            details.append({"txt": f"   > Kalkulation: {calc_txt}", "ep": 0, "sum": 0})
            sum_pos_material += k_sicht

        # 5. KENNZAHL: PREIS PRO METER (HIGHLIGHT)
        # Material rabattiert + Montageanteil / Länge
        mat_rabattiert = sum_pos_material * (1 - (rabatt/100))
        montage_anteil = z['laenge'] * montage_anteil_pro_m
        real_lfm_preis = (mat_rabattiert + montage_anteil) / z['laenge'] if z['laenge'] > 0 else 0

        # Als erste Zeile einfügen
        details.insert(0, {
            "txt": f"KENNZAHL: {real_lfm_preis:.2f} EUR / lfm (fertig montiert & rabattiert)", 
            "ep": 0, "sum": 0, "highlight": True
        })

        pos_liste.append({
            "titel": f"Zaun: {z['bezeichnung']} ({z['laenge']}m)", 
            "details": details, 
            "preis_total": sum_pos_material
        })
        total_netto_material += sum_pos_material

    # --- B. TORE ---
    for i, t in enumerate(st.session_state['tore']):
        details = []
        farbfaktor = db.farben[t['farbe']]
        sum_tor = 0

        # Tor Basis
        p_basis = db.get_tor_preis(t['modell'], t['sl'], t['th']) * farbfaktor
        details.append({"txt": f"Torflügel: {t['modell']} (SL {t['sl']} x TH {t['th']})", "ep": p_basis, "sum": p_basis})
        sum_tor += p_basis

        # Säulen
        p_saeule = db.torsaeulen[t['saeule']] * db.faktor
        details.append({"txt": f"Torsäulen-Set: {t['saeule']}", "ep": p_saeule, "sum": p_saeule})
        sum_tor += p_saeule

        # Zubehör (Loop durch Auswahl)
        if t['zub']:
            for z_item in t['zub']:
                p_item = db.tor_zubehoer[z_item] * db.faktor
                details.append({"txt": f"Zubehör: {z_item}", "ep": p_item, "sum": p_item})
                sum_tor += p_item
        
        pos_liste.append({
            "titel": f"Tor: {t['modell']} ({t['farbe']})", 
            "details": details, 
            "preis_total": sum_tor
        })
        total_netto_material += sum_tor

    # --- C. GESAMT ---
    rabatt_wert = total_netto_material * (rabatt / 100)
    netto_rabattiert = total_netto_material - rabatt_wert
    final_netto = netto_rabattiert + total_montage_kosten
    
    return {
        "positionen": pos_liste,
        "rabatt": rabatt_wert,
        "montage": total_montage_kosten,
        "total_netto": final_netto,
        "mwst": final_netto * 0.20,
        "brutto": final_netto * 1.20,
        "beton_total": total_saecke_projekt
    }


# ==========================================
# 4. PDF GENERATOR
# ==========================================
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
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(10, 8, "#", 1, 0, 'C', 1)
    pdf.cell(100, 8, "Position / Beschreibung", 1, 0, 'L', 1)
    pdf.cell(35, 8, "Einzelpreis", 1, 0, 'R', 1)
    pdf.cell(45, 8, "Gesamt (Netto)", 1, 1, 'R', 1)
    
    # Loop Positionen
    for idx, pos in enumerate(res['positionen']):
        # Hauptzeile
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(10, 8, str(idx+1), "LRT", 0, 'C') 
        pdf.cell(135, 8, txt(pos['titel']), "LT", 0, 'L')
        pdf.cell(45, 8, txt(f"{pos['preis_total']:,.2f} EUR"), "LRT", 1, 'R')
        
        # Details
        pdf.set_font("Arial", '', 9)
        for d in pos['details']:
            is_highlight = d.get('highlight', False)
            
            pdf.cell(10, 5, "", "LR", 0) # Leerer Rand links
            
            if is_highlight:
                # Highlight Zeile (Blau + Fett Kursiv)
                pdf.set_font("Arial", 'BI', 9)
                pdf.set_text_color(0, 50, 150)
                pdf.cell(100, 5, txt(f" > {d['txt']}"), "L", 0, 'L')
                pdf.cell(35, 5, "", 0, 0) # Kein EP
                pdf.cell(45, 5, "", "R", 1) # Kein Gesamt
                pdf.set_font("Arial", '', 9)
                pdf.set_text_color(0,0,0)
            elif d['ep'] == 0 and d['sum'] == 0:
                # Infozeile (Grau)
                pdf.set_text_color(100,100,100)
                pdf.cell(100, 5, txt(f"     {d['txt']}"), "L", 0, 'L')
                pdf.cell(35, 5, "", 0, 0)
                pdf.cell(45, 5, "", "R", 1)
                pdf.set_text_color(0,0,0)
            else:
                # Standard Zeile
                pdf.cell(100, 5, txt(f" - {d['txt']}"), "L", 0, 'L')
                pdf.cell(35, 5, txt(f"à {d['ep']:,.2f} EUR"), 0, 0, 'R')
                pdf.cell(45, 5, txt(f"{d['sum']:,.2f} EUR"), "R", 1, 'R')
        
        # Strich unten
        pdf.cell(190, 1, "", "T", 1) 

    # Summenblock
    pdf.ln(5)
    def sum_row(lab, val, bold=False, color=False):
        if bold: pdf.set_font("Arial", 'B', 11)
        else: pdf.set_font("Arial", '', 10)
        if color: pdf.set_fill_color(200, 255, 200)
        fill = 1 if color else 0
        pdf.cell(145, 8, txt(lab), 0, 0, 'R', fill)
        pdf.cell(45, 8, txt(f"{val:,.2f} EUR"), 1, 1, 'R', fill)

    if res['rabatt'] > 0: sum_row(f"Abzüglich Rabatt", -res['rabatt'])
    if res['montage'] > 0: sum_row(f"Montageleistung (Pauschal)", res['montage'])

    pdf.ln(2)
    sum_row("GESAMT NETTO", res['total_netto'], bold=True)
    sum_row("MwSt (20%)", res['mwst'])
    sum_row("GESAMT BRUTTO", res['brutto'], bold=True, color=True)

    # Footer Logistik
    if res['beton_total'] > 0:
        pdf.ln(10)
        pdf.set_font("Arial", 'I', 9)
        pdf.multi_cell(0, 5, txt(f"Logistik Hinweis: Für dieses Projekt werden gesamt ca. {res['beton_total']} Sack Fertigbeton benötigt."))

    return pdf.output(dest='S').encode('latin-1')


# ==========================================
# 5. MAIN GUI
# ==========================================
def main():
    # Setup mit Branding
    st.set_page_config(
        page_title="Zaun-Profi",
        page_icon="logo_firma.png" if os.path.exists("logo_firma.png") else "🚧",
        layout="wide"
    )
    
    # Header mit Logos
    col_img1, col_title, col_img2 = st.columns([1, 4, 1])
    with col_img1:
        if os.path.exists("logo_firma.png"): st.image("logo_firma.png", width=100)
    with col_title:
        st.title("🏗️ Multi-Zaun Projektierung")
    with col_img2:
        if os.path.exists("logo_brix.png"): st.image("logo_brix.png", width=100)

    # Sidebar
    with st.sidebar:
        st.header("Admin")
        faktor = st.number_input("Preisfaktor:", 0.5, 2.0, 1.0, 0.01)
    
    db = ZaunDatabase(faktor)

    # Layout Spalten
    col_L, col_R = st.columns([1.2, 1])

    with col_L:
        tab1, tab2, tab3 = st.tabs(["1️⃣ Zäune", "2️⃣ Tore", "3️⃣ Global"])
        
        # TAB 1: Zäune
        with tab1:
            st.subheader("Neuen Zaunabschnitt hinzufügen")
            with st.form("zaun_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                bez = c1.text_input("Bezeichnung:", "Vorgarten")
                typ = c2.selectbox("Matten:", list(db.matten_preise.keys()))
                
                c3, c4 = st.columns(2)
                laenge = c3.number_input("Länge (m):", 1.0, 500.0, 10.0)
                hoehe = c4.select_slider("Höhe (mm):", options=[830,1030,1230,1430,1630,1830,2030], value=1230)
                
                c5, c6 = st.columns(2)
                farbe = c5.selectbox("Farbe:", list(db.farben.keys()))
                sicht = c6.selectbox("Sichtschutz:", list(db.sichtschutz_daten.keys()))
                
                # Reihen-Logik
                reihen_default = int(hoehe / 200)
                reihen = 0
                if sicht != "Keiner":
                    reihen = st.number_input("Anzahl Reihen (Streifen):", 1, 15, reihen_default)
                
                c7, c8 = st.columns(2)
                mont = c7.radio("Montage:", ["Einbetonieren", "Auf Fundament"])
                steher = c8.selectbox("Steher:", list(db.steher_basis.keys()))
                ecken = st.number_input("Ecken:", 0, 20, 0)
                
                beton = 2
                if mont == "Einbetonieren":
                    beton = st.number_input("Säcke Beton/Steher:", 1, 10, 2)

                if st.form_submit_button("➕ Zaun speichern"):
                    add_zaun(bez, typ, farbe, laenge, hoehe, steher, ecken, sicht, reihen, mont, beton)
                    st.rerun()

            if st.session_state['zauene']:
                st.write("📋 **Liste:**")
                for i, z in enumerate(st.session_state['zauene']):
                    with st.expander(f"{i+1}. {z['bezeichnung']} ({z['laenge']}m)", expanded=True):
                        st.caption(f"{z['typ']} | H:{z['hoehe']}mm | {z['montage']}")
                        if st.button("Löschen", key=f"del_{i}"): delete_zaun(i); st.rerun()

        # TAB 2: Tore
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
                if st.form_submit_button("➕ Tor speichern"):
                    add_tor(mod, sl, th, ts, tz, tf)
                    st.rerun()
            
            if st.session_state['tore']:
                for i, t in enumerate(st.session_state['tore']):
                    with st.expander(f"Tor: {t['modell']}", expanded=True):
                        st.caption(f"{t['sl']}x{t['th']} | Zubehör: {len(t['zub'])} Teile")
                        if st.button("Löschen", key=f"delt_{i}"): delete_tor(i); st.rerun()

        # TAB 3: Global
        with tab3:
            h_std = st.number_input("Montage (h):", 0.0, 500.0, 0.0)
            h_satz = st.number_input("Satz (€):", 0.0, 200.0, 65.0)
            rabatt = st.slider("Rabatt %:", 0, 50, 0)

    # RECHTS: Output
    with col_R:
        res = calculate_project(db, h_std, h_satz, rabatt)
        
        st.subheader("Kalkulation")
        k1, k2 = st.columns(2)
        k1.metric("Netto", f"€ {res['total_netto']:,.2f}")
        k2.metric("Brutto", f"€ {res['brutto']:,.2f}")
        
        # Vorschau
        if res['positionen']:
            st.markdown("---")
            for p in res['positionen']:
                st.text(f"{p['titel']} -> € {p['preis_total']:,.2f}")
            if res['montage'] > 0: st.text(f"Montage -> € {res['montage']:,.2f}")

        # PDF Button
        pdf_bytes = create_pdf(res)
        st.download_button("📄 PDF Angebot (Final)", pdf_bytes, "Angebot.pdf", "application/pdf", type="primary")
        
        # PDF Viewer für Preisliste
        if os.path.exists("preisliste_draht.pdf"):
            with st.expander("Katalog"):
                pdf_viewer("preisliste_draht.pdf", height=500)

if __name__ == "__main__":
    main()
