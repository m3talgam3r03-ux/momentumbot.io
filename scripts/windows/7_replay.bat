@echo off
setlocal
rem Rigioca lo storico del canale sui prezzi M1 con le regole del config. Nessun ordine.
cd /d "%~dp0..\.."
if not exist data\storico.jsonl goto :nostorico
if not exist data\xauusd_m1.csv goto :noprezzi
set /p OFFSET=Scarto server-UTC in ore (stampato da 6_esporta_prezzi_mt5.bat, es. 3): 
.venv\Scripts\python -m momentum_master.replay --storico data\storico.jsonl --prezzi data\xauusd_m1.csv --offset-server %OFFSET% --out data\replay.md
if errorlevel 1 goto :errore
echo.
echo Rapporto salvato in data\replay.md: mandalo a Claude.
pause
exit /b 0

:nostorico
echo Manca data\storico.jsonl: converti prima l'export di Telegram (vedi README).
pause
exit /b 1

:noprezzi
echo Manca data\xauusd_m1.csv: esegui prima 6_esporta_prezzi_mt5.bat
pause
exit /b 1

:errore
echo.
echo ERRORE: copia le ultime righe e mandale a Claude.
pause
exit /b 1
