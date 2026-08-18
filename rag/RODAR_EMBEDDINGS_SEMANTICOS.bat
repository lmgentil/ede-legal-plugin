@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo  RAG JURIDICO - Geracao de embeddings semanticos
echo ============================================================
echo.

where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (
  echo [ERRO] Python nao encontrado.
  echo Instale em https://www.python.org/downloads/
  echo e marque a opcao "Add Python to PATH" durante a instalacao.
  pause
  exit /b 1
)

echo [1/2] Instalando dependencias (pode demorar varios minutos na 1a vez)...
%PY% -m pip install sentence-transformers pandas pyarrow scikit-learn joblib rank_bm25 pyyaml "huggingface_hub<1.0"
if errorlevel 1 (
  echo [ERRO] Falha ao instalar dependencias.
  pause
  exit /b 1
)

echo.
echo [2/2] Gerando embeddings semanticos...
echo (na 1a execucao o modelo de ~1 GB sera baixado - aguarde)
set HF_HUB_DISABLE_XET=1
%PY% build_embeddings_semantic.py
if errorlevel 1 (
  echo [ERRO] Falha na geracao dos embeddings.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo  CONCLUIDO! A busca hibrida ja usara os vetores semanticos.
echo  Teste com:
echo    %PY% search_hybrid.py "resposta do reu prazo"
echo ============================================================
pause
