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

echo [2/2] 启动服务（局域网模式，手机可访问）...
echo.
echo   电脑和 iPhone 连同一个 Wi-Fi，用 Safari 打开下面打印的“手机”地址，
echo   再点 分享 - 添加到主屏幕，就是一个独立的全屏 App。
echo.
python run.py --host 0.0.0.0
pause
