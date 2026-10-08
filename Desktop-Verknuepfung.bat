@echo off
REM =====================================================================
REM  Legt einen Startknopf fuer die Verschnittoptimierung auf den Desktop.
REM
REM  Doppelklick genuegt. Die Verknuepfung zeigt auf start_nesting.bat
REM  in diesem Ordner - der Ordner darf danach nicht mehr verschoben
REM  oder umbenannt werden, sonst findet die Verknuepfung ihr Ziel nicht.
REM
REM  Aufruf mit /still unterdrueckt die Meldungen (so ruft
REM  start_nesting.bat diese Datei auf).
REM =====================================================================
setlocal
set "ORDNER=%~dp0"
set "NAME=Nesting - Verschnittoptimierung"
set "STILL="
if /i "%~1"=="/still" set "STILL=1"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ordner = $env:ORDNER.TrimEnd('\'); $schale = New-Object -ComObject WScript.Shell; $pfad = Join-Path $schale.SpecialFolders('Desktop') ($env:NAME + '.lnk'); $v = $schale.CreateShortcut($pfad); $v.TargetPath = Join-Path $ordner 'start_nesting.bat'; $v.WorkingDirectory = $ordner; $symbol = Join-Path $ordner 'nesting.ico'; if (Test-Path $symbol) { $v.IconLocation = $symbol }; $v.Description = 'Verschnittoptimierung - Meingassner Metalltechnik'; $v.Save()"
if errorlevel 1 goto fehler
if defined STILL goto ende

echo.
echo   Fertig. Auf dem Desktop liegt jetzt der Knopf
echo   "%NAME%".
echo.
pause
goto ende

:fehler
if defined STILL goto ende
echo.
echo   Die Verknuepfung konnte nicht angelegt werden.
echo   Notfalls von Hand: Rechtsklick auf start_nesting.bat,
echo   dann "Senden an" - "Desktop (Verknuepfung erstellen)".
echo.
pause

:ende
endlocal
