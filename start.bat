@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist "web\site\index.html" (
  echo [1/2] 首次运行，正在构建前端...
  pushd web
  call npm install --no-audit --no-fund
  call npm run build
  popd
)

echo [2/2] 启动服务...
python run.py
pause
