@echo off
setlocal
rem Prova: esporta i primi 50 messaggi dello storico in data\prova.jsonl
cd /d "%~dp0..\.."

if not exist .env goto :noenv
set /p CANALE=Username del canale, es. @nomecanale, oppure id -100...: 
if exist data\prova.jsonl del data\prova.jsonl
.venv\Scripts\python -m momentum_master.exporter export --channel "%CANALE%" --out data\prova.jsonl --limit 50
if errorlevel 1 goto :errore

echo.
echo PROVA RIUSCITA. Controlla che i messaggi siano 50 e le date sensate.
echo Prossimo passo: 3_esporta_tutto.bat
pause
exit /b 0

:noenv
echo Manca il file .env: esegui prima 1_installa.bat
pause
exit /b 1

:errore
echo.
echo ERRORE. Copia le ultime righe e mandale a Claude, togliendo chiavi e numeri di telefono.
pause
exit /b 1
