@echo off
setlocal
rem Elenca i gruppi Telegram che contengono il testo indicato, con il loro id (sola lettura).
cd /d "%~dp0..\.."
if not exist .env goto :noenv
set /p TESTO=Parte del nome del gruppo (es. MOMENTUM oppure SALA): 
.venv\Scripts\python -m momentum_master.listener --trova-gruppo "%TESTO%"
echo.
echo Copia l'id del gruppo giusto (numero negativo) in config\config.yaml alla voce telegram: group_id
pause
exit /b 0

:noenv
echo Manca il file .env: esegui prima 1_installa.bat
pause
exit /b 1
