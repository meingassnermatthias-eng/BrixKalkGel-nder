@echo off
REM =====================================================================
REM  Verschnittoptimierung (Nesting) starten - Windows
REM
REM  Doppelklick genuegt. Beim ersten Start wird eine eigene
REM  Python-Umgebung im Ordner .venv angelegt und die benoetigten
REM  Pakete werden installiert - das dauert einige Minuten.
REM  Jeder weitere Start geht dann sofort.
REM
REM  Voraussetzung: Python 3.10 oder neuer von python.org,
REM  bei der Installation "Add Python to PATH" ankreuzen.
REM =====================================================================
cd /d "%~dp0"
title Nesting - Verschnittoptimierung

set PYTHON=python
where py >nul 2>&1
if %errorlevel%==0 set PYTHON=py

%PYTHON% --version >nul 2>&1
if not %errorlevel%==0 (
    echo.
    echo   Python wurde nicht gefunden.
    echo   Bitte von https://www.python.org/downloads/ installieren
    echo   und dabei "Add Python to PATH" ankreuzen.
    echo.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo   Erster Start: richte die Python-Umgebung ein ...
    echo.
    %PYTHON% -m venv .venv
    if not %errorlevel%==0 goto fehler
    call ".venv\Scripts\python.exe" -m pip install --upgrade pip
    call ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if not %errorlevel%==0 goto fehler
    echo.
    echo   Einrichtung fertig.
    echo.
)

echo   Starte die Verschnittoptimierung - der Browser oeffnet sich gleich.
echo   Zum Beenden dieses Fenster schliessen oder Strg+C druecken.
echo.
call ".venv\Scripts\python.exe" -m streamlit run app_nesting.py
goto ende

:fehler
echo.
echo   Die Einrichtung ist fehlgeschlagen. Bitte den Text oben
echo   an die EDV weitergeben.
echo.
pause
exit /b 1

:ende
