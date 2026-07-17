@echo off
rem Avvio di BrioFEview per i test (fase alpha).
rem Preferisce il sorgente Python (sempre aggiornato); l'exe di dist e' solo
rem un fallback se Python non e' disponibile.
rem Puoi anche trascinare un file .xml/.p7m o una cartella su questo .bat.

setlocal
cd /d "%~dp0"

where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw -m visualizzatore %*
    goto :eof
)
where python >nul 2>nul
if %errorlevel%==0 (
    python -m visualizzatore %*
    goto :eof
)

if exist "dist\BrioFEview\BrioFEview.exe" (
    start "" "dist\BrioFEview\BrioFEview.exe" %*
) else (
    echo Python non trovato e nessun exe compilato in dist\.
    pause
)
