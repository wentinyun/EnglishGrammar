#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""内容校验器。

用法:
    python tools/validate_content.py                    # 校验 content/ 下全部文件
    python tools/validate_content.py content/morph/nouns.json
    python tools/validate_content.py --quiet            # 只输出汇总

退出码: 0 = 通过（允许 warning）, 1 = 有 error。
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
TAXONOMY = CONTENT / "_taxonomy.json"

VALID_TAGS = {"高频", "易错", "难点", "基础", "写作"}
DRILL_TYPES = {"choice", "fill", "correct", "order", "translate"}
REQUIRED_ITEM = ["id", "title", "brief", "difficulty", "tags", "prereq", "concept", "review", "drills"]
FULLWIDTH_PUNCT = "，。；：！？（）【】“”"


def norm(s: str) -> str:
    """答案归一化：全角转半角、弯引号统一、压缩空白、去首尾标点。"""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("—", "-").replace("–", "-")
    s = re.sub(r"\s+", " ", s).strip()
    s = s.strip(" .,!?;:")
    return s.lower()


class Report:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.items = 0
        self.drills = 0

    def err(self, where: str, msg: str):
        self.errors.append(f"[ERROR] {where}: {msg}")

    def warn(self, where: str, msg: str):
        self.warnings.append(f"[WARN ] {where}: {msg}")


def load_taxonomy() -> dict:
    data = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    return data


def chapter_index(tax: dict) -> dict[tuple[str, str], dict]:
    idx = {}
    for lv in tax["levels"]:
        for ch in lv["chapters"]:
            idx[(lv["id"], ch["slug"])] = {"level_name": lv["name"], "chapter_name": ch["name"], "points": ch["points"]}
    return idx


def check_structure(path: Path, rep: Report) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        rep.err(str(path), f"JSON 解析失败: {e}")
        return None
    if not isinstance(data, dict):
        rep.err(str(path), "顶层必须是对象")
        return None
    for k in ("level1", "chapter", "items"):
        if k not in data:
            rep.err(str(path), f"缺少顶层字段 {k}")
            return None
    return data


def check_english(text: str, where: str, rep: Report, must_sentence: bool = True):
    if not text or not isinstance(text, str):
        rep.err(where, "英文为空")
        return
    if re.search(r"[\u4e00-\u9fff]", text):
        rep.err(where, f"英文里出现中文: {text[:40]}")
    if must_sentence:
        head = text.lstrip("\"'([")
        if head and head[0].isalpha() and not head[0].isupper():
            rep.warn(where, f"首字母未大写: {text[:40]}")
        if not text.rstrip().endswith((".", "?", "!")):
            rep.warn(where, f"句末缺少标点: {text[:40]}")


def check_concept(item: dict, where: str, rep: Report):
    c = item.get("concept")
    if not isinstance(c, dict):
        rep.err(where, "concept 缺失或不是对象")
        return
    summary = c.get("summary", "")
    if len(summary) < 20:
        rep.err(where, "concept.summary 过短（<20 字），必须给出判定标准")
    for bad in ("非常重要", "总之", "由此可见", "值得注意的是"):
        if bad in summary:
            rep.warn(where, f"summary 出现填充词「{bad}」")

    secs = c.get("sections")
    if not isinstance(secs, list) or not (2 <= len(secs) <= 4):
        rep.err(where, f"concept.sections 需 2–4 个，当前 {len(secs) if isinstance(secs, list) else 'N/A'}")
    else:
        for i, s in enumerate(secs):
            if not isinstance(s, dict) or not s.get("h"):
                rep.err(where, f"sections[{i}] 缺少 h")
                continue
            if not s.get("p") and not s.get("bullets"):
                rep.err(where, f"sections[{i}] 的 p 与 bullets 同时为空")
            if s.get("bullets") and not isinstance(s["bullets"], list):
                rep.err(where, f"sections[{i}].bullets 必须是数组")

    exs = c.get("examples")
    if not isinstance(exs, list) or not (4 <= len(exs) <= 8):
        rep.err(where, f"concept.examples 需 4–8 条，当前 {len(exs) if isinstance(exs, list) else 'N/A'}")
    else:
        bad_ok = 0
        for i, ex in enumerate(exs):
            w = f"{where} exemplars[{i}]"
            if not isinstance(ex, dict):
                rep.err(w, "例句必须是对象")
                continue
            for k in ("en", "zh", "ok", "note"):
                if k not in ex:
                    rep.err(w, f"缺少 {k}")
            if ex.get("ok") is False:
                bad_ok += 1
            check_english(ex.get("en", ""), w, rep)
            if not ex.get("zh"):
                rep.warn(w, "缺少中文翻译")
            if len(ex.get("note", "")) < 6:
                rep.warn(w, "note 过短，应说明演示了哪条规则")
        if bad_ok < 2:
            rep.err(where, f"反面例句至少 2 条，当前 {bad_ok}")

    pits = c.get("pitfalls")
    if not isinstance(pits, list) or not (2 <= len(pits) <= 3):
        rep.err(where, f"concept.pitfalls 需 2–3 条，当前 {len(pits) if isinstance(pits, list) else 'N/A'}")
    else:
        for i, p in enumerate(pits):
            if not isinstance(p, dict) or not all(p.get(k) for k in ("wrong", "right", "why")):
                rep.err(f"{where} pitfalls[{i}]", "wrong/right/why 三者都必须非空")
            elif p["wrong"].strip() == p["right"].strip():
                rep.err(f"{where} pitfalls[{i}]", "wrong 与 right 相同")

    ct = c.get("contrast")
    if not isinstance(ct, dict) or not ct.get("withTitle") or not ct.get("diff"):
        rep.warn(where, "concept.contrast 缺失或为空（建议补）")


def check_review(item: dict, where: str, rep: Report):
    r = item.get("review")
    if not isinstance(r, dict):
        rep.err(where, "review 缺失或不是对象")
        return
    core = r.get("core")
    if not isinstance(core, list) or not (3 <= len(core) <= 6):
        rep.err(where, f"review.core 需 3–6 条，当前 {len(core) if isinstance(core, list) else 'N/A'}")
    if not r.get("trigger"):
        rep.err(where, "review.trigger 不能为空")
    qc = r.get("quickCheck")
    if not isinstance(qc, list) or not (2 <= len(qc) <= 3):
        rep.err(where, f"review.quickCheck 需 2–3 条，当前 {len(qc) if isinstance(qc, list) else 'N/A'}")
    else:
        for i, q in enumerate(qc):
            if not isinstance(q, dict) or not q.get("q") or not q.get("a"):
                rep.err(f"{where} quickCheck[{i}]", "q/a 都必须非空")


def check_drill(d: dict, kp_id: str, n: int, where: str, rep: Report):
    t = d.get("type")
    if t not in DRILL_TYPES:
        rep.err(where, f"未知题型 {t}")
        return
    for k in ("id", "stem", "explain", "difficulty"):
        if d.get(k) in (None, ""):
            rep.err(where, f"缺少 {k}")
    if d.get("id") != f"{kp_id}.d{n}":
        rep.err(where, f"id 应为 {kp_id}.d{n}，实际 {d.get('id')}")
    if not isinstance(d.get("difficulty"), int) or not (1 <= d["difficulty"] <= 4):
        rep.err(where, "difficulty 需为 1–4 的整数")
    if len(d.get("explain", "")) < 15:
        rep.err(where, "explain 少于 15 字，必须解释为什么")
    stem = d.get("stem", "")
    if not stem:
        rep.err(where, "stem 为空")

    if t == "choice":
        opts = d.get("options")
        if not isinstance(opts, list) or len(opts) != 4:
            rep.err(where, f"choice 必须有 4 个选项，当前 {len(opts) if isinstance(opts, list) else 'N/A'}")
            return
        if len({norm(o) for o in opts}) != 4:
            rep.err(where, "choice 选项存在重复")
        for o in opts:
            if re.match(r"^[A-Da-d][.、)]", o.strip()):
                rep.err(where, f"选项不要带 A./B. 前缀: {o}")
        if d.get("answer") not in opts:
            rep.err(where, f"answer「{d.get('answer')}」不在 options 中")
        if not d.get("trap"):
            rep.warn(where, "choice 缺少 trap（干扰项错因）")

    elif t == "fill":
        if "___" not in stem:
            rep.err(where, "fill 的 stem 必须含 ___")
        if not d.get("answer"):
            rep.err(where, "fill 缺少 answer")
        acc = d.get("accept")
        if not isinstance(acc, list) or len(acc) < 1:
            rep.err(where, "fill 的 accept 必须是非空数组")
        elif norm(d.get("answer", "")) not in {norm(a) for a in acc}:
            rep.err(where, "accept 未包含标准答案的归一化形式")

    elif t == "correct":
        if not d.get("stem") or not d.get("answer"):
            rep.err(where, "correct 缺少 stem/answer")
        if norm(d.get("stem", "")) == norm(d.get("answer", "")):
            rep.err(where, "correct 的 stem 与 answer 相同（题干没有错）")
        check_english(d.get("answer", ""), where, rep)
        acc = d.get("accept", [])
        if not isinstance(acc, list):
            rep.err(where, "correct 的 accept 必须是数组")
        elif norm(d.get("answer", "")) not in {norm(a) for a in acc}:
            rep.err(where, "correct 的 accept 未包含标准答案")

    elif t == "order":
        toks = d.get("tokens")
        if not isinstance(toks, list) or len(toks) < 3:
            rep.err(where, "order 的 tokens 至少 3 个")
        ans = d.get("answer", "")
        check_english(ans, where, rep)
        if toks and isinstance(toks, list):
            joined = norm(" ".join(toks)).replace(" ", "")
            if joined != norm(ans).replace(" ", ""):
                rep.err(where, "tokens 拼合后与 answer 不一致（必须能唯一还原）")
            if " ".join(toks) == " ".join(sorted(toks)):
                rep.warn(where, "tokens 看起来未打乱")

    elif t == "translate":
        req = d.get("require")
        if not isinstance(req, list) or not req or not all(isinstance(g, list) and g for g in req):
            rep.err(where, "translate 的 require 必须是非空二维数组")
        if not d.get("answer"):
            rep.err(where, "translate 缺少 answer")
        fb = d.get("forbid", [])
        if not isinstance(fb, list):
            rep.err(where, "translate 的 forbid 必须是数组")


def check_item(item: dict, expect_title: str, level1: str, chapter: str, rep: Report):
    where = f"{level1}/{chapter}/{item.get('title', '?')}"
    for k in REQUIRED_ITEM:
        if k not in item:
            rep.err(where, f"缺少字段 {k}")
            return
    if item.get("title") != expect_title:
        rep.err(where, f"title 与 taxonomy 不一致，应为「{expect_title}」")
    kp_id = item.get("id", "")
    if not re.fullmatch(r"[a-z_]+\.[a-z_]+(\.[a-z0-9-]+)+", kp_id or ""):
        rep.err(where, f"id 格式不合法: {kp_id}")
    if not kp_id.startswith(f"{level1}.{chapter}."):
        rep.err(where, f"id 前缀应为 {level1}.{chapter}.，实际 {kp_id}")
    if len(item.get("brief", "")) > 32:
        rep.warn(where, f"brief 超过 32 字: {len(item['brief'])}")
    if not isinstance(item.get("difficulty"), int) or not (1 <= item["difficulty"] <= 4):
        rep.err(where, "difficulty 需为 1–4 的整数")
    tags = item.get("tags")
    if not isinstance(tags, list) or not (1 <= len(tags) <= 3) or any(t not in VALID_TAGS for t in tags):
        rep.err(where, f"tags 不合法: {tags}")
    if not isinstance(item.get("prereq"), list):
        rep.err(where, "prereq 必须是数组")

    check_concept(item, where, rep)
    check_review(item, where, rep)

    drills = item.get("drills")
    if not isinstance(drills, list) or not (4 <= len(drills) <= 7):
        rep.err(where, f"drills 需 4–7 道，当前 {len(drills) if isinstance(drills, list) else 'N/A'}")
        return
    types = {d.get("type") for d in drills if isinstance(d, dict)}
    if len(types) < 3:
        rep.err(where, f"题型需至少 3 种，当前 {sorted(types)}")
    if drills[0].get("type") != "choice":
        rep.err(where, "第 1 题必须是 choice")
    stems = [norm(d.get("stem", "")) for d in drills if isinstance(d, dict)]
    if len(stems) != len(set(stems)):
        rep.err(where, "同一知识点内存在重复题干")
    for i, d in enumerate(drills, start=1):
        if not isinstance(d, dict):
            rep.err(where, f"drills[{i}] 不是对象")
            continue
        check_drill(d, kp_id, i, f"{where}#d{i}", rep)
        rep.drills += 1


def validate_file(path: Path, cidx: dict, rep: Report, seen_ids: set[str], seen_titles: set[str]) -> None:
    data = check_structure(path, rep)
    if data is None:
        return
    lv, ch = data["level1"], data["chapter"]
    if (lv, ch) not in cidx:
        rep.err(str(path), f"taxonomy 中不存在 {lv}/{ch}")
        return
    expect = cidx[(lv, ch)]
    # 路径校验
    expect_path = CONTENT / lv / f"{ch}.json"
    if path.resolve() != expect_path.resolve():
        rep.err(str(path), f"路径应为 {expect_path.relative_to(ROOT)}")
    items = data["items"]
    if not isinstance(items, list):
        rep.err(str(path), "items 必须是数组")
        return
    if len(items) != len(expect["points"]):
        rep.err(str(path), f"知识点数量不符：应为 {len(expect['points'])}，实际 {len(items)}")
    for i, title in enumerate(expect["points"]):
        if i >= len(items):
            rep.err(str(path), f"缺少知识点「{title}」")
            continue
        item = items[i]
        if not isinstance(item, dict):
            rep.err(str(path), f"items[{i}] 不是对象")
            continue
        check_item(item, title, lv, ch, rep)
        iid = item.get("id")
        if iid:
            if iid in seen_ids:
                rep.err(str(path), f"知识点 id 重复: {iid}")
            seen_ids.add(iid)
        if title in seen_titles:
            rep.err(str(path), f"知识点标题重复: {title}")
        seen_titles.add(title)
        rep.items += 1


def check_prereq(all_ids: set[str], all_items: list[dict], rep: Report):
    for it in all_items:
        for p in it.get("prereq") or []:
            if p not in all_ids:
                rep.warn(f"{it.get('id')}", f"prereq 指向不存在的 id: {p}")


def main(argv: list[str]) -> int:
    quiet = "--quiet" in argv
    args = [a for a in argv if not a.startswith("-")]
    tax = load_taxonomy()
    cidx = chapter_index(tax)
    rep = Report()

    if args:
        files = [Path(a if Path(a).is_absolute() else ROOT / a) for a in args]
    else:
        files = sorted(p for p in CONTENT.rglob("*.json") if p.name != "_taxonomy.json")

    if not files:
        print("没有找到内容文件。")
        return 1

    seen_ids: set[str] = set()
    seen_titles: set[str] = set()
    all_items: list[dict] = []
    for f in files:
        before = len(rep.errors)
        data = None
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
        validate_file(f, cidx, rep, seen_ids, seen_titles)
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            all_items.extend([i for i in data["items"] if isinstance(i, dict)])
        status = "OK  " if len(rep.errors) == before else "FAIL"
        if not quiet:
            print(f"{status} {f.relative_to(ROOT)}")

    if not args:
        check_prereq(seen_ids, all_items, rep)

    print()
    for w in rep.warnings:
        print(w)
    for e in rep.errors:
        print(e)
    print()
    print(f"知识点 {rep.items} 个 / 训练题 {rep.drills} 道 | 错误 {len(rep.errors)} / 警告 {len(rep.warnings)}")
    return 0 if not rep.errors else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
