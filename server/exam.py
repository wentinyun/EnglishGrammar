"""考试模式：按考试类型加权抽题、限时作答、整卷判分。"""
from __future__ import annotations

import json
import random
import uuid
from datetime import timedelta

import db
from content import CONTENT
from grade import grade as grade_answer

PROFILES = [
    {
        "id": "zhongkao", "name": "中考语法", "count": 30, "minutes": 40,
        "desc": "以词法基础、时态、简单从句为主",
        "weights": {"morph": 0.34, "tense_voice": 0.22, "syntax": 0.18, "clause": 0.12,
                    "special": 0.06, "nonfinite": 0.05, "collocation": 0.03},
    },
    {
        "id": "gaokao", "name": "高考语法", "count": 40, "minutes": 55,
        "desc": "从句、非谓语、特殊句式并重",
        "weights": {"morph": 0.20, "tense_voice": 0.18, "syntax": 0.14, "clause": 0.18,
                    "special": 0.14, "nonfinite": 0.12, "collocation": 0.04},
    },
    {
        "id": "cet4", "name": "四级语法", "count": 40, "minutes": 50,
        "desc": "搭配与非谓语占比更高",
        "weights": {"morph": 0.22, "tense_voice": 0.20, "syntax": 0.14, "clause": 0.16,
                    "special": 0.10, "nonfinite": 0.10, "collocation": 0.08},
    },
    {
        "id": "cet6", "name": "六级语法", "count": 40, "minutes": 50,
        "desc": "难句结构与虚拟语气加权重",
        "weights": {"morph": 0.18, "tense_voice": 0.18, "syntax": 0.12, "clause": 0.20,
                    "special": 0.16, "nonfinite": 0.10, "collocation": 0.06},
    },
    {
        "id": "kaoyan", "name": "考研语法", "count": 35, "minutes": 50,
        "desc": "长难句、从句嵌套、非谓语为主",
        "weights": {"morph": 0.12, "tense_voice": 0.14, "syntax": 0.14, "clause": 0.24,
                    "special": 0.16, "nonfinite": 0.14, "collocation": 0.06},
    },
    {
        "id": "ielts", "name": "雅思语法", "count": 30, "minutes": 40,
        "desc": "写作常用结构、搭配与复杂句",
        "weights": {"morph": 0.18, "tense_voice": 0.20, "syntax": 0.16, "clause": 0.18,
                    "special": 0.12, "nonfinite": 0.10, "collocation": 0.06},
    },
]


def _seen() -> set[str]:
    with db.db() as conn:
        rows = conn.execute("SELECT drill_id FROM drill_stat WHERE attempts > 0").fetchall()
    return {r["drill_id"] for r in rows}


def _pool(level1: str, seen: set[str]) -> list[dict]:
    out = []
    for kp_id in CONTENT.order:
        kp = CONTENT.kps[kp_id]
        if kp["level1"] != level1:
            continue
        for d in kp["drills"]:
            out.append(d)
    return out


def list_profiles() -> list[dict]:
    return [{k: v for k, v in p.items() if k != "weights"} for p in PROFILES]


def start(profile_id: str, count: int | None = None) -> dict:
    prof = next((p for p in PROFILES if p["id"] == profile_id), None)
    if not prof:
        raise ValueError("未知考试类型")
    total = count or prof["count"]
    seen = _seen()
    chosen: list[dict] = []

    for level1, w in prof["weights"].items():
        n = max(1, round(total * w))
        pool = _pool(level1, seen)
        if not pool:
            continue
        # 优先没做过的题，其次按难度分层抽样
        unseen = [d for d in pool if d["id"] not in seen]
        source = unseen if len(unseen) >= n else pool
        random.shuffle(source)
        source.sort(key=lambda d: d.get("difficulty", 2))
        # 按难度分层取：1-2 简单、3 中等、4 难
        buckets = {1: [], 2: [], 3: [], 4: []}
        for d in source:
            buckets[min(4, max(1, d.get("difficulty", 2)))].append(d)
        want = {1: 0.2, 2: 0.35, 3: 0.3, 4: 0.15}
        picked = []
        for k, ratio in want.items():
            take = int(round(n * ratio))
            picked.extend(buckets[k][:take])
        rest = [d for d in source if d not in picked]
        random.shuffle(rest)
        while len(picked) < n and rest:
            picked.append(rest.pop())
        chosen.extend(picked[:n])

    random.shuffle(chosen)
    chosen = chosen[:total]
    paper = {
        "profile": prof["id"],
        "profile_name": prof["name"],
        "minutes": prof["minutes"],
        "questions": [d["id"] for d in chosen],
    }
    eid = uuid.uuid4().hex[:12]
    started = db.now()
    with db.db() as conn:
        conn.execute(
            "INSERT INTO exam(id, profile, paper, started_at) VALUES (?,?,?,?)",
            (eid, profile_id, json.dumps(paper, ensure_ascii=False), db.iso(started)),
        )
    return get(eid)


def get(eid: str) -> dict:
    with db.db() as conn:
        row = conn.execute("SELECT * FROM exam WHERE id=?", (eid,)).fetchone()
    if not row:
        raise KeyError(eid)
    paper = json.loads(row["paper"])
    started = db.parse_dt(row["started_at"])
    deadline = started + timedelta(minutes=paper["minutes"]) if started else db.now()
    questions = []
    for i, did in enumerate(paper["questions"], start=1):
        d = CONTENT.drills.get(did)
        if not d:
            continue
        q = {
            "no": i,
            "id": d["id"],
            "type": d["type"],
            "stem": d["stem"],
            "difficulty": d.get("difficulty", 2),
            "level1": d["level1"],
            "kp_id": d["kp_id"],
            "kp_title": CONTENT.kps[d["kp_id"]]["title"],
        }
        for k in ("options", "tokens"):
            if d.get(k):
                q[k] = d[k]
        questions.append(q)
    return {
        "id": eid,
        "profile": paper["profile"],
        "profile_name": paper["profile_name"],
        "minutes": paper["minutes"],
        "started_at": row["started_at"],
        "deadline": db.iso(deadline),
        "submitted": bool(row["submitted_at"]),
        "result": json.loads(row["result"]) if row["result"] else None,
        "questions": questions,
    }


def submit(eid: str, answers: dict[str, str]) -> dict:
    with db.db() as conn:
        row = conn.execute("SELECT * FROM exam WHERE id=?", (eid,)).fetchone()
    if not row:
        raise KeyError(eid)
    paper = json.loads(row["paper"])
    details = []
    per_level: dict[str, dict] = {}
    hits = 0

    for did in paper["questions"]:
        d = CONTENT.drills.get(did)
        if not d:
            continue
        ua = answers.get(did, "")
        res = grade_answer(d, ua)
        lv = d["level1"]
        bucket = per_level.setdefault(lv, {"total": 0, "correct": 0})
        bucket["total"] += 1
        if res["correct"]:
            hits += 1
            bucket["correct"] += 1
        kp = CONTENT.kps[d["kp_id"]]
        details.append({
            "id": did,
            "kp_id": d["kp_id"],
            "kp_title": kp["title"],
            "level1": lv,
            "level1_name": kp["level1_name"],
            "type": d["type"],
            "stem": d["stem"],
            "options": d.get("options"),
            "user_answer": ua,
            "correct": res["correct"],
            "expected": res.get("expected"),
            "explain": d.get("explain"),
            "trap": d.get("trap"),
            "difficulty": d.get("difficulty", 2),
        })
        # 记录题目统计与错题
        now = db.now()
        with db.db() as conn:
            conn.execute(
                """INSERT INTO drill_stat(drill_id, kp_id, attempts, correct, last_seen, last_correct)
                   VALUES (?,?,1,?,?,?)
                   ON CONFLICT(drill_id) DO UPDATE SET
                     attempts=attempts+1, correct=correct+excluded.correct,
                     last_seen=excluded.last_seen, last_correct=excluded.last_correct""",
                (did, d["kp_id"], 1 if res["correct"] else 0, db.iso(now), 1 if res["correct"] else 0),
            )
            if not res["correct"]:
                conn.execute(
                    """INSERT INTO error_log(kp_id, drill_id, user_answer, correct_answer, source, resolved, created_at)
                       VALUES (?,?,?,?,?,0,?)""",
                    (d["kp_id"], did, ua, str(res.get("expected") or ""), "exam", db.iso(now)),
                )

    total = len(details)
    score = round(100 * hits / total, 1) if total else 0
    result = {
        "total": total,
        "hits": hits,
        "score": score,
        "grade": _grade(score),
        "levels": [
            {"id": k, "name": next((lv["name"] for lv in CONTENT.levels if lv["id"] == k), k),
             "total": v["total"], "correct": v["correct"],
             "rate": round(v["correct"] / v["total"], 2) if v["total"] else 0}
            for k, v in per_level.items()
        ],
        "details": details,
    }
    with db.db() as conn:
        conn.execute("UPDATE exam SET answers=?, submitted_at=?, result=? WHERE id=?",
                     (json.dumps(answers, ensure_ascii=False), db.iso(db.now()),
                      json.dumps(result, ensure_ascii=False), eid))
    return result


def _grade(score: float) -> str:
    if score >= 90:
        return "优秀"
    if score >= 80:
        return "良好"
    if score >= 60:
        return "及格"
    return "待补强"


def history(limit: int = 20) -> list[dict]:
    with db.db() as conn:
        rows = conn.execute("SELECT * FROM exam ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        res = json.loads(r["result"]) if r["result"] else None
        out.append({
            "id": r["id"],
            "profile": r["profile"],
            "started_at": r["started_at"],
            "submitted": bool(r["submitted_at"]),
            "score": res["score"] if res else None,
            "grade": res["grade"] if res else None,
            "total": res["total"] if res else None,
            "hits": res["hits"] if res else None,
        })
    return out
