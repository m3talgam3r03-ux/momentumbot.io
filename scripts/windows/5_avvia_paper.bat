@echo off
setlocal
rem Avvia il bot in PAPER: legge il gruppo, classifica e decide, NON invia ordini.
rem Per fermarlo: chiudi la finestra o premi Ctrl+C.
cd /d "%~dp0..\.."
if not exist .env goto :noenv
.venv\Scripts\python -m momentum_master.config config\config.yaml
if errorlevel 1 goto :errore
.venv\Scripts\python -m momentum_master.listener --config config\config.yaml --db data\momentum.sqlite
pause
exit /b 0

:noenv
echo Manca il file .env: esegui prima 1_installa.bat
pause
exit /b 1

:errore
echo.
echo Il config non e' valido: leggi l'errore qui sopra.
pause
exit /b 1
