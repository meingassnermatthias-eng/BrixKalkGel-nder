import streamlit as st
import math
import pandas as pd
from fpdf import FPDF
import datetime
import os
import json
from streamlit_pdf_viewer import pdf_viewer

# ==========================================
# 1. STANDARD DATEN (Neue Struktur: VZ vs FARBE)
# ==========================================
def get_default_data():
    return {
        # MATTEN: p_vz = Preis Verzinkt, p_fb = Preis Farbe (Standard)
        "matten": {
            "Leicht 6/5/6": {
                830:  {'p_vz': 28.00, 'nr_vz': 'M-L-0830-V', 'p_fb': 35.00, 'nr_fb': 'M-L-0830-F'}, 
                1030: {'p_vz': 33.00, 'nr_vz': 'M-L-1030-V', 'p_fb': 42.00, 'nr_fb': 'M-L-1030-F'}, 
                1230: {'p_vz': 39.00, 'nr_vz': 'M-L-1230-V', 'p_fb': 49.00, 'nr_fb': 'M-L-1230-F'}, 
                1430: {'p_vz': 46.00, 'nr_vz': 'M-L-1430-V', 'p_fb': 58.00, 'nr_fb': 'M-L-1430-F'}, 
                1630: {'p_vz': 52.00, 'nr_vz': 'M-L-1630-V', 'p_fb': 65.00, 'nr_fb': 'M-L-1630-F'}, 
                1830: {'p_vz': 60.00, 'nr_vz': 'M-L-1830-V', 'p_fb': 75.00, 'nr_fb': 'M-L-1830-F'}, 
                2030: {'p_vz': 68.00, 'nr_vz': 'M-L-2030-V', 'p_fb': 85.00, 'nr_fb': 'M-L-2030-F'}
            },
            "Schwer 8/6/8": {
                830:  {'p_vz': 38.00, 'nr_vz': 'M-S-0830-V', 'p_fb': 48.00, 'nr_fb': 'M-S-0830-F'}, 
                1030: {'p_vz': 46.00, 'nr_vz': 'M-S-1030-V', 'p_fb': 58.00, 'nr_fb': 'M-S-1030-F'}, 
                1230: {'p_vz': 55.00, 'nr_vz': 'M-S-1230-V', 'p_fb': 69.00, 'nr_fb': 'M-S-1230-F'}, 
                1430: {'p_vz': 63.00, 'nr_vz': 'M-S-1430-V', 'p_fb': 79.00, 'nr_fb': 'M-S-1430-F'}, 
                1630: {'p_vz': 71.00, 'nr_vz': 'M-S-1630-V', 'p_fb': 89.00, 'nr_fb': 'M-S-1630-F'}, 
                1830: {'p_vz': 79.00, 'nr_vz': 'M-S-1830-V', 'p_fb': 99.00, 'nr_fb': 'M-S-1830-F'}, 
                2030: {'p_vz': 88.00, 'nr_vz': 'M-S-2030-V', 'p_fb': 110.00, 'nr_fb': 'M-S-2030-F'}
            }
        },
        # STEHER
        "steher": {
            "Rechteck 60x40":    {'p_vz': 24.00, 'nr_vz': 'ST-RE-V', 'p_fb': 30.00, 'nr_fb': 'ST-RE-F'}, 
            "Rundrohr 60mm":     {'p_vz': 28.00, 'nr_vz': 'ST-RD-V', 'p_fb': 35.00, 'nr_fb': 'ST-RD-F'}, 
            "Typ SL 60 (Klemm)": {'p_vz': 36.00, 'nr_vz': 'ST-SL-V', 'p_fb': 45.00, 'nr_fb': 'ST-SL-F'}, 
            "Typ 70k (Design)":  {'p_vz': 44.00, 'nr_vz': 'ST-70-V', 'p_fb': 55.00, 'nr_fb': 'ST-70-F'}
        },
        # TORE
        "tore": {
            "Gehtür 1-flg": [
                {'max_b': 1000, 'max_h': 1250, 'p_vz': 360.00, 'nr_vz': 'GT-100-125-V', 'p_fb': 450.00, 'nr_fb': 'GT-100-125-F'}, 
                {'max_b': 1000, 'max_h': 2000, 'p_vz': 440.00, 'nr_vz': 'GT-100-200-V', 'p_fb': 550.00, 'nr_fb': 'GT-100-200-F'}
            ],
            "Einfahrtstor 2-flg": [
                {'max_b': 3000, 'max_h': 1250, 'p_vz': 960.00, 'nr_vz': 'ET-300-125-V', 'p_fb': 1200.00, 'nr_fb': 'ET-300-125-F'}, 
                {'max_b': 3000, 'max_h': 2000, 'p_vz': 1120.00, 'nr_vz': 'ET-300-200-V', 'p_fb': 1400.00, 'nr_fb': 'ET-300-200-F'}
            ]
        },
        # ZUBEHÖR (Hat meistens keinen Unterschied VZ/Farbe, daher p_vz = p_fb oder neutral)
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
        "farben": {
            "Verzinkt": "VZ", 
            "Anthrazit (7016)": "FB", 
            "Moosgrün (6005)": "FB", 
            "Sonderfarbe": "SONDER"
        }
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

    def is_color(self, farbe_name):
        code = self.farben.get(farbe_name, "FB")
        return code # "VZ", "FB" oder "SONDER"

    def get_matte_preis(self, typ, hoehe, farb_code):
        if typ not in self.data['matten']: return 0, "N/A"
        
        verf = sorted([int(k) for k in self.data['matten'][typ].keys()])
        if not verf: return 0, "N/A"
        passende_h = min(verf, key=lambda x: abs(x - hoehe))
        item = self.data['matten'][typ][passende_h]
        
        # Unterscheidung Verzinkt vs Farbe
        if farb_code == "VZ":
            preis = item.get('p_vz', 0)
            nr = item.get('nr_vz', '')
        else:
            preis = item.get('p_fb', 0)
            nr = item.get('nr_fb', '')
            
        if farb_code == "SONDER":
            preis *= 1.15 # Aufschlag für Sonderfarbe auf den Farbpreis
            nr += "-SON"
            
        return preis * self.faktor, nr

    def get_steher_preis(self, typ, hoehe, farb_code):
        if typ not in self.data['steher']: return 0, "N/A"
        basis = self.data['steher'][typ]
        
        if farb_code == "VZ":
            p_meter = basis.get('p_vz', 0)
            nr = basis.get('nr_vz', '')
        else:
            p_meter = basis.get('p_fb', 0)
            nr = basis.get('nr_fb', '')

        if farb_code == "SONDER":
            p_meter *= 1.15
            nr += "-SON"

        p_total = p_meter * (hoehe/1000) * self.faktor
        return p_total, nr

    def get_tor_preis(self, modell, b, h, farb_code):
        moegliche = self.data['tore'].get(modell, [])
        if not moegliche: return 0, "N/A"
        passende = [t for t in moegliche if t['max_b'] >= b and t['max_h'] >= h]
        
        if not passende: 
             t = max(moegliche, key=lambda x: x.get('p_fb', 0))
             base_p = t.get('p_fb', 0) * 1.30
             return base_p * self.faktor, "SONDERGRÖSSE"
        
        t = min(passende, key=lambda x: x.get('p_fb', 0))
        
        if farb_code == "VZ":
            preis = t.get('p_vz', 0)
            nr = t.get('nr_vz', '')
        else:
            preis = t.get('p_fb', 0)
            nr = t.get('nr_fb', '')
            
        if farb_code == "SONDER":
            preis *= 1.15
            nr += "-SON"
            
        return preis * self.faktor, nr

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

    # A. ZÄUNE
    for i, z in enumerate(st.session_state['zauene']):
        details = []
        farb_code = db.is_color(z['farbe']) # VZ oder FB
        sum_pos_material = 0

        # Matten
        anz_matten = math.ceil(z['laenge'] / 2.5)
        p_matte_einzel, nr_matte = db.get_matte_preis(z['typ'], z['hoehe'], farb_code)
        k_matten = anz_matten * p_matte_einzel
        details.append({"txt": f"Matte: {anz_matten} Stk {z['typ']} ({z['farbe']}, H={z['hoehe']})", "nr": nr_matte, "ep": p_matte_einzel, "sum": k_matten})
        sum_pos_material += k_matten
        
        # Steher
        anz_steher = anz_matten + 1 + z['ecken']
        p_steher_total, nr_steher = db.get_steher_preis(z['steher'], z['hoehe'], farb_code)
        k_steher = anz_steher * p_steher_total
        l_steher_mm = z['hoehe'] + 600 if z['montage'] == "Einbetonieren" else z['hoehe'] + 100
        details.append({"txt": f"Steher: {anz_steher} Stk '{z['steher']}' (L={l_steher_mm}mm)", "nr": nr_steher, "ep": p_steher_total, "sum": k_steher})
        sum_pos_material += k_steher

        # Montage Material
        if z['montage'] == "Einbetonieren":
            beton_anz = anz_steher * z['beton_stk']
            p_beton = db.data['zubehoer']['montage']['Beton_Sack']['p']
            k_beton = beton_anz * p_beton
            details.append({"txt": f"Fundament: {beton_anz} Säcke Fertigbeton", "nr": "BETON", "ep": p_beton, "sum": k_beton})
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

    # B. TORE
    for i, t in enumerate(st.session_state['tore']):
        details = []
        farb_code = db.is_color(t['farbe'])
        sum_tor = 0

        p_basis, nr_tor = db.get_tor_preis(t['modell'], t['sl'], t['th'], farb_code)
        details.append({"txt": f"Torflügel: {t['modell']} ({t['sl']}x{t['th']})", "nr": nr_tor, "ep": p_basis, "sum": p_basis})
        sum_tor += p_basis

        ts_info = db.data['zubehoer']['torsaeulen'][t['saeule']]
        p_saeule = ts_info['p'] * db.faktor
        details.append({"txt": f"Torsäulen-Set: {t['saeule']}", "nr": ts_info['nr'], "ep": p_saeule, "sum": p_saeule})
        sum_tor += p_saeule

        if t['zub']:
            for z_name in t['zub']:
                item_data = None
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
    st.subheader("📝 Preis-Manager")
    st.info("Hier kannst du Preise für Verzinkt (VZ) und Farbe (FB) getrennt anlegen. Vergiss nicht zu SPEICHERN!")

    # JSON EXPORT
    c_dl, c_up = st.columns(2)
    with c_dl:
        json_str = json.dumps(st.session_state['db_data'], indent=2)
        st.download_button("💾 Datenbank sichern", json_str, "preise.json", "application/json", type="primary")
    with c_up:
        uploaded = st.file_uploader("📂 Datenbank laden", type=["json"])
        if uploaded is not None:
            try:
                st.session_state['db_data'] = json.load(uploaded)
                st.success("Erfolgreich geladen!")
                st.rerun()
            except: st.error("Fehler beim Laden!")

    st.divider()
    data = st.session_state['db_data']
    tab_m, tab_s, tab_t, tab_z = st.tabs(["Matten", "Steher", "Tore", "Zubehör"])
    
    # 1. MATTEN EDITOR (VZ vs FB)
    with tab_m:
        rows = []
        for typ, heights in data['matten'].items():
            for h, info in heights.items():
                rows.append({
                    "Typ": typ, "Höhe": h, 
                    "Preis_VZ": info.get('p_vz',0), "ArtNr_VZ": info.get('nr_vz',''),
                    "Preis_FB": info.get('p_fb',0), "ArtNr_FB": info.get('nr_fb','')
                })
        
        df = pd.DataFrame(rows)
        edited_df = st.data_editor(df, num_rows="dynamic", key="edit_mat", use_container_width=True)
        
        if st.button("Matten speichern", type="primary"):
            new_mat = {}
            for _, row in edited_df.iterrows():
                if not row['Typ']: continue
                t, h = row['Typ'], int(row['Höhe'])
                if t not in new_mat: new_mat[t] = {}
                new_mat[t][h] = {
                    'p_vz': row['Preis_VZ'], 'nr_vz': row['ArtNr_VZ'],
                    'p_fb': row['Preis_FB'], 'nr_fb': row['ArtNr_FB']
                }
            st.session_state['db_data']['matten'] = new_mat
            st.success("Gespeichert!")

    # 2. STEHER EDITOR (VZ vs FB)
    with tab_s:
        rows = []
        for typ, info in data['steher'].items():
            rows.append({
                "Typ": typ, 
                "Preis_VZ": info.get('p_vz',0), "ArtNr_VZ": info.get('nr_vz',''),
                "Preis_FB": info.get('p_fb',0), "ArtNr_FB": info.get('nr_fb','')
            })
        df_s = pd.DataFrame(rows)
        edited_s = st.data_editor(df_s, num_rows="dynamic", key="edit_st", use_container_width=True)
        
        if st.button("Steher speichern", type="primary"):
            new_st = {}
            for _, row in edited_s.iterrows():
                if row['Typ']: 
                    new_st[row['Typ']] = {
                        'p_vz': row['Preis_VZ'], 'nr_vz': row['ArtNr_VZ'],
                        'p_fb': row['Preis_FB'], 'nr_fb': row['ArtNr_FB']
                    }
            st.session_state['db_data']['steher'] = new_st
            st.success("Gespeichert!")

    # 3. TORE EDITOR (VZ vs FB)
    with tab_t:
        rows = []
        for mod, variants in data['tore'].items():
            for v in variants:
                rows.append({
                    "Modell": mod, "Breite": v['max_b'], "Höhe": v['max_h'], 
                    "Preis_VZ": v.get('p_vz',0), "ArtNr_VZ": v.get('nr_vz',''),
                    "Preis_FB": v.get('p_fb',0), "ArtNr_FB": v.get('nr_fb','')
                })
        
        df_t = pd.DataFrame(rows)
        edited_t = st.data_editor(df_t, num_rows="dynamic", key="edit_tore", use_container_width=True)
        
        if st.button("Tore speichern", type="primary"):
            new_tore = {}
            for _, row in edited_t.iterrows():
                m = row['Modell']
                if not m: continue
                if m not in new_tore: new_tore[m] = []
                new_tore[m].append({
                    'max_b': int(row['Breite']), 'max_h': int(row['Höhe']), 
                    'p_vz': float(row['Preis_VZ']), 'nr_vz': row['ArtNr_VZ'],
                    'p_fb': float(row['Preis_FB']), 'nr_fb': row['ArtNr_FB']
                })
            st.session_state['db_data']['tore'] = new_tore
            st.success("Gespeichert!")

    # 4. ZUBEHÖR
    with tab_z:
        rows = []
        for cat in ['montage', 'sichtschutz', 'tor_parts', 'torsaeulen']:
            if cat in data['zubehoer']:
                for name, info in data['zubehoer'][cat].items():
                    rows.append({"Kategorie": cat, "Artikel": name, "Preis": info['p'], "ArtNr": info.get('nr','')})
        
        df_z = pd.DataFrame(rows)
        edited_z = st.data_editor(df_z, num_rows="dynamic", key="edit_zub", use_container_width=True)
        
        if st.button("Zubehör speichern", type="primary"):
            for _, row in edited_z.iterrows():
                cat, name = row['Kategorie'], row['Artikel']
                if not cat or not name: continue
                if cat not in st.session_state['db_data']['zubehoer']:
                    st.session_state['db_data']['zubehoer'][cat] = {}
                
                # Zubehör hat meist keine VZ/FB Trennung, wir bleiben beim einfachen Preis 'p'
                st.session_state['db_data']['zubehoer'][cat][name] = {'p': row['Preis'], 'nr': row['ArtNr']}
                # Fix für Sichtschutz
                if cat == 'sichtschutz' and 'einheit' not in st.session_state['db_data']['zubehoer'][cat][name]:
                     st.session_state['db_data']['zubehoer'][cat][name].update({'einheit': "Stk", 'len': 1.0})
            st.success("Gespeichert!")

# ==========================================
# 6. MAIN APP
# ==========================================
def main():
    st.set_page_config(page_title="Zaun-Profi V6.0", page_icon="🏗️", layout="wide")
    
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
            
            matten_opts = list(st.session_state['db_data']['matten'].keys())
            typ = c2.selectbox("Matten:", matten_opts)
            
            c3, c4 = st.columns(2)
            laenge = c3.number_input("Länge (m):", 1.0, 500.0, 10.0)
            
            if typ in st.session_state['db_data']['matten']:
                h_opts = sorted([int(x) for x in st.session_state['db_data']['matten'][typ].keys()])
            else: h_opts = [1030]
            
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
            
            zub_map = {k: k for k in st.session_state['db_data']['zubehoer']['tor_parts'].keys()}
            tz = st.multiselect("Zubehör:", list(zub_map.keys()))
            
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
        
        st.markdown("---")
        res = calculate_project(db, h_std, h_satz, rabatt)
        
        k1, k2 = st.columns(2)
        k1.metric("Netto", f"€ {res['total_netto']:,.2f}")
        k2.metric("Brutto", f"€ {res['brutto']:,.2f}")
        
        pdf_bytes = create_pdf(res)
        st.download_button("📄 PDF Angebot (Final)", pdf_bytes, "Angebot.pdf", "application/pdf", type="primary")

    with tab4:
        render_price_editor()

if __name__ == "__main__":
    main()
