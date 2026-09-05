#!/usr/bin/env bash
# =====================================================================
#  Verschnittoptimierung (Nesting) starten - macOS und Linux
#
#  Einmalig ausfuehrbar machen:  chmod +x start_nesting.sh
#  Danach starten mit:           ./start_nesting.sh
#
#  Beim ersten Start wird eine eigene Python-Umgebung im Ordner .venv
#  angelegt und die benoetigten Pakete werden installiert.
# =====================================================================
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 wurde nicht gefunden. Bitte Python 3.10 oder neuer installieren."
    exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
    echo
    echo "  Erster Start: richte die Python-Umgebung ein ..."
    echo
    python3 -m venv .venv
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/python -m pip install -r requirements.txt
    echo
    echo "  Einrichtung fertig."
    echo
fi

echo "  Starte die Verschnittoptimierung - der Browser oeffnet sich gleich."
echo "  Zum Beenden Strg+C druecken."
echo
exec .venv/bin/python -m streamlit run app_nesting.py
