import streamlit as st
import math
import pandas as pd
from fpdf import FPDF
import datetime
import base64
import os
from streamlit_pdf_viewer import pdf_viewer

# --- 1. DATENBANK (Komplex) ---
class ZaunDatabase:
    def __init__(self, preisfaktor=1.0):
        self.faktor = preisfaktor

        # A. MATTEN (Preise pro Stück)
        self.matten_preise = {
            "Leicht 6/5/6": {830: 35.00, 1030: 42.00, 1230: 49.00, 1430: 58.00, 1630: 65.00, 1830: 75.00, 2030: 85.00},
            "Schwer 8/6/8": {830: 48.00, 1030: 58.00, 1230: 69.00, 1430: 79.00, 1630: 89.00, 1830: 99.00, 2030: 110.00}
        }

        # B. ZAUNSTEHER (Typen & Preise)
        # Preise hier beispielhaft für Höhe 1230mm - müssten für alle Höhen hinterlegt werden
        # Wir nutzen hier einen Basisfaktor pro Höhe zur Vereinfachung
        self.steher_basis = {
            "Rechteck 60x40 (Standard)": 30.00,
            "Rundrohr 60mm": 35.00,
            "Typ SL 60 (Klemmschiene)": 45.00,
            "Typ 70k (Design)": 55.00
        }

        # C. TOR-PREISLISTE (Matrix: Bis Breite / Bis Höhe)
        # Struktur: {'Typ': [ {'max_b': 1000, 'max_h': 1200, 'preis': 400}, ... ]}
        self.tore_db = {
            "Gehtür 1-flg": [
                {'max_b': 1000, 'max_h': 1250, 'preis': 450.00},
                {'max_b': 1000, 'max_h': 2000, 'preis': 550.00},
                {'max_b': 1250, 'max_h': 1250, 'preis': 520.00},
                {'max_b': 1250, 'max_h': 2000, 'preis': 620.00},
            ],
            "Einfahrtstor 2-flg": [
                {'max_b': 3000, 'max_h': 1250, 'preis': 1200.00},
                {'max_b': 3000, 'max_h': 2000, 'preis': 1400.00},
                {'max_b': 4000, 'max_h': 1250, 'preis': 1500.00},
                {'max_b': 4000, 'max_h': 2000, 'preis': 1800.00},
            ],
            "Schiebetor (Freitragend)": [
                {'max_b': 3500, 'max_h': 1400, 'preis': 2800.00},
                {'max_b': 4500, 'max_h': 1400, 'preis': 3500.00},
            ]
        }

        # D. TORSÄULEN (Paarpreis oder Einzeln je nach Tor, hier Pauschal pro Tor angenommen)
        self.torsaeulen = {
            "Standard (Quadratrohr)": 150.00,
            "Verstärkt (für große Tore)": 300.00,
            "Alu-Design": 400.00
        }

        # E. MONTAGE MATERIAL
        self.beton_sack_preis = 9.00 # Fertigbeton pro Sack
        self.konsole_preis = 25.00   # Fußplatte pro Stück
        self.montagemat_preis = 8.00 # Schrauben/Anker pro Steher

        # F. EXTRAS
        self.sichtschutz = {
            "Keiner": 0.00,
            "Rolle (Weich-PVC, 35m)": 59.00,  # Preis pro Rolle
            "Hart-PVC Streifen (Set)": 110.00 # Preis pro Matte (ca 2.5m)
        }
        
        self.tor_zubehoer = {
            "Schloss + Drücker": 80.00,
            "E-Öffner Vorbereitung": 45.00,
            "Bodenriegel": 30.00,
            "Zackenleiste (Übersteigschutz)": 25.00
        }

        self.farben = {"Verzinkt": 1.0, "RAL 6005 (Moosgrün)": 1.15, "RAL 7016 (Anthrazit)": 1.15, "Sonderfarbe": 1.30}

    # HILFSFUNKTIONEN
    def get_matte_preis(self, typ, hoehe):
        verf = sorted(self.matten_preise[typ].keys())
        passende_h = min(verf, key=lambda x: abs(x - hoehe))
        return self.matten_preise[typ][passende_h] * self.faktor, passende_h

    def get_tor_preis(self, modell, b_lichte, h_tor):
        # Suche den günstigen Preis, der von den Maßen her passt (nächstgrößere Größe)
        moegliche = self.tore_db.get(modell, [])
        passende = [t for t in moegliche if t['max_b'] >= b_lichte and t['max_h'] >= h_tor]
        
        if not passende:
            # Falls Maße zu groß, nimm das größte + 20% Individualzuschlag
            teuerstes = max(moegliche, key=lambda x: x['preis'])
            return teuerstes['preis'] * 1.20 * self.faktor, True # True = Übergröße
        
        # Nimm das günstigste der passenden
        bester_treffer = min(passende, key=lambda x: x['preis'])
        return bester_treffer['preis'] * self.faktor, False

# --- SESSION STATE INITIALISIEREN (Für Tor-Liste) ---
if 'gates' not in st.session_state:
    st.session_state['gates'] = []

def add_gate(typ, sl, th, saeulen, zubehoer_liste):
    st.session_state['gates'].append({
        "typ": typ, "sl": sl, "th": th, "saeulen": saeulen, "zubehoer": zubehoer_liste
    })

def remove_gate(index):
    st.session_state['gates'].pop(index)

# --- RECHNER LOGIK ---
def berechne_gesamt(d, db):
    # 1. ZAUN
    matten_len = 2.5
    anz_matten = math.ceil(d['zaun_laenge'] / matten_len)
    
    # Preis Matte
    p_matte, real_h = db.get_matte_preis(d['matten_typ'], d['zaun_hoehe'])
    k_matten = anz_matten * p_matte * db.farben[d['farbe']]

    # Steher (Matten + 1 + Ecken)
    anz_steher = anz_matten + 1 + d['ecken']
    # Steherpreis ist hier simuliert über Basisfaktor je nach Höhe
    hoehen_faktor = (d['zaun_hoehe'] / 1000) 
    p_steher_basis = db.steher_basis[d['steher_typ']] * hoehen_faktor
    k_steher = anz_steher * p_steher_basis * db.farben[d['farbe']] * db.faktor

    # 2. BEFESTIGUNG / FUNDAMENT
    k_fundament = 0
    k_beton = 0
    details_montage = ""

    if d['montage_art'] == "Einbetonieren":
        # Säcke berechnen
        saecke_pro_steher = d['beton_saecke_input']
        total_saecke = anz_steher * saecke_pro_steher
        k_beton = total_saecke * db.beton_sack_preis
        details_montage = f"{total_saecke} Sack Fertigbeton"
    else:
        # Auf Fundament
        k_konsolen = anz_steher * db.konsole_preis
        k_material = anz_steher * db.montagemat_preis
        k_fundament = (k_konsolen + k_material) * db.faktor
        details_montage = f"{anz_steher}x Konsole + Montagematerial"

    # 3. SICHTSCHUTZ
    k_sichtschutz = 0
    if d['sichtschutz_typ'] == "Rolle (Weich-PVC, 35m)":
        # Wieviele Rollen? Länge / 35
        anz_rollen = math.ceil(d['zaun_laenge'] / 35)
        k_sichtschutz = anz_rollen * db.sichtschutz[d['sichtschutz_typ']]
    elif d['sichtschutz_typ'] == "Hart-PVC Streifen (Set)":
        # Pro Matte ein Set
        k_sichtschutz = anz_matten * db.sichtschutz[d['sichtschutz_typ']]
    
    k_sichtschutz *= db.farben[d['farbe']] # Farbe auch für Sichtschutz relevant? Meistens ja.

    # 4. TORE (Aus Liste)
    k_tore_total = 0
    tor_details = []
    
    for gate in st.session_state['gates']:
        p_basis, is_over = db.get_tor_preis(gate['typ'], gate['sl'], gate['th'])
        p_basis *= db.farben[d['farbe']]
        
        # Torsäulen
        p_saeulen = db.torsaeulen[gate['saeulen']] * db.faktor
        
        # Zubehör
        p_zub = sum([db.tor_zubehoer[z] for z in gate['zubehoer']]) * db.faktor
        
        p_gate_total = p_basis + p_saeulen + p_zub
        k_tore_total += p_gate_total
        
        tor_details.append({
            "text": f"{gate['typ']} ({gate['sl']}x{gate['th']}mm)",
            "preis": p_gate_total,
            "saeulen": gate['saeulen'],
            "zub": ", ".join(gate['zubehoer'])
        })

    # 5. MONTAGE ARBEIT
    k_arbeit = d['arb_stunden'] * d['arb_satz']

    # GESAMT
    summe_netto = k_matten + k_steher + k_fundament + k_beton + k_sichtschutz + k_tore_total + k_arbeit
    
    return {
        "detail": {
            "matten": {"m": anz_matten, "p": k_matten},
            "steher": {"m": anz_steher, "p": k_steher},
            "montage_mat": {"txt": details_montage, "p": k_fundament + k_beton},
            "sicht": {"p": k_sichtschutz},
            "tore": tor_details,
            "arbeit": k_arbeit
        },
        "netto": summe_netto,
        "mwst": summe_netto * 0.20,
        "brutto": summe_netto * 1.20,
        "input": d
    }

# --- PDF ERSTELLUNG ---
def create_pdf(res, db):
    pdf = FPDF()
    pdf.add_page()
    def txt(s): return str(s).encode('latin-1', 'replace').decode('latin-1')

    # Header
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt("ZAUN & TOR ANGEBOT"), ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 10, txt(f"Datum: {datetime.date.today().strftime('%d.%m.%Y')}"), ln=True, align='R')
    
    d = res['input']
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, txt(f"Farbe: {d['farbe']} | Matten: {d['matten_typ']}"), ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 6, txt(f"Zaunlänge: {d['zaun_laenge']}m | Höhe: {d['zaun_hoehe']}mm"), ln=True)
    pdf.cell(0, 6, txt(f"Montage auf: {d['montage_art']}"), ln=True)
    pdf.ln(5)

    # Tabelle
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(130, 8, txt("Position"), 1, 0, 'L', 1)
    pdf.cell(60, 8, txt("Preis (Netto)"), 1, 1, 'R', 1)
    pdf.set_font("Arial", '', 10)

    def row(pos, val):
        pdf.cell(130, 8, txt(pos), 1)
        pdf.cell(60, 8, txt(f"{val:,.2f} EUR"), 1, 1, 'R')

    # Positionen
    det = res['detail']
    row(f"Gittermatten ({det['matten']['m']} Stk)", det['matten']['p'])
    row(f"Zaunsteher ({det['steher']['m']} Stk) - {d['steher_typ']}", det['steher']['p'])
    
    if det['montage_mat']['p'] > 0:
        row(f"Montagematerial ({det['montage_mat']['txt']})", det['montage_mat']['p'])
        
    if det['sicht']['p'] > 0:
        row(f"Sichtschutz: {d['sichtschutz_typ']}", det['sicht']['p'])
        
    # Tore einzeln listen
    for t in det['tore']:
        t_text = f"Tor: {t['text']} inkl. {t['saeulen']}"
        row(t_text, t['preis'])
        if t['zub']:
            pdf.set_font("Arial", 'I', 8)
            pdf.cell(190, 5, txt(f"   Zubehör: {t['zub']}"), 0, 1)
            pdf.set_font("Arial", '', 10)

    if det['arbeit'] > 0:
        row(f"Montagearbeit ({d['arb_stunden']} Std)", det['arbeit'])

    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(130, 10, txt("GESAMT NETTO"), 0, 0, 'R')
    pdf.cell(60, 10, txt(f"{res['netto']:,.2f} EUR"), 1, 1, 'R')
    pdf.cell(130, 10, txt("MwSt (20%)"), 0, 0, 'R')
    pdf.cell(60, 10, txt(f"{res['mwst']:,.2f} EUR"), 1, 1, 'R')
    pdf.set_fill_color(200, 255, 200)
    pdf.cell(130, 10, txt("GESAMT BRUTTO"), 0, 0, 'R')
    pdf.cell(60, 10, txt(f"{res['brutto']:,.2f} EUR"), 1, 1, 'R', 1)

    return pdf.output(dest='S').encode('latin-1')

# --- MAIN APP ---
def main():
    st.set_page_config(page_title="Profi Zaun-Kalkulator", page_icon="🚧", layout="wide")
    
    with st.sidebar:
        st.header("Admin")
        faktor = st.number_input("Preisfaktor:", 0.5, 2.0, 1.0, 0.01)
    
    db = ZaunDatabase(faktor)
    st.title("🚧 Profi-Kalkulator: Drahtgitter & Tore")

    col_L, col_R = st.columns([1, 1])

    with col_L:
        tab_zaun, tab_tore, tab_mont = st.tabs(["📏 Zaun", "🚪 Tore (+)", "🔨 Montage"])

        with tab_zaun:
            st.subheader("Zaun Konfiguration")
            typ = st.selectbox("Matten-Typ:", list(db.matten_preise.keys()))
            farbe = st.selectbox("Farbe:", list(db.farben.keys()))
            
            c1, c2 = st.columns(2)
            laenge = c1.number_input("Zaunlänge (ohne Tore) in m:", 1.0, 1000.0, 10.0, 0.5)
            hoehe = c2.select_slider("Höhe (mm):", options=[830, 1030, 1230, 1430, 1630, 1830, 2030], value=1230)
            
            steher = st.selectbox("Steher-Typ:", list(db.steher_basis.keys()))
            ecken = st.number_input("Anzahl Ecken:", 0, 50, 0)
            
            st.divider()
            sicht = st.selectbox("Sichtschutz:", list(db.sichtschutz.keys()))

        with tab_tore:
            st.subheader("Tor hinzufügen")
            with st.form("tor_form"):
                t_mod = st.selectbox("Modell:", list(db.tore_db.keys()))
                c_t1, c_t2 = st.columns(2)
                t_sl = c_t1.number_input("Säulenlichte (SL) mm:", 800, 6000, 1000, 50)
                t_th = c_t2.number_input("Torhöhe (TH) mm:", 800, 2500, 1200, 50)
                
                t_saeule = st.selectbox("Torsäulen:", list(db.torsaeulen.keys()))
                t_zub = st.multiselect("Zubehör:", list(db.tor_zubehoer.keys()))
                
                add_btn = st.form_submit_button("➕ Tor zur Liste hinzufügen")
                if add_btn:
                    add_gate(t_mod, t_sl, t_th, t_saeule, t_zub)
                    st.success("Tor hinzugefügt!")
                    st.rerun()

            # Liste anzeigen
            if st.session_state['gates']:
                st.write("### Gewählte Tore:")
                for i, g in enumerate(st.session_state['gates']):
                    col_info, col_del = st.columns([4, 1])
                    with col_info:
                        st.info(f"Position {i+1}: {g['typ']} | SL:{g['sl']} | TH:{g['th']} | {g['saeulen']}")
                    with col_del:
                        if st.button("🗑️", key=f"del_{i}"):
                            remove_gate(i)
                            st.rerun()

        with tab_mont:
            st.subheader("Befestigung")
            m_art = st.radio("Montageart:", ["Einbetonieren", "Auf Fundament (dübeln)"])
            
            if m_art == "Einbetonieren":
                saecke = st.number_input("Säcke Beton pro Steher:", 1, 10, 2, help="9€ pro Sack")
            else:
                saecke = 0
                st.info("Berechnet automatisch Konsolen & Anker.")

            st.divider()
            h_std = st.number_input("Arbeitszeit (Std):", 0.0, 500.0, 0.0)
            h_satz = st.number_input("Stundensatz (€):", 0.0, 200.0, 65.0)

    # RECHTS: ERGEBNIS
    with col_R:
        # Berechnen
        inp = {
            "matten_typ": typ, "farbe": farbe, "zaun_laenge": laenge, "zaun_hoehe": hoehe,
            "steher_typ": steher, "ecken": ecken, "sichtschutz_typ": sicht,
            "montage_art": m_art, "beton_saecke_input": saecke,
            "arb_stunden": h_std, "arb_satz": h_satz
        }
        res = berechne_gesamt(inp, db)

        st.subheader("Kalkulation")
        k1, k2, k3 = st.columns(3)
        k1.metric("Netto", f"€ {res['netto']:,.2f}")
        k2.metric("MwSt", f"€ {res['mwst']:,.2f}")
        k3.metric("Brutto", f"€ {res['brutto']:,.2f}")
        
        st.markdown("---")
        # Detail Tabelle
        rows = [
            ["Zaunmatten", f"€ {res['detail']['matten']['p']:,.2f}"],
            ["Steher", f"€ {res['detail']['steher']['p']:,.2f}"],
            ["Montage-Mat.", f"€ {res['detail']['montage_mat']['p']:,.2f}"],
        ]
        if res['detail']['sicht']['p'] > 0:
            rows.append(["Sichtschutz", f"€ {res['detail']['sicht']['p']:,.2f}"])
        
        # Tore Summe
        sum_tore = sum([t['preis'] for t in res['detail']['tore']])
        if sum_tore > 0:
            rows.append(["Tore (Gesamt)", f"€ {sum_tore:,.2f}"])
            
        rows.append(["Arbeit", f"€ {res['detail']['arbeit']:,.2f}"])

        st.dataframe(pd.DataFrame(rows, columns=["Posten", "Summe"]), hide_index=True, use_container_width=True)

        # PDF Viewer + Download
        pdf_data = create_pdf(res, db)
        st.download_button("📄 Angebot PDF", pdf_data, "Angebot_Zaun.pdf", "application/pdf", type="primary")

        st.subheader("Preisliste")
        if os.path.exists("preisliste_draht.pdf"):
            pdf_viewer("preisliste_draht.pdf", height=600)

if __name__ == "__main__":
    main()
