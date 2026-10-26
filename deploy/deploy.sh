#!/usr/bin/env bash
# 英语语法全景 —— 一键更新（本机 Git Bash 执行）
#
#   bash deploy/deploy.sh
#
# 流程：本地推送到 GitHub → 服务器 git reset --hard → 装依赖 → 构建前端 → 重启 → 健康检查
# 服务器事实见 ../DEPLOY_PLAYBOOK.md：ubuntu@101.42.38.77，systemd，端口 8788。
set -euo pipefail

cd "$(dirname "$0")/.."

TARGET="${TARGET:-ubuntu@101.42.38.77}"
DEST="${DEST:-/home/ubuntu/EnglishGrammar}"
PORT="${PORT:-8788}"
SERVICE="${SERVICE:-english-grammar}"
BRANCH="${BRANCH:-main}"
REPO="${REPO:-git@github.com:wentinyun/EnglishGrammar.git}"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "本地有未提交的改动，先提交再部署：" >&2
  git status --short >&2
  exit 1
fi

echo "==> 推送到 origin/$BRANCH"
git push origin "$BRANCH"

echo "==> 服务器拉取并重启"
ssh "$TARGET" "DEST='$DEST' PORT='$PORT' SERVICE='$SERVICE' BRANCH='$BRANCH' REPO='$REPO' bash -s" <<'REMOTE'
set -euo pipefail
cd "$DEST"

# 服务器首次到 GitHub 会卡在 host key 确认，统一用 BatchMode + accept-new
export GIT_SSH_COMMAND="ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new"

if [ ! -d .git ]; then
  echo "  首次部署：初始化仓库"
  git init -q -b "$BRANCH"
  git remote add origin "$REPO"
fi

git fetch -q origin "$BRANCH"
git reset -q --hard "origin/$BRANCH"
echo "  当前版本: $(git log --oneline -1)"

echo "  安装 Python 依赖"
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
if ! .venv/bin/pip install -q -r requirements.txt; then
  echo "  默认源失败，改用清华源"
  .venv/bin/pip install -q -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
fi

# 前端产物不入库（.gitignore 排除了 web/site），必须在服务器构建
if command -v npm >/dev/null 2>&1; then
  echo "  构建前端"
  if (cd web && npm install --no-audit --no-fund --silent && npm run build --silent); then
    echo "  前端构建完成"
  else
    echo "  ⚠ 前端构建失败，沿用现有 web/site（若从未构建过会 404）"
  fi
else
  echo "  ⚠ 服务器没有 node/npm，无法构建前端"
fi

mkdir -p data backups

echo "  重启服务"
sudo install -m 644 deploy/english-grammar.service "/etc/systemd/system/${SERVICE}.service"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE" >/dev/null 2>&1 || true
sudo systemctl restart "$SERVICE"

for _ in $(seq 1 20); do
  if curl -fsS "http://127.0.0.1:${PORT}/api/health" 2>/dev/null; then
    echo
    echo "  健康检查通过：127.0.0.1:${PORT}"
    exit 0
  fi
  sleep 1
done

echo "健康检查失败，最近日志：" >&2
sudo journalctl -u "$SERVICE" -n 40 --no-pager >&2
exit 1
REMOTE

IP="${TARGET#*@}"
CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://$IP:$PORT/" || echo 000)
printf '公网 http://%s:%s/ → %s\n' "$IP" "$PORT" "$CODE"
if [ "$CODE" != "200" ]; then
  echo "公网不通：服务本机正常的话，去腾讯云控制台安全组放行 $PORT"
fi
