@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo ERRO: .venv nao encontrado. Rode: py -3.12 -m venv .venv
  echo Depois: .venv\Scripts\python.exe -m pip install -r requirements.txt
  exit /b 1
)

echo [aviso] O comando gerar ficou como apelido. Prefira agente-criativos.
".venv\Scripts\python.exe" gerar.py %*
exit /b %ERRORLEVEL%
