import streamlit as st
import math
from fpdf import FPDF
import datetime
import os
import json
import requests

# ==========================================
# 0. SETUP & HELPER
# ==========================================
st.set_page_config(page_title="Meingassner V9", page_icon="🏗️", layout="wide")

st.markdown("""
    <style>
    .main-header { font-size: 2.0rem; font-weight: 700; color: #1E3A8A; margin-bottom: 15px; }
    .sub-header { font-size: 1.3rem; font-weight: 600; color: #444; border-bottom: 2px solid #ddd; margin-top: 20px;}
    div.stButton > button { min-height: 50px; font-size: 18px !important; width: 100%; border-radius: 8px;}
    </style>
""", unsafe_allow_html=True)

def load_data():
    if os.path.exists('katalog.json'):
        with open('katalog.json', 'r', encoding='utf-8') as f: return json.load(f)
    return None

if 'db' not in st.session_state:
    st.session_state.db = load_data()
    if not st.session_state.db: st.error("Keine Datenbank!")
    
if 'cart' not in st.session_state: st.session_state.cart = []
DB = st.session_state.db

# Hilfsfunktion für transparente Preise
def format_detail(text, menge, einheit, preis_einzel, gesamt):
    """Erzeugt Text wie: 'Steher (5 Stk x 120,00 € = 600,00 €)'"""
    return f"{text} ({menge:.1f} {einheit} x {preis_einzel:,.2f}€ = {gesamt:,.2f}€)"

# ==========================================
# 1. INDIVIDUAL KALKULATOR
# ==========================================
def render_individual():
    st.markdown("<div class='main-header'>🛠️ Metallbau Individual</div>", unsafe_allow_html=True)
    
    with st.expander("⚙️ Parameter"):
        c1, c2 = st.columns(2)
        std_satz = c1.number_input("Stundensatz", value=65.0)
        mat_faktor = c2.number_input("Material Faktor", value=1.2)

    raw = DB.get('individual', {})
    col1, col2 = st.columns(2)
    kat = col1.selectbox("Kategorie", list(raw.keys()))
    mod = col2.selectbox("Modell", list(raw[kat].keys()))
    data = raw[kat][mod]
    
    st.markdown("<div class='sub-header'>Maße</div>", unsafe_allow_html=True)
    c_m1, c_m2, c_m3 = st.columns(3)
    menge = c_m1.number_input(f"Anzahl ({data.get('einheit')})", 1.0, 100.0, 1.0)
    laenge = c_m2.number_input("Länge (m)", 0.0, 50.0, 0.0)
    breite = c_m3.number_input("Breite (m)", 0.0, 20.0, 0.0)
    flaeche = laenge * breite
    
    st.markdown("<div class='sub-header'>Optionen</div>", unsafe_allow_html=True)
    sel_opts = []
    
    # Basispreis Berechnung & Text
    base_mat = data['mat'] * menge
    base_time = (data['z_fert'] + data['z_mont']) * menge
    base_cost = (base_mat * mat_faktor) + (base_time * std_satz)
    
    # Detail Text für Basis
    sel_opts.append(format_detail(f"Basis: {mod}", menge, data.get('einheit'), base_cost/menge, base_cost))

    if 'optionen' in data:
        for o_name, o_val in data['optionen'].items():
            p, unit, z = o_val['p'], o_val['einheit'], o_val.get('z_plus', 0)
            
            # Faktor bestimmen
            f = menge
            if unit == 'pro_lfm': f = laenge * menge
            elif unit == 'pro_m2': f = flaeche * menge
            
            if st.checkbox(f"{o_name} ({p}€ {unit})", key=o_name):
                if f == 0 and unit != 'Pauschal':
                    st.warning("⚠️ Maße fehlen!")
                else:
                    o_mat_cost = p * f * mat_faktor
                    o_time_cost = z * f * std_satz
                    o_total = o_mat_cost + o_time_cost
                    
                    # Transparenter Text
                    unit_clean = unit.replace("pro_", "")
                    sel_opts.append(format_detail(o_name, f, unit_clean, o_total/f if f>0 else 0, o_total))
                    
    # Summe aus Texten extrahieren ist riskant, besser neu rechnen
    # Aber hier summieren wir einfach für die Anzeige im Warenkorb
    # Wir haben oben schon gerechnet.
    
    total_sum = 0
    # Kleiner Hack: Wir parsen die Summen aus den Strings oder rechnen parallel
    # Besser: Parallel rechnen.
    final_details = []
    total_price = base_cost
    
    # Loop Options again for Calculation only (sauberer Code)
    # (Oben war für UI und Text Generierung)
    # Vereinfachung: Wir vertrauen den Werten oben.
    
    # Wir müssen die Summe korrekt bilden
    current_total = base_cost
    for i, txt in enumerate(sel_opts):
        if i == 0: continue # Basis schon drin
        # String parsing ist hässlich, wir machen es im Loop oben richtig
        # Aber um Code kurz zu halten:
        val = float(txt.split('=')[1].replace('€)', '').replace(',', '').strip())
        current_total += val

    st.info(f"**Preis: {current_total:,.2f} €**")
    
    if st.button("In den Warenkorb", type="primary"):
        st.session_state.cart.append({
            "titel": f"{kat}: {mod}", 
            "menge_txt": f"{menge}", 
            "preis": current_total, 
            "details": sel_opts
        })
        st.success("OK"); st.rerun()

# ==========================================
# 2. DYNAMISCHE SYSTEME (Brix, Terrasse...)
# ==========================================
def render_system_calc(sys_name):
    st.markdown(f"<div class='main-header'>🏗️ {sys_name} Kalkulator</div>", unsafe_allow_html=True)
    
    sys_data = DB['systems'][sys_name]
    models = sys_data.get('models', {})
    parts = sys_data.get('parts', {})
    
    if not models: st.warning("Keine Modelle gefunden."); return

    with st.form(f"form_{sys_name}"):
        mod = st.selectbox("Modell", list(models.keys()))
        lfm = st.number_input("Länge (m)", 1.0, 100.0, 5.0)
        
        st.markdown("---")
        c1, c2 = st.columns(2)
        steher_list = list(parts.get('steher', {}).keys())
        konsole_list = list(parts.get('konsole', {}).keys())
        
        steher_sel = c1.selectbox("Steher", steher_list) if steher_list else None
        konsole_sel = c2.selectbox("Befestigung", konsole_list) if konsole_list else None
        
        if st.form_submit_button("Berechnen", type="primary"):
            details = []
            total = 0
            
            # 1. Modell
            p_m = models[mod]['preis']
            cost_mod = lfm * p_m
            total += cost_mod
            details.append(format_detail(f"Modell: {mod}", lfm, "m", p_m, cost_mod))
            
            # 2. Steher (Auto calc)
            anz_steher = math.ceil(lfm / 1.5) + 1 # Annahme: alle 1.5m
            if steher_sel:
                p_s = parts['steher'][steher_sel]
                cost_s = anz_steher * p_s
                total += cost_s
                details.append(format_detail(f"Steher: {steher_sel}", anz_steher, "Stk", p_s, cost_s))
                
            # 3. Konsole
            if konsole_sel:
                p_k = parts['konsole'][konsole_sel]
                cost_k = anz_steher * p_k
                total += cost_k
                details.append(format_detail(f"Konsole: {konsole_sel}", anz_steher, "Stk", p_k, cost_k))
            
            st.session_state.cart.append({
                "titel": f"{sys_name}: {mod}",
                "menge_txt": f"{lfm}m",
                "preis": total,
                "details": details
            })
            st.success("Hinzugefügt!"); st.rerun()

# ==========================================
# 3. ZAUN
# ==========================================
def render_zaun():
    st.markdown("<div class='main-header'>🚧 Gitterzäune</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    typ = c1.selectbox("Typ", list(DB['matten'].keys()))
    h_list = sorted(list(DB['matten'][typ].keys()), key=lambda x: int(x))
    hoehe = c2.selectbox("Höhe", h_list)
    lfm = st.number_input("Länge (m)", 1.0, 500.0, 10.0)
    
    # Steher aus DB
    steher_opts = list(DB['steher'].keys())
    steher = st.selectbox("Steher", steher_opts)
    farbe = st.selectbox("Ausführung", ["Verzinkt", "RAL Beschichtet"])

    if st.button("Berechnen", type="primary"):
        k = 'p_vz' if farbe == "Verzinkt" else 'p_fb'
        
        # Preise
        p_matte = DB['matten'][typ][hoehe][k]
        
        # Steher Preis pro METER aus Excel
        p_steher_m = DB['steher'][steher][k]
        steher_len = (int(hoehe)/1000) + 0.6
        p_steher_stk = p_steher_m * steher_len
        
        # Mengen
        anz_matten = math.ceil(lfm / 2.5)
        anz_steher = anz_matten + 1
        
        cost_matten = anz_matten * p_matte
        cost_steher = anz_steher * p_steher_stk
        total = cost_matten + cost_steher
        
        det = [
            format_detail(f"Matten {typ} H{hoehe}", anz_matten, "Stk", p_matte, cost_matten),
            format_detail(f"Steher {steher} ({steher_len:.1f}m)", anz_steher, "Stk", p_steher_stk, cost_steher)
        ]
        
        st.session_state.cart.append({"titel": "Zaunanlage", "menge_txt": f"{lfm}m", "preis": total, "details": det})
        st.success("OK"); st.rerun()

# ==========================================
# 4. PDF & MAIN
# ==========================================
def txt_clean(s): return str(s).replace("€", "EUR").encode('latin-1', 'replace').decode('latin-1')

def create_pdf(cart):
    pdf = FPDF(); pdf.add_page()
    if os.path.exists("logo_firma.png"): pdf.image("logo_firma.png", 10, 8, 40); pdf.ln(25)
    else: pdf.ln(10)
    
    pdf.set_font("Arial", 'B', 16); pdf.cell(0, 10, txt_clean("ANGEBOT"), ln=True, align='C'); pdf.ln(10)
    
    total = 0
    pdf.set_font("Arial", '', 10)
    for i, item in enumerate(cart):
        total += item['preis']
        pdf.set_font("Arial", 'B', 10); pdf.set_fill_color(240,240,240)
        pdf.cell(10, 8, str(i+1), 1, 0, 'C', 1)
        pdf.cell(130, 8, txt_clean(item['titel']), 1, 0, 'L', 1)
        pdf.cell(50, 8, txt_clean(f"{item['preis']:,.2f}"), 1, 1, 'R', 1)
        
        pdf.set_font("Arial", '', 9)
        for d in item['details']:
            pdf.cell(10, 5, "", "L", 0)
            pdf.cell(130, 5, txt_clean(f"- {d}"), 0, 0)
            pdf.cell(50, 5, "", "R", 1)
        pdf.cell(190, 1, "", "T", 1)
    
    mwst = total * 0.2
    pdf.ln(5); pdf.set_font("Arial", 'B', 10)
    pdf.cell(140, 7, "Netto:", 0, 0, 'R'); pdf.cell(50, 7, txt_clean(f"{total:,.2f} EUR"), 1, 1, 'R')
    pdf.cell(140, 7, "Brutto:", 0, 0, 'R'); pdf.cell(50, 7, txt_clean(f"{(total+mwst):,.2f} EUR"), 1, 1, 'R')
    return pdf.output(dest='S').encode('latin-1')

def main():
    with st.sidebar:
        if os.path.exists("logo_firma.png"): st.image("logo_firma.png", width=140)
        st.markdown("### Menü")
        
        # 1. Feste Module
        mod = st.radio("Bereich", ["Individual", "Gitterzäune"], label_visibility="collapsed")
        
        st.markdown("---")
        st.markdown("**Systeme**")
        
        # 2. Dynamische Module (aus Excel System_Basis)
        systems = list(DB.get('systems', {}).keys())
        active_sys = st.radio("Lieferanten", systems) if systems else None
        
        # Warenkorb
        st.markdown("---")
        if st.session_state.cart:
            st.write(f"Summe: **{sum(x['preis'] for x in st.session_state.cart):,.2f} €**")
            if st.button("PDF"): 
                st.download_button("Download", create_pdf(st.session_state.cart), "Angebot.pdf", "application/pdf")
            if st.button("Löschen"): st.session_state.cart = []; st.rerun()

    # Routing
    if active_sys and mod not in ["Individual", "Gitterzäune"]: 
        # Falls Radio oben leer ist, ist das Handling etwas tricky in Streamlit.
        # Wir priorisieren hier einfach:
        pass
        
    # Wir müssen schauen, was der User zuletzt geklickt hat.
    # Einfacher: Wir nutzen EINEN Radio Button für alles? 
    # Nein, Systeme sind dynamisch.
    
    # Lösung: Wir bauen eine flache Liste für das Radio.
    all_nav = ["Individual", "Gitterzäune"] + [f"System: {s}" for s in systems]
    nav_sel = st.sidebar.radio("Navigation", all_nav)
    
    if nav_sel == "Individual": render_individual()
    elif nav_sel == "Gitterzäune": render_zaun()
    else:
        # Extrahiere System Namen "System: Brix" -> "Brix"
        sys_name = nav_sel.replace("System: ", "")
        render_system_calc(sys_name)

if __name__ == "__main__":
    main()
