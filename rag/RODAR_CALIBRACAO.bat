@echo off
cd /d "%~dp0"
where py >nul 2>nul && set "PY=py -3"
if not defined PY set "PY=python"
%PY% calibrar_confianca.py > calibracao_log.txt 2>&1
