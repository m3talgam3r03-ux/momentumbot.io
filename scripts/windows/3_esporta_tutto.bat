@echo off
setlocal
rem Export completo dello storico + rapporto di esplorazione. Rilancialo se si interrompe: riprende.
cd /d "%~dp0..\.."

if not exist .env goto :noenv
set /p CANALE=Username del canale, es. @nomecanale, oppure id -100...: 
.venv\Scripts\python -m momentum_master.exporter export --channel "%CANALE%" --out data\storico.jsonl
if errorlevel 1 goto :errore
.venv\Scripts\python -m momentum_master.analysis --file data\storico.jsonl --out data\esplorazione.md
if errorlevel 1 goto :errore

echo.
echo EXPORT COMPLETATO. Manda a Claude questi 3 file della cartella data:
echo   storico.jsonl   storico.summary.json   esplorazione.md
echo NON mandare MAI il file .env ne' i file .session
explorer data
pause
exit /b 0

:noenv
echo Manca il file .env: esegui prima 1_installa.bat
pause
exit /b 1

:errore
echo.
echo ERRORE. Rilancia questo file: l'export riprende da dove si era fermato.
echo Se l'errore si ripete, copia le ultime righe e mandale a Claude, togliendo chiavi e numeri.
pause
exit /b 1
