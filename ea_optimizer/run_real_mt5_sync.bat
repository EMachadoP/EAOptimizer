@echo off
setlocal

set SCRIPT_DIR=%~dp0
set PYTHON_BIN=%LocalAppData%\Programs\Python\Python313\python.exe

if not exist "%PYTHON_BIN%" (
  echo Python 3.13 nao encontrado em "%PYTHON_BIN%".
  echo Ajuste o caminho no arquivo run_real_mt5_sync.bat se necessario.
  exit /b 1
)

set API_URL=%EAOPTIMIZER_REMOTE_API_URL%
if "%API_URL%"=="" set API_URL=https://eaoptimizer.onrender.com

set SYMBOL=%EAOPTIMIZER_MT5_SYMBOL%
if "%SYMBOL%"=="" set SYMBOL=XAUUSDm

set DAYS=%EAOPTIMIZER_SYNC_DAYS%
if "%DAYS%"=="" set DAYS=30

set MT5_PATH=%MT5_PATH%
if "%MT5_PATH%"=="" set MT5_PATH=C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe

echo ===============================================
echo EAOptimizer - Sincronizacao Real via MT5
echo API_URL=%API_URL%
echo SYMBOL=%SYMBOL%
echo DAYS=%DAYS%
echo MT5_PATH=%MT5_PATH%
echo ===============================================

"%PYTHON_BIN%" "%SCRIPT_DIR%sync_mt5_to_cloud.py" --api-url "%API_URL%" --symbol "%SYMBOL%" --days %DAYS% --mt5-path "%MT5_PATH%"

if errorlevel 1 (
  echo.
  echo Falha na sincronizacao real do MT5.
  exit /b 1
)

echo.
echo Sincronizacao concluida com sucesso.
exit /b 0
