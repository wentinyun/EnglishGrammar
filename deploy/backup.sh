#!/usr/bin/env bash
# 在服务器上备份 SQLite（走在线备份接口，服务不用停）。
#   sudo -u grammar bash /opt/english-grammar/deploy/backup.sh
# 建议加进 crontab：
#   17 3 * * * /usr/bin/env bash /opt/english-grammar/deploy/backup.sh >> /opt/english-grammar/backups/backup.log 2>&1
set -euo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
KEEP="${KEEP:-14}"

mkdir -p "$APP_DIR/backups"

APP_DIR="$APP_DIR" python3 - <<'PY'
import os
import sqlite3
from datetime import datetime
from pathlib import Path

app = Path(os.environ["APP_DIR"])
src = app / "data" / "grammar.db"
if not src.exists():
    raise SystemExit(f"没有找到 {src}")

dst = app / "backups" / f"grammar-{datetime.now():%Y%m%d-%H%M%S}.db"
# 用 SQLite 在线备份 API：即便服务正在写，也能拿到一致快照
with sqlite3.connect(src) as s, sqlite3.connect(dst) as d:
    s.backup(d)
print("备份完成:", dst, dst.stat().st_size, "bytes")
PY

# 只保留最近 KEEP 份
ls -1t "$APP_DIR"/backups/grammar-*.db 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f
