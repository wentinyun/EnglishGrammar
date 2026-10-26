"""内容装载：把 content/ 下的 JSON 读进内存并做一致性检查。

启动即校验，内容有问题就直接拒绝启动 —— 避免带病数据进入学习记录。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = ROOT / "content"


class ContentError(RuntimeError):
    pass


class Content:
    def __init__(self) -> None:
        self.levels: list[dict] = []
        self.kps: dict[str, dict] = {}
        self.order: list[str] = []
        self.drills: dict[str, dict] = {}
        self.chapter_of: dict[str, dict] = {}

    def load(self) -> "Content":
        tax_path = CONTENT_DIR / "_taxonomy.json"
        tax = json.loads(tax_path.read_text(encoding="utf-8"))
        problems: list[str] = []

        for lv in tax["levels"]:
            lv_node = {"id": lv["id"], "name": lv["name"], "chapters": []}
            for ch in lv["chapters"]:
                fp = CONTENT_DIR / lv["id"] / f"{ch['slug']}.json"
                if not fp.exists():
                    problems.append(f"缺少内容文件 {fp.relative_to(ROOT)}")
                    continue
                data = json.loads(fp.read_text(encoding="utf-8"))
                items = data.get("items") or []
                titles = [it.get("title") for it in items]
                if titles != ch["points"]:
                    problems.append(
                        f"{lv['id']}/{ch['slug']} 标题与 taxonomy 不一致："
                        f"期望 {len(ch['points'])} 个，实际 {len(titles)} 个"
                    )
                    continue
                ch_node = {"slug": ch["slug"], "name": ch["name"], "points": []}
                for it in items:
                    kp = dict(it)
                    kp["level1"] = lv["id"]
                    kp["level1_name"] = lv["name"]
                    kp["chapter"] = ch["slug"]
                    kp["chapter_name"] = ch["name"]
                    kp["ord"] = len(self.order)
                    drills = kp.get("drills") or []
                    for d in drills:
                        if d["id"] in self.drills:
                            problems.append(f"题目 id 重复: {d['id']}")
                        d = dict(d)
                        d["kp_id"] = kp["id"]
                        d["level1"] = lv["id"]
                        self.drills[d["id"]] = d
                    self.kps[kp["id"]] = kp
                    self.order.append(kp["id"])
                    ch_node["points"].append(kp["id"])
                self.chapter_of[ch["slug"]] = {"level1": lv["id"], "name": ch["name"]}
                lv_node["chapters"].append(ch_node)
            self.levels.append(lv_node)

        if problems:
            raise ContentError("内容装载失败：\n- " + "\n- ".join(problems))
        return self

    # ---------- 查询辅助 ----------

    def kp(self, kp_id: str) -> dict:
        kp = self.kps.get(kp_id)
        if not kp:
            raise KeyError(kp_id)
        return kp

    def brief(self, kp_id: str) -> dict:
        kp = self.kps[kp_id]
        return {
            "id": kp["id"],
            "title": kp["title"],
            "brief": kp["brief"],
            "level1": kp["level1"],
            "level1_name": kp["level1_name"],
            "chapter": kp["chapter"],
            "chapter_name": kp["chapter_name"],
            "difficulty": kp["difficulty"],
            "tags": kp["tags"],
            "drill_count": len(kp["drills"]),
        }

    def public_kp(self, kp_id: str, include_answer: bool = False) -> dict:
        """给前端的知识点结构；默认不含答案（训练时逐题下发）。"""
        kp = self.kp(kp_id)
        drills = []
        for d in kp["drills"]:
            item = {
                "id": d["id"],
                "type": d["type"],
                "stem": d["stem"],
                "difficulty": d.get("difficulty", 2),
            }
            if "options" in d:
                item["options"] = d["options"]
            if "tokens" in d:
                item["tokens"] = d["tokens"]
            if d.get("hint"):
                item["hint"] = d["hint"]
            if include_answer:
                item.update(self.drill_answer(d))
            drills.append(item)
        return {
            **self.brief(kp_id),
            "prereq": kp.get("prereq") or [],
            "concept": kp["concept"],
            "review": kp["review"],
            "drills": drills,
        }

    def public_drill(self, drill_id: str) -> dict:
        d = self.drills[drill_id]
        item = {
            "id": d["id"],
            "kp_id": d["kp_id"],
            "type": d["type"],
            "stem": d["stem"],
            "difficulty": d.get("difficulty", 2),
            "level1": d["level1"],
        }
        for k in ("options", "tokens", "hint"):
            if d.get(k):
                item[k] = d[k]
        return item

    @staticmethod
    def drill_answer(d: dict) -> dict:
        out = {"answer": d.get("answer"), "explain": d.get("explain")}
        for k in ("accept", "require", "forbid", "trap"):
            if d.get(k):
                out[k] = d[k]
        return out

    def tree(self) -> list[dict]:
        return [
            {
                "id": lv["id"],
                "name": lv["name"],
                "chapters": [
                    {"slug": c["slug"], "name": c["name"], "points": list(c["points"])}
                    for c in lv["chapters"]
                ],
            }
            for lv in self.levels
        ]


CONTENT = Content()
