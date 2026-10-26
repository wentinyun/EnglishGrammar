#!/usr/bin/env bash
# 英语语法全景 —— 本地 → 服务器 一键部署 / 更新
#
# 在本机 Git Bash 里执行：
#   bash deploy/deploy.sh
#
# 服务器事实见 ../../DEPLOY_PLAYBOOK.md：ubuntu@101.42.38.77，systemd，端口顺延到 8788。
# 本项目没有 git 仓库，所以走 tar over ssh 直传（比建私库少一步，效果相同）。
set -euo pipefail

cd "$(dirname "$0")/.."

TARGET="${TARGET:-ubuntu@101.42.38.77}"
APP="${APP:-EnglishGrammar}"
DEST="${DEST:-/home/ubuntu/$APP}"
PORT="${PORT:-8788}"
SERVICE="${SERVICE:-english-grammar}"

if [[ ! -f web/site/index.html ]]; then
  echo "web/site 不存在，先构建前端：cd web && npm run build" >&2
  exit 1
fi

echo "==> 上传代码到 $TARGET:$DEST"
tar czf - \
  --exclude=./.git \
  --exclude=./.workbuddy \
  --exclude=./node_modules \
  --exclude=./web/node_modules \
  --exclude=./.venv \
  --exclude=./data \
  --exclude='*.pyc' \
  --exclude='__pycache__' \
  --exclude='.wbapp_*' \
  . | ssh "$TARGET" "mkdir -p '$DEST' && tar xzf - -C '$DEST'"

echo "==> 服务器：装依赖、装服务、重启"
ssh "$TARGET" "DEST='$DEST' PORT='$PORT' SERVICE='$SERVICE' bash -s" <<'REMOTE'
set -euo pipefail
cd "$DEST"

# 1) Python 依赖
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q --upgrade pip
if ! .venv/bin/pip install -q -r requirements.txt; then
  echo "  默认源失败，改用清华源重试"
  .venv/bin/pip install -q -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
fi

# 2) 前端：服务器有 node 就重新构建，失败则沿用上传好的 web/site
if command -v npm >/dev/null 2>&1; then
  echo "  构建前端"
  if (cd web && npm install --no-audit --no-fund --silent && npm run build --silent); then
    echo "  前端构建完成"
  else
    echo "  ⚠ 前端构建失败，沿用已上传的 web/site（功能不受影响）"
  fi
else
  echo "  服务器无 node，使用已上传的 web/site"
fi

mkdir -p data backups

# 3) systemd 单元
sudo install -m 644 deploy/english-grammar.service "/etc/systemd/system/${SERVICE}.service"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE" >/dev/null 2>&1 || true
sudo systemctl restart "$SERVICE"

# 4) 健康检查
for _ in $(seq 1 20); do
  if curl -fsS "http://127.0.0.1:${PORT}/api/health" 2>/dev/null; then
    echo
    echo "本机健康检查通过（127.0.0.1:${PORT}）"
    exit 0
  fi
  sleep 1
done

echo "健康检查失败，最近日志：" >&2
sudo journalctl -u "$SERVICE" -n 40 --no-pager >&2
exit 1
REMOTE

echo
echo "==> 公网验证"
IP=$(echo "$TARGET" | cut -d@ -f2)
CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://$IP:$PORT/" || echo 000)
printf 'http://%s:%s/  → %s\n' "$IP" "$PORT" "$CODE"
if [ "$CODE" != "200" ]; then
  echo "公网不通：服务本机正常的话，去腾讯云控制台安全组放行 $PORT 端口"
fi
