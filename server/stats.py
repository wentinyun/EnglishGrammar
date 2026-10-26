"""统计与报表：掌握度、留存、热力图、遗忘预测、错题本。"""
from __future__ import annotations

import json
from datetime import timedelta

import db
import srs
from content import CONTENT
from session import _all_cards, _day_row


def _acc_map() -> dict[str, dict]:
    with db.db() as conn:
        rows = conn.execute(
            """SELECT kp_id,
                      COUNT(*) AS tried,
                      SUM(attempts) AS attempts,
                      SUM(correct) AS correct
               FROM drill_stat WHERE attempts > 0 GROUP BY kp_id"""
        ).fetchall()
    out = {}
    for r in rows:
        out[r["kp_id"]] = {
            "tried": r["tried"],
            "attempts": r["attempts"],
            "acc": (r["correct"] / r["attempts"]) if r["attempts"] else 0.0,
        }
    return out


def kp_progress() -> dict[str, dict]:
    """每个知识点的状态与掌握度，供课程树与筛选使用。"""
    cards = _all_cards()
    accs = _acc_map()
    now = db.now()
    out = {}
    for kp_id in CONTENT.order:
        card = cards.get(kp_id)
        acc = accs.get(kp_id)
        tried = acc["tried"] if acc else 0
        coverage = min(tried / max(1, len(CONTENT.kps[kp_id]["drills"])), 1.0)
        m = srs.mastery(card, acc["acc"] if acc else 0.0, coverage, now)
        status = srs.status_of(card, m)
        due = card["due_at"] if card else None
        out[kp_id] = {
            "status": status,
            "mastery": m,
            "due_at": db.iso(due) if due else None,
            "reps": card["reps"] if card else 0,
            "lapses": card["lapses"] if card else 0,
            "stability": round(card["stability"], 1) if card else 0,
            "tried": tried,
        }
    return out


def overview() -> dict:
    cards = _all_cards()
    prog = kp_progress()
    now = db.now()
    total = len(CONTENT.order)
    counts = {"new": 0, "review": 0, "relearning": 0, "leech": 0, "mastered": 0}
    due_now = 0
    due_24h = 0
    ms = []
    for kp_id, p in prog.items():
        counts[p["status"]] = counts.get(p["status"], 0) + 1
        if p["status"] != "new":
            ms.append(p["mastery"])
        card = cards.get(kp_id)
        if card and card["due_at"]:
            if card["due_at"] <= now:
                due_now += 1
            if card["due_at"] <= now + timedelta(hours=24):
                due_24h += 1
    with db.db() as conn:
        tot = conn.execute("SELECT COUNT(*) AS c, SUM(correct) AS ok, SUM(total) AS t, SUM(minutes) AS m FROM day_stat").fetchone()
        days = conn.execute("SELECT COUNT(*) AS c FROM day_stat WHERE reviews > 0").fetchone()
        learned_at = conn.execute("SELECT MIN(created_at) AS d FROM card").fetchone()
        cv = conn.execute("SELECT COUNT(*) AS c, COUNT(DISTINCT kp_id) AS k FROM concept_log").fetchone()

    total_answers = tot["t"] or 0
    return {
        "total_kp": total,
        "learned": total - counts["new"],
        "unlearned": counts["new"],
        "mastered": counts["mastered"],
        "reviewing": counts["review"] + counts["relearning"],
        "leech": counts["leech"],
        "due_now": due_now,
        "due_24h": due_24h,
        "avg_mastery": round(sum(ms) / len(ms), 1) if ms else 0.0,
        "answers_total": total_answers,
        "accuracy": round((tot["ok"] or 0) / total_answers, 3) if total_answers else 0,
        "minutes_total": round(tot["m"] or 0, 1),
        "active_days": days["c"] or 0,
        "started_at": learned_at["d"],
        "streak": streak(),
        "concept_reads": cv["c"] or 0,
        "concept_kps": cv["k"] or 0,
        "levels": level_mastery(prog),
    }


def streak() -> int:
    with db.db() as conn:
        rows = conn.execute(
            "SELECT day FROM day_stat WHERE reviews > 0 ORDER BY day DESC LIMIT 400"
        ).fetchall()
    days = [r["day"] for r in rows]
    if not days:
        return 0
    today = db.now().date()
    from datetime import date
    parsed = []
    for d in days:
        try:
            parsed.append(date.fromisoformat(d))
        except ValueError:
            continue
    if not parsed:
        return 0
    # 今天还没学不断签，从昨天开始算
    cursor = today if parsed[0] == today else today - timedelta(days=1)
    n = 0
    ps = set(parsed)
    while cursor in ps:
        n += 1
        cursor -= timedelta(days=1)
    return n


def level_mastery(prog: dict | None = None) -> list[dict]:
    prog = prog or kp_progress()
    out = []
    for lv in CONTENT.levels:
        ids = [k for ch in lv["chapters"] for k in ch["points"]]
        vals = [prog[i]["mastery"] for i in ids if prog[i]["status"] != "new"]
        learned = sum(1 for i in ids if prog[i]["status"] != "new")
        out.append({
            "id": lv["id"],
            "name": lv["name"],
            "total": len(ids),
            "learned": learned,
            "mastery": round(sum(vals) / len(vals), 1) if vals else 0.0,
            "due": sum(1 for i in ids if prog[i]["due_at"] and db.parse_dt(prog[i]["due_at"]) <= db.now()),
        })
    return out


def heatmap(days: int = 182) -> list[dict]:
    start = (db.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    with db.db() as conn:
        rows = conn.execute(
            "SELECT day, reviews, new_kp, correct, total FROM day_stat WHERE day >= ? ORDER BY day",
            (start,),
        ).fetchall()
    m = {r["day"]: dict(r) for r in rows}
    out = []
    for i in range(days):
        d = (db.now() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        r = m.get(d)
        out.append({
            "day": d,
            "reviews": r["reviews"] if r else 0,
            "new": r["new_kp"] if r else 0,
            "accuracy": round(r["correct"] / r["total"], 2) if r and r["total"] else None,
        })
    return out


def forecast(days: int = 14) -> list[dict]:
    cards = _all_cards()
    now = db.now()
    buckets = {i: 0 for i in range(days + 1)}  # 0 = 已过期
    for kp_id, c in cards.items():
        if kp_id not in CONTENT.kps or not c["due_at"]:
            continue
        delta = (c["due_at"].date() - now.date()).days
        if delta < 0:
            buckets[0] += 1
        elif delta <= days:
            buckets[delta] += 1
    out = []
    for i in range(days + 1):
        d = now + timedelta(days=i)
        out.append({
            "day": d.strftime("%Y-%m-%d"),
            "label": "今天" if i == 0 else f"{d.month}/{d.day}",
            "count": buckets[i],
        })
    return out


def retention() -> dict:
    """可回忆概率分布：用于发现「即将遗忘但还没到期」的知识点。"""
    cards = _all_cards()
    now = db.now()
    rows = []
    for kp_id, c in cards.items():
        if kp_id not in CONTENT.kps or not c["stability"]:
            continue
        last = c["last_review"]
        elapsed = (now - last).total_seconds() / 86400 if last else 0
        r = srs.retrievability(elapsed, c["stability"])
        brief = CONTENT.brief(kp_id)
        rows.append({"kp_id": kp_id, "r": round(r, 3), "stability": round(c["stability"], 1),
                     "title": brief["title"], "level1_name": brief["level1_name"],
                     "chapter_name": brief["chapter_name"]})
    buckets = {"0-50": 0, "50-70": 0, "70-85": 0, "85-95": 0, "95-100": 0}
    for x in rows:
        r = x["r"] * 100
        if r < 50:
            buckets["0-50"] += 1
        elif r < 70:
            buckets["50-70"] += 1
        elif r < 85:
            buckets["70-85"] += 1
        elif r < 95:
            buckets["85-95"] += 1
        else:
            buckets["95-100"] += 1
    soon = sorted([x for x in rows if x["r"] < 0.8], key=lambda x: x["r"])[:12]
    return {
        "buckets": buckets,
        "at_risk": soon,
        "avg": round(sum(x["r"] for x in rows) / len(rows), 3) if rows else 0,
    }


def weak(limit: int = 20) -> list[dict]:
    prog = kp_progress()
    accs = _acc_map()
    items = []
    for kp_id, p in prog.items():
        if p["status"] == "new":
            continue
        acc = accs.get(kp_id, {}).get("acc", 1.0)
        score = (1 - acc) * 2 + (1 if p["status"] == "leech" else 0) + (1 - p["mastery"] / 100)
        items.append((score, kp_id, acc))
    items.sort(reverse=True)
    out = []
    for score, kp_id, acc in items[:limit]:
        out.append({
            **CONTENT.brief(kp_id),
            "mastery": prog[kp_id]["mastery"],
            "accuracy": round(acc, 2),
            "status": prog[kp_id]["status"],
            "lapses": prog[kp_id]["lapses"],
        })
    return out


def errors(limit: int = 200, kp_id: str | None = None) -> dict:
    sql = """SELECT e.*, k.title AS kp_title, k.chapter_name, k.level1_name
             FROM error_log e JOIN (SELECT 1) dummy
             LEFT JOIN (SELECT 1) x ON 1=1"""
    # 上面只是占位，实际用 python 侧补 kp 信息，避免为错误表再建关联表
    with db.db() as conn:
        if kp_id:
            rows = conn.execute(
                "SELECT * FROM error_log WHERE kp_id=? ORDER BY created_at DESC LIMIT ?", (kp_id, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM error_log ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        total = conn.execute("SELECT COUNT(*) AS c FROM error_log WHERE resolved=0").fetchone()["c"]
    out = []
    gen_ids = [r["drill_id"] for r in rows if r["drill_id"] not in CONTENT.drills]
    gen_map: dict[str, dict] = {}
    if gen_ids:
        q = ",".join("?" * len(gen_ids))
        with db.db() as conn:
            grows = conn.execute(
                f"SELECT id, payload FROM gen_drill WHERE id IN ({q})", gen_ids
            ).fetchall()
        for g in grows:
            gen_map[g["id"]] = json.loads(g["payload"])

    for r in rows:
        d = CONTENT.drills.get(r["drill_id"]) or gen_map.get(r["drill_id"])
        brief = CONTENT.brief(r["kp_id"]) if r["kp_id"] in CONTENT.kps else None
        out.append({
            "id": r["id"],
            "kp_id": r["kp_id"],
            "kp_title": brief["title"] if brief else r["kp_id"],
            "level1_name": brief["level1_name"] if brief else "",
            "chapter_name": brief["chapter_name"] if brief else "",
            "drill_id": r["drill_id"],
            "type": d["type"] if d else "",
            "stem": d["stem"] if d else "",
            "options": d.get("options") if d else None,
            "user_answer": r["user_answer"],
            "correct_answer": r["correct_answer"],
            "explain": d.get("explain") if d else "",
            "generated": bool(d.get("generated")) if d else False,
            "resolved": bool(r["resolved"]),
            "created_at": r["created_at"],
            "source": r["source"],
        })
    return {"total_unresolved": total, "items": out}


def kp_detail_stats(kp_id: str) -> dict:
    with db.db() as conn:
        log = conn.execute(
            "SELECT * FROM review_log WHERE kp_id=? ORDER BY created_at DESC LIMIT 30", (kp_id,)
        ).fetchall()
        errs = conn.execute(
            "SELECT COUNT(*) AS c FROM error_log WHERE kp_id=? AND resolved=0", (kp_id,)
        ).fetchone()["c"]
    return {
        "history": [dict(r) for r in log],
        "unresolved_errors": errs,
    }


def export_all() -> dict:
    with db.db() as conn:
        data = {t: [dict(r) for r in conn.execute(f"SELECT * FROM {t}").fetchall()]
                for t in ("card", "review_log", "drill_stat", "error_log", "day_stat", "setting", "concept_log")}
    data["_meta"] = {"app": "EnglishGrammar", "version": 1, "exported_at": db.iso(db.now())}
    return data


def import_all(data: dict) -> dict:
    need = {"card", "drill_stat", "day_stat", "error_log", "review_log"}
    if not need.issubset(data.keys()):
        raise ValueError("备份文件格式不正确，缺少表：" + ", ".join(sorted(need - set(data.keys()))))
    with db.db() as conn:
        for t in ("card", "review_log", "drill_stat", "error_log", "day_stat"):
            conn.execute(f"DELETE FROM {t}")
        for r in data["card"]:
            conn.execute(
                """INSERT INTO card(kp_id, state, stability, difficulty, due_at, last_review, reps, lapses, leech, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (r["kp_id"], r["state"], r["stability"], r["difficulty"], r["due_at"], r["last_review"],
                 r["reps"], r["lapses"], r["leech"], r["created_at"]),
            )
        for r in data["drill_stat"]:
            conn.execute(
                """INSERT INTO drill_stat(drill_id, kp_id, attempts, correct, last_seen, last_correct)
                   VALUES (?,?,?,?,?,?)""",
                (r["drill_id"], r["kp_id"], r["attempts"], r["correct"], r["last_seen"], r["last_correct"]),
            )
        for r in data["day_stat"]:
            conn.execute(
                "INSERT INTO day_stat(day, reviews, new_kp, correct, total, minutes) VALUES (?,?,?,?,?,?)",
                (r["day"], r["reviews"], r["new_kp"], r["correct"], r["total"], r["minutes"]),
            )
        for r in data["error_log"]:
            conn.execute(
                """INSERT INTO error_log(kp_id, drill_id, user_answer, correct_answer, source, resolved, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (r["kp_id"], r["drill_id"], r["user_answer"], r["correct_answer"], r["source"],
                 r["resolved"], r["created_at"], r.get("updated_at")),
            )
        for r in data["review_log"]:
            conn.execute(
                """INSERT INTO review_log(kp_id, drill_id, mode, rating, correct, total, hits, latency_ms,
                                          prev_stability, new_stability, interval_days, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (r["kp_id"], r["drill_id"], r["mode"], r["rating"], r["correct"], r["total"], r["hits"],
                 r["latency_ms"], r["prev_stability"], r["new_stability"], r["interval_days"], r["created_at"]),
            )
        conn.execute("DELETE FROM concept_log")
        for r in data.get("concept_log") or []:
            conn.execute(
                "INSERT INTO concept_log(kp_id, day, viewed_at) VALUES (?,?,?)",
                (r["kp_id"], r["day"], r["viewed_at"]),
            )
    return {"imported": True}


def reset(scope: str = "all") -> dict:
    with db.db() as conn:
        if scope in ("all", "progress"):
            for t in ("card", "review_log", "drill_stat", "error_log", "day_stat", "session", "exam", "concept_log"):
                conn.execute(f"DELETE FROM {t}")
        elif scope == "errors":
            conn.execute("DELETE FROM error_log")
        elif scope == "sessions":
            conn.execute("DELETE FROM session")
    return {"ok": True, "scope": scope}
