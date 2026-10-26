"""答案归一化与判分。

判分原则：
1. 不做「模糊匹配」，只做「归一化后的精确匹配」，避免把一知半解的答案判对。
2. 归一化只处理与语法无关的差异：大小写、全半角、弯引号、多余空格、句末标点。
3. 汉译英用「必备结构 + 禁用结构」双重判定：所有必备结构组都命中且不含禁用
   结构才算对；部分命中的按比例给出 partial，用于提示缺了哪一块。
"""
from __future__ import annotations

import re
import unicodedata


def normalize(text: str | None) -> str:
    if not text:
        return ""
    s = unicodedata.normalize("NFKC", str(text))
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("—", "-").replace("–", "-").replace("…", "...")
    s = s.replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = s.strip(" .,!?;:。，！？；：")
    return s.lower()


def _squash(text: str) -> str:
    """去掉所有空白，用于容忍标点与空格差异。"""
    return re.sub(r"\s+", "", normalize(text))


def grade(drill: dict, user_answer: str) -> dict:
    """返回 {correct, partial, expected, feedback, missing}"""
    t = drill.get("type")
    ua = (user_answer or "").strip()

    if t == "choice":
        ans = drill.get("answer", "")
        ok = normalize(ua) == normalize(ans)
        return {
            "correct": ok,
            "partial": 1.0 if ok else 0.0,
            "expected": ans,
            "feedback": "" if ok else f"正确选项是「{ans}」。",
            "missing": [] if ok else [ans],
        }

    if t in ("fill", "correct"):
        accept = drill.get("accept") or [drill.get("answer", "")]
        ans = drill.get("answer", "")
        u_key = _squash(ua)
        ok = bool(u_key) and any(u_key == _squash(a) for a in accept)
        if ok:
            return {"correct": True, "partial": 1.0, "expected": ans, "feedback": "", "missing": []}
        return {
            "correct": False,
            "partial": 0.0,
            "expected": ans,
            "feedback": f"参考答案：{ans}",
            "missing": [],
        }

    if t == "order":
        ans = drill.get("answer", "")
        ok = _squash(ua) == _squash(ans)
        return {
            "correct": ok,
            "partial": 1.0 if ok else 0.0,
            "expected": ans,
            "feedback": "" if ok else f"正确语序：{ans}",
            "missing": [] if ok else [ans],
        }

    if t == "translate":
        groups = drill.get("require") or []
        forbid = drill.get("forbid") or []
        u_norm = normalize(ua)
        hit_groups: list[list[str]] = []
        missing: list[str] = []
        for group in groups:
            alts = [normalize(a) for a in group]
            if any(a and a in u_norm for a in alts):
                hit_groups.append(group)
            else:
                missing.append(" / ".join(group))
        banned = [f for f in forbid if normalize(f) and normalize(f) in u_norm]
        partial = (len(hit_groups) / len(groups)) if groups else (1.0 if u_norm else 0.0)
        ok = (not missing) and (not banned) and bool(u_norm)
        fb = []
        if missing:
            fb.append("缺少结构：" + "；".join(missing))
        if banned:
            fb.append("出现典型错误结构：" + "；".join(banned))
        if ok:
            fb = []
        return {
            "correct": ok,
            "partial": round(partial, 3),
            "expected": drill.get("answer", ""),
            "feedback": " ｜ ".join(fb),
            "missing": missing,
            "banned": banned,
        }

    return {"correct": False, "partial": 0.0, "expected": "", "feedback": "未知题型", "missing": []}
