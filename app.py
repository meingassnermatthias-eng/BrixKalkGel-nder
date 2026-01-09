import streamlit as st
import math
import pandas as pd
from fpdf import FPDF
import datetime
import os
import json
import io

# ==========================================
# 0. KONFIGURATION & STYLES
# ==========================================
st.set_page_config(page_title="Meingassner V8", page_icon="🏗️", layout="wide")

# Custom CSS für Touch-Optimierung auf Tablets
st.markdown("""
    <style>
    .main-header { font-size: 2.2rem; font-weight: 700; color: #1E3A8A; margin-bottom: 15px; }
    .sub-header { font-size: 1.5rem; font-weight: 600; color: #444; margin-top: 20px; margin-bottom: 10px; border-bottom: 2px solid #ddd; padding-bottom: 5px; }
    .card { background-color: #f9f9f9; padding: 20px; border-radius: 10px; border: 1px solid #ddd; margin-bottom: 20px; }
    /* Größere Buttons für Touch */
    div.stButton > button { min-height: 50px; font-size: 18px !important; border-radius: 8px; }
    input { font-size: 16px !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 1. DATENBANK & STATE MANAGEMENT
# ==========================================

def get_full_default_data():
    """Liefert die Standard-Datenbankstruktur zurück."""
    return {
        # --- BEREICH 1: INDIVIDUAL (EXCEL EDITIERBAR) ---
        "individual": {
            "Überdachung": {
                "Carport Stahl Flachdach": {
                    "einheit": "Stk", "mat": 1500.00, "z_fert": 20.0, "z_mont": 15.0,
                    "optionen": {
                        "Sandwichpaneel Eindeckung": {"p": 45.00, "einheit": "pro_m2", "z_plus": 0.2},
                        "Dachrinne Titanzink": {"p": 35.00, "einheit": "pro_lfm", "z_plus": 0.3},
                        "Wandanschlussblech": {"p": 18.00, "einheit": "pro_lfm", "z_plus": 0.1},
                        "Punktfundamente": {"p": 150.00, "einheit": "Pauschal", "z_plus": 2.0}
                    }
                }
            },
            "Treppe": {
                "Stahltreppe Gerade": {
                    "einheit": "Stufe", "mat": 120.00, "z_fert": 2.5, "z_mont": 1.5,
                    "optionen": {
                        "Wangen aus U-Profil": {"p": 0.00, "einheit": "Pauschal", "z_plus": 0.0},
                        "Wangen aus Flachstahl": {"p": 40.00, "einheit": "Pauschal", "z_plus": 0.5},
                        "Stufen Gitterrost": {"p": 35.00, "einheit": "Pauschal", "z_plus": 0.0},
                        "Geländer einseitig": {"p": 140.00, "einheit": "pro_lfm", "z_plus": 2.0}
                    }
                }
            }
        },
        # --- BEREICH 2: GITTERZÄUNE (STATISCH) ---
        "matten": {
            "Leicht 6/5/6": {
                "1030": {'p_vz': 33.00, 'p_fb': 42.00}, 
                "1230": {'p_vz': 39.00, 'p_fb': 49.00},
                "1430": {'p_vz': 46.00, 'p_fb': 58.00}
            },
            "Schwer 8/6/8": {
                "1030": {'p_vz': 46.00, 'p_fb': 58.00},
                "1230": {'p_vz': 55.00, 'p_fb': 69.00}
            }
        },
        "steher": {
            "Rechteck 60x40": {'p_vz': 24.00, 'p_fb': 30.00},
            "Rechteck mit Fußplatte": {'p_vz': 38.00, 'p_fb': 45.00}
        },
        # --- BEREICH 3: BRIX (STATISCH) ---
        "brix": {
            "Decor 22 (Stäbe)": {"preis": 204.00, "kat": "L"},
            "Latten-Classic": {"preis": 206.00, "kat": "S"},
            "Glasal (Glas)": {"preis": 307.00, "kat": "S"}
        }
    }

def init_session():
    if 'db' not in st.session_state:
        # Lade DB oder Defaults
        if os.path.exists('katalog.json'):
            try:
                with open('katalog.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    defaults = get_full_default_data()
                    # Fehlende Keys ergänzen
                    for k in defaults:
                        if k not in data: data[k] = defaults[k]
                    st.session_state.db = data
            except:
                st.session_state.db = get_full_default_data()
        else:
            st.session_state.db = get_full_default_data()
            
    if 'cart' not in st.session_state: st.session_state.cart = []

init_session()
DB = st.session_state.db

# ==========================================
# 2. PDF GENERATOR
# ==========================================
def txt_clean(s):
    """Reinigt Text für FPDF (Latin-1) und ersetzt €."""
    if not isinstance(s, str): s = str(s)
    s = s.replace("€", "EUR").replace("–", "-")
    # Mapping für Umlaute, falls encoding='latin-1' strict ist
    return s.encode('latin-1', 'replace').decode('latin-1')

def create_pdf(cart_items):
    pdf = FPDF()
    pdf.add_page()
    
    # Logo
    if os.path.exists("logo_firma.png"): 
        pdf.image("logo_firma.png", 10, 8, 40)
        pdf.ln(25)
    else: 
        pdf.ln(10)
    
    # Header
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt_clean("ANGEBOT"), ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 10, txt_clean(f"Datum: {datetime.date.today().strftime('%d.%m.%Y')}"), ln=True, align='R')
    pdf.ln(10)
    
    # Tabelle Header
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(10, 8, "#", 1, 0, 'C', 1)
    pdf.cell(110, 8, "Position / Beschreibung", 1, 0, 'L', 1)
    pdf.cell(25, 8, "Menge", 1, 0, 'C', 1)
    pdf.cell(45, 8, "Gesamt (Netto)", 1, 1, 'R', 1)
    
    # Positionen
    total_net = 0
    pdf.set_font("Arial", '', 9)
    
    for idx, item in enumerate(cart_items):
        total_net += item['preis']
        
        # Hauptzeile
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(10, 8, str(idx+1), "LRT", 0, 'C')
        pdf.cell(110, 8, txt_clean(item['titel']), "LRT", 0, 'L')
        pdf.cell(25, 8, txt_clean(item['menge_txt']), "LRT", 0, 'C')
        pdf.cell(45, 8, txt_clean(f"{item['preis']:,.2f}"), "LRT", 1, 'R')
        
        # Details
        pdf.set_font("Arial", '', 8)
        for d in item.get('details', []):
            pdf.cell(10, 5, "", "LR", 0)
            pdf.cell(110, 5, txt_clean(f"  - {d}"), "LR", 0, 'L')
            pdf.cell(25, 5, "", "LR", 0)
            pdf.cell(45, 5, "", "LR", 1)
            
        # Abschlusslinie Item
        pdf.cell(190, 1, "", "T", 1)

    # Summenblock
    mwst = total_net * 0.20
    brutto = total_net + mwst
    
    pdf.ln(5)
    pdf.set_font("Arial", '', 10)
    pdf.cell(145, 7, "Netto Summe:", 0, 0, 'R')
    pdf.cell(45, 7, txt_clean(f"{total_net:,.2f} EUR"), 1, 1, 'R')
    
    pdf.cell(145, 7, "20% MwSt:", 0, 0, 'R')
    pdf.cell(45, 7, txt_clean(f"{mwst:,.2f} EUR"), 1, 1, 'R')
    
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(145, 8, "Gesamt Brutto:", 0, 0, 'R')
    pdf.cell(45, 8, txt_clean(f"{brutto:,.2f} EUR"), 1, 1, 'R')
    
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 3. MODUL A: INDIVIDUAL (CORE FEATURE)
# ==========================================
def render_individual():
    st.markdown("<div class='main-header'>🛠️ Metallbau Individual</div>", unsafe_allow_html=True)
    
    # 1. Parameter Sidebar für dieses Modul
    with st.expander("⚙️ Kalkulations-Parameter (Stundensatz/Faktor)", expanded=False):
        c_p1, c_p2 = st.columns(2)
        std_satz = c_p1.number_input("Stundensatz (€/h)", 40.0, 150.0, 65.0)
        mat_faktor = c_p2.number_input("Material-Aufschlag (Faktor)", 1.0, 3.0, 1.20)

    # 2. Produktauswahl
    raw_indiv = DB.get('individual', {})
    if not raw_indiv:
        st.error("Datenbank leer! Bitte im Admin-Bereich Daten importieren.")
        return

    col_cat, col_mod = st.columns(2)
    kats = sorted(list(raw_indiv.keys()))
    kat = col_cat.selectbox("Kategorie", kats)
    
    modelle = raw_indiv[kat]
    mod = col_mod.selectbox("Modell / Ausführung", list(modelle.keys()))
    
    data = modelle[mod]
    base_unit = data.get('einheit', 'Stk')
    
    # 3. Dimensionen
    st.markdown("<div class='sub-header'>1. Maße & Menge</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    menge = c1.number_input(f"Anzahl ({base_unit})", 0.0, 1000.0, 1.0, step=1.0)
    laenge = c2.number_input("Länge (m)", 0.0, 100.0, 0.0, step=0.1)
    breite = c3.number_input("Breite (m)", 0.0, 20.0, 0.0, step=0.1)
    
    flaeche = round(laenge * breite, 2)
    if flaeche > 0:
        st.caption(f"ℹ️ Berechnete Fläche: **{flaeche} m²** (für Quadratmeter-Optionen relevant)")

    # 4. Optionen
    st.markdown("<div class='sub-header'>2. Ausstattung & Optionen</div>", unsafe_allow_html=True)
    
    selected_options = []
    avail_opts = data.get('optionen', {})
    
    if not avail_opts:
        st.info("Keine Optionen für dieses Modell hinterlegt.")
    else:
        # Wir nutzen Container für bessere Touch-Bedienung
        for opt_name, opt_data in avail_opts.items():
            p = opt_data.get('p', 0.0)
            unit = opt_data.get('einheit', 'Pauschal')
            z_plus = opt_data.get('z_plus', 0.0) # Zeit pro Einheit
            
            # Preisberechnungsvorschau
            calc_factor = 0
            if unit == 'Pauschal':
                calc_factor = menge
                desc = "pro Stk/Pauschal"
            elif unit == 'pro_lfm':
                calc_factor = laenge * menge
                desc = "pro lfm"
            elif unit == 'pro_m2':
                calc_factor = flaeche * menge
                desc = "pro m²"
            
            surcharge = p * calc_factor
            
            # Checkbox mit dynamischem Text
            if st.checkbox(f"{opt_name} (+ {p:.2f}€ {desc})", key=f"opt_{mod}_{opt_name}"):
                # Validierung
                if calc_factor == 0 and unit != 'Pauschal':
                    st.warning(f"⚠️ '{opt_name}' benötigt {'Länge' if unit=='pro_lfm' else 'Fläche (LxB)'} > 0!")
                else:
                    selected_options.append({
                        "name": opt_name,
                        "price_sum": surcharge,
                        "time_sum": z_plus * calc_factor,
                        "detail_txt": f"{opt_name} ({calc_factor:.1f} {unit.replace('pro_', '')})"
                    })

    # 5. Berechnung
    base_mat = data.get('mat', 0.0) * menge
    base_time = (data.get('z_fert', 0.0) + data.get('z_mont', 0.0)) * menge
    
    opt_mat_sum = sum(x['price_sum'] for x in selected_options)
    opt_time_sum = sum(x['time_sum'] for x in selected_options)
    
    total_mat = (base_mat + opt_mat_sum) * mat_faktor
    total_time = (base_time + opt_time_sum) * std_satz
    
    endpreis = total_mat + total_time
    
    # 6. Ergebnis & Add
    st.markdown("---")
    res_col1, res_col2 = st.columns([2, 1])
    
    with res_col1:
        st.markdown(f"### Gesamtpreis: {endpreis:,.2f} €")
        st.caption("Inkl. Material, Fertigung, Montage & Gewinnaufschlag (Netto)")
        
    with res_col2:
        if st.button("🛒 In den Warenkorb", type="primary", use_container_width=True):
            details = [f"Basis: {mod} ({menge} {base_unit})"]
            if laenge > 0: details.append(f"Maße: {laenge}m x {breite}m")
            details.extend([x['detail_txt'] for x in selected_options])
            
            item = {
                "titel": f"{kat}: {mod}",
                "menge_txt": f"{menge} {base_unit}",
                "preis": endpreis,
                "details": details
            }
            st.session_state.cart.append(item)
            st.success("Hinzugefügt!")
            st.rerun()

# ==========================================
# 4. MODUL B: ZÄUNE (Optimiert)
# ==========================================
def render_zaun():
    st.markdown("<div class='main-header'>🚧 Gitterzäune</div>", unsafe_allow_html=True)
    
    with st.form("zaun_calc"):
        c1, c2 = st.columns(2)
        typ = c1.selectbox("Matten-Typ", list(DB['matten'].keys()))
        h_opts = sorted(list(DB['matten'][typ].keys()), key=lambda x: int(x))
        hoehe = c2.selectbox("Höhe (mm)", h_opts)
        
        c3, c4 = st.columns(2)
        laenge = c3.number_input("Länge des Zauns (m)", 1.0, 1000.0, 10.0)
        farbe = c4.selectbox("Oberfläche", ["Verzinkt", "Anthrazit", "Moosgrün"])
        
        steher = st.selectbox("Steher Typ", list(DB['steher'].keys()))
        faktor = st.number_input("Preisfaktor (Marge)", 0.5, 2.0, 1.0)
        
        if st.form_submit_button("Berechnen & Hinzufügen", type="primary", use_container_width=True):
            key_p = 'p_vz' if farbe == "Verzinkt" else 'p_fb'
            
            # Logik
            anz_matten = math.ceil(laenge / 2.5)
            p_matte = DB['matten'][typ][hoehe].get(key_p, 0)
            
            anz_steher = anz_matten + 1
            p_steher_m = DB['steher'][steher].get(key_p, 0)
            # Steher ist immer etwas länger als der Zaun hoch ist (Fundament)
            steher_laenge = (int(hoehe) / 1000) + 0.6 
            p_steher_stk = p_steher_m * steher_laenge
            
            mat_total = (anz_matten * p_matte) + (anz_steher * p_steher_stk)
            endpreis = mat_total * faktor
            
            details = [
                f"Typ: {typ} H{hoehe}, {farbe}",
                f"{anz_matten} Stk Matten (à 2,5m)",
                f"{anz_steher} Stk Steher ({steher})"
            ]
            
            st.session_state.cart.append({
                "titel": "Gitterzaun-Anlage",
                "menge_txt": f"{laenge}m",
                "preis": endpreis,
                "details": details
            })
            st.success("Wurde zum Angebot hinzugefügt.")
            st.rerun()

# ==========================================
# 5. MODUL C: BRIX (Optimiert)
# ==========================================
def render_brix():
    st.markdown("<div class='main-header'>🏢 Brix Balkone</div>", unsafe_allow_html=True)
    
    with st.form("brix_calc"):
        mod = st.selectbox("Modell", list(DB['brix'].keys()))
        
        c1, c2 = st.columns(2)
        l_ger = c1.number_input("Länge Gerade (m)", 0.0, 100.0, 5.0)
        l_schr = c2.number_input("Länge Schräg (m)", 0.0, 50.0, 0.0)
        
        c3, c4 = st.columns(2)
        farbe_sel = c3.selectbox("Farbe", ["Standard", "Sonderfarbe (+15%)"])
        montage = c4.selectbox("Montageart", ["Boden", "Wand"])
        
        if st.form_submit_button("Berechnen & Hinzufügen", type="primary", use_container_width=True):
            info = DB['brix'][mod]
            l_ges = l_ger + l_schr
            
            if l_ges <= 0:
                st.error("Länge muss > 0 sein.")
            else:
                preis_m = info['preis']
                if "Sonderfarbe" in farbe_sel: preis_m *= 1.15
                
                # Schätzung Steher (ca alle 1.3m)
                anz_steher = math.ceil(l_ges / 1.3) + 1
                preis_steher_pauschal = anz_steher * 120.00 
                
                total = (l_ges * preis_m) + preis_steher_pauschal
                
                details = [
                    f"Modell: {mod}",
                    f"Ausführung: {farbe_sel}",
                    f"Montage: {montage} (inkl. ca. {anz_steher} Steher)"
                ]
                
                st.session_state.cart.append({
                    "titel": f"Brix Geländer ({mod})",
                    "menge_txt": f"{l_ges:.2f}m",
                    "preis": total,
                    "details": details
                })
                st.success("Hinzugefügt!")
                st.rerun()

# ==========================================
# 6. WARENKORB (SIDEBAR & PDF)
# ==========================================
def render_cart_ui():
    st.markdown("### 📋 Aktuelles Angebot")
    
    if not st.session_state.cart:
        st.info("Warenkorb ist leer.")
        return

    total = 0
    for i, item in enumerate(st.session_state.cart):
        with st.expander(f"{item['titel']} ({item['preis']:,.2f} €)", expanded=False):
            for d in item['details']:
                st.text(f"- {d}")
            if st.button("🗑️ Entfernen", key=f"del_{i}"):
                st.session_state.cart.pop(i)
                st.rerun()
        total += item['preis']
    
    st.markdown("---")
    mwst = total * 0.2
    brutto = total * 1.2
    
    st.markdown(f"**Netto:** {total:,.2f} €")
    st.markdown(f"**Brutto:** {brutto:,.2f} €")
    
    # PDF Generieren
    if st.button("📄 PDF Erstellen", type="primary", use_container_width=True):
        pdf_bytes = create_pdf(st.session_state.cart)
        st.download_button(
            label="⬇️ Download PDF",
            data=pdf_bytes,
            file_name=f"Angebot_{datetime.date.today()}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
        
    if st.button("Alles löschen", use_container_width=True):
        st.session_state.cart = []
        st.rerun()

# ==========================================
# 7. ADMIN & EXCEL LOGIK
# ==========================================
def render_admin():
    st.markdown("<div class='main-header'>⚙️ Datenbank Verwaltung</div>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["💾 Backup (JSON)", "📊 Excel Import/Export (Individual)"])
    
    # --- JSON BACKUP ---
    with tab1:
        st.info("Sichert die **gesamte** Datenbank (Individual + Zäune + Brix).")
        json_str = json.dumps(st.session_state.db, indent=2, ensure_ascii=False)
        st.download_button("⬇️ Full Backup Download", json_str, "db_backup.json", "application/json")
        
        uploaded_json = st.file_uploader("Backup wiederherstellen (JSON)", type=['json'])
        if uploaded_json:
            try:
                data = json.load(uploaded_json)
                st.session_state.db = data
                st.success("Datenbank erfolgreich wiederhergestellt!")
            except Exception as e:
                st.error(f"Fehler beim Laden: {e}")

    # --- EXCEL LOGIK ---
    with tab2:
        st.info("Hier können die Produkte für 'Metallbau Individual' bearbeitet werden.")
        
        # 1. EXPORT
        if st.button("⬇️ Excel Template herunterladen"):
            # Flatten Logic
            rows_prod = []
            rows_opt = []
            
            indiv_data = st.session_state.db.get('individual', {})
            for cat, models in indiv_data.items():
                for mod_name, mod_data in models.items():
                    # Produkt Zeile
                    rows_prod.append({
                        "Kategorie": cat,
                        "Produkt": mod_name,
                        "Einheit": mod_data.get('einheit', 'Stk'),
                        "Materialpreis": mod_data.get('mat', 0),
                        "Zeit_Fertigung": mod_data.get('z_fert', 0),
                        "Zeit_Montage": mod_data.get('z_mont', 0)
                    })
                    # Optionen Zeilen
                    for opt_name, opt_data in mod_data.get('optionen', {}).items():
                        rows_opt.append({
                            "Produkt": mod_name,
                            "Option": opt_name,
                            "Preis": opt_data.get('p', 0),
                            "Einheit_Typ": opt_data.get('einheit', 'Pauschal'), # Pauschal, pro_lfm, pro_m2
                            "Zeit_Plus": opt_data.get('z_plus', 0)
                        })
            
            # Create Excel
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                pd.DataFrame(rows_prod).to_excel(writer, sheet_name='Produkte', index=False)
                pd.DataFrame(rows_opt).to_excel(writer, sheet_name='Optionen', index=False)
            
            st.download_button(
                label="Excel Datei speichern",
                data=buffer.getvalue(),
                file_name="individual_katalog.xlsx",
                mime="application/vnd.ms-excel"
            )

        st.markdown("---")
        
        # 2. IMPORT
        st.write("Excel Datei hochladen, um 'Individual' zu aktualisieren:")
        excel_file = st.file_uploader("Excel Datei (.xlsx)", type=['xlsx'])
        
        if excel_file and st.button("🚀 Import starten"):
            try:
                df_p = pd.read_excel(excel_file, 'Produkte')
                df_o = pd.read_excel(excel_file, 'Optionen')
                
                new_indiv = {}
                
                # Aufbau Produkte
                for _, row in df_p.iterrows():
                    cat = str(row['Kategorie']).strip()
                    prod = str(row['Produkt']).strip()
                    
                    if cat not in new_indiv: new_indiv[cat] = {}
                    
                    new_indiv[cat][prod] = {
                        "einheit": str(row['Einheit']),
                        "mat": float(row['Materialpreis']),
                        "z_fert": float(row['Zeit_Fertigung']),
                        "z_mont": float(row['Zeit_Montage']),
                        "optionen": {}
                    }
                
                # Aufbau Optionen
                count_opt = 0
                for _, row in df_o.iterrows():
                    p_ref = str(row['Produkt']).strip()
                    opt_name = str(row['Option']).strip()
                    
                    # Option nur einfügen, wenn Produkt existiert
                    found = False
                    for c in new_indiv:
                        if p_ref in new_indiv[c]:
                            new_indiv[c][p_ref]['optionen'][opt_name] = {
                                "p": float(row['Preis']),
                                "einheit": str(row['Einheit_Typ']),
                                "z_plus": float(row['Zeit_Plus'])
                            }
                            found = True
                            count_opt += 1
                            break
                
                # Update Session State (Nur Individual überschreiben)
                st.session_state.db['individual'] = new_indiv
                
                # Speichern auf Disk optional
                with open('katalog.json', 'w', encoding='utf-8') as f:
                    json.dump(st.session_state.db, f, indent=2, ensure_ascii=False)
                    
                st.success(f"Import erfolgreich! {len(df_p)} Produkte und {count_opt} Optionen geladen.")
                
            except Exception as e:
                st.error(f"Fehler beim Import: {e}")

# ==========================================
# 8. MAIN APP LOGIC
# ==========================================
def main():
    # Sidebar Navigation
    with st.sidebar:
        if os.path.exists("logo_firma.png"): 
            st.image("logo_firma.png", width=150)
        else:
            st.header("Meingassner")
            
        st.markdown("---")
        app_mode = st.radio("Modus", ["🏗️ Kalkulator", "⚙️ Datenbank Admin"])
        st.markdown("---")
        
        if app_mode == "🏗️ Kalkulator":
            module = st.radio("Bereich wählen", 
                              ["Metallbau Individual", "Gitterzäune", "Brix Balkone"])
            st.markdown("---")
            render_cart_ui()
    
    # Main Content
    if app_mode == "⚙️ Datenbank Admin":
        render_admin()
    else:
        if module == "Metallbau Individual":
            render_individual()
        elif module == "Gitterzäune":
            render_zaun()
        elif module == "Brix Balkone":
            render_brix()

if __name__ == "__main__":
    main()
