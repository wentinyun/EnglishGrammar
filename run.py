"""启动脚本：双击或 `python run.py`。

首次运行会自动建库；浏览器打开 http://127.0.0.1:8765

想在 iPhone 上「添加到主屏幕」，用手机和电脑连同一个 Wi-Fi 后：
    python run.py --host 0.0.0.0
启动时会把局域网地址打出来，手机浏览器直接输那个地址即可。
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "server"))

import uvicorn  # noqa: E402

from app import app  # noqa: E402

# 云端/容器部署时由平台注入 PORT，此时必须绑 0.0.0.0 才能被反向代理访问。
_ENV_PORT = os.environ.get("PORT")
DEFAULT_PORT = int(_ENV_PORT) if _ENV_PORT else 8765
DEFAULT_HOST = os.environ.get("HOST") or ("0.0.0.0" if _ENV_PORT else "127.0.0.1")


def _arg(flag: str, default: str) -> str:
    """支持 `--host 0.0.0.0` 和 `--host=0.0.0.0` 两种写法。"""
    for i, a in enumerate(sys.argv):
        if a == flag and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if a.startswith(flag + "="):
            return a.split("=", 1)[1]
    return default


def _lan_ip() -> str | None:
    """取本机在局域网里的地址（不会真的发包）。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def main() -> None:
    host = _arg("--host", DEFAULT_HOST)
    port = int(_arg("--port", str(DEFAULT_PORT)))
    public = host in ("0.0.0.0", "::")
    browse_host = "127.0.0.1" if public else host

    if "--no-browser" not in sys.argv:
        threading.Timer(1.6, lambda: webbrowser.open(f"http://{browse_host}:{port}/")).start()

    print("\n  英语语法全景学习系统", flush=True)
    print(f"    本机  →  http://{browse_host}:{port}/", flush=True)
    if public:
        ip = _lan_ip()
        if ip:
            print(f"    手机  →  http://{ip}:{port}/   （同一 Wi-Fi，iPhone 用 Safari 打开后「添加到主屏幕」）", flush=True)
        else:
            print("    手机  →  http://<本机局域网IP>:%d/   （没探测到局域网地址）" % port, flush=True)
    print(flush=True)

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=os.environ.get("LOG_LEVEL", "warning"),
        # 放在 nginx 后面时要信任反代过来的 X-Forwarded-*，否则日志里全是 127.0.0.1
        proxy_headers=True,
        forwarded_allow_ips=os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1"),
    )


if __name__ == "__main__":
    main()
