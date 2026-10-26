"""用 Chrome DevTools Protocol 做真机尺寸截图。

Windows 上 headless 的窗口有 ~500px 最小宽度，直接 --window-size=390 会被撑到
504，截出来的图等于右侧裁掉一截，无法判断移动端布局。这里用
Emulation.setDeviceMetricsOverride 强制 390×844 的移动视口。

用法：
    python tools/shot.py m-today 390x844 "#/today"
    python tools/shot.py m-today 390x844 "#/today" 390x844
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import websocket

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "docs" / "shots"
CHROME = Path(r"C:\Users\Administrator\AppData\Local\Google\Chrome\Application\chrome.exe")
PORT = 9333
BASE = "http://127.0.0.1:8765"


def _candidates() -> list[str]:
    return [
        r"C:\Users\Administrator\AppData\Local\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]


def _launch() -> subprocess.Popen:
    exe = next((p for p in _candidates() if Path(p).exists()), None)
    if not exe:
        raise SystemExit("找不到 Chrome / Edge")
    proc = subprocess.Popen(
        [
            exe,
            f"--remote-debugging-port={PORT}",
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--hide-scrollbars",
            "--allow-file-access-from-files",
            "--remote-allow-origins=*",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1).read()
            return proc
        except Exception:
            time.sleep(0.2)
    proc.kill()
    raise SystemExit("Chrome 调试端口没有起来")


def _ws_url() -> str:
    data = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list", timeout=3).read())
    for page in data:
        if page.get("type") == "page":
            return page["webSocketDebuggerUrl"]
    raise SystemExit("没有可用页面")


class CDP:
    def __init__(self, url: str) -> None:
        self.ws = websocket.create_connection(url, timeout=20)
        self.i = 0

    def send(self, method: str, params: dict | None = None) -> dict:
        self.i += 1
        mid = self.i
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})


def main() -> None:
    args = sys.argv[1:]
    name = args[0] if args else "shot"
    size = args[1] if len(args) > 1 else "390x844"
    route = args[2] if len(args) > 2 else "today"
    # Git Bash 会把以 / 开头的参数当成路径改写，所以这里统一用不带 # 的路由
    hash_path = route if route.startswith("#") else "#/" + route.lstrip("/")
    scroll = int(args[3]) if len(args) > 3 else 0
    # 第 5 个参数：加载后先点一下某个选择器（用来打开弹层等交互态）
    click = args[4] if len(args) > 4 else ""
    w, h = (int(x) for x in size.split("x"))
    mobile = w <= 900

    proc = _launch()
    try:
        cdp = CDP(_ws_url())
        cdp.send("Page.enable")
        cdp.send(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": w,
                "height": h,
                "deviceScaleFactor": 2,
                "mobile": mobile,
                "screenWidth": w,
                "screenHeight": h,
            },
        )
        if mobile:
            cdp.send(
                "Emulation.setTouchEmulationEnabled",
                {"enabled": True, "maxTouchPoints": 5},
            )
            cdp.send(
                "Emulation.setUserAgentOverride",
                {
                    "userAgent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
                    "platform": "iPhone",
                },
            )
        target = BASE + "/" + hash_path
        cdp.send("Page.navigate", {"url": target})
        time.sleep(3.4)
        if scroll:
            cdp.send("Runtime.evaluate", {"expression": f"window.scrollTo(0,{scroll})"})
            time.sleep(0.5)
        if click:
            cdp.send(
                "Runtime.evaluate",
                {
                    "expression": "(function(){var el=document.querySelector("
                    + repr(click)
                    + "); if(el){el.click(); return 'clicked';} return 'not-found';})()",
                    "returnByValue": True,
                },
            )
            time.sleep(0.9)
        info = cdp.send(
            "Runtime.evaluate",
            {"expression": "location.hash + ' | w=' + document.documentElement.clientWidth + ' sw=' + document.documentElement.scrollWidth + ' | ' + document.body.innerText.slice(0,30)",
             "returnByValue": True},
        )
        print("debug:", target, "->", info["result"].get("value"))
        shot = cdp.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        SHOTS.mkdir(parents=True, exist_ok=True)
        out = SHOTS / f"{name}.png"
        out.write_bytes(base64.b64decode(shot["data"]))
        print(f"wrote {out.relative_to(ROOT)} ({w}x{h})")
    finally:
        proc.kill()


if __name__ == "__main__":
    main()
