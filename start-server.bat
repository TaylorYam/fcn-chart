@echo off
rem 內網共用模式：先自動更新到最新版，再啟動讓同事可以從公司內網連線。
rem 只在公司網路使用；第一次啟動時 Windows 防火牆若詢問，請只允許「私人網路」。
chcp 65001 >nul
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo 找不到 uv，請先安裝：https://docs.astral.sh/uv/getting-started/installation/
  pause
  exit /b 1
)

set "BRANCH="
for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set "BRANCH=%%b"
if /i "%BRANCH%"=="main" (
  echo 正在更新到最新版...
  git pull --ff-only
  if errorlevel 1 echo [警告] 自動更新失敗，將以目前版本啟動。
) else (
  echo [提示] 目前不在 main 分支，略過自動更新。
)

set "APP_HOST=0.0.0.0"
uv run fcn-chart
pause
