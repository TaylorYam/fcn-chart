@echo off
rem 雙擊啟動 FCN Chart：第一次執行會自動安裝相依套件，之後自動開啟瀏覽器。
chcp 65001 >nul
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo 找不到 uv，請先安裝：https://docs.astral.sh/uv/getting-started/installation/
  pause
  exit /b 1
)
rem 公司網路常用自有根憑證做 HTTPS 檢查：讓 uv 改用 Windows 憑證存放區，才連得上 PyPI。
set "UV_NATIVE_TLS=1"
uv run fcn-chart
pause
