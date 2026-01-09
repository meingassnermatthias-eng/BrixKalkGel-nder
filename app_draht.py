import streamlit as st
import math
import pandas as pd
from fpdf import FPDF
import datetime
import os
import json
import requests

# ==========================================
# 0. SETUP
# ==========================================
st.set_page_config(page_title="Meingassner Kalkulator", page_icon="🏗️", layout="wide")

# Link zu deiner Raw-JSON auf GitHub (Ersetze dies später mit deinem echten Link!)
# Wenn keine URL da ist, sucht er lokal.
GITHUB_JSON_URL = "https://raw.githubusercontent.com/DEIN_USER/DEIN_REPO/main/katalog.json"

st.markdown("""
    <style>
    .main-header { font-size: 2.0rem; font-weight: 700; color: #1E3A8A; margin-bottom: 15px; }
    .sub-header { font-size: 1.3rem; font-weight: 600; color: #444; border-bottom: 2px solid #ddd; padding-bottom: 5px; margin-top: 15px;}
    div.stButton > button { min-height: 50px; font-size: 18px !important; border-radius: 8px; width: 100%; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 1. DATEN LADEN
# ==========================================
@st.cache_data(ttl=600) # Cache für 10 Minuten, damit er nicht ständig neu lädt
def load_data():
    # 1. Versuch: Lokal (für Testzwecke)
    if os.path.exists('katalog.json'):
        with open('katalog.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # 2. Versuch: GitHub (wenn lokal nicht vorhanden)
    try:
        r = requests.get(GITHUB_JSON_URL)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    
    return None

if 'db' not in st.session_state:
    data = load_data()
    if data:
        st.session_state.db = data
    else:
        st.error("Fehler: Keine Datenbank gefunden (katalog.json).")
        st.stop()

if 'cart' not in st.session_state: st.session_state.cart = []

DB = st.session_state.db

# ==========================================
# 2. PDF FUNKTIONEN
# ==========================================
def txt_clean(s):
    s = str(s).replace("€", "EUR").replace("–", "-")
    return s.encode('latin-1', 'replace').decode('latin-1')

def create_pdf(cart_items):
    pdf = FPDF()
    pdf.add_page()
    if os.path.exists("logo_firma.png"): 
        pdf.image("logo_firma.png", 10, 8, 40); pdf.ln(25)
    else: pdf.ln(10)
    
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt_clean("ANGEBOT / KOSTENSCHÄTZUNG"), ln=True, align='C')
    pdf.ln(10)
    
    total_net = 0
    pdf.set_font("Arial", '', 10)
    
    # Header
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(10, 8, "#", 1, 0, 'C', 1)
    pdf.cell(110, 8, "Position", 1, 0, 'L', 1)
    pdf.cell(25, 8, "Menge", 1, 0, 'C', 1)
    pdf.cell(45, 8, "Gesamt", 1, 1, 'R', 1)
    
    for idx, item in enumerate(cart_items):
        total_net += item['preis']
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(10, 8, str(idx+1), "LRT", 0, 'C')
        pdf.cell(110, 8, txt_clean(item['titel']), "LRT", 0, 'L')
        pdf.cell(25, 8, txt_clean(item['menge_txt']), "LRT", 0, 'C')
        pdf.cell(45, 8, txt_clean(f"{item['preis']:,.2f}"), "LRT", 1, 'R')
        
        pdf.set_font("Arial", '', 9)
        for d in item['details']:
            pdf.cell(10, 5, "", "LR", 0)
            pdf.cell(110, 5, txt_clean(f" - {d}"), "LR", 0, 'L')
            pdf.cell(25, 5, "", "LR", 0); pdf.cell(45, 5, "", "LR", 1)
        pdf.cell(190, 1, "", "T", 1)
        
    mwst = total_net * 0.20
    brutto = total_net + mwst
    
    pdf.ln(5)
    pdf.set_font("Arial", '', 10)
    pdf.cell(145, 7, "Netto:", 0, 0, 'R'); pdf.cell(45, 7, txt_clean(f"{total_net:,.2f} EUR"), 1, 1, 'R')
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(145, 8, "Brutto:", 0, 0, 'R'); pdf.cell(45, 8, txt_clean(f"{brutto:,.2f} EUR"), 1, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 3. KALKULATOR MODULE
# ==========================================

def render_individual():
    st.markdown("<div class='main-header'>🛠️ Metallbau Individual</div>", unsafe_allow_html=True)
    
    # Settings (versteckt im Expander um Platz zu sparen)
    with st.expander("Einstellungen (Stundensatz / Faktor)"):
        c1, c2 = st.columns(2)
        std_satz = c1.number_input("Stundensatz (€)", value=65.0)
        mat_faktor = c2.number_input("Material Faktor", value=1.2)

    raw = DB.get('individual', {})
    if not raw: st.error("Datenbank leer."); return

    col1, col2 = st.columns(2)
    kat = col1.selectbox("Kategorie", list(raw.keys()))
    mod = col2.selectbox("Modell", list(raw[kat].keys()))
    
    data = raw[kat][mod]
    
    st.markdown(f"<div class='sub-header'>Maße & Menge ({data.get('einheit')})</div>", unsafe_allow_html=True)
    c_m1, c_m2, c_m3 = st.columns(3)
    menge = c_m1.number_input("Anzahl", 1.0, 100.0, 1.0)
    laenge = c_m2.number_input("Länge (m)", 0.0, 50.0, 0.0)
    breite = c_m3.number_input("Breite (m)", 0.0, 20.0, 0.0)
    flaeche = laenge * breite
    
    st.markdown("<div class='sub-header'>Optionen</div>", unsafe_allow_html=True)
    opts_sel = []
    
    # Optionen rendern
    if 'optionen' in data:
        for o_name, o_val in data['optionen'].items():
            p, unit, z = o_val['p'], o_val['einheit'], o_val.get('z_plus', 0)
            
            # Faktor berechnen
            calc_f = menge if unit == 'Pauschal' else (laenge*menge if unit == 'pro_lfm' else flaeche*menge)
            
            if st.checkbox(f"{o_name} ({p}€ {unit})", key=o_name):
                if calc_f == 0 and unit != 'Pauschal':
                    st.warning("⚠️ Maße fehlen!")
                else:
                    cost = p * calc_f
                    time = z * calc_f
                    opts_sel.append({'txt': f"{o_name} ({calc_f:.1f} {unit})", 'c': cost, 't': time})

    # Berechnung
    basis_mat = data['mat'] * menge
    basis_zeit = (data['z_fert'] + data['z_mont']) * menge
    
    opt_mat = sum(x['c'] for x in opts_sel)
    opt_zeit = sum(x['t'] for x in opts_sel)
    
    total = ((basis_mat + opt_mat) * mat_faktor) + ((basis_zeit + opt_zeit) * std_satz)
    
    st.info(f"**Preis: {total:,.2f} €** (Netto)")
    
    if st.button("In den Warenkorb", type="primary"):
        det = [f"Basis: {mod} ({menge} Stk)"] 
        if laenge > 0: det.append(f"Maße: {laenge}m x {breite}m")
        det += [x['txt'] for x in opts_sel]
        
        st.session_state.cart.append({"titel": f"{kat}: {mod}", "menge_txt": f"{menge}", "preis": total, "details": det})
        st.success("OK")
        st.rerun()

def render_zaun():
    st.markdown("<div class='main-header'>🚧 Gitterzäune</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    typ = c1.selectbox("Typ", list(DB['matten'].keys()))
    h_list = sorted(list(DB['matten'][typ].keys()), key=lambda x: int(x))
    hoehe = c2.selectbox("Höhe", h_list)
    
    c3, c4 = st.columns(2)
    lfm = c3.number_input("Länge (m)", 1.0, 500.0, 10.0)
    farbe = c4.selectbox("Farbe", ["Verzinkt", "RAL Farbe"])
    steher = st.selectbox("Steher", list(DB['steher'].keys()))
    
    if st.button("Berechnen", type="primary"):
        k = 'p_vz' if farbe == "Verzinkt" else 'p_fb'
        m_cnt = math.ceil(lfm / 2.5)
        st_cnt = m_cnt + 1
        
        p_m = DB['matten'][typ][hoehe][k]
        p_s = DB['steher'][steher][k] * (int(hoehe)/1000 + 0.6)
        
        summe = (m_cnt * p_m) + (st_cnt * p_s)
        st.session_state.cart.append({
            "titel": f"Zaun {typ} H{hoehe}", 
            "menge_txt": f"{lfm}m", 
            "preis": summe, 
            "details": [f"{m_cnt} Matten", f"{st_cnt} Steher ({steher})", farbe]
        })
        st.rerun()

def render_brix():
    st.markdown("<div class='main-header'>🏢 Brix Geländer</div>", unsafe_allow_html=True)
    
    # Check ob Daten da sind
    if 'brix' not in DB or not DB['brix']:
        st.warning("⚠️ Keine Brix-Daten (Modelle) gefunden.")
        return

    # Formular
    with st.form("brix_form"):
        # 1. Modell Wahl
        mod = st.selectbox("Modell", list(DB['brix'].keys()))
        
        c1, c2 = st.columns(2)
        lfm = c1.number_input("Länge (m)", 1.0, 100.0, 5.0)
        farbe_aufschlag = c2.selectbox("Farbe", ["Standard", "Sonderfarbe (+15%)"])

        st.markdown("---")
        st.markdown("**Zubehör & Montage**")
        
        # 2. Zubehör Wahl (Daten aus DB['brix_extras'])
        extras = DB.get('brix_extras', {'steher': {}, 'konsole': {}})
        
        # Fallback, falls Excel leer war
        steher_opts = list(extras.get('steher', {}).keys())
        konsole_opts = list(extras.get('konsole', {}).keys())
        
        c3, c4 = st.columns(2)
        steher_wahl = c3.selectbox("Steher Typ", steher_opts) if steher_opts else None
        konsole_wahl = c4.selectbox("Montage/Konsole", konsole_opts) if konsole_opts else None

        if st.form_submit_button("Berechnen", type="primary", use_container_width=True):
            # Preise holen
            dat_mod = DB['brix'][mod]
            p_mod = dat_mod['preis']
            if "Sonderfarbe" in farbe_aufschlag: p_mod *= 1.15
            
            p_steher = extras['steher'].get(steher_wahl, 0) if steher_wahl else 0
            p_konsole = extras['konsole'].get(konsole_wahl, 0) if konsole_wahl else 0
            
            # Mengen Berechnung
            # Faustformel: Alle 1,3m ein Steher, plus einer am Ende
            anz_steher = math.ceil(lfm / 1.3) + 1
            
            # Kosten
            kosten_gel = lfm * p_mod
            kosten_steher = anz_steher * p_steher
            kosten_konsole = anz_steher * p_konsole # Pro Steher eine Konsole
            
            total = kosten_gel + kosten_steher + kosten_konsole
            
            # Details für Warenkorb
            det = [
                f"Modell: {mod} ({dat_mod['kat']})",
                f"Farbe: {farbe_aufschlag}",
                f"Steher: {anz_steher}x {steher_wahl} (à {p_steher:.2f})",
                f"Konsole: {anz_steher}x {konsole_wahl} (à {p_konsole:.2f})"
            ]
            
            st.session_state.cart.append({
                "titel": f"Brix: {mod}",
                "menge_txt": f"{lfm:.2f}m",
                "preis": total,
                "details": det
            })
            st.success("Hinzugefügt!")
            st.rerun()
# ==========================================
# 4. MAIN & WARENKORB
# ==========================================
def main():
    with st.sidebar:
        if os.path.exists("logo_firma.png"): st.image("logo_firma.png", width=140)
        nav = st.radio("Menü", ["Individual", "Zäune", "Brix"])
        
        st.markdown("---")
        st.markdown("### 🛒 Warenkorb")
        if st.session_state.cart:
            s = sum(x['preis'] for x in st.session_state.cart)
            st.write(f"Summe: **{s:,.2f} €**")
            if st.button("PDF Angebot"):
                pdf = create_pdf(st.session_state.cart)
                st.download_button("Download PDF", pdf, "Angebot.pdf", "application/pdf")
            if st.button("Löschen"):
                st.session_state.cart = []
                st.rerun()
        else:
            st.caption("Leer")

    if nav == "Individual": render_individual()
    elif nav == "Zäune": render_zaun()
    elif nav == "Brix": render_brix()

if __name__ == "__main__":
    main()
