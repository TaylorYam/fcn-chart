@echo off
rem 連線診斷：測試能否連到 Yahoo、TradingView、CDN，結果存成 diagnose.txt。
chcp 65001 >nul
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo 找不到 uv，請先安裝：https://docs.astral.sh/uv/getting-started/installation/
  pause
  exit /b 1
)
set "UV_NATIVE_TLS=1"
set "PYTHONIOENCODING=utf-8"
uv run python -m fcn_chart.diagnose
pause
