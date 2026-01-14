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
        pass

setup_app_icon(LOGO_DATEI)

# --- 2. EXCEL GENERATOR (ALU + DRAHTGITTER) ---
def generiere_neue_excel_datei():
    """Erstellt die katalog.xlsx mit ALLEN Modellen (Alu & Draht) komplett neu"""
    
    # 1. STARTSEITE (Das Menü)
    startseite_data = {
        "System": [
            # --- ALU BRIX ---
            "1. Alu-Stab (Decor, Staketen)", 
            "2. Alu-Flächig (Perforée, Flat)",
            "3. Alu-Latten & Palisaden", 
            "4. Alu-Horizontal", 
            "5. Alu-Glas", 
            "6. Alu-Zubehör",
            # --- DRAHTGITTER NEU ---
            "7. Draht-Gittermatten (Doppelstab)",
            "8. Draht-Geflecht (Rollen)",
            "9. Draht-Steinkörbe",
            "10. Draht-Tore & Türen"
        ],
        "Blattname": [
            "Brix_Stab", "Brix_Flaechig", "Brix_Latten", "Brix_Horizontal", "Brix_Glas", "Brix_Extras",
            "Draht_Matten", "Draht_Rollen", "Draht_Stein", "Draht_Tore"
        ]
    }
    df_start = pd.DataFrame(startseite_data)

    # --- A) BRIX ALU DATEN (Wie vorher) ---
    stab_data = [
        {"Typ": "Zahl", "Bezeichnung": "Länge des Geländers (m)", "Variable": "L", "Optionen": "", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Modell", "Variable": "P_Modell", "Optionen": "Decor 22 (Stäbe eng):204, Decor 60 (Stäbe weit):204, Staketen 40mm:169, Staketen 60mm:169, Staketen 22mm:169, Verti.Sign (Kantig):207", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Farbe", "Variable": "F_Faktor", "Optionen": "Standard (STF):1.0, Sonder (SOF):1.10, Spezial (SPF):1.30", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Montageart Steher", "Variable": "P_Steher", "Optionen": "Aufsatzmontage (Boden):125, Seitenmontage (Wand):161", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Verlauf", "Variable": "P_Form", "Optionen": "Gerade:0, Schräg (Treppe):32", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Anzahl Ecken (90°)", "Variable": "Ecken", "Optionen": "", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Montage & Arbeit (€/m)", "Variable": "P_Arbeit", "Optionen": "", "Formel": ""},
        {"Typ": "Preis", "Bezeichnung": "Gesamtpreis", "Variable": "Endpreis", "Optionen": "", "Formel": "((P_Modell + P_Form) * L * F_Faktor) + ((math.ceil(L/1.3)+1) * P_Steher * F_Faktor) + (Ecken * 95) + (L * P_Arbeit)"}
    ]
    df_stab = pd.DataFrame(stab_data)
    
    # Kopien für Alu-Varianten (gekürzt, damit Code übersichtlich bleibt)
    df_flaechig = df_stab.copy()
    df_latten = df_stab.copy()
    df_horiz = df_stab.copy()
    df_glas = df_stab.copy()
    
    extra_data = [
        {"Typ": "Auswahl", "Bezeichnung": "Artikel", "Variable": "P_Art", "Optionen": "Wand-Handlauf SideRail:70, Blumenkasten 85cm:135", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Menge", "Variable": "Menge", "Optionen": "", "Formel": ""},
        {"Typ": "Preis", "Bezeichnung": "Gesamt", "Variable": "Endpreis", "Optionen": "", "Formel": "P_Art * Menge"}
    ]
    df_extras = pd.DataFrame(extra_data)

    # --- B) DRAHTGITTER DATEN (NEU aus PDF) ---
    
    # 7. Gittermatten (Doppelstab)
    # Logik: Länge durch 2.5m = Anzahl Matten. Säulen = Matten + 1.
    matten_data = [
        {"Typ": "Zahl", "Bezeichnung": "Länge des Zauns (m)", "Variable": "L", "Optionen": "", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Höhe & Stärke", "Variable": "P_Matte_Lfm", 
         # Preise ca. aus PDF umgerechnet auf LFM (Mattenpreis / 2.5)
         "Optionen": "H 830mm (Leicht 6/5/6):18, H 1030mm (Leicht 6/5/6):22, H 1230mm (Leicht 6/5/6):26, H 1430mm (Leicht 6/5/6):31, H 1030mm (Schwer 8/6/8):32, H 1230mm (Schwer 8/6/8):38", 
         "Formel": "Preis pro Laufmeter Matte"},
        {"Typ": "Auswahl", "Bezeichnung": "Säulen-Typ", "Variable": "P_Saeule", 
         "Optionen": "Rechteckrohr mit Klemmhaltern:35, Rechteckrohr mit Abdeckleiste:45", 
         "Formel": "Preis pro Stück"},
        {"Typ": "Auswahl", "Bezeichnung": "Montageart Säule", "Variable": "P_Fundament", 
         "Optionen": "Zum Einbetonieren:0, Mit Dübelplatte (Aufpreis):18", 
         "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Farbe", "Variable": "F_Faktor", 
         "Optionen": "Verzinkt:1.0, Moosgrün (RAL6005):1.15, Anthrazit (RAL7016):1.15", 
         "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Anzahl Ecken", "Variable": "Ecken", "Optionen": "", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Montage (€/m)", "Variable": "P_Arbeit", "Optionen": "", "Formel": ""},
        
        # Formel: (Mattenpreis * L * F) + (SäulenAnzahl * (Säulenpreis + Fundament) * F) + (Ecken * 30) + Arbeit
        # Säulenanzahl = Aufrunden(Länge / 2.5) + 1
        {"Typ": "Preis", "Bezeichnung": "Gesamtpreis", "Variable": "Endpreis", "Optionen": "", 
         "Formel": "(L * P_Matte_Lfm * F_Faktor) + ((math.ceil(L/2.5)+1) * (P_Saeule + P_Fundament) * F_Faktor) + (Ecken * 30) + (L * P_Arbeit)"}
    ]
    df_matten = pd.DataFrame(matten_data)

    # 8. Drahtgeflecht (Rollen)
    # Logik: Einfacher Meterpreis + Säulenabstand ca 2.5m + Streben
    rollen_data = [
        {"Typ": "Zahl", "Bezeichnung": "Länge des Zauns (m)", "Variable": "L", "Optionen": "", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Höhe Geflecht", "Variable": "P_Geflecht", 
         "Optionen": "Höhe 100cm:12, Höhe 125cm:15, Höhe 150cm:18", 
         "Formel": "Preis pro m Geflecht"},
        {"Typ": "Auswahl", "Bezeichnung": "Säulen & Zubehör (Durchschnitt)", "Variable": "P_Zubehoer", 
         "Optionen": "Standard Rundsäulen (alle 2.5m):15", 
         "Formel": "Umgerechnet auf lfm"},
         {"Typ": "Auswahl", "Bezeichnung": "Oberfläche", "Variable": "F_Faktor", 
         "Optionen": "Dickverzinkt:1.0, Grün beschichtet:1.2", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Anzahl Ecken (Brauchen Streben)", "Variable": "Ecken", "Optionen": "", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Montage (€/m)", "Variable": "P_Arbeit", "Optionen": "", "Formel": ""},
        
        # Formel: (Geflecht + Zubehör) * L * F + Streben für Ecken + Arbeit
        {"Typ": "Preis", "Bezeichnung": "Gesamtpreis", "Variable": "Endpreis", "Optionen": "", 
         "Formel": "((P_Geflecht + P_Zubehoer) * L * F_Faktor) + (Ecken * 25 * F_Faktor) + (L * P_Arbeit)"}
    ]
    df_rollen = pd.DataFrame(rollen_data)

    # 9. Steinkörbe (Gabionen)
    stein_data = [
        {"Typ": "Zahl", "Bezeichnung": "Länge (m)", "Variable": "L", "Optionen": "", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Korb Typ", "Variable": "P_Korb", 
         "Optionen": "Breite 15cm (H80):150, Breite 15cm (H100):180, Breite 25cm (H100):220", 
         "Formel": "Preis pro lfm Korb ohne Steine"},
        {"Typ": "Zahl", "Bezeichnung": "Steinfüllung (Pauschal €/m)", "Variable": "P_Stein", "Optionen": "", "Formel": "Ca. Preis für Steine"},
        {"Typ": "Zahl", "Bezeichnung": "Montage (€/m)", "Variable": "P_Arbeit", "Optionen": "", "Formel": ""},
        {"Typ": "Preis", "Bezeichnung": "Gesamtpreis", "Variable": "Endpreis", "Optionen": "", 
         "Formel": "L * (P_Korb + P_Stein + P_Arbeit)"}
    ]
    df_stein = pd.DataFrame(stein_data)

    # 10. Tore & Türen
    tore_data = [
        {"Typ": "Auswahl", "Bezeichnung": "Tor Modell", "Variable": "P_Tor", 
         "Optionen": "Gehtür 1-Flg (B100 x H100):350, Gehtür 1-Flg (B100 x H120):390, Einfahrtstor 2-Flg (B300 x H100):850, Einfahrtstor 2-Flg (B300 x H120):950", 
         "Formel": "Stückpreis"},
        {"Typ": "Auswahl", "Bezeichnung": "Farbe", "Variable": "F_Faktor", 
         "Optionen": "Verzinkt:1.0, Moosgrün/Anthrazit:1.15", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Anzahl", "Variable": "Menge", "Optionen": "", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Montage Pauschal (€)", "Variable": "P_Montage", "Optionen": "", "Formel": ""},
        {"Typ": "Preis", "Bezeichnung": "Gesamtpreis", "Variable": "Endpreis", "Optionen": "", 
         "Formel": "(P_Tor * F_Faktor * Menge) + P_Montage"}
    ]
    df_tore = pd.DataFrame(tore_data)


    try:
        with pd.ExcelWriter(EXCEL_DATEI, engine="openpyxl") as writer:
            df_start.to_excel(writer, sheet_name="Startseite", index=False)
            
            # ALU
            df_stab.to_excel(writer, sheet_name="Brix_Stab", index=False)
            df_flaechig.to_excel(writer, sheet_name="Brix_Flaechig", index=False)
            df_latten.to_excel(writer, sheet_name="Brix_Latten", index=False)
            df_horiz.to_excel(writer, sheet_name="Brix_Horizontal", index=False)
            df_glas.to_excel(writer, sheet_name="Brix_Glas", index=False)
            df_extras.to_excel(writer, sheet_name="Brix_Extras", index=False)
            
            # DRAHT
            df_matten.to_excel(writer, sheet_name="Draht_Matten", index=False)
            df_rollen.to_excel(writer, sheet_name="Draht_Rollen", index=False)
            df_stein.to_excel(writer, sheet_name="Draht_Stein", index=False)
            df_tore.to_excel(writer, sheet_name="Draht_Tore", index=False)
            
        return True
    except Exception as e:
        st.error(f"Fehler: {e}")
        return False

# --- 3. HELPER & UI ---
def clean_df_columns(df):
    if not df.empty: 
        df.columns = df.columns.str.strip()
        rename_map = {'Formel / Info': 'Formel', 'Formel/Info': 'Formel', 'Info': 'Formel'}
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
        st.error(f"Fehler: {e}")
        return False

# --- SESSION STATE ---
if 'positionen' not in st.session_state: st.session_state['positionen'] = []
if 'kunden_daten' not in st.session_state: 
    st.session_state['kunden_daten'] = {"Name": "", "Strasse": "", "Ort": "", "Tel": "", "Email": "", "Notiz": ""}
if 'fertiges_pdf' not in st.session_state: st.session_state['fertiges_pdf'] = None
if 'zusatzkosten' not in st.session_state:
    st.session_state['zusatzkosten'] = {"kran": 0.0, "montage_mann": 2, "montage_std": 0.0, "montage_satz": 65.0}

# --- PDF ---
def clean_text(text):
    if not isinstance(text, str): text = str(text)
    text = text.replace("€", "EUR").replace("–", "-").replace("„", '"').replace("“", '"')
    return text.encode('latin-1', 'replace').decode('latin-1')

class PDF(FPDF):
    def header(self):
        if os.path.exists(LOGO_DATEI): self.image(LOGO_DATEI, 10, 8, 60)
        self.set_font('Arial', 'B', 16)
        heute = datetime.now().strftime("%d.%m.%Y")
        titel = f"Kostenschätzung vom {heute}"
        self.cell(0, 18, clean_text(titel), 0, 1, 'R')
        self.ln(10)
    def footer(self):
        self.set_y(-15); self.set_font('Arial', 'I', 8); self.cell(0, 10, f'Seite {self.page_no()}', 0, 0, 'C')

def create_pdf(positionen_liste, kunden_dict, fotos, montage_summe, kran_summe):
    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=10)
    pdf.ln(5)
    
    # Kundendaten
    pdf.ln(10); pdf.set_font("Arial", 'B', 12); pdf.cell(0, 6, "Kundeninformation:", ln=True); pdf.set_font("Arial", size=10)
    k_text = ""
    if kunden_dict["Name"]: k_text += f"{kunden_dict['Name']}\n"
    if kunden_dict["Strasse"]: k_text += f"{kunden_dict['Strasse']}\n"
    if kunden_dict["Ort"]: k_text += f"{kunden_dict['Ort']}\n"
    k_text += "\n"
    if kunden_dict["Tel"]: k_text += f"Tel: {kunden_dict['Tel']}\n"
    if kunden_dict["Email"]: k_text += f"Email: {kunden_dict['Email']}\n"
    pdf.multi_cell(0, 5, clean_text(k_text))
    if kunden_dict["Notiz"]:
        pdf.ln(5); pdf.set_font("Arial", 'B', 10); pdf.cell(0, 5, "Bemerkung / Notizen:", ln=True); pdf.set_font("Arial", size=10)
        pdf.multi_cell(0, 5, clean_text(kunden_dict["Notiz"]))
    pdf.ln(10)
    
    # Tabelle
    pdf.set_font("Arial", 'B', 10); pdf.set_fill_color(240, 240, 240)
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
        y_end = pdf.get_y(); row_height = y_end - y_start
        pdf.set_xy(x_start + w_desc, y_start)
        pdf.cell(w_menge, row_height, clean_text(str(pos['Menge'])), 1, 0, 'C')
        pdf.cell(w_ep, row_height, f"{pos['Einzelpreis']:.2f}", 1, 0, 'R')
        pdf.cell(w_gesamt, row_height, f"{pos['Preis']:.2f}", 1, 1, 'R')
        gesamt_summe += pos['Preis']

    if montage_summe > 0:
        pdf.cell(w_desc, 8, clean_text("Montagekosten (gem. Aufwand)"), 1, 0, 'L')
        pdf.cell(w_menge, 8, "1", 1, 0, 'C')
        pdf.cell(w_ep, 8, f"{montage_summe:.2f}", 1, 0, 'R')
        pdf.cell(w_gesamt, 8, f"{montage_summe:.2f}", 1, 1, 'R')
        gesamt_summe += montage_summe
    if kran_summe > 0:
        pdf.cell(w_desc, 8, clean_text("Kranarbeiten / Hebegerät (Pauschale)"), 1, 0, 'L')
        pdf.cell(w_menge, 8, "1", 1, 0, 'C')
        pdf.cell(w_ep, 8, f"{kran_summe:.2f}", 1, 0, 'R')
        pdf.cell(w_gesamt, 8, f"{kran_summe:.2f}", 1, 1, 'R')
        gesamt_summe += kran_summe

    pdf.ln(5); pdf.set_font("Arial", 'B', 12)
    pdf.cell(w_desc + w_menge + w_ep, 10, "Gesamtsumme:", 0, 0, 'R')
    pdf.cell(w_gesamt, 10, f"{gesamt_summe:.2f} EUR", 1, 1, 'R')

    if fotos:
        pdf.add_page(); pdf.cell(0, 10, "Baustellen-Dokumentation / Fotos", 0, 1, 'L')
        for foto_upload in fotos:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
                    tmp_file.write(foto_upload.getvalue())
                    tmp_path = tmp_file.name
                if pdf.get_y() > 180: pdf.add_page()
                pdf.image(tmp_path, w=160); pdf.ln(10); os.unlink(tmp_path)
            except Exception as e: pdf.cell(0, 10, f"Fehler: {str(e)}", ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- NAVIGATION ---
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
                if df_config.empty: st.warning("Blatt leer.")
                elif 'Formel' not in df_config.columns: st.error("Fehler: 'Formel' fehlt.")
                else:
                    vars_calc = {}; desc_parts = []
                    for index, zeile in df_config.iterrows():
                        typ = str(zeile.get('Typ', '')).strip().lower()
                        label = str(zeile.get('Bezeichnung', 'Unbenannt'))
                        var_name = str(zeile.get('Variable', '')).strip()
                        
                        if typ == 'zahl':
                            val = st.number_input(label, value=0.0, step=1.0, key=f"{blatt}_{index}")
                            vars_calc[var_name] = val
                            if val > 0: desc_parts.append(f"{label}: {val}")
                        elif typ == 'auswahl':
                            raw_opts = str(zeile.get('Optionen', '')).split(',')
                            opts_dict = {}; opts_names = []
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
                                    st.session_state['positionen'].append({"Beschreibung": full_desc, "Menge": 1.0, "Einzelpreis": preis, "Preis": preis})
                                    st.success("Hinzugefügt!")
                            except Exception as e: st.error(f"Fehler: {e}")
            with col_mini_cart:
                st.info("🛒 Schnell-Check")
                if st.session_state['positionen']:
                    cnt = len(st.session_state['positionen']); sum_live = sum(p['Preis'] for p in st.session_state['positionen'])
                    st.write(f"**{cnt} Pos.** | **{sum_live:.2f} €**")
                else: st.write("Leer")
    else: st.warning("Keine Daten. Bitte im Admin-Bereich 'Reset' drücken!")

# TEIL B: WARENKORB
elif menue_punkt == "🛒 Warenkorb / Abschluss":
    st.title("🛒 Warenkorb")
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
                c1.write(f"**{short_desc}**"); 
                with c1.expander("Details"): st.write(pos['Beschreibung'])
                neue_menge = c2.number_input("Menge", value=float(pos['Menge']), step=1.0, key=f"qty_{i}", label_visibility="collapsed")
                if neue_menge != pos['Menge']:
                    st.session_state['positionen'][i]['Menge'] = neue_menge
                    st.session_state['positionen'][i]['Preis'] = neue_menge * pos['Einzelpreis']
                    st.rerun()
                c3.write(f"{pos['Preis']:.2f} €")
                if c4.button("🗑️", key=f"del_{i}"): indices_to_delete.append(i)
            if indices_to_delete:
                for index in sorted(indices_to_delete, reverse=True): del st.session_state['positionen'][index]
                st.session_state['fertiges_pdf'] = None; st.rerun()
            st.markdown("---")
            total_artikel = sum(p['Preis'] for p in st.session_state['positionen'])
            m_sum = st.session_state['zusatzkosten']['montage_mann'] * st.session_state['zusatzkosten']['montage_std'] * st.session_state['zusatzkosten']['montage_satz']
            k_sum = st.session_state['zusatzkosten']['kran']
            if m_sum > 0: st.write(f"➕ Montage: **{m_sum:.2f} €**")
            if k_sum > 0: st.write(f"➕ Kran: **{k_sum:.2f} €**")
            st.markdown(f"### Gesamtsumme: {total_artikel + m_sum + k_sum:.2f} €")
            if st.button("Alles löschen", type="secondary"): st.session_state['positionen'] = []; st.rerun()
        else: st.info("Leer.")

    with col_daten:
        with st.expander("🏗️ Montage & Zusatzkosten", expanded=True):
            c_m1, c_m2, c_m3 = st.columns(3)
            st.session_state['zusatzkosten']['montage_mann'] = c_m1.number_input("Mann", value=st.session_state['zusatzkosten']['montage_mann'], step=1)
            st.session_state['zusatzkosten']['montage_std'] = c_m2.number_input("Std", value=st.session_state['zusatzkosten']['montage_std'], step=1.0)
            st.session_state['zusatzkosten']['montage_satz'] = c_m3.number_input("Satz €", value=st.session_state['zusatzkosten']['montage_satz'], step=5.0)
            st.markdown("---")
            st.session_state['zusatzkosten']['kran'] = st.number_input("Kran Pauschale €", value=st.session_state['zusatzkosten']['kran'], step=50.0)
        
        st.subheader("Kundendaten")
        with st.form("abschluss"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Name", value=st.session_state['kunden_daten']['Name'])
            strasse = c2.text_input("Straße", value=st.session_state['kunden_daten']['Strasse'])
            c3, c4 = st.columns(2)
            ort = c3.text_input("Ort", value=st.session_state['kunden_daten']['Ort'])
            tel = c4.text_input("Tel", value=st.session_state['kunden_daten']['Tel'])
            email = st.text_input("Email", value=st.session_state['kunden_daten']['Email'])
            notiz = st.text_area("Notiz", value=st.session_state['kunden_daten']['Notiz'])
            st.markdown("---")
            fotos = st.file_uploader("Fotos", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])
            submitted = st.form_submit_button("💾 PDF Generieren")
        if submitted:
            st.session_state['kunden_daten'] = {"Name": name, "Strasse": strasse, "Ort": ort, "Tel": tel, "Email": email, "Notiz": notiz}
            m_sum = st.session_state['zusatzkosten']['montage_mann'] * st.session_state['zusatzkosten']['montage_std'] * st.session_state['zusatzkosten']['montage_satz']
            k_sum = st.session_state['zusatzkosten']['kran']
            if st.session_state['positionen'] or m_sum > 0 or k_sum > 0:
                pdf_bytes = create_pdf(st.session_state['positionen'], st.session_state['kunden_daten'], fotos, m_sum, k_sum)
                st.session_state['fertiges_pdf'] = pdf_bytes
                st.success("Erstellt!")
            else: st.error("Leer.")
        if st.session_state['fertiges_pdf']:
            st.download_button("⬇️ PDF Laden", data=st.session_state['fertiges_pdf'], file_name="kostenschaetzung.pdf", mime="application/pdf", type="primary")

# TEIL C: ADMIN
elif menue_punkt == "🔐 Admin":
    st.title("Admin")
    pw = st.text_input("Passwort:", type="password")
    if pw == "1234":
        st.info("Hier kannst du den Katalog zurücksetzen (Alu + Draht).")
        if st.button("🚀 Katalog-Datei neu erstellen (Reset)", type="primary"):
            if generiere_neue_excel_datei(): st.success("Neu erstellt! Bitte F5 drücken."); st.cache_data.clear()
        st.markdown("---")
        sheets = lade_alle_blattnamen()
        if sheets:
            sh = st.selectbox("Blatt:", sheets)
            df = lade_blatt(sh)
            df_new = st.data_editor(df, num_rows="dynamic", use_container_width=True)
            if st.button("💾 Speichern"):
                if speichere_excel(df_new, sh): st.success("Gespeichert!"); st.cache_data.clear()
            st.markdown("---")
            with open(EXCEL_DATEI, "rb") as f: st.download_button("💾 Backup Excel", data=f, file_name="backup.xlsx")
    else: st.warning("Bitte Passwort eingeben.")
