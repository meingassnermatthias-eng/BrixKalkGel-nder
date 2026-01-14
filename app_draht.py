import streamlit as st
import pandas as pd
from fpdf import FPDF
import base64
import os
import tempfile
import math
from datetime import datetime

# --- 1. SETUP & KONFIGURATION ---
LOGO_DATEI = "Meingassner Metalltechnik 2023.png"
EXCEL_DATEI = "katalog.xlsx"

st.set_page_config(page_title="Meingassner App", layout="wide", page_icon=LOGO_DATEI)

def setup_app_icon(image_file):
    if os.path.exists(image_file):
        with open(image_file, "rb") as f:
            data = f.read()
        encoded = base64.b64encode(data).decode()
        icon_html = f"""
        <link rel="apple-touch-icon" href="data:image/png;base64,{encoded}">
        <link rel="icon" type="image/png" href="data:image/png;base64,{encoded}">
        """
        st.markdown(icon_html, unsafe_allow_html=True)
        st.sidebar.image(image_file, width=200)
    else:
        # Falls kein Logo da ist, zeige Warnung aber stürze nicht ab
        # st.sidebar.warning(f"Logo '{image_file}' nicht gefunden.")
        pass

setup_app_icon(LOGO_DATEI)

# --- 2. EXCEL GENERATOR (Die "Mega-Maschine") ---
def generiere_neue_excel_datei():
    """Erstellt die katalog.xlsx mit ALLEN Modellen komplett neu"""
    
    # 1. STARTSEITE
    startseite_data = {
        "System": [
            "1. Stab-Optik (Decor, Staketen)",
            "2. Flächige Optik (Perforée, Flat)",
            "3. Latten & Palisaden",
            "4. Horizontal-Design",
            "5. Glas-Geländer",
            "6. Zubehör & Extras"
        ],
        "Blattname": [
            "Brix_Stab", "Brix_Flaechig", "Brix_Latten", 
            "Brix_Horizontal", "Brix_Glas", "Brix_Extras"
        ]
    }
    df_start = pd.DataFrame(startseite_data)

    # 2. STAB-OPTIK
    stab_data = [
        {"Typ": "Zahl", "Bezeichnung": "Länge des Geländers (m)", "Variable": "L", "Optionen": "", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Modell", "Variable": "P_Modell", 
         "Optionen": "Decor 22 (Stäbe eng):204, Decor 60 (Stäbe weit):204, Staketen 40mm:169, Staketen 60mm:169, Staketen 22mm:169, Verti.Sign (Kantig):207", 
         "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Farbe", "Variable": "F_Faktor", 
         "Optionen": "Standard (STF):1.0, Sonder (SOF):1.10, Spezial (SPF):1.30", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Montageart Steher", "Variable": "P_Steher", 
         "Optionen": "Aufsatzmontage (Boden):125, Seitenmontage (Wand):161", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Verlauf", "Variable": "P_Form", 
         "Optionen": "Gerade:0, Schräg (Treppe):32", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Anzahl Ecken (90°)", "Variable": "Ecken", "Optionen": "", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Montage & Arbeit (€/m)", "Variable": "P_Arbeit", "Optionen": "", "Formel": ""},
        {"Typ": "Preis", "Bezeichnung": "Gesamtpreis", "Variable": "Endpreis", "Optionen": "", 
         "Formel": "((P_Modell + P_Form) * L * F_Faktor) + ((math.ceil(L/1.3)+1) * P_Steher * F_Faktor) + (Ecken * 95) + (L * P_Arbeit)"}
    ]
    df_stab = pd.DataFrame(stab_data)

    # 3. FLÄCHIGE OPTIK
    flaechig_data = [
        {"Typ": "Zahl", "Bezeichnung": "Länge des Geländers (m)", "Variable": "L", "Optionen": "", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Modell-Basis", "Variable": "P_Modell", 
         "Optionen": "Decor-Perforée (Lochblech):250, Staket-on-Flat (Stab+Blech):255, Flat-Design (Rahmenlos):265", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Füllung Material", "Variable": "P_Full", 
         "Optionen": "Standard Lochblech/Vollblech:0, Acrylglas satiniert:0, Noppenblech:0", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Farbe", "Variable": "F_Faktor", 
         "Optionen": "Standard (STF):1.0, Sonder (SOF):1.10", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Montageart Steher", "Variable": "P_Steher", 
         "Optionen": "Aufsatzmontage:125, Seitenmontage:161", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Verlauf", "Variable": "P_Form", 
         "Optionen": "Gerade:0, Schräg (Treppe):32", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Anzahl Ecken", "Variable": "Ecken", "Optionen": "", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Montage & Arbeit (€/m)", "Variable": "P_Arbeit", "Optionen": "", "Formel": ""},
        {"Typ": "Preis", "Bezeichnung": "Gesamtpreis", "Variable": "Endpreis", "Optionen": "", 
         "Formel": "((P_Modell + P_Full + P_Form) * L * F_Faktor) + ((math.ceil(L/1.3)+1) * P_Steher * F_Faktor) + (Ecken * 95) + (L * P_Arbeit)"}
    ]
    df_flaechig = pd.DataFrame(flaechig_data)

    # 4. LATTEN & PALISADEN
    latten_data = [
        {"Typ": "Zahl", "Bezeichnung": "Länge des Geländers (m)", "Variable": "L", "Optionen": "", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Modell", "Variable": "P_Modell", 
         "Optionen": "Latte Classic (Aufliegend):206, Latten Füllung (Innen):210, Palisaden (Rundstab):180, Paliquadra (Eckig):218", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Farbe", "Variable": "F_Faktor", 
         "Optionen": "Standard (STF):1.0, Sonder (SOF):1.10, Holzdekor:1.4", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Montageart Steher", "Variable": "P_Steher", 
         "Optionen": "Aufsatzmontage:125, Seitenmontage:161", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Verlauf", "Variable": "P_Form", 
         "Optionen": "Gerade:0, Schräg:30", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Anzahl Ecken", "Variable": "Ecken", "Optionen": "", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Montage & Arbeit (€/m)", "Variable": "P_Arbeit", "Optionen": "", "Formel": ""},
        {"Typ": "Preis", "Bezeichnung": "Gesamtpreis", "Variable": "Endpreis", "Optionen": "", 
         "Formel": "((P_Modell + P_Form) * L * F_Faktor) + ((math.ceil(L/1.3)+1) * P_Steher * F_Faktor) + (Ecken * 95) + (L * P_Arbeit)"}
    ]
    df_latten = pd.DataFrame(latten_data)

    # 5. HORIZONTAL DESIGN
    horiz_data = [
        {"Typ": "Zahl", "Bezeichnung": "Länge des Geländers (m)", "Variable": "L", "Optionen": "", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Modell", "Variable": "P_Modell", 
         "Optionen": "Staketto (Zwischen Steher):221, Frontline (Vor Steher):210, Lamello (Schräglamelle):221, Inquer (Stab 19x40):190", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Farbe", "Variable": "F_Faktor", 
         "Optionen": "Standard (STF):1.0, Sonder (SOF):1.10", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Montageart Steher", "Variable": "P_Steher", 
         "Optionen": "Aufsatzmontage:125, Seitenmontage:161", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Verlauf", "Variable": "P_Form", 
         "Optionen": "Gerade:0, Schräg (max 6 Grad!):35", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Anzahl Ecken", "Variable": "Ecken", "Optionen": "", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Montage & Arbeit (€/m)", "Variable": "P_Arbeit", "Optionen": "", "Formel": ""},
        {"Typ": "Preis", "Bezeichnung": "Gesamtpreis", "Variable": "Endpreis", "Optionen": "", 
         "Formel": "((P_Modell + P_Form) * L * F_Faktor) + ((math.ceil(L/1.3)+1) * P_Steher * F_Faktor) + (Ecken * 105) + (L * P_Arbeit)"}
    ]
    df_horiz = pd.DataFrame(horiz_data)

    # 6. GLAS-GELÄNDER
    glas_data = [
        {"Typ": "Zahl", "Bezeichnung": "Länge des Geländers (m)", "Variable": "L", "Optionen": "", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "System-Typ", "Variable": "P_System", 
         "Optionen": "Glasal (Rahmen oben/unten):307, Glasalo (Rahmen seitlich):284, Glas-Clips (Punktgehalten):170, Glas-Klemmen (Eckig):180", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Glas-Füllung (VSG 10)", "Variable": "P_Glas", 
         "Optionen": "VSG Klar Rechteckig:130, VSG Matt Rechteckig:165, VSG Klar Schräg:220, VSG Matt Schräg:260", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Farbe Rahmen", "Variable": "F_Faktor", 
         "Optionen": "Standard (STF):1.0, Sonder (SOF):1.10", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Montageart Steher", "Variable": "P_Steher", 
         "Optionen": "Aufsatzmontage:125, Seitenmontage:161", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Verlauf", "Variable": "P_Form", 
         "Optionen": "Gerade:0, Schräg:45", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Anzahl Ecken", "Variable": "Ecken", "Optionen": "", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Montage & Arbeit (€/m)", "Variable": "P_Arbeit", "Optionen": "", "Formel": ""},
        {"Typ": "Preis", "Bezeichnung": "Gesamtpreis", "Variable": "Endpreis", "Optionen": "", 
         "Formel": "((P_System + P_Glas + P_Form) * L * F_Faktor) + ((math.ceil(L/1.3)+1) * P_Steher * F_Faktor) + (Ecken * 110) + (L * P_Arbeit)"}
    ]
    df_glas = pd.DataFrame(glas_data)

    # 7. ZUBEHÖR
    extra_data = [
        {"Typ": "Auswahl", "Bezeichnung": "Artikel", "Variable": "P_Art",
         "Optionen": "Wand-Handlauf SideRail:70, Blumenkasten 85cm:135, Blumenkasten 115cm:156, Blumenkasten 165cm:192",
         "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Menge / Länge", "Variable": "Menge", "Optionen": "", "Formel": ""},
        {"Typ": "Preis", "Bezeichnung": "Gesamt", "Variable": "Endpreis", "Optionen": "", 
         "Formel": "P_Art * Menge"}
    ]
    df_extras = pd.DataFrame(extra_data)

    # SPEICHERN
    try:
        with pd.ExcelWriter(EXCEL_DATEI, engine="openpyxl") as writer:
            df_start.to_excel(writer, sheet_name="Startseite", index=False)
            df_stab.to_excel(writer, sheet_name="Brix_Stab", index=False)
            df_flaechig.to_excel(writer, sheet_name="Brix_Flaechig", index=False)
            df_latten.to_excel(writer, sheet_name="Brix_Latten", index=False)
            df_horiz.to_excel(writer, sheet_name="Brix_Horizontal", index=False)
            df_glas.to_excel(writer, sheet_name="Brix_Glas", index=False)
            df_extras.to_excel(writer, sheet_name="Brix_Extras", index=False)
        return True
    except Exception as e:
        st.error(f"Fehler beim Erstellen der Datei: {e}")
        return False

# --- 3. HELPER FUNKTIONEN ---
def clean_df_columns(df):
    if not df.empty: 
        df.columns = df.columns.str.strip()
        rename_map = {
            'Formel / Info': 'Formel', 'Formel/Info': 'Formel',
            'Info': 'Formel', 'Preisfindung': 'Formel'
        }
        df.rename(columns=rename_map, inplace=True)
    return df

def lade_startseite():
    if not os.path.exists(EXCEL_DATEI): return pd.DataFrame()
    try: return clean_df_columns(pd.read_excel(EXCEL_DATEI, sheet_name="Startseite"))
    except: return pd.DataFrame()

def lade_blatt(blatt_name):
    if not os.path.exists(EXCEL_DATEI): return pd.DataFrame()
    try: return clean_df_columns(pd.read_excel(EXCEL_DATEI, sheet_name=blatt_name))
    except: return pd.DataFrame()

def lade_alle_blattnamen():
    if not os.path.exists(EXCEL_DATEI): return []
    return pd.ExcelFile(EXCEL_DATEI).sheet_names

def speichere_excel(df, blatt_name):
    try:
        mode = "a" if os.path.exists(EXCEL_DATEI) else "w"
        with pd.ExcelWriter(EXCEL_DATEI, engine="openpyxl", mode=mode, if_sheet_exists="replace") as writer:
            df.to_excel(writer, sheet_name=blatt_name, index=False)
        return True
    except Exception as e:
        st.error(f"Fehler beim Speichern: {e}")
        return False

# --- 4. SESSION STATE ---
if 'positionen' not in st.session_state: st.session_state['positionen'] = []
if 'kunden_daten' not in st.session_state: 
    st.session_state['kunden_daten'] = {"Name": "", "Strasse": "", "Ort": "", "Tel": "", "Email": "", "Notiz": ""}
if 'fertiges_pdf' not in st.session_state:
    st.session_state['fertiges_pdf'] = None

# --- 5. PDF ENGINE ---
def clean_text(text):
    if not isinstance(text, str): text = str(text)
    text = text.replace("€", "EUR").replace("–", "-").replace("„", '"').replace("“", '"')
    return text.encode('latin-1', 'replace').decode('latin-1')

class PDF(FPDF):
    def header(self):
        if os.path.exists(LOGO_DATEI):
            self.image(LOGO_DATEI, 10, 8, 60)
        self.set_font('Arial', 'B', 16)
        heute = datetime.now().strftime("%d.%m.%Y")
        titel = f"Kostenschätzung vom {heute}"
        self.cell(0, 18, clean_text(titel), 0, 1, 'R')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Seite {self.page_no()}', 0, 0, 'C')

def create_pdf(positionen_liste, kunden_dict, fotos):
    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=10)
    pdf.ln(5)
    
    # Kundendaten
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 6, "Kundeninformation:", ln=True)
    pdf.set_font("Arial", size=10)
    k_text = ""
    if kunden_dict["Name"]: k_text += f"{kunden_dict['Name']}\n"
    if kunden_dict["Strasse"]: k_text += f"{kunden_dict['Strasse']}\n"
    if kunden_dict["Ort"]: k_text += f"{kunden_dict['Ort']}\n"
    k_text += "\n"
    if kunden_dict["Tel"]: k_text += f"Tel: {kunden_dict['Tel']}\n"
    if kunden_dict["Email"]: k_text += f"Email: {kunden_dict['Email']}\n"
    pdf.multi_cell(0, 5, clean_text(k_text))
    
    if kunden_dict["Notiz"]:
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 5, "Bemerkung / Notizen:", ln=True)
        pdf.set_font("Arial", size=10)
        pdf.multi_cell(0, 5, clean_text(kunden_dict["Notiz"]))
    pdf.ln(10)
    
    # Tabelle
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(240, 240, 240)
    w_desc, w_menge, w_ep, w_gesamt = 100, 25, 30, 35
    pdf.cell(w_desc, 8, "Beschreibung", 1, 0, 'L', True)
    pdf.cell(w_menge, 8, "Menge", 1, 0, 'C', True)
    pdf.cell(w_ep, 8, "EP (EUR)", 1, 0, 'R', True)
    pdf.cell(w_gesamt, 8, "Gesamt", 1, 1, 'R', True)
    pdf.set_font("Arial", size=10)
    gesamt_summe = 0
    
    for pos in positionen_liste:
        raw_desc = str(pos['Beschreibung'])
        parts = raw_desc.split("|")
        main_title = parts[0].strip()
        details = ""
        if len(parts) > 1:
            details_raw = parts[1]
            details = "\n" + details_raw.replace(",", "\n -").strip()
            if not details.strip().startswith("-"): details = details.replace("\n", "\n - ", 1)
        final_desc_text = clean_text(f"{main_title}{details}")
        
        x_start, y_start = pdf.get_x(), pdf.get_y()
        pdf.multi_cell(w_desc, 5, final_desc_text, border=1, align='L')
        y_end = pdf.get_y()
        row_height = y_end - y_start
        pdf.set_xy(x_start + w_desc, y_start)
        pdf.cell(w_menge, row_height, clean_text(str(pos['Menge'])), 1, 0, 'C')
        pdf.cell(w_ep, row_height, f"{pos['Einzelpreis']:.2f}", 1, 0, 'R')
        pdf.cell(w_gesamt, row_height, f"{pos['Preis']:.2f}", 1, 1, 'R')
        gesamt_summe += pos['Preis']

    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(w_desc + w_menge + w_ep, 10, "Gesamtsumme:", 0, 0, 'R')
    pdf.cell(w_gesamt, 10, f"{gesamt_summe:.2f} EUR", 1, 1, 'R')

    if fotos:
        pdf.add_page()
        pdf.cell(0, 10, "Baustellen-Dokumentation / Fotos", 0, 1, 'L')
        for foto_upload in fotos:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
                    tmp_file.write(foto_upload.getvalue())
                    tmp_path = tmp_file.name
                if pdf.get_y() > 180: pdf.add_page()
                pdf.image(tmp_path, w=160)
                pdf.ln(10)
                os.unlink(tmp_path)
            except Exception as e:
                pdf.cell(0, 10, f"Fehler beim Bild: {str(e)}", ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- 6. NAVIGATION ---
st.sidebar.header("Navigation")
index_df = lade_startseite()
katalog_items = index_df['System'].tolist() if not index_df.empty and 'System' in index_df.columns else []

menue_punkt = st.sidebar.radio("Gehe zu:", ["📂 Konfigurator / Katalog", "🛒 Warenkorb / Abschluss", "🔐 Admin"])
st.sidebar.markdown("---")

# TEIL A: KONFIGURATOR
if menue_punkt == "📂 Konfigurator / Katalog":
    st.title("Artikel Konfigurator")
    if katalog_items:
        auswahl_system = st.selectbox("System wählen:", katalog_items)
        row = index_df[index_df['System'] == auswahl_system]
        if not row.empty:
            blatt = row.iloc[0]['Blattname']
            df_config = lade_blatt(blatt)
            
            col_konfig, col_mini_cart = st.columns([2, 1])
            with col_konfig:
                st.subheader(f"Konfiguration: {auswahl_system}")
                if df_config.empty:
                    st.warning("Dieses Blatt ist noch leer.")
                elif 'Formel' not in df_config.columns:
                    st.error(f"Fehler: Spalte 'Formel' fehlt im Blatt '{blatt}'!")
                else:
                    vars_calc = {}
                    desc_parts = []
                    for index, zeile in df_config.iterrows():
                        typ = str(zeile.get('Typ', '')).strip().lower()
                        label = str(zeile.get('Bezeichnung', 'Unbenannt'))
                        var_name = str(zeile.get('Variable', '')).strip()
                        
                        if typ == 'zahl':
                            val = st.number_input(label, value=0.0, step=0.1, key=f"{blatt}_{index}")
                            vars_calc[var_name] = val
                            if val > 0: desc_parts.append(f"{label}: {val}")
                        
                        elif typ == 'auswahl':
                            raw_opts = str(zeile.get('Optionen', '')).split(',')
                            opts_dict = {}
                            opts_names = []
                            for opt in raw_opts:
                                if ':' in opt:
                                    n, v = opt.split(':')
                                    opts_dict[n.strip()] = float(v)
                                    opts_names.append(n.strip())
                                else:
                                    opts_dict[opt.strip()] = 0
                                    opts_names.append(opt.strip())
                            wahl = st.selectbox(label, opts_names, key=f"{blatt}_{index}")
                            vars_calc[var_name] = opts_dict.get(wahl, 0)
                            desc_parts.append(f"{label}: {wahl}")

                        elif typ == 'preis':
                            formel = str(zeile.get('Formel', ''))
                            st.markdown("---")
                            try:
                                safe_env = {"__builtins__": None, "math": math, "round": round, "int": int, "float": float}
                                safe_env.update(vars_calc)
                                preis = eval(formel, safe_env)
                                st.subheader(f"Preis: {preis:.2f} €")
                                if st.button("In den Warenkorb", type="primary"):
                                    full_desc = f"{auswahl_system} | " + ", ".join(desc_parts)
                                    st.session_state['positionen'].append({
                                        "Beschreibung": full_desc, "Menge": 1.0, "Einzelpreis": preis, "Preis": preis
                                    })
                                    st.success("Hinzugefügt!")
                            except Exception as e:
                                st.error(f"Berechnungsfehler: {e}")
            with col_mini_cart:
                st.info("🛒 Schnell-Check")
                if st.session_state['positionen']:
                    cnt = len(st.session_state['positionen'])
                    sum_live = sum(p['Preis'] for p in st.session_state['positionen'])
                    st.write(f"**{cnt} Pos.** | **{sum_live:.2f} €**")
                else:
                    st.write("Leer")
    else:
        st.warning("Keine Daten. Bitte im Admin-Bereich 'Reset' drücken!")

# TEIL B: WARENKORB
elif menue_punkt == "🛒 Warenkorb / Abschluss":
    st.title("🛒 Warenkorb & Abschluss")
    col_liste, col_daten = st.columns([1.2, 0.8])
    with col_liste:
        st.subheader("Positionen")
        if st.session_state['positionen']:
            h1, h2, h3, h4 = st.columns([3, 1, 1, 0.5])
            h1.markdown("**Beschreibung**"); h2.markdown("**Menge**"); h3.markdown("**Preis**"); h4.markdown("**Del**")
            st.markdown("---")
            indices_to_delete = []
            for i, pos in enumerate(st.session_state['positionen']):
                c1, c2, c3, c4 = st.columns([3, 1, 1, 0.5])
                short_desc = pos['Beschreibung'].split("|")[0]
                c1.write(f"**{short_desc}**")
                with c1.expander("Details"): st.write(pos['Beschreibung'])
                neue_menge = c2.number_input("Menge", value=float(pos['Menge']), step=0.1, key=f"qty_{i}", label_visibility="collapsed")
                if neue_menge != pos['Menge']:
                    st.session_state['positionen'][i]['Menge'] = neue_menge
                    st.session_state['positionen'][i]['Preis'] = neue_menge * pos['Einzelpreis']
                    st.rerun()
                c3.write(f"{pos['Preis']:.2f} €")
                if c4.button("🗑️", key=f"del_{i}"): indices_to_delete.append(i)
            if indices_to_delete:
                for index in sorted(indices_to_delete, reverse=True): del st.session_state['positionen'][index]
                st.session_state['fertiges_pdf'] = None
                st.rerun()
            st.markdown("---")
            total = sum(p['Preis'] for p in st.session_state['positionen'])
            st.markdown(f"### Gesamt: {total:.2f} €")
            if st.button("Alles löschen", type="secondary"):
                st.session_state['positionen'] = []
                st.rerun()
        else:
            st.info("Warenkorb leer.")

    with col_daten:
        st.subheader("Kundendaten")
        with st.form("abschluss_form"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Name / Firma", value=st.session_state['kunden_daten']['Name'])
            strasse = c2.text_input("Straße", value=st.session_state['kunden_daten']['Strasse'])
            c3, c4 = st.columns(2)
            ort = c3.text_input("Ort / PLZ", value=st.session_state['kunden_daten']['Ort'])
            tel = c4.text_input("Telefon", value=st.session_state['kunden_daten']['Tel'])
            email = st.text_input("Email", value=st.session_state['kunden_daten']['Email'])
            notiz = st.text_area("Notiz", value=st.session_state['kunden_daten']['Notiz'])
            st.markdown("---")
            fotos = st.file_uploader("Fotos", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])
            submitted = st.form_submit_button("💾 PDF Generieren")
        if submitted:
            st.session_state['kunden_daten'] = {"Name": name, "Strasse": strasse, "Ort": ort, "Tel": tel, "Email": email, "Notiz": notiz}
            if st.session_state['positionen']:
                pdf_bytes = create_pdf(st.session_state['positionen'], st.session_state['kunden_daten'], fotos)
                st.session_state['fertiges_pdf'] = pdf_bytes
                st.success("PDF erstellt!")
            else:
                st.error("Warenkorb leer.")
        if st.session_state['fertiges_pdf']:
            st.download_button("⬇️ PDF Herunterladen", data=st.session_state['fertiges_pdf'], file_name="kostenschaetzung.pdf", mime="application/pdf", type="primary")

# TEIL C: ADMIN
elif menue_punkt == "🔐 Admin":
    st.title("Admin Bereich")
    pw = st.text_input("Passwort:", type="password")
    if pw == "1234":
        # --- DER NEUE START-KNOPF ---
        st.markdown("### 🚀 Katalog-Reset")
        st.info("Drücke diesen Knopf, um die Excel-Datei mit ALLEN Brix-Modellen (Stäbe, Glas, Latten...) neu zu erstellen.")
        if st.button("🚀 Katalog-Datei neu erstellen (Reset)", type="primary"):
            if generiere_neue_excel_datei():
                st.success("Erfolg! Der Katalog wurde komplett neu erstellt. Bitte lade die Seite neu (F5).")
                st.cache_data.clear()
            else:
                st.error("Fehler beim Erstellen.")
        
        st.markdown("---")
        st.write("### ✏️ Bearbeiten")
        sheets = lade_alle_blattnamen()
        if sheets:
            sh = st.selectbox("Blatt bearbeiten:", sheets)
            df = lade_blatt(sh)
            df_new = st.data_editor(df, num_rows="dynamic", use_container_width=True)
            if st.button("💾 Änderungen speichern"):
                if speichere_excel(df_new, sh): 
                    st.success("Gespeichert!")
                    st.cache_data.clear()
            
            st.markdown("---")
            with open(EXCEL_DATEI, "rb") as f:
                st.download_button("💾 Backup herunterladen", data=f, file_name="backup.xlsx")
        else:
            st.warning("Keine Excel-Datei vorhanden. Bitte oben 'Reset' drücken!")
