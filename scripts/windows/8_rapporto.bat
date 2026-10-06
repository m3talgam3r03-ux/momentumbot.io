@echo off
setlocal
rem Rapporto della giornata dal registro della PAPER (sola lettura).
cd /d "%~dp0..\.."
if not exist data\momentum.sqlite goto :noreg
set /p GIORNO=Giorno (AAAA-MM-GG, invio = oggi): 
if "%GIORNO%"=="" (
  .venv\Scripts\python -m momentum_master.report data\momentum.sqlite > data\rapporto.md
) else (
  .venv\Scripts\python -m momentum_master.report data\momentum.sqlite --giorno %GIORNO% > data\rapporto.md
)
type data\rapporto.md
echo.
echo Salvato in data\rapporto.md
pause
exit /b 0

:noreg
echo Nessun registro: avvia prima la PAPER con 5_avvia_paper.bat
pause
exit /b 1
