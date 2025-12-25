import streamlit as st
import math
import pandas as pd
from fpdf import FPDF
import datetime
import os
import json
from streamlit_pdf_viewer import pdf_viewer

# ==========================================
# 1. STANDARD DATEN (Fallback)
# ==========================================
def get_default_data():
    return {
        "matten": {
            "Leicht 6/5/6": {
                830: {'p': 35.00, 'nr': 'M-L-0830'}, 1030: {'p': 42.00, 'nr': 'M-L-1030'}, 
                1230: {'p': 49.00, 'nr': 'M-L-1230'}, 1430: {'p': 58.00, 'nr': 'M-L-1430'}, 
                1630: {'p': 65.00, 'nr': 'M-L-1630'}, 1830: {'p': 75.00, 'nr': 'M-L-1830'}, 
                2030: {'p': 85.00, 'nr': 'M-L-2030'}
            },
            "Schwer 8/6/8": {
                830: {'p': 48.00, 'nr': 'M-S-0830'}, 1030: {'p': 58.00, 'nr': 'M-S-1030'}, 
                1230: {'p': 69.00, 'nr': 'M-S-1230'}, 1430: {'p': 79.00, 'nr': 'M-S-1430'}, 
                1630: {'p': 89.00, 'nr': 'M-S-1630'}, 1830: {'p': 99.00, 'nr': 'M-S-1830'}, 
                2030: {'p': 110.00, 'nr': 'M-S-2030'}
            }
        },
        "steher": {
            "Rechteck 60x40": {'p': 30.00, 'nr': 'ST-RE-6040'}, 
            "Rundrohr 60mm": {'p': 35.00, 'nr': 'ST-RD-60'}, 
            "Typ SL 60 (Klemm)": {'p': 45.00, 'nr': 'ST-SL-60'}, 
            "Typ 70k (Design)": {'p': 55.00, 'nr': 'ST-70K'}
        },
        "tore": {
            "Gehtür 1-flg": [
                {'max_b': 1000, 'max_h': 1250, 'p': 450.00, 'nr': 'GT-100-125'}, 
                {'max_b': 1000, 'max_h': 2000, 'p': 550.00, 'nr': 'GT-100-200'},
                {'max_b': 1250, 'max_h': 1250, 'p': 520.00, 'nr': 'GT-125-125'}, 
                {'max_b': 1250, 'max_h': 2000, 'p': 620.00, 'nr': 'GT-125-200'}
            ],
            "Einfahrtstor 2-flg": [
                {'max_b': 3000, 'max_h': 1250, 'p': 1200.00, 'nr': 'ET-300-125'}, 
                {'max_b': 3000, 'max_h': 2000, 'p': 1400.00, 'nr': 'ET-300-200'},
                {'max_b': 4000, 'max_h': 1250, 'p': 1500.00, 'nr': 'ET-400-125'}, 
                {'max_b': 4000, 'max_h': 2000, 'p': 1800.00, 'nr': 'ET-400-200'}
            ],
            "Schiebetor": [
                {'max_b': 3500, 'max_h': 1400, 'p': 2800.00, 'nr': 'ST-350-140'}, 
                {'max_b': 4500, 'max_h': 1400, 'p': 3500.00, 'nr': 'ST-450-140'}
            ]
        },
        "zubehoer": {
            "torsaeulen": {
                "Standard": {'p': 150.00, 'nr': 'TS-STD'}, 
                "Verstärkt": {'p': 300.00, 'nr': 'TS-HVY'}, 
                "Alu-Design": {'p': 400.00, 'nr': 'TS-ALU'}
            },
            "montage": {
                "Beton_Sack": {'p': 9.00, 'nr': 'BET-25KG'},
                "Konsole": {'p': 25.00, 'nr': 'ALU-FP'},
                "Montagemat": {'p': 8.00, 'nr': 'MON-SET'}
            },
            "sichtschutz": {
                "Keiner": {'p': 0.00, 'einheit': '', 'len': 0, 'nr': '-'},
                "Rolle (Weich 30m)": {'p': 49.00, 'einheit': 'Rollen', 'len': 30.0, 'nr': 'PVC-R-30'},
                "Hart-PVC (Streifen 2,5m)": {'p': 6.50, 'einheit': 'Streifen', 'len': 2.5, 'nr': 'PVC-H-25'}
            },
            "tor_parts": {
                "Profilzylinder": {'p': 35.00, 'nr': 'PZ-3S'},
                "Drücker ALU": {'p': 45.00, 'nr': 'DR-ALU'},
                "Drücker NIRO": {'p': 75.00, 'nr': 'DR-NIRO'},
                "Locinox-Schloss": {'p': 110.00, 'nr': 'LOC-IND'},
                "E-Öffner Modul": {'p': 85.00, 'nr': 'E-OEFF'},
                "Bodenanschlag": {'p': 40.00, 'nr': 'B-ANS'},
                "Bodenriegel": {'p': 55.00, 'nr': 'B-RIE'},
                "Tor-Feststeller": {'p': 65.00, 'nr': 'T-FEST'},
                "Türschließer": {'p': 350.00, 'nr': 'SAMSON'},
                "Zackenleiste": {'p': 35.00, 'nr': 'ZACK-25'}
            }
        },
        "farben": {"Verzinkt": 1.0, "Anthrazit (7016)": 1.15, "Moosgrün (6005)": 1.15, "Sonderfarbe": 1.30}
    }

if 'db_data' not in st.session_state:
    st.session_state['db_data'] = get_default_data()

# ==========================================
# 2. LOGIK KLASSE
# ==========================================
class ZaunDatabase:
    def __init__(self, preisfaktor=1.0):
        self.faktor = preisfaktor
        self.data = st.session_state['db_data']
        self.farben = self.data['farben']

    def get_matte_preis(self, typ, hoehe):
        # Fallback falls Typ gelöscht wurde
        if typ not in self.data['matten']: return 0, "N/A"
        
        # Nächste Höhe finden
        verf = sorted([int(k) for k in self.data['matten'][typ].keys()])
        if not verf: return 0, "N/A"
        passende_h = min(verf, key=lambda x: abs(x - hoehe))
        item = self.data['matten'][typ][passende_h]
        return item['p'] * self.faktor, item['nr']

    def get_steher_preis(self, typ, hoehe):
        if typ not in self.data['steher']: return 0, "N/A"
        basis = self.data['steher'][typ]
        p_raw = basis['p'] * (hoehe/1000) * self.faktor
        return p_raw, basis['nr']

    def get_tor_preis(self, modell, b, h):
        moegliche = self.data['tore'].get(modell, [])
        if not moegliche: return 0, "N/A"
        passende = [t for t in moegliche if t['max_b'] >= b and t['max_h'] >= h]
        if not passende: 
             t = max(moegliche, key=lambda x: x['p'])
             return t['p'] * 1.20 * self.faktor, t['nr'] + "-SONDER"
        t = min(passende, key=lambda x: x['p'])
        return t['p'] * self.faktor, t['nr']

# ==========================================
# 3. HELPER FUNCTIONS
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
# 4. RECHNER ENGINE
# ==========================================
def calculate_project(db, montage_std, montage_satz, rabatt):
    pos_liste = []
    total_netto_material = 0
    total_saecke_projekt = 0
    
    total_zaun_laenge = sum([z['laenge'] for z in st.session_state['zauene']])
    total_montage_kosten = montage_std * montage_satz
    montage_anteil_pro_m = (total_montage_kosten / total_zaun_laenge) if total_zaun_laenge > 0 else 0

    # A. Zäune
    for i, z in enumerate(st.session_state['zauene']):
        details = []
        farbfaktor = db.farben.get(z['farbe'], 1.0)
        sum_pos_material = 0

        # Matten
        anz_matten = math.ceil(z['laenge'] / 2.5)
        p_matte_einzel, nr_matte = db.get_matte_preis(z['typ'], z['hoehe'])
        p_matte_einzel *= farbfaktor
        k_matten = anz_matten * p_matte_einzel
        details.append({"txt": f"Gittermatten: {anz_matten} Stk {z['typ']} ({z['farbe']}, H={z['hoehe']})", "nr": nr_matte, "ep": p_matte_einzel, "sum": k_matten})
        sum_pos_material += k_matten
        
        # Steher
        anz_steher = anz_matten + 1 + z['ecken']
        p_steher_raw, nr_steher = db.get_steher_preis(z['steher'], z['hoehe'])
        p_steher_raw *= farbfaktor
        k_steher = anz_steher * p_steher_raw
        l_steher_mm = z['hoehe'] + 600 if z['montage'] == "Einbetonieren" else z['hoehe'] + 100
        details.append({"txt": f"Steher: {anz_steher} Stk '{z['steher']}' (L={l_steher_mm}mm)", "nr": nr_steher, "ep": p_steher_raw, "sum": k_steher})
        sum_pos_material += k_steher

        # Montage Material
        if z['montage'] == "Einbetonieren":
            beton_anz = anz_steher * z['beton_stk']
            p_beton = db.data['zubehoer']['montage']['Beton_Sack']['p']
            k_beton = beton_anz * p_beton
            details.append({"txt": f"Fundament: {beton_anz} Säcke Fertigbeton", "nr": db.data['zubehoer']['montage']['Beton_Sack']['nr'], "ep": p_beton, "sum": k_beton})
            sum_pos_material += k_beton
            total_saecke_projekt += beton_anz
        else:
            p_kons = db.data['zubehoer']['montage']['Konsole']['p']
            p_mat = db.data['zubehoer']['montage']['Montagemat']['p']
            p_set = (p_kons + p_mat) * db.faktor
            k_kons = anz_steher * p_set
            details.append({"txt": f"Montage-Set: {anz_steher}x Konsole & Anker", "nr": "SET-KON", "ep": p_set, "sum": k_kons})
            sum_pos_material += k_kons

        # Sichtschutz
        if z['sicht'] != "Keiner":
            info = db.data['zubehoer']['sichtschutz'][z['sicht']]
            reihen = z['reihen']
            if "Rolle" in z['sicht']:
                total_bahnen_m = z['laenge'] * reihen
                anz_einheiten = math.ceil(total_bahnen_m / info['len'])
                calc_txt = f"{reihen} Reihen à {z['laenge']}m"
            else:
                anz_einheiten = anz_matten * reihen
                calc_txt = f"{reihen} Reihen für {anz_matten} Matten"
            
            p_sicht = info['p']
            k_sicht = anz_einheiten * p_sicht
            details.append({"txt": f"Sichtschutz: {anz_einheiten} {info['einheit']} ({z['sicht']})", "nr": info['nr'], "ep": p_sicht, "sum": k_sicht})
            details.append({"txt": f"   > Kalkulation: {calc_txt}", "nr": "", "ep": 0, "sum": 0})
            sum_pos_material += k_sicht

        # LFM Preis
        mat_rabattiert = sum_pos_material * (1 - (rabatt/100))
        montage_anteil = z['laenge'] * montage_anteil_pro_m
        real_lfm_preis = (mat_rabattiert + montage_anteil) / z['laenge'] if z['laenge'] > 0 else 0
        details.insert(0, {"txt": f"KENNZAHL: {real_lfm_preis:.2f} EUR / lfm (fertig montiert & rabattiert)", "nr":"", "ep": 0, "sum": 0, "highlight": True})

        pos_liste.append({"titel": f"Zaun: {z['bezeichnung']} ({z['laenge']}m)", "details": details, "preis_total": sum_pos_material})
        total_netto_material += sum_pos_material

    # B. Tore
    for i, t in enumerate(st.session_state['tore']):
        details = []
        farbfaktor = db.farben.get(t['farbe'], 1.0)
        sum_tor = 0

        p_basis, nr_tor = db.get_tor_preis(t['modell'], t['sl'], t['th'])
        p_basis *= farbfaktor
        details.append({"txt": f"Torflügel: {t['modell']} ({t['sl']}x{t['th']})", "nr": nr_tor, "ep": p_basis, "sum": p_basis})
        sum_tor += p_basis

        if t['saeule'] in db.data['zubehoer']['torsaeulen']:
            ts_info = db.data['zubehoer']['torsaeulen'][t['saeule']]
            p_saeule = ts_info['p'] * db.faktor
            details.append({"txt": f"Torsäulen-Set: {t['saeule']}", "nr": ts_info['nr'], "ep": p_saeule, "sum": p_saeule})
            sum_tor += p_saeule

        if t['zub']:
            for z_name in t['zub']:
                item_data = None
                # Suche nach passendem Zubehör Key
                for k, v in db.data['zubehoer']['tor_parts'].items():
                    if k in z_name:
                        item_data = v
                        break
                if item_data:
                    p_item = item_data['p'] * db.faktor
                    details.append({"txt": f"Zubehör: {z_name}", "nr": item_data['nr'], "ep": p_item, "sum": p_item})
                    sum_tor += p_item
        
        pos_liste.append({"titel": f"Tor: {t['modell']} ({t['farbe']})", "details": details, "preis_total": sum_tor})
        total_netto_material += sum_tor

    rabatt_wert = total_netto_material * (rabatt / 100)
    netto_rabattiert = total_netto_material - rabatt_wert
    final_netto = netto_rabattiert + total_montage_kosten
    
    return {
        "positionen": pos_liste, "rabatt": rabatt_wert, "montage": total_montage_kosten,
        "total_netto": final_netto, "mwst": final_netto * 0.20, "brutto": final_netto * 1.20,
        "beton_total": total_saecke_projekt
    }

# ==========================================
# 5. PDF & EDITOR UI
# ==========================================
def create_pdf(res):
    pdf = FPDF()
    pdf.add_page()
    def txt(s): return str(s).encode('latin-1', 'replace').decode('latin-1')

    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt("ANGEBOT - ZAUNBAU"), ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 10, txt(f"Datum: {datetime.date.today().strftime('%d.%m.%Y')}"), ln=True, align='R')
    pdf.ln(10)

    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(10, 8, "#", 1, 0, 'C', 1)
    pdf.cell(25, 8, "ArtNr", 1, 0, 'C', 1)
    pdf.cell(85, 8, "Position / Beschreibung", 1, 0, 'L', 1)
    pdf.cell(30, 8, "Einzelpreis", 1, 0, 'R', 1)
    pdf.cell(40, 8, "Gesamt", 1, 1, 'R', 1)
    
    for idx, pos in enumerate(res['positionen']):
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(10, 8, str(idx+1), "LRT", 0, 'C')
        pdf.cell(25, 8, "", "LRT", 0) 
        pdf.cell(115, 8, txt(pos['titel']), "LRT", 0, 'L')
        pdf.cell(40, 8, txt(f"{pos['preis_total']:,.2f}"), "LRT", 1, 'R')
        
        pdf.set_font("Arial", '', 9)
        for d in pos['details']:
            is_hl = d.get('highlight', False)
            art_nr = d.get('nr', "")
            
            pdf.cell(10, 5, "", "LR", 0)
            if is_hl:
                pdf.set_font("Arial", 'BI', 9)
                pdf.set_text_color(0, 50, 150)
                pdf.cell(25, 5, "", "LR", 0)
                pdf.cell(85, 5, txt(f" > {d['txt']}"), "L", 0, 'L')
                pdf.cell(30, 5, "", 0, 0)
                pdf.cell(40, 5, "", "R", 1)
                pdf.set_font("Arial", '', 9)
                pdf.set_text_color(0,0,0)
            elif d['ep'] == 0:
                pdf.set_text_color(100,100,100)
                pdf.cell(25, 5, "", "LR", 0)
                pdf.cell(85, 5, txt(f"     {d['txt']}"), "L", 0, 'L')
                pdf.cell(30, 5, "", 0, 0)
                pdf.cell(40, 5, "", "R", 1)
                pdf.set_text_color(0,0,0)
            else:
                pdf.cell(25, 5, txt(art_nr), "LR", 0, 'C')
                pdf.cell(85, 5, txt(f" - {d['txt']}"), "L", 0, 'L')
                pdf.cell(30, 5, txt(f"{d['ep']:,.2f}"), 0, 0, 'R')
                pdf.cell(40, 5, txt(f"{d['sum']:,.2f}"), "R", 1, 'R')
        pdf.cell(190, 1, "", "T", 1) 

    pdf.ln(5)
    def sum_row(lab, val, bold=False, color=False):
        if bold: pdf.set_font("Arial", 'B', 11)
        else: pdf.set_font("Arial", '', 10)
        if color: pdf.set_fill_color(200, 255, 200)
        fill = 1 if color else 0
        pdf.cell(150, 8, txt(lab), 0, 0, 'R', fill)
        pdf.cell(40, 8, txt(f"{val:,.2f} EUR"), 1, 1, 'R', fill)

    if res['rabatt'] > 0: sum_row(f"Abzüglich Rabatt", -res['rabatt'])
    if res['montage'] > 0: sum_row(f"Montageleistung", res['montage'])

    pdf.ln(2)
    sum_row("GESAMT NETTO", res['total_netto'], bold=True)
    sum_row("MwSt (20%)", res['mwst'])
    sum_row("GESAMT BRUTTO", res['brutto'], bold=True, color=True)

    if res['beton_total'] > 0:
        pdf.ln(10)
        pdf.set_font("Arial", 'I', 9)
        pdf.multi_cell(0, 5, txt(f"Logistik: {res['beton_total']} Sack Fertigbeton."))

    return pdf.output(dest='S').encode('latin-1')

def render_price_editor():
    st.subheader("📝 Preisliste bearbeiten")
    
    # IMPORT / EXPORT BUTTONS
    c_dl, c_up = st.columns(2)
    with c_dl:
        json_str = json.dumps(st.session_state['db_data'], indent=2)
        st.download_button("💾 Datenbank speichern (JSON)", json_str, "preise.json", "application/json", type="primary")
    with c_up:
        uploaded = st.file_uploader("📂 Datenbank laden", type=["json"])
        if uploaded is not None:
            try:
                st.session_state['db_data'] = json.load(uploaded)
                st.success("Datenbank geladen!")
                st.rerun()
            except:
                st.error("Fehler beim Laden!")

    st.divider()
    
    # TABS FOR EDITORS
    data = st.session_state['db_data']
    tab_m, tab_s, tab_z = st.tabs(["Gittermatten", "Steher", "Zubehör/Tore"])
    
    # 1. MATTEN EDITOR
    with tab_m:
        st.info("Tabelle ist bearbeitbar! Neue Zeile mit '+' unten.")
        rows = []
        for typ, heights in data['matten'].items():
            for h, info in heights.items():
                rows.append({"Typ": typ, "Höhe": h, "Preis": info['p'], "ArtNr": info['nr']})
        
        df = pd.DataFrame(rows)
        edited_df = st.data_editor(df, num_rows="dynamic", key="edit_mat", use_container_width=True)
        
        if st.button("Matten speichern", type="primary"):
            new_mat = {}
            for _, row in edited_df.iterrows():
                if not row['Typ']: continue
                t, h = row['Typ'], int(row['Höhe'])
                if t not in new_mat: new_mat[t] = {}
                new_mat[t][h] = {'p': row['Preis'], 'nr': row['ArtNr']}
            st.session_state['db_data']['matten'] = new_mat
            st.success("Gespeichert!")

    # 2. STEHER EDITOR
    with tab_s:
        rows = []
        for typ, info in data['steher'].items():
            rows.append({"Typ": typ, "Preis_pro_m": info['p'], "ArtNr": info['nr']})
        
        df_s = pd.DataFrame(rows)
        edited_s = st.data_editor(df_s, num_rows="dynamic", key="edit_st", use_container_width=True)
        
        if st.button("Steher speichern", type="primary"):
            new_st = {}
            for _, row in edited_s.iterrows():
                if row['Typ']:
                    new_st[row['Typ']] = {'p': row['Preis_pro_m'], 'nr': row['ArtNr']}
            st.session_state['db_data']['steher'] = new_st
            st.success("Gespeichert!")

    # 3. ZUBEHÖR EDITOR (Flat List)
    with tab_z:
        rows = []
        # Flatten structure
        for cat in ['montage', 'sichtschutz', 'tor_parts', 'torsaeulen']:
            if cat in data['zubehoer']:
                for name, info in data['zubehoer'][cat].items():
                    rows.append({"Kategorie": cat, "Artikel": name, "Preis": info['p'], "ArtNr": info.get('nr','')})
        
        df_z = pd.DataFrame(rows)
        edited_z = st.data_editor(df_z, num_rows="dynamic", key="edit_zub", use_container_width=True)
        
        if st.button("Zubehör speichern", type="primary"):
            # Rebuild structure (careful not to delete unspecified cats)
            for _, row in edited_z.iterrows():
                cat, name = row['Kategorie'], row['Artikel']
                if cat in st.session_state['db_data']['zubehoer']:
                    # Update or Add
                    if name not in st.session_state['db_data']['zubehoer'][cat]:
                        st.session_state['db_data']['zubehoer'][cat][name] = {}
                    
                    st.session_state['db_data']['zubehoer'][cat][name]['p'] = row['Preis']
                    st.session_state['db_data']['zubehoer'][cat][name]['nr'] = row['ArtNr']
                    
                    # Special fields handling (restore defaults if new)
                    if cat == 'sichtschutz' and 'einheit' not in st.session_state['db_data']['zubehoer'][cat][name]:
                         st.session_state['db_data']['zubehoer'][cat][name]['einheit'] = "Stk"
                         st.session_state['db_data']['zubehoer'][cat][name]['len'] = 1.0

            st.success("Gespeichert!")

# ==========================================
# 6. MAIN APP
# ==========================================
def main():
    st.set_page_config(page_title="Zaun-Profi V5.0", page_icon="🏗️", layout="wide")
    
    c1, c2, c3 = st.columns([1,4,1])
    if os.path.exists("logo_firma.png"): c1.image("logo_firma.png", width=100)
    c2.title("🏗️ Multi-Zaun Projektierung")
    if os.path.exists("logo_brix.png"): c3.image("logo_brix.png", width=100)

    with st.sidebar:
        st.header("Admin")
        faktor = st.number_input("Globaler Faktor:", 0.5, 2.0, 1.0, 0.01)
    
    db = ZaunDatabase(faktor)

    tab1, tab2, tab3, tab4 = st.tabs(["1️⃣ Zäune", "2️⃣ Tore", "3️⃣ Global", "📝 PREIS-MANAGER"])

    with tab1:
        st.subheader("Zaun hinzufügen")
        with st.form("zaun_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            bez = c1.text_input("Bezeichnung:", "Vorgarten")
            
            # Dynamische Listen aus DB laden
            matten_opts = list(st.session_state['db_data']['matten'].keys())
            typ = c2.selectbox("Matten:", matten_opts)
            
            c3, c4 = st.columns(2)
            laenge = c3.number_input("Länge (m):", 1.0, 500.0, 10.0)
            
            # Höhen passend zum Typ
            if typ in st.session_state['db_data']['matten']:
                h_opts = sorted(st.session_state['db_data']['matten'][typ].keys())
            else:
                h_opts = [1030]
            hoehe = c4.select_slider("Höhe (mm):", options=h_opts, value=h_opts[min(1, len(h_opts)-1)])
            
            c5, c6 = st.columns(2)
            farbe = c5.selectbox("Farbe:", list(db.farben.keys()))
            sicht_opts = list(st.session_state['db_data']['zubehoer']['sichtschutz'].keys())
            sicht = c6.selectbox("Sichtschutz:", sicht_opts)
            
            reihen = 0
            if sicht != "Keiner":
                reihen = st.number_input("Reihen:", 1, 15, int(hoehe/200))
            
            c7, c8 = st.columns(2)
            mont = c7.radio("Montage:", ["Einbetonieren", "Auf Fundament"])
            steher_opts = list(st.session_state['db_data']['steher'].keys())
            steher = c8.selectbox("Steher:", steher_opts)
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
                    st.caption(f"{z['typ']} | H:{z['hoehe']}mm")
                    if st.button("Löschen", key=f"del_{i}"): delete_zaun(i); st.rerun()

    with tab2:
        st.subheader("Tore")
        with st.form("tor_form"):
            tore_opts = list(st.session_state['db_data']['tore'].keys())
            mod = st.selectbox("Modell:", tore_opts)
            c1, c2 = st.columns(2)
            sl = c1.number_input("Lichte (mm):", 800, 5000, 1000, 50)
            th = c2.number_input("Höhe (mm):", 800, 2500, 1200, 50)
            
            ts_opts = list(st.session_state['db_data']['zubehoer']['torsaeulen'].keys())
            ts = st.selectbox("Säulen:", ts_opts)
            tf = st.selectbox("Farbe:", list(db.farben.keys()))
            
            zub_opts = list(st.session_state['db_data']['zubehoer']['tor_parts'].keys())
            tz = st.multiselect("Zubehör:", zub_opts)
            
            if st.form_submit_button("➕ Tor speichern"):
                add_tor(mod, sl, th, ts, tz, tf)
                st.rerun()
        
        if st.session_state['tore']:
            for i, t in enumerate(st.session_state['tore']):
                with st.expander(f"Tor: {t['modell']}", expanded=True):
                    if st.button("Löschen", key=f"delt_{i}"): delete_tor(i); st.rerun()

    with tab3:
        h_std = st.number_input("Montage (h):", 0.0, 500.0, 0.0)
        h_satz = st.number_input("Satz (€):", 0.0, 200.0, 65.0)
        rabatt = st.slider("Rabatt %:", 0, 50, 0)
        
        res = calculate_project(db, h_std, h_satz, rabatt)
        
        st.subheader("Kalkulation")
        k1, k2 = st.columns(2)
        k1.metric("Netto", f"€ {res['total_netto']:,.2f}")
        k2.metric("Brutto", f"€ {res['brutto']:,.2f}")
        
        pdf_bytes = create_pdf(res)
        st.download_button("📄 PDF Angebot (Final)", pdf_bytes, "Angebot.pdf", "application/pdf", type="primary")

    with tab4:
        render_price_editor()

if __name__ == "__main__":
    main()
