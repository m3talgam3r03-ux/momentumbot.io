@echo off
setlocal
rem Installa l'ambiente Python del progetto, lancia i test e prepara il file .env.
cd /d "%~dp0..\.."

where python >nul 2>nul
if errorlevel 1 goto :nopython
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 goto :vecchio

if not exist .venv\Scripts\python.exe python -m venv .venv
if errorlevel 1 goto :errore
.venv\Scripts\python -m pip install --upgrade pip
if errorlevel 1 goto :errore
.venv\Scripts\python -m pip install -r requirements-dev.txt
if errorlevel 1 goto :errore
.venv\Scripts\python -m pip install -e .
if errorlevel 1 goto :errore
.venv\Scripts\python -m pytest
if errorlevel 1 goto :errore

if exist .env goto :fine
copy .env.example .env >nul
echo.
echo Si apre il file .env: compila TG_API_ID e TG_API_HASH, salva e chiudi Blocco note.
notepad .env

:fine
echo.
echo INSTALLAZIONE COMPLETATA. Prossimo passo: 2_esporta_prova.bat
pause
exit /b 0

:nopython
echo Python non trovato. Installa Python 3.12 da python.org spuntando "Add python.exe to PATH".
pause
exit /b 1

:vecchio
echo Serve Python 3.11 o successivo. Versione trovata:
python --version
echo Installa Python 3.12 da python.org spuntando "Add python.exe to PATH".
pause
exit /b 1

:errore
echo.
echo ERRORE. Copia le ultime righe rosse e mandale a Claude, togliendo chiavi e numeri di telefono.
pause
exit /b 1
