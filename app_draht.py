import streamlit as st
import pandas as pd
from fpdf import FPDF
import base64
import os
import tempfile
import math
from datetime import datetime

# ==========================================
# 1. KONFIGURATION & SETUP
# ==========================================
LOGO_DATEI = "Meingassner Metalltechnik 2023.png"
EXCEL_DATEI = "katalog.xlsx"
MWST_SATZ = 0.20  # 20% MwSt

st.set_page_config(page_title="Meingassner Kalkulator", layout="wide", page_icon=LOGO_DATEI)

# ==========================================
# 2. SICHERHEIT (PASSWORT-CHECK)
# ==========================================
def check_password():
    if "password" not in st.secrets:
        # Fallback für lokale Tests ohne Secrets
        return True 

    def password_entered():
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("🔒 Bitte Passwort eingeben:", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("🔒 Bitte Passwort eingeben:", type="password", on_change=password_entered, key="password")
        st.error("⛔ Passwort falsch.")
        return False
    else:
        return True

if not check_password():
    st.stop()

# ==========================================
# 3. HELFER-FUNKTIONEN
# ==========================================
def safe_float(value):
    if pd.isna(value): return 0.0
    s_val = str(value).replace(',', '.').strip()
    try: return float(s_val)
    except: return 0.0

def clean_df_columns(df):
    if df is None: return pd.DataFrame()
    if not df.empty: 
        df.columns = df.columns.str.strip()
        rename_map = {'Formel / Info': 'Formel', 'Formel/Info': 'Formel', 'Info': 'Formel'}
        df.rename(columns=rename_map, inplace=True)
        if 'Variable' in df.columns:
            df = df.dropna(subset=['Variable'])
    return df

def lade_startseite():
    if not os.path.exists(EXCEL_DATEI):
        st.error(f"❌ Datei '{EXCEL_DATEI}' nicht gefunden!")
        return pd.DataFrame()
    try: return clean_df_columns(pd.read_excel(EXCEL_DATEI, sheet_name="Startseite"))
    except: return pd.DataFrame()

def lade_blatt(blatt_name):
    if not os.path.exists(EXCEL_DATEI): return pd.DataFrame()
    try: 
        sauberer_name = str(blatt_name).strip()
        df = pd.read_excel(EXCEL_DATEI, sheet_name=sauberer_name)
        return clean_df_columns(df)
    except ValueError:
        st.error(f"❌ FEHLER: Blatt '{blatt_name}' fehlt in Excel!")
        return pd.DataFrame()
    except Exception: return pd.DataFrame()

def lade_alle_blattnamen():
    if not os.path.exists(EXCEL_DATEI): return []
    return pd.ExcelFile(EXCEL_DATEI).sheet_names

def speichere_excel(df, blatt_name):
    try:
        with pd.ExcelWriter(EXCEL_DATEI, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            df.to_excel(writer, sheet_name=blatt_name, index=False)
        return True
    except: return False

def setup_app_icon(image_file):
    if os.path.exists(image_file):
        try:
            with open(image_file, "rb") as f:
                data = f.read()
            encoded = base64.b64encode(data).decode()
            st.sidebar.image(image_file, width=200)
        except: pass

setup_app_icon(LOGO_DATEI)

# ==========================================
# 4. SESSION STATE
# ==========================================
def init_state():
    if 'positionen' not in st.session_state: st.session_state['positionen'] = []
    if 'kunden_daten' not in st.session_state: 
        st.session_state['kunden_daten'] = {"Name": "", "Strasse": "", "Ort": "", "Tel": "", "Email": "", "Notiz": ""}
    if 'fertiges_pdf' not in st.session_state: st.session_state['fertiges_pdf'] = None
    if 'fertiges_intern_pdf' not in st.session_state: st.session_state['fertiges_intern_pdf'] = None

    default_zk = {
        "kran": 0.0, "montage_mann": 2, "montage_std": 0.0, "montage_satz": 65.0,
        "zuschlag_prozent": 0.0, "zuschlag_label": "Normal",
        "provision_prozent": 0.0, # Versteckter Aufschlag
        "rabatt_prozent": 0.0,    # Sichtbarer Rabatt
        "skonto_prozent": 0.0     # Skonto Info
    }
    if 'zusatzkosten' not in st.session_state:
        st.session_state['zusatzkosten'] = default_zk.copy()
    else:
        # Neue Keys hinzufügen falls Session alt ist
        for k, v in default_zk.items():
            if k not in st.session_state['zusatzkosten']:
                st.session_state['zusatzkosten'][k] = v

init_state()

# ==========================================
# 5. PDF ENGINES (MIT PROVISION & RABATT)
# ==========================================
def clean_text(text):
    if text is None: return ""
    text = str(text).replace("€", "EUR").replace("–", "-").replace("„", '"').replace("“", '"')
    try: return text.encode('latin-1', 'replace').decode('latin-1')
    except: return text

class PDF(FPDF):
    def header(self):
        if os.path.exists(LOGO_DATEI): 
            try: self.image(LOGO_DATEI, 10, 8, 60)
            except: pass
        self.set_font('Arial', 'B', 16)
        heute = datetime.now().strftime("%d.%m.%Y")
        self.cell(0, 18, clean_text(f"Kostenschätzung vom {heute}"), 0, 1, 'R')
        self.ln(10)
    def footer(self):
        self.set_y(-15); self.set_font('Arial', 'I', 8); self.cell(0, 10, f'Seite {self.page_no()}', 0, 0, 'C')

def create_pdf(positionen_liste, kunden_dict, fotos, montage_summe, kran_summe, zeige_details, zuschlag_prozent, zuschlag_label, zuschlag_transparent, provision_prozent, rabatt_prozent, skonto_prozent):
    pdf = PDF(); pdf.alias_nb_pages(); pdf.add_page()
    
    # KUNDENINFO
    pdf.ln(10); pdf.set_font("Arial", 'B', 12); pdf.cell(0, 6, "Kundeninformation:", ln=True); pdf.set_font("Arial", size=10)
    k_text = f"{kunden_dict.get('Name','')}\n{kunden_dict.get('Strasse','')}\n{kunden_dict.get('Ort','')}\n\nTel: {kunden_dict.get('Tel','')}\nEmail: {kunden_dict.get('Email','')}"
    pdf.multi_cell(0, 5, clean_text(k_text))
    if kunden_dict.get("Notiz"):
        pdf.ln(5); pdf.set_font("Arial", 'B', 10); pdf.cell(0, 5, "Bemerkung:", ln=True); pdf.set_font("Arial", size=10)
        pdf.multi_cell(0, 5, clean_text(kunden_dict["Notiz"]))
    pdf.ln(10)
    
    # TABELLE SETUP
    pdf.set_font("Arial", 'B', 10); pdf.set_fill_color(240, 240, 240)
    w_desc, w_menge, w_ep, w_gesamt = 100, 25, 30, 35
    pdf.cell(w_desc, 8, "Beschreibung", 1, 0, 'L', True); pdf.cell(w_menge, 8, "Menge", 1, 0, 'C', True)
    pdf.cell(w_ep, 8, "EP (EUR)", 1, 0, 'R', True); pdf.cell(w_gesamt, 8, "Gesamt", 1, 1, 'R', True)
    pdf.set_font("Arial", size=10)
    
    # FAKTOR FÜR VERSTECKTE PROVISION
    # Wenn Provision 10%, dann Faktor 1.10. Alle Einzelpreise werden damit multipliziert.
    prov_faktor = 1 + (provision_prozent / 100.0)

    subtotal_list = 0
    
    # POSITIONEN
    for pos in positionen_liste:
        if not pos: continue
        
        # Preise für Kunden aufblasen (versteckte Provision)
        ep_kunde = pos.get('Einzelpreis', 0) * prov_faktor
        gp_kunde = pos.get('Preis', 0) * prov_faktor
        
        raw_desc = str(pos.get('Beschreibung', '')); parts = raw_desc.split("|")
        main_title = parts[0].strip()
        details = ("\n" + parts[1].replace(",", "\n -").strip()) if len(parts) > 1 else ""
        
        if pos.get('RefMenge', 0) > 0:
            einheit_preis_k = ep_kunde / float(pos['RefMenge'])
            details += f"\n   (entspricht {einheit_preis_k:.2f} EUR / {pos.get('RefEinheit', 'Stk')})"

        x_start, y_start = pdf.get_x(), pdf.get_y()
        pdf.multi_cell(w_desc, 5, clean_text(f"{main_title}{details}"), border=1, align='L')
        y_end = pdf.get_y(); row_height = y_end - y_start
        pdf.set_xy(x_start + w_desc, y_start)
        pdf.cell(w_menge, row_height, clean_text(str(pos.get('Menge', 0))), 1, 0, 'C')
        pdf.cell(w_ep, row_height, f"{ep_kunde:.2f}", 1, 0, 'R')
        pdf.cell(w_gesamt, row_height, f"{gp_kunde:.2f}", 1, 1, 'R')
        subtotal_list += gp_kunde

    # ZUSATZKOSTEN (auch mit Provision versehen!)
    zuschlag_wert = 0
    # Erschwernis
    basis_fuer_zuschlag = subtotal_list + (montage_summe * prov_faktor) + (kran_summe * prov_faktor)
    if zuschlag_prozent > 0:
        zuschlag_wert = basis_fuer_zuschlag * (zuschlag_prozent / 100.0)

    versteckter_zuschlag = 0
    if zuschlag_prozent > 0 and not zuschlag_transparent:
        versteckter_zuschlag = zuschlag_wert
        zuschlag_wert = 0

    # Montage
    montage_final = (montage_summe * prov_faktor) + versteckter_zuschlag
    if montage_final > 0:
        txt = "Montagearbeiten" if zeige_details else "Montage & Regie (Pauschal)"
        pdf.cell(w_desc, 8, clean_text(txt), 1, 0, 'L'); pdf.cell(w_menge, 8, "1", 1, 0, 'C')
        pdf.cell(w_ep, 8, f"{montage_final:.2f}", 1, 0, 'R'); pdf.cell(w_gesamt, 8, f"{montage_final:.2f}", 1, 1, 'R')
        subtotal_list += montage_final

    # Kran
    kran_final = kran_summe * prov_faktor
    if kran_final > 0:
        pdf.cell(w_desc, 8, clean_text("Kranarbeiten"), 1, 0, 'L'); pdf.cell(w_menge, 8, "1", 1, 0, 'C')
        pdf.cell(w_ep, 8, f"{kran_final:.2f}", 1, 0, 'R'); pdf.cell(w_gesamt, 8, f"{kran_final:.2f}", 1, 1, 'R')
        subtotal_list += kran_final

    # Erschwernis sichtbar
    if zuschlag_wert > 0:
        pdf.cell(w_desc + w_menge + w_ep, 8, "Zwischensumme:", 0, 0, 'R'); pdf.cell(w_gesamt, 8, f"{subtotal_list:.2f}", 1, 1, 'R')
        label = f"Erschwernis ({zuschlag_label} {zuschlag_prozent}%)"
        pdf.cell(w_desc + w_menge + w_ep, 8, clean_text(label), 0, 0, 'R'); pdf.cell(w_gesamt, 8, f"{zuschlag_wert:.2f}", 1, 1, 'R')
        subtotal_list += zuschlag_wert

    # --- RABATT BLOCK ---
    rabatt_wert = 0
    if rabatt_prozent > 0:
        rabatt_wert = subtotal_list * (rabatt_prozent / 100.0)
        pdf.ln(2)
        pdf.set_font("Arial", '', 10)
        pdf.cell(w_desc + w_menge + w_ep, 6, "Zwischensumme Listenpreis:", 0, 0, 'R')
        pdf.cell(w_gesamt, 6, f"{subtotal_list:.2f}", 0, 1, 'R')
        
        pdf.set_font("Arial", 'B', 10)
        pdf.set_text_color(200, 0, 0) # Rot für Rabatt
        pdf.cell(w_desc + w_menge + w_ep, 6, f"Abzug Rabatt ({rabatt_prozent:.1f}%):", 0, 0, 'R')
        pdf.cell(w_gesamt, 6, f"- {rabatt_wert:.2f}", 0, 1, 'R')
        pdf.set_text_color(0, 0, 0) # Schwarz zurück
        
        subtotal_list -= rabatt_wert

    # STEUER & ENDSUMME
    netto = subtotal_list
    mwst = netto * MWST_SATZ
    brutto = netto + mwst

    pdf.ln(2); pdf.set_font("Arial", 'B', 12)
    pdf.cell(w_desc + w_menge + w_ep, 0, "", 0, 0, 'R')
    pdf.line(pdf.get_x() + w_desc + w_menge + w_ep, pdf.get_y(), pdf.get_x() + w_desc + w_menge + w_ep + w_gesamt, pdf.get_y())
    pdf.ln(2)
    
    pdf.set_font("Arial", '', 11)
    pdf.cell(w_desc + w_menge + w_ep, 6, "Summe Netto:", 0, 0, 'R'); pdf.cell(w_gesamt, 6, f"{netto:.2f} EUR", 0, 1, 'R')
    pdf.cell(w_desc + w_menge + w_ep, 6, f"zzgl. {int(MWST_SATZ*100)}% MwSt:", 0, 0, 'R'); pdf.cell(w_gesamt, 6, f"{mwst:.2f} EUR", 0, 1, 'R')
    pdf.set_font("Arial", 'B', 14); pdf.cell(w_desc + w_menge + w_ep, 10, "GESAMTSUMME:", 0, 0, 'R'); pdf.cell(w_gesamt, 10, f"{brutto:.2f} EUR", 1, 1, 'R')

    # SKONTO TEXT
    if skonto_prozent > 0:
        skonto_wert = brutto * (skonto_prozent / 100.0)
        zahlbar_skonto = brutto - skonto_wert
        pdf.ln(5)
        pdf.set_font("Arial", 'I', 10)
        text_skonto = f"Zahlbar sofort rein Netto. Bei Zahlung innerhalb von 10 Tagen gewähren wir {skonto_prozent}% Skonto ({skonto_wert:.2f} EUR). Zahlbetrag dann: {zahlbar_skonto:.2f} EUR."
        pdf.multi_cell(0, 5, clean_text(text_skonto), 0, 'R')

    if fotos:
        pdf.add_page()
        for f in fotos:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as t: t.write(f.getvalue()); tmp=t.name
            pdf.image(tmp, w=160); pdf.ln(10); os.unlink(tmp)
    return pdf.output(dest='S').encode('latin-1')

def create_internal_pdf(positionen_liste, kunden_dict, zusatzkosten):
    pdf = PDF(); pdf.alias_nb_pages(); pdf.add_page()
    pdf.set_font("Arial", 'B', 11); pdf.cell(0, 8, f"INTERN: {clean_text(kunden_dict.get('Name',''))}", 0, 1)
    
    # INTERNE KALKULATION ZEIGEN
    prov = zusatzkosten.get('provision_prozent', 0)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 6, f"Versteckte Provision eingerechnet: {prov}%", 0, 1)
    
    pdf.ln(5); pdf.set_fill_color(220, 220, 220); pdf.set_font("Arial", 'B', 10)
    pdf.cell(10, 8, "#", 1, 0, 'C', True); pdf.cell(120, 8, "Material & AV (Echte Kosten)", 1, 0, 'L', True); pdf.cell(60, 8, "Kalk. Wert (Ohne Prov)", 1, 1, 'R', True)
    
    total_intern = 0
    for i, pos in enumerate(positionen_liste):
        titel = clean_text(pos.get('Beschreibung','').split('|')[0])
        details = ""
        if pos.get('MaterialDetails'):
            for d in pos['MaterialDetails']: details += f"\n  -> {d}"
        
        # Intern zeigen wir den "echten" Preis ohne Provision
        preis_intern = pos.get('Preis', 0)
        total_intern += preis_intern
        
        pdf.set_font("Arial", '', 10)
        x_start, y_start = pdf.get_x(), pdf.get_y()
        pdf.set_x(20)
        pdf.multi_cell(120, 5, f"{titel}{clean_text(details)}", border=0)
        y_end = pdf.get_y(); h = y_end - y_start
        pdf.set_xy(x_start, y_start)
        pdf.cell(10, h, str(i+1), 1, 0, 'C')
        pdf.set_xy(20+120, y_start)
        pdf.cell(60, h, f"{preis_intern:.2f}", 1, 1, 'R')
        pdf.set_y(y_end)
        
    pdf.ln(5); 
    pdf.cell(0, 10, clean_text(f"Zusatz: Montage {zusatzkosten.get('montage_std')}h / {zusatzkosten.get('montage_mann')} Mann"), 1, 1)
    
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 6. HAUPTPROGRAMM
# ==========================================
st.sidebar.header("Navigation")
if st.sidebar.button("⚠️ Speicher leeren (Reset)"):
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()

index_df = lade_startseite()
katalog_items = []
if index_df is not None and not index_df.empty and 'Kategorie' in index_df.columns:
    kategorien = index_df['Kategorie'].unique()
    wahl_kategorie = st.sidebar.selectbox("Filter Kategorie:", kategorien)
    katalog_items = index_df[index_df['Kategorie'] == wahl_kategorie]['System'].tolist()

menue_punkt = st.sidebar.radio("Gehe zu:", ["📂 Konfigurator / Katalog", "🛒 Warenkorb / Abschluss", "🔐 Admin"])
st.sidebar.markdown("---")

# --- A: KONFIGURATOR ---
if menue_punkt == "📂 Konfigurator / Katalog":
    st.title("Artikel Konfigurator")
    if katalog_items:
        auswahl_system = st.selectbox("System wählen:", katalog_items)
        row = pd.DataFrame()
        if index_df is not None and not index_df.empty:
            row = index_df[(index_df['System'] == auswahl_system)]
            if 'Kategorie' in index_df.columns and 'wahl_kategorie' in locals():
                row = row[row['Kategorie'] == wahl_kategorie]
            
        if not row.empty:
            blatt = row.iloc[0]['Blattname']
            df_config = lade_blatt(blatt)
            if df_config.empty: st.warning("Leer.")
            else:
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.subheader(f"Konfiguration: {auswahl_system}")
                    try:
                        vars_calc = {}; desc_parts = []
                        for index, zeile in df_config.iterrows():
                            if pd.isna(zeile.get('Typ')): continue 
                            typ = str(zeile.get('Typ', '')).strip().lower()
                            lbl = str(zeile.get('Bezeichnung', ''))
                            var = str(zeile.get('Variable', '')).strip()
                            
                            if typ == 'zahl':
                                val = st.number_input(lbl, value=safe_float(str(zeile.get('Optionen',''))), step=1.0, key=f"{blatt}_{index}")
                                vars_calc[var] = val
                                if val!=0: desc_parts.append(f"{lbl}: {val}")
                            elif typ == 'auswahl':
                                raw_opts = str(zeile.get('Optionen', '')).split(',')
                                opts = {}; opt_names = []
                                for o in raw_opts:
                                    if ':' in o: n,v=o.split(':'); opts[n.strip()]=safe_float(v); opt_names.append(n.strip())
                                    else: opts[o.strip()]=0; opt_names.append(o.strip())
                                if opt_names:
                                    sel = st.selectbox(lbl, opt_names, key=f"{blatt}_{index}")
                                    vars_calc[var] = opts.get(sel,0); desc_parts.append(f"{lbl}: {sel}")
                            elif typ == 'mehrfach':
                                raw_opts = str(zeile.get('Optionen', '')).split(',')
                                opts = {}; opt_names = []
                                for o in raw_opts:
                                    if ':' in o: n,v=o.split(':'); opts[n.strip()]=safe_float(v); opt_names.append(n.strip())
                                    else: opts[o.strip()]=0; opt_names.append(o.strip())
                                sel = st.multiselect(lbl, opt_names, key=f"{blatt}_{index}")
                                vars_calc[var] = sum(opts[s] for s in sel)
                                if sel: desc_parts.append(f"{lbl}: {','.join(sel)}")
                            elif typ == 'berechnung':
                                try:
                                    env={"__builtins__":None,"math":math,"round":round,"int":int,"float":float,"max":max,"min":min}; env.update(vars_calc)
                                    vars_calc[var] = eval(str(zeile.get('Formel','')), env)
                                except: vars_calc[var]=0
                            elif typ == 'preis':
                                try:
                                    env={"__builtins__":None,"math":math,"round":round,"int":int,"float":float,"max":max,"min":min}; env.update(vars_calc)
                                    preis = eval(str(zeile.get('Formel','')), env)
                                    st.subheader(f"Preis: {preis:.2f} €")
                                    with st.expander("Debug"): st.json(vars_calc)
                                    if st.button("In den Warenkorb", type="primary"):
                                        mat=[]
                                        # MATERIAL LOGIK
                                        l = vars_calc.get('L',0)
                                        if 'P_Glas' in vars_calc and 'N_Felder' in vars_calc: # Glasgel
                                            h=vars_calc.get('H',0.85); calc_l=max(l,1.0)
                                            mat.append(f"Glasfläche: {(calc_l*h):.2f} m²"); mat.append(f"Handlauf: {calc_l:.2f}m")
                                            n_k=int(vars_calc['N_Felder'])*4
                                            if 'Ecken' in vars_calc: n_k+=int(vars_calc['Ecken'])*4
                                            mat.append(f"Klemmen: {n_k} Stk")
                                        elif 'N_Spar' in vars_calc: # Terrasse
                                            mat.append(f"Dachfläche: {(l*vars_calc.get('B',0)):.2f} m²")
                                            mat.append(f"Säulen: {int(vars_calc.get('N_Col',0))} | Sparren: {int(vars_calc.get('N_Spar',0))}")
                                            lfm=(int(vars_calc.get('N_Col',0))*vars_calc.get('H',2.5)) + (int(vars_calc.get('N_Spar',0))*vars_calc.get('B',0)) + l
                                            mat.append(f"Stahlfläche (Beschichtung): {(lfm*0.4):.2f} m²")
                                        elif 'N_Rows' in vars_calc: # Horizontal
                                            mat.append(f"Füllung: {int(vars_calc['N_Rows'])} Reihen")
                                            mat.append(f"Laufmeter Füllung: {(l*int(vars_calc['N_Rows'])):.2f} m")
                                        elif l>0 and 'Treppe' not in str(auswahl_system): # Standard
                                            abst=1.2 if 'Edelstahl' in auswahl_system else 1.3
                                            stps=math.ceil(l/abst)+1; mat.append(f"Steher: {stps} Stk")
                                        
                                        st.session_state['positionen'].append({
                                            "Beschreibung": f"{auswahl_system} | " + ",".join(desc_parts),
                                            "Menge": 1.0, "Einzelpreis": preis, "Preis": preis,
                                            "RefMenge": max(l,1.0), "RefEinheit": "m", "MaterialDetails": mat
                                        })
                                        st.success("OK")
                                except Exception as e: st.error(f"Fehler: {e}")
                    except Exception as e: st.error(f"Blatt Fehler: {e}")
                
                with c2:
                    st.info("Warenkorb")
                    if st.session_state['positionen']:
                        st.write(f"{len(st.session_state['positionen'])} Pos. | {sum(p['Preis'] for p in st.session_state['positionen']):.2f} €")

# --- B: WARENKORB ---
elif menue_punkt == "🛒 Warenkorb / Abschluss":
    st.title("🛒 Warenkorb")
    c1, c2 = st.columns([1.2, 0.8])
    with c1:
        st.subheader("Positionen")
        if st.session_state['positionen']:
            to_del = []
            for i, p in enumerate(st.session_state['positionen']):
                cc1, cc2, cc3, cc4 = st.columns([3, 1, 1, 0.5])
                cc1.markdown(f"**{p['Beschreibung'].split('|')[0]}**"); cc1.caption(p['Beschreibung'])
                p['Menge'] = cc2.number_input("Anz", value=float(p['Menge']), step=1.0, key=f"q_{i}")
                p['Preis'] = p['Menge'] * p['Einzelpreis']
                cc3.write(f"{p['Preis']:.2f} €")
                if cc4.button("X", key=f"d_{i}"): to_del.append(i)
            for i in sorted(to_del, reverse=True): del st.session_state['positionen'][i]
            if to_del: st.rerun()
            
            total = sum(p['Preis'] for p in st.session_state['positionen'])
            st.markdown("---")
            st.subheader(f"Summe Artikel: {total:.2f} €")
        else: st.info("Leer")

    with c2:
        with st.expander("🏗️ Montage & Zusatzkosten", expanded=True):
            zk = st.session_state['zusatzkosten']
            c_m1, c_m2 = st.columns(2)
            zk['montage_mann'] = c_m1.number_input("Mann", value=int(zk['montage_mann']), step=1)
            zk['montage_std'] = c_m2.number_input("Std", value=float(zk['montage_std']), step=1.0)
            zk['montage_satz'] = st.number_input("Satz €", value=float(zk['montage_satz']), step=5.0)
            zk['kran'] = st.number_input("Kran €", value=float(zk['kran']), step=50.0)
            
            st.markdown("---")
            st.write("**Risiko-Zuschlag**")
            zk['zuschlag_prozent'] = st.slider("Risiko %", 0, 30, int(zk.get('zuschlag_prozent',0)))
            zk['zuschlag_transparent'] = st.checkbox("Sichtbar?", value=True)

        with st.expander("💰 Preisgestaltung (Provision & Rabatt)", expanded=True):
            st.info("Diese Einstellungen beeinflussen den Endpreis!")
            zk['provision_prozent'] = st.number_input("Versteckte Provision % (aufschlagen)", 0.0, 50.0, float(zk.get('provision_prozent',0)), step=1.0, help="Erhöht Einzelpreise auf dem PDF unsichtbar")
            zk['rabatt_prozent'] = st.number_input("Sichtbarer Rabatt % (abziehen)", 0.0, 50.0, float(zk.get('rabatt_prozent',0)), step=1.0, help="Wird am Ende sichtbar abgezogen")
            zk['skonto_prozent'] = st.number_input("Skonto Info %", 0.0, 10.0, float(zk.get('skonto_prozent',0)), step=1.0, help="Nur Text-Info im Footer")

        st.subheader("Kunde & PDF")
        with st.form("pdf"):
            kd = st.session_state['kunden_daten']
            kd['Name'] = st.text_input("Name", kd['Name'])
            kd['Strasse'] = st.text_input("Str", kd['Strasse'])
            kd['Ort'] = st.text_input("Ort", kd['Ort'])
            kd['Email'] = st.text_input("Email", kd['Email'])
            kd['Notiz'] = st.text_area("Notiz", kd['Notiz'])
            fotos = st.file_uploader("Fotos", accept_multiple_files=True)
            if st.form_submit_button("📄 Erstellen"):
                m_sum = zk['montage_mann'] * zk['montage_std'] * zk['montage_satz']
                st.session_state['fertiges_pdf'] = create_pdf(
                    st.session_state['positionen'], kd, fotos, m_sum, zk['kran'], 
                    True, zk['zuschlag_prozent'], "Risiko", zk.get('zuschlag_transparent', True),
                    zk['provision_prozent'], zk['rabatt_prozent'], zk['skonto_prozent']
                )
                st.session_state['fertiges_intern_pdf'] = create_internal_pdf(st.session_state['positionen'], kd, zk)
                st.success("Fertig!")
        
        if st.session_state['fertiges_pdf']:
            c_d1, c_d2 = st.columns(2)
            c_d1.download_button("Kunde PDF", st.session_state['fertiges_pdf'], "angebot.pdf", "application/pdf")
            c_d2.download_button("Intern PDF", st.session_state['fertiges_intern_pdf'], "fertigung.pdf", "application/pdf")

# --- C: ADMIN ---
elif menue_punkt == "🔐 Admin":
    st.title("Admin")
    if st.text_input("PW", type="password") == "1234":
        if st.button("Reset Excel"): 
            if generiere_neue_excel_datei(): st.success("OK")
        sheets = lade_alle_blattnamen()
        if sheets:
            sh = st.selectbox("Blatt", sheets)
            df = lade_blatt(sh)
            new_df = st.data_editor(df, num_rows="dynamic")
            if st.button("Speichern"):
                if speichere_excel(new_df, sh): st.success("Gespeichert")
