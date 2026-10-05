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
set "IS_GIT="
git rev-parse --is-inside-work-tree >nul 2>nul && set "IS_GIT=1"
for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set "BRANCH=%%b"
if not defined IS_GIT (
  echo [提示] 這不是用 git 下載的版本（例如 zip 解壓縮），略過自動更新。
) else if /i "%BRANCH%"=="main" (
  echo 正在更新到最新版...
  git pull --ff-only
  if errorlevel 1 echo [警告] 自動更新失敗，將以目前版本啟動。
) else (
  echo [提示] 目前不在 main 分支，略過自動更新。
)

set "APP_HOST=0.0.0.0"
rem 公司網路常用自有根憑證做 HTTPS 檢查：讓 uv 改用 Windows 憑證存放區，才連得上 PyPI。
set "UV_NATIVE_TLS=1"
uv run fcn-chart
pause
