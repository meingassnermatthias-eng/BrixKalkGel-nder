import streamlit as st
import pandas as pd
from fpdf import FPDF
import base64
import os
import tempfile
import math
from datetime import datetime

# --- 1. SETUP ---
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

# --- 2. EXCEL GENERATOR (JETZT MIT EDELSTAHL) ---
def generiere_neue_excel_datei():
    """Erstellt die katalog.xlsx mit ALLEN Inhalten neu"""
    
    startseite_data = {
        "System": [
            "1. Alu-Geländer Stab", "2. Alu-Geländer Flächig", "3. Alu-Geländer Glas", 
            "4. Alu-Zaun Stab & Latten", "5. Alu-Zaun Sichtschutz", "6. Alu-Tore", "7. Alu-Schiebetore",
            "8. Draht-Gittermatten (Smart)", "9. Draht-Geflecht & Stein", 
            "10. Stahl-Wangentreppe", "11. Zubehör & Extras",
            "12. Edelstahl-Geländer (Eigen)"  # <-- HIER NEU
        ],
        "Blattname": [
            "Brix_Gel_Stab", "Brix_Gel_Flaechig", "Brix_Gel_Glas",
            "Brix_Zaun_Stab", "Brix_Zaun_Sicht", "Brix_Tore", "Brix_Schiebe",
            "Draht_Matten", "Draht_Mix", 
            "Stahl_Treppe", "Extras",
            "Eigen_Edelstahl" # <-- NEUES BLATT
        ]
    }
    df_start = pd.DataFrame(startseite_data)

    # --- BRIX DATEN (Gekürzt für Übersicht) ---
    gel_stab_data = [
        {"Typ": "Zahl", "Bezeichnung": "Länge (m)", "Variable": "L", "Optionen": "", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Modell", "Variable": "P_Modell", "Optionen": "Decor 22:204, Staketen:169", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Farbe", "Variable": "F_Faktor", "Optionen": "Standard:1.0, Sonder:1.10", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Montage Steher", "Variable": "P_Steher", "Optionen": "Aufsatz:125, Seite:161", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Ecken", "Variable": "Ecken", "Optionen": "", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Montage (€/m)", "Variable": "P_Arbeit", "Optionen": "", "Formel": ""},
        {"Typ": "Preis", "Bezeichnung": "Gesamtpreis", "Variable": "Endpreis", "Optionen": "", "Formel": "(P_Modell * L * F_Faktor) + ((math.ceil(L/1.3)+1) * P_Steher * F_Faktor) + (Ecken * 95) + (L * P_Arbeit)"}
    ]
    df_gel_stab = pd.DataFrame(gel_stab_data)
    
    # Kopien der Brix-Struktur
    df_gel_flaechig = df_gel_stab.copy()
    df_gel_glas = df_gel_stab.copy()
    df_zaun_stab = df_gel_stab.copy()
    df_zaun_sicht = df_gel_stab.copy()
    df_tore = df_gel_stab.copy()
    df_schiebe = df_gel_stab.copy()

    # --- DRAHT MIT BETON LOGIK ---
    matten_data = [
        {"Typ": "Zahl", "Bezeichnung": "Länge (m)", "Variable": "L", "Optionen": "", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Preis/Sack Beton (€)", "Variable": "P_Sack", "Optionen": "", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Konsole Typ", "Variable": "P_Konsole", "Optionen": "---:0, Leicht:15, Schwer:45", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Montage-Art", "Variable": "Ist_Beton", "Optionen": "Einbetonieren:1, Aufdübeln:0", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Matte Höhe", "Variable": "P_Matte", "Optionen": "H 1030:22, H 1230:26", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Säulen-Typ", "Variable": "P_Saeule", "Optionen": "Klemmhalter:35", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Farbe", "Variable": "F_Faktor", "Optionen": "Verzinkt:1.0, Farbe:1.15", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Montage (€/m)", "Variable": "P_Arbeit", "Optionen": "", "Formel": ""},
        {"Typ": "Preis", "Bezeichnung": "Gesamtpreis", "Variable": "Endpreis", "Optionen": "", 
         "Formel": "(L * P_Matte * F_Faktor) + ((math.ceil(L/2.5)+1) * ((P_Saeule * F_Faktor) + (Ist_Beton * 2 * P_Sack) + ((1-Ist_Beton) * P_Konsole))) + (L * P_Arbeit)"}
    ]
    df_matten = pd.DataFrame(matten_data)
    
    df_draht_mix = df_gel_stab.copy()

    # --- STAHL TREPPE ---
    treppe_data = [
        {"Typ": "Zahl", "Bezeichnung": "Geschoßhöhe (m)", "Variable": "H", "Optionen": "", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Treppenbreite (B)", "Variable": "B", "Optionen": "800mm:0.8, 1000mm:1.0, 1200mm:1.2", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Gitterrost-Stufe", "Variable": "P_Stufe", "Optionen": "MW 30x30:40, MW 30x10:55", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Wangen-Profil (lfm)", "Variable": "P_Wange", "Optionen": "Flachstahl:60, U-Profil:85", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Oberfläche Wangen", "Variable": "F_Faktor", "Optionen": "Verzinkt:1.0, Pulver:1.3", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Podest-Länge (m)", "Variable": "L_Podest", "Optionen": "", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Podest-Belag (€/qm)", "Variable": "P_Rost", "Optionen": "Gitterrost:80, Tränenblech:90", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Stundensatz (€)", "Variable": "P_Satz", "Optionen": "", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Montagematerial", "Variable": "P_Mat", "Optionen": "", "Formel": ""},
        {"Typ": "Preis", "Bezeichnung": "Gesamtpreis", "Variable": "Endpreis", "Optionen": "", 
         "Formel": "(math.ceil(H/0.18) * P_Stufe) + ((H * 1.8 * 2) * P_Wange * F_Faktor) + (L_Podest * B * P_Rost) + ((H/2.7) * 12 * P_Satz) + P_Mat"}
    ]
    df_treppe = pd.DataFrame(treppe_data)

    # --- NEU: EDELSTAHL GELÄNDER (EIGEN) ---
    edelstahl_data = [
        {"Typ": "Zahl", "Bezeichnung": "Länge des Geländers (m)", "Variable": "L", "Optionen": "", "Formel": ""},
        {"Typ": "Auswahl", "Bezeichnung": "Modell", "Variable": "P_Modell", 
         "Optionen": "Relinggeländer 5 Stäbe:240, Relinggeländer 7 Stäbe:260, Glasgeländer (V2A+VSG):450, Nur Handlauf V2A:85", 
         "Formel": "Meterpreis Material"},
        {"Typ": "Auswahl", "Bezeichnung": "Steher-Profil", "Variable": "P_Steher", 
         "Optionen": "Rundrohr 42.4mm:90, Quadratrohr 40x40mm:110, Flachstahlsteher:130", 
         "Formel": "Stückpreis"},
        {"Typ": "Auswahl", "Bezeichnung": "Montageart Steher", "Variable": "P_Montageart", 
         "Optionen": "Aufgeschraubt (Boden):0, Stirnseitig (Wand):35", 
         "Formel": "Aufpreis pro Steher"},
        {"Typ": "Zahl", "Bezeichnung": "Anzahl Ecken", "Variable": "Ecken", "Optionen": "", "Formel": ""},
        {"Typ": "Zahl", "Bezeichnung": "Montage & Fertigung (€/m)", "Variable": "P_Arbeit", "Optionen": "", "Formel": ""},
        # Formel: (L * Meterpreis) + (Anzahl Steher * (SteherPreis + MontageAufpreis)) + Ecken + Arbeit
        # Steherabstand ca 1.2m
        {"Typ": "Preis", "Bezeichnung": "Gesamtpreis", "Variable": "Endpreis", "Optionen": "", 
         "Formel": "(L * P_Modell) + ((math.ceil(L/1.2)+1) * (P_Steher + P_Montageart)) + (Ecken * 150) + (L * P_Arbeit)"}
    ]
    df_edelstahl = pd.DataFrame(edelstahl_data)

    df_extras = pd.DataFrame([{"Typ":"Preis", "Bezeichnung":"Dummy", "Variable":"X", "Optionen":"", "Formel":"0"}])

    try:
        with pd.ExcelWriter(EXCEL_DATEI, engine="openpyxl") as writer:
            df_start.to_excel(writer, sheet_name="Startseite", index=False)
            df_gel_stab.to_excel(writer, sheet_name="Brix_Gel_Stab", index=False)
            df_gel_flaechig.to_excel(writer, sheet_name="Brix_Gel_Flaechig", index=False)
            df_gel_glas.to_excel(writer, sheet_name="Brix_Gel_Glas", index=False)
            df_zaun_stab.to_excel(writer, sheet_name="Brix_Zaun_Stab", index=False)
            df_zaun_sicht.to_excel(writer, sheet_name="Brix_Zaun_Sicht", index=False)
            df_tore.to_excel(writer, sheet_name="Brix_Tore", index=False)
            df_schiebe.to_excel(writer, sheet_name="Brix_Schiebe", index=False)
            df_matten.to_excel(writer, sheet_name="Draht_Matten", index=False)
            df_draht_mix.to_excel(writer, sheet_name="Draht_Mix", index=False)
            df_treppe.to_excel(writer, sheet_name="Stahl_Treppe", index=False)
            df_extras.to_excel(writer, sheet_name="Extras", index=False)
            # NEU
            df_edelstahl.to_excel(writer, sheet_name="Eigen_Edelstahl", index=False)
        return True
    except Exception as e:
        st.error(f"Fehler: {e}")
        return False

# --- 3. HELPER ---
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

# --- 4. SESSION STATE ---
if 'positionen' not in st.session_state: st.session_state['positionen'] = []
if 'kunden_daten' not in st.session_state: 
    st.session_state['kunden_daten'] = {"Name": "", "Strasse": "", "Ort": "", "Tel": "", "Email": "", "Notiz": ""}
if 'fertiges_pdf' not in st.session_state: st.session_state['fertiges_pdf'] = None
if 'zusatzkosten' not in st.session_state:
    st.session_state['zusatzkosten'] = {"kran": 0.0, "montage_mann": 2, "montage_std": 0.0, "montage_satz": 65.0}

# --- 5. PDF ENGINE ---
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

def create_pdf(positionen_liste, kunden_dict, fotos, montage_summe, kran_summe, zeige_details):
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
        text_montage = "Montagearbeiten (lt. Angabe)" if zeige_details else "Montagearbeiten (Pauschal)"
        pdf.cell(w_desc, 8, clean_text(text_montage), 1, 0, 'L')
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
            
            zeige_details = st.checkbox("Details (Stunden/Satz) im PDF anzeigen?", value=True)
            
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
                pdf_bytes = create_pdf(st.session_state['positionen'], st.session_state['kunden_daten'], fotos, m_sum, k_sum, zeige_details)
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
        st.info("Setzt ALLE Kataloge zurück (Alu, Draht, Treppe, Edelstahl).")
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
