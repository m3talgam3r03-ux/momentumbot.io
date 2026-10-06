@echo off
setlocal
rem Esporta i prezzi M1 dell'oro da MetaTrader 5 (terminale FPG aperto, anche DEMO).
cd /d "%~dp0..\.."
.venv\Scripts\python -m pip install -q -r requirements-windows.txt
if errorlevel 1 goto :errore
set /p SIMBOLO=Nome esatto del simbolo dell'oro sul conto (es. XAUUSD oppure XAUUSD-e): 
set /p DAL=Dal giorno (AAAA-MM-GG, es. 2026-08-25): 
set /p AL=Al giorno escluso (AAAA-MM-GG, es. 2026-10-07): 
.venv\Scripts\python -m momentum_master.replay.export_mt5 --simbolo "%SIMBOLO%" --dal %DAL% --al %AL% --out data\xauusd_m1.csv
if errorlevel 1 goto :errore
echo.
echo Fatto. Annota lo "scarto server-UTC" stampato qui sopra: serve per il replay.
pause
exit /b 0

:errore
echo.
echo ERRORE: copia le ultime righe e mandale a Claude.
pause
exit /b 1
