@echo off
REM =====================================================================
REM  Verschnittoptimierung (Nesting) starten - Windows
REM
REM  Doppelklick genuegt.
REM  Fehlt Python, bietet das Skript die Installation an.
REM  Beim ersten Start werden ausserdem die benoetigten Pakete geladen -
REM  das dauert einige Minuten. Jeder weitere Start geht sofort.
REM =====================================================================
cd /d "%~dp0"
title Nesting - Verschnittoptimierung
setlocal enabledelayedexpansion

REM ---------------------------------------------------------------
REM  1. Python suchen
REM ---------------------------------------------------------------
set PYTHON=
for %%P in (py python) do (
    if not defined PYTHON (
        %%P -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>&1
        if !errorlevel!==0 set PYTHON=%%P
    )
)

REM  frisch per winget installiertes Python ist noch nicht im PATH
if not defined PYTHON (
    for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%D\python.exe" set PYTHON="%%D\python.exe"
    )
)

REM ---------------------------------------------------------------
REM  2. Python bei Bedarf installieren
REM ---------------------------------------------------------------
if not defined PYTHON (
    echo.
    echo   Python ist auf diesem Rechner noch nicht installiert.
    echo   Es wird einmalig gebraucht, damit das Programm laufen kann.
    echo.
    where winget >nul 2>&1
    if !errorlevel!==0 (
        set /p ANTWORT="  Jetzt automatisch installieren? [J/N] "
        if /i "!ANTWORT!"=="J" (
            echo.
            echo   Installiere Python ... bitte warten.
            echo.
            winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
            echo.
            echo   ============================================================
            echo    Python wurde installiert.
            echo    Bitte dieses Fenster schliessen und start_nesting.bat
            echo    noch einmal doppelklicken.
            echo   ============================================================
            echo.
            pause
            exit /b 0
        )
    )
    echo.
    echo   Bitte Python von https://www.python.org/downloads/ installieren
    echo   und dabei "Add Python to PATH" ankreuzen.
    echo   Danach start_nesting.bat erneut doppelklicken.
    echo.
    pause
    exit /b 1
)

REM ---------------------------------------------------------------
REM  3. Eigene Umgebung anlegen und Pakete laden
REM ---------------------------------------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo   Erster Start: richte die Arbeitsumgebung ein.
    echo   Das dauert ein paar Minuten - bitte das Fenster offen lassen.
    echo.
    %PYTHON% -m venv .venv
    if not !errorlevel!==0 goto fehler
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if not !errorlevel!==0 goto fehler
    echo.
    echo   Einrichtung fertig.
    echo.
)

REM ---------------------------------------------------------------
REM  4. Starten
REM ---------------------------------------------------------------
echo   Starte die Verschnittoptimierung - der Browser oeffnet sich gleich.
echo   Zum Beenden dieses Fenster schliessen oder Strg+C druecken.
echo.
".venv\Scripts\python.exe" -m streamlit run app_nesting.py
goto ende

:fehler
echo.
echo   Die Einrichtung ist fehlgeschlagen.
echo   Bitte den Text oben abfotografieren und weitergeben.
echo.
pause
exit /b 1

:ende
endlocal
