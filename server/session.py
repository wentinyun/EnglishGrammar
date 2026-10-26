"""学习会话引擎：组卷、逐题下发、判分、结算。

一次会话（session）是一个队列，元素只有三种：
    concept  学习：展示完整讲解，读完点继续
    recall   复习：先回忆，再展开复习卡并自评（模糊/吃力/记得/熟练）
    drill    训练：一道题

学习一个知识点的流程 = concept + N 道题
复习一个知识点的流程 = recall + M 道题（顽固知识点会插入 concept 重讲）

评分规则（决定记忆曲线走向）：
    学习模式  纯按本组正确率折算，首次接触最高只给 3 分（good），避免一次做对就
              跳到十几天后
    复习模式  min(自评, 正确率折算)，取更保守的一方
    训练模式  不改动调度，只记录题目统计与错题
"""
from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timedelta

import db
import srs
import variants
from content import CONTENT
from grade import grade as grade_answer


# ---------------------------------------------------------------- 卡片

def _card(kp_id: str) -> dict | None:
    with db.db() as conn:
        row = conn.execute("SELECT * FROM card WHERE kp_id=?", (kp_id,)).fetchone()
    if not row:
        return None
    c = dict(row)
    c["due_at"] = db.parse_dt(c["due_at"])
    c["last_review"] = db.parse_dt(c["last_review"])
    c["created_at"] = db.parse_dt(c["created_at"])
    return c


def _all_cards() -> dict[str, dict]:
    with db.db() as conn:
        rows = conn.execute("SELECT * FROM card").fetchall()
    out = {}
    for row in rows:
        c = dict(row)
        c["due_at"] = db.parse_dt(c["due_at"])
        c["last_review"] = db.parse_dt(c["last_review"])
        out[c["kp_id"]] = c
    return out


def _save_card(kp_id: str, res: dict, now: datetime, is_new: bool) -> None:
    with db.db() as conn:
        if is_new:
            conn.execute(
                """INSERT INTO card(kp_id, state, stability, difficulty, due_at, last_review,
                                    reps, lapses, leech, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (kp_id, res["state"], res["stability"], res["difficulty"], db.iso(res["due_at"]),
                 db.iso(res["last_review"]), res["reps"], res["lapses"], res["leech"], db.iso(now)),
            )
        else:
            conn.execute(
                """UPDATE card SET state=?, stability=?, difficulty=?, due_at=?, last_review=?,
                                   reps=?, lapses=?, leech=? WHERE kp_id=?""",
                (res["state"], res["stability"], res["difficulty"], db.iso(res["due_at"]),
                 db.iso(res["last_review"]), res["reps"], res["lapses"], res["leech"], kp_id),
            )


# ---------------------------------------------------------------- 今日统计

def _today() -> str:
    return db.now().strftime("%Y-%m-%d")


def _day_row(day: str | None = None) -> dict:
    day = day or _today()
    with db.db() as conn:
        row = conn.execute("SELECT * FROM day_stat WHERE day=?", (day,)).fetchone()
    if not row:
        return {"day": day, "reviews": 0, "new_kp": 0, "correct": 0, "total": 0, "minutes": 0.0}
    return dict(row)


def _bump_day(reviews: int = 0, new_kp: int = 0, correct: int = 0, total: int = 0, minutes: float = 0.0) -> None:
    day = _today()
    with db.db() as conn:
        conn.execute(
            """INSERT INTO day_stat(day, reviews, new_kp, correct, total, minutes)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(day) DO UPDATE SET
                 reviews=reviews+excluded.reviews,
                 new_kp=new_kp+excluded.new_kp,
                 correct=correct+excluded.correct,
                 total=total+excluded.total,
                 minutes=minutes+excluded.minutes""",
            (day, reviews, new_kp, correct, total, minutes),
        )


# ---------------------------------------------------------------- 选题

def _drill_stats(kp_id: str) -> dict[str, dict]:
    ids = [d["id"] for d in CONTENT.kp(kp_id)["drills"]]
    if not ids:
        return {}
    q = ",".join("?" * len(ids))
    with db.db() as conn:
        rows = conn.execute(f"SELECT * FROM drill_stat WHERE drill_id IN ({q})", ids).fetchall()
    return {r["drill_id"]: dict(r) for r in rows}


def _pick_drills(kp_id: str, n: int) -> list[dict]:
    """自适应选本知识点最该做的 n 道题。

    权重设计：没做过 +4；做错过按错误率加权；距上次越久越优先；
    难度偏离中等优先级的轻微惩罚。最后保证题型尽量分散。
    """
    kp = CONTENT.kp(kp_id)
    drills = kp["drills"]
    if n >= len(drills):
        return list(drills)

    stats = _drill_stats(kp_id)
    now = db.now()
    weighted: list[tuple[dict, float]] = []
    for d in drills:
        st = stats.get(d["id"])
        w = 1.0
        if not st or not st.get("attempts"):
            w += 4.0
        else:
            acc = st["correct"] / st["attempts"]
            w += (1 - acc) * 4.0
            last = db.parse_dt(st.get("last_seen"))
            if last:
                w += min((now - last).days / 14.0, 1.5)
            if st.get("last_correct") == 0:
                w += 1.5
        w += (d.get("difficulty", 2) - 2) * 0.2
        weighted.append((d, max(0.15, w)))

    picked: list[dict] = []
    used_types: set[str] = set()
    pool = weighted[:]
    while len(picked) < n and pool:
        # 前两题优先不同类型，制造题型切换
        candidates = pool
        if len(picked) < 2:
            fresh = [(d, w) for d, w in pool if d["type"] not in used_types]
            if fresh:
                candidates = fresh
        total = sum(w for _, w in candidates)
        r = random.uniform(0, total)
        acc = 0.0
        for i, (d, w) in enumerate(candidates):
            acc += w
            if r <= acc:
                picked.append(d)
                used_types.add(d["type"])
                pool = [(x, y) for x, y in pool if x["id"] != d["id"]]
                break
    return picked



# ---------------------------------------------------------------- 变式

def _mix_variants(kp_id: str, fixed: list[dict], mode: str, gen: dict[str, dict],
                  seed: str) -> list[dict]:
    """把固定题与模板变式混排。变式的答案由模板算出，判分照旧走精确匹配。"""
    if mode == "off" or not fixed or not variants.has(kp_id):
        return fixed
    n = len(fixed)
    if mode == "only":
        want, keep = n, 0
    elif mode == "half":
        want = max(1, n // 2)
        keep = n - want
    else:
        want, keep = 1, n - 1
    made = variants.make(kp_id, want, seed=seed)
    if not made:
        return fixed
    for d in made:
        gen[d["id"]] = d
    return fixed[:keep] + made


def _drill_of(state: dict, drill_id: str) -> dict:
    d = CONTENT.drills.get(drill_id)
    if d:
        return d
    d = (state.get("gen") or {}).get(drill_id)
    if not d:
        raise KeyError(drill_id)
    return d


def _public(d: dict) -> dict:
    item = {k: d[k] for k in ("id", "kp_id", "type", "stem", "difficulty") if k in d}
    for k in ("options", "tokens", "hint"):
        if d.get(k):
            item[k] = d[k]
    item["generated"] = bool(d.get("generated"))
    return item


# ---------------------------------------------------------------- 组卷

def _due_sorted(limit: int) -> tuple[list[str], int]:
    now = db.now()
    cards = _all_cards()
    due = []
    for kp_id, c in cards.items():
        if kp_id not in CONTENT.kps:
            continue
        if c["due_at"] and c["due_at"] <= now:
            due.append((kp_id, c))
    # 顽固点优先；其次按「已遗忘程度」排序（可回忆概率越低越靠前）
    def urgency(item):
        kp_id, c = item
        last = c["last_review"]
        elapsed = (now - last).total_seconds() / 86400 if last else 999
        r = srs.retrievability(elapsed, c["stability"] or 0.1)
        return (0 if c["leech"] else 1, r)

    due.sort(key=urgency)
    return [kp_id for kp_id, _ in due[:limit]], len(due)


def _unlearned(limit: int, level1: str | None = None, chapter: str | None = None) -> list[str]:
    cards = _all_cards()
    out = []
    for kp_id in CONTENT.order:
        if kp_id in cards:
            continue
        kp = CONTENT.kps[kp_id]
        if level1 and kp["level1"] != level1:
            continue
        if chapter and kp["chapter"] != chapter:
            continue
        out.append(kp_id)
        if len(out) >= limit:
            break
    return out


def _concept_sorted(limit: int) -> list[str]:
    """「只复习概念」的队列：学过的点里，最快要忘的先看。

    排序沿用复习的紧迫度（顽固点优先，其次可回忆概率低的在前），
    但同一紧迫度下，把「最近没回看过」的提前——否则每天都是同样的八个点。
    """
    now = db.now()
    cards = _all_cards()
    with db.db() as conn:
        seen = {
            r["kp_id"]: r["d"]
            for r in conn.execute("SELECT kp_id, MAX(viewed_at) AS d FROM concept_log GROUP BY kp_id")
        }
    rows: list[tuple[tuple, str]] = []
    for kp_id, c in cards.items():
        if kp_id not in CONTENT.kps:
            continue
        last = c["last_review"]
        elapsed = (now - last).total_seconds() / 86400 if last else 999
        r = srs.retrievability(elapsed, c["stability"] or 0.1)
        viewed = db.parse_dt(seen.get(kp_id))
        quiet = (now - viewed).total_seconds() / 3600 if viewed else 9999
        rows.append(((0 if c["leech"] else 1, round(r, 4), -quiet), kp_id))
    rows.sort()
    return [kp for _, kp in rows[:limit]]


def _weak(limit: int) -> list[str]:
    """弱项：错误率高的、顽固的、以及记忆已经明显衰减的。"""
    cards = _all_cards()
    rows: list[tuple[float, str]] = []
    now = db.now()
    with db.db() as conn:
        agg = conn.execute(
            """SELECT kp_id, SUM(correct) * 1.0 / SUM(attempts) AS acc
               FROM drill_stat WHERE attempts > 0 GROUP BY kp_id"""
        ).fetchall()
    acc_map = {r["kp_id"]: r["acc"] for r in agg}
    for kp_id, c in cards.items():
        if kp_id not in CONTENT.kps:
            continue
        acc = acc_map.get(kp_id, 1.0)
        last = c["last_review"]
        elapsed = (now - last).total_seconds() / 86400 if last else 999
        r = srs.retrievability(elapsed, c["stability"] or 0.1)
        score = (1 - acc) * 2 + (1 - r) + (1.0 if c["leech"] else 0)
        rows.append((score, kp_id))
    rows.sort(reverse=True)
    return [kp for _, kp in rows[:limit]]


def build(mode: str, kp_ids: list[str] | None = None, limit: int | None = None,
          level1: str | None = None, chapter: str | None = None) -> dict:
    st = db.get_settings()
    today = _day_row()
    queue: list[dict] = []
    blocks: dict[str, dict] = {}
    chosen: list[str] = []
    skipped: list[dict] = []
    gen: dict[str, dict] = {}
    vmode = st["variant_mode"]

    if kp_ids:
        chosen = [k for k in kp_ids if k in CONTENT.kps]
    elif mode == "learn":
        cap = min(st["new_per_day"] - today["new_kp"], limit or 99)
        chosen = _unlearned(max(0, cap), level1, chapter)
    elif mode == "grow":
        # 成长拓扑模式：从「现在就能学」的前沿里按解锁价值取
        import topology
        cap = min(st["new_per_day"] - today["new_kp"], limit or 5)
        chosen = [f["id"] for f in topology.frontier(max(0, cap))]
    elif mode == "review":
        cap = min(st["review_per_day"] - today["reviews"], limit or 99)
        chosen, _ = _due_sorted(max(0, cap))
    elif mode == "concept":
        chosen = _concept_sorted(limit or st["concept_per_round"])
    elif mode == "train":
        chosen = _weak(limit or 5)

    # 前置锁定只在「学习」时生效：复习永远不该被拦（能复习说明已经学过）
    if mode == "learn" and st["prereq_gate"] and chosen:
        import topology
        states = topology.node_states()
        keep = []
        for k in chosen:
            blockers = (states.get(k) or {}).get("blocked_by") or []
            if blockers:
                skipped.append({
                    "kp_id": k,
                    "title": CONTENT.kps[k]["title"],
                    "blocked_by": [CONTENT.kps[b]["title"] for b in blockers],
                })
            else:
                keep.append(k)
        chosen = keep

    learn_n = st["learn_drills"]
    review_n = st["review_drills"]

    for kp_id in chosen:
        kp = CONTENT.kps[kp_id]
        card = _card(kp_id)
        learned = card is not None
        if mode == "concept":
            # 纯阅读：只发讲解，不发题，也不结算
            queue.append({"kind": "concept", "kp_id": kp_id})
            blocks[kp_id] = {"total": 0, "answered": 0, "concept_only": True}
            continue
        if mode in ("learn", "grow") and not learned:
            queue.append({"kind": "concept", "kp_id": kp_id})
            drills = kp["drills"][:learn_n]
        elif mode == "train":
            drills = _pick_drills(kp_id, max(4, review_n + 1))
        else:
            queue.append({"kind": "recall", "kp_id": kp_id})
            if learned and card and card.get("leech"):
                queue.append({"kind": "concept", "kp_id": kp_id})
            drills = _pick_drills(kp_id, review_n)
        drills = _mix_variants(kp_id, drills, vmode, gen, seed=kp_id + str(len(queue)))
        for d in drills:
            queue.append({"kind": "drill", "kp_id": kp_id, "drill_id": d["id"]})
        blocks[kp_id] = {"total": len(drills), "answered": 0}

    state = {
        "mode": mode,
        "queue": queue,
        "pos": 0,
        "answers": {},
        "self_rating": {},
        "blocks": blocks,
        "graded": [],
        "chosen": chosen,
        "gen": gen,
        "created_at": db.iso(db.now()),
    }
    sid = uuid.uuid4().hex[:12]
    with db.db() as conn:
        conn.execute(
            "INSERT INTO session(id, mode, config, state, started_at) VALUES (?,?,?,?,?)",
            (sid, mode, json.dumps({"kp_ids": kp_ids, "limit": limit, "level1": level1, "chapter": chapter},
                                   ensure_ascii=False), json.dumps(state, ensure_ascii=False), db.iso(db.now())),
        )
    out = get(sid)
    if skipped:
        out["skipped"] = skipped
    return out


# ---------------------------------------------------------------- 读取

def _load(sid: str) -> tuple[dict, dict]:
    with db.db() as conn:
        row = conn.execute("SELECT * FROM session WHERE id=?", (sid,)).fetchone()
    if not row:
        raise KeyError(sid)
    return dict(row), json.loads(row["state"])


def _save(sid: str, state: dict) -> None:
    with db.db() as conn:
        conn.execute("UPDATE session SET state=? WHERE id=?", (json.dumps(state, ensure_ascii=False), sid))


def _item_payload(state: dict) -> dict | None:
    if state["pos"] >= len(state["queue"]):
        return None
    q = state["queue"][state["pos"]]
    kp_id = q["kp_id"]
    item = {"kind": q["kind"], "kp_id": kp_id, "kp": CONTENT.brief(kp_id)}
    if q["kind"] in ("concept", "recall"):
        kp = CONTENT.kp(kp_id)
        item["concept"] = kp["concept"]
        item["review"] = kp["review"]
        if q["kind"] == "recall":
            card = _card(kp_id)
            item["last_review"] = db.iso(card["last_review"]) if card and card.get("last_review") else None
            item["lapses"] = card["lapses"] if card else 0
    else:
        item["drill"] = _public(_drill_of(state, q["drill_id"]))
        blk = state["blocks"].get(kp_id, {})
        item["index_in_block"] = blk.get("answered", 0) + 1
        item["block_total"] = blk.get("total", 0)
    return item


def get(sid: str) -> dict:
    row, state = _load(sid)
    answered = len(state["answers"])
    hits = sum(1 for a in state["answers"].values() if a["correct"])
    return {
        "id": sid,
        "mode": state["mode"],
        "pos": state["pos"],
        "total": len(state["queue"]),
        "answered": answered,
        "hits": hits,
        "kp_count": len(state["blocks"]),
        "item": _item_payload(state),
        "finished": state["pos"] >= len(state["queue"]),
        "summary": json.loads(row["summary"]) if row["summary"] else None,
    }


# ---------------------------------------------------------------- 答题

def _log_answer(drill: dict, user: str, res: dict, latency_ms: int, source: str) -> None:
    now = db.now()
    with db.db() as conn:
        if drill.get("generated"):
            conn.execute(
                """INSERT INTO gen_drill(id, kp_id, payload, created_at) VALUES (?,?,?,?)
                   ON CONFLICT(id) DO NOTHING""",
                (drill["id"], drill["kp_id"], json.dumps(drill, ensure_ascii=False), db.iso(now)),
            )
        conn.execute(
            """INSERT INTO drill_stat(drill_id, kp_id, attempts, correct, last_seen, last_correct)
               VALUES (?,?,1,?,?,?)
               ON CONFLICT(drill_id) DO UPDATE SET
                 attempts=attempts+1,
                 correct=correct+excluded.correct,
                 last_seen=excluded.last_seen,
                 last_correct=excluded.last_correct""",
            (drill["id"], drill["kp_id"], 1 if res["correct"] else 0, db.iso(now), 1 if res["correct"] else 0),
        )
        if res["correct"]:
            conn.execute(
                "UPDATE error_log SET resolved=1, updated_at=? WHERE drill_id=? AND resolved=0",
                (db.iso(now), drill["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO error_log(kp_id, drill_id, user_answer, correct_answer, source, resolved, created_at)
                   VALUES (?,?,?,?,?,0,?)""",
                (drill["kp_id"], drill["id"], user, str(res.get("expected") or ""), source, db.iso(now)),
            )


def _apply_card(kp_id: str, rating: int, mode: str, agg: dict) -> dict | None:
    st = db.get_settings()
    card = _card(kp_id)
    is_new = card is None
    res = srs.schedule(card, rating, db.now(), st["retention"])
    _save_card(kp_id, res, db.now(), is_new)
    with db.db() as conn:
        conn.execute(
            """INSERT INTO review_log(kp_id, drill_id, mode, rating, correct, total, hits, latency_ms,
                                      prev_stability, new_stability, interval_days, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (kp_id, None, mode, rating, 1 if agg["hits"] >= agg["total"] * 0.6 else 0,
             agg["total"], agg["hits"], agg.get("latency", 0),
             res["prev_stability"], res["stability"], res["interval_days"], db.iso(db.now())),
        )
    _bump_day(new_kp=1 if is_new else 0)
    return {
        "kp_id": kp_id,
        "rating": rating,
        "state": res["state"],
        "stability": round(res["stability"], 2),
        "difficulty": round(res["difficulty"], 2),
        "interval_days": round(res["interval_days"], 2),
        "due_at": db.iso(res["due_at"]),
        "leech": bool(res["leech"]),
        "first_time": is_new,
    }


def _grade_block_if_done(state: dict, kp_id: str) -> dict | None:
    blk = state["blocks"].get(kp_id)
    if not blk or kp_id in state["graded"]:
        return None
    if not blk.get("total"):
        # 概念回看这类没有题目的块，不参与评分
        return None
    if blk["answered"] < blk["total"]:
        return None
    graded = [a for a in state["answers"].values() if a["kp_id"] == kp_id]
    hits = sum(1 for a in graded if a["correct"])
    total = len(graded)
    latency = sum(a.get("latency_ms", 0) for a in graded)
    acc = hits / total if total else 0
    mode = state["mode"]

    if mode == "train":
        state["graded"].append(kp_id)
        return {"kp_id": kp_id, "rating": None, "accuracy": round(acc, 2), "train_only": True}

    if mode in ("learn", "grow"):
        rating = min(srs.rating_from_accuracy(acc), 3)
    else:
        rating = srs.combine_rating(state["self_rating"].get(kp_id), acc)

    out = _apply_card(kp_id, rating, mode, {"hits": hits, "total": total, "latency": latency})
    out["accuracy"] = round(acc, 2)
    state["graded"].append(kp_id)
    return out


def answer(sid: str, drill_id: str, user_answer: str, latency_ms: int = 0, hint_used: bool = False) -> dict:
    row, state = _load(sid)
    if state["pos"] >= len(state["queue"]):
        return get(sid)
    q = state["queue"][state["pos"]]
    if q["kind"] != "drill" or q["drill_id"] != drill_id:
        raise ValueError("当前题目与会话进度不一致，请刷新")

    drill = _drill_of(state, drill_id)
    res = grade_answer(drill, user_answer)
    if hint_used:
        res["partial"] = min(res["partial"], 0.99)

    state["answers"][drill_id] = {
        "kp_id": q["kp_id"],
        "correct": res["correct"],
        "partial": res["partial"],
        "user": user_answer,
        "latency_ms": latency_ms,
    }
    state["blocks"][q["kp_id"]]["answered"] += 1
    state["pos"] += 1

    _log_answer(drill, user_answer, res, latency_ms, state["mode"])
    _bump_day(reviews=1, correct=1 if res["correct"] else 0, total=1, minutes=latency_ms / 60000.0)
    graded = _grade_block_if_done(state, q["kp_id"])
    _save(sid, state)

    payload = get(sid)
    payload["result"] = {
        "correct": res["correct"],
        "partial": res["partial"],
        "expected": res.get("expected"),
        "feedback": res.get("feedback"),
        "explain": drill.get("explain"),
        "trap": drill.get("trap"),
        "answer": res.get("expected"),
        "missing": res.get("missing") or [],
        "type": drill["type"],
    }
    payload["kp_update"] = graded
    return payload


def recall(sid: str, kp_id: str, rating: int) -> dict:
    _, state = _load(sid)
    if state["pos"] < len(state["queue"]):
        q = state["queue"][state["pos"]]
        if q["kind"] == "recall" and q["kp_id"] == kp_id:
            state["self_rating"][kp_id] = int(max(1, min(4, rating)))
            state["pos"] += 1
            _save(sid, state)
    return get(sid)


def advance(sid: str) -> dict:
    """读完讲解/跳过当前非答题项。"""
    _, state = _load(sid)
    if state["pos"] < len(state["queue"]):
        q = state["queue"][state["pos"]]
        if q["kind"] in ("concept", "recall"):
            if q["kind"] == "concept" and state["mode"] == "concept":
                # 翻过去了才算读过；直接在概念回看里点退出不计
                db.log_concept_view(q["kp_id"])
            state["pos"] += 1
            _save(sid, state)
    return get(sid)


def finish(sid: str) -> dict:
    row, state = _load(sid)
    answers = list(state["answers"].values())
    hits = sum(1 for a in answers if a["correct"])
    total = len(answers)
    started = db.parse_dt(row["started_at"])
    minutes = (db.now() - started).total_seconds() / 60 if started else 0
    summary = {
        "mode": state["mode"],
        "kp_count": len(state["blocks"]),
        "answered": total,
        "hits": hits,
        "accuracy": round(hits / total, 3) if total else 0,
        "minutes": round(minutes, 1),
        "graded": state["graded"],
    }
    with db.db() as conn:
        conn.execute("UPDATE session SET ended_at=?, summary=? WHERE id=?",
                     (db.iso(db.now()), json.dumps(summary, ensure_ascii=False), sid))
    out = get(sid)
    out["summary"] = summary
    return out


def _streak() -> int:
    from datetime import date
    with db.db() as conn:
        rows = conn.execute(
            "SELECT day FROM day_stat WHERE reviews > 0 ORDER BY day DESC LIMIT 400"
        ).fetchall()
    days = {r["day"] for r in rows}
    today = db.now().date()
    cursor = today if today.isoformat() in days else today - timedelta(days=1)
    n = 0
    while cursor.isoformat() in days:
        n += 1
        cursor -= timedelta(days=1)
    return n


# ---------------------------------------------------------------- 今日计划

def plan_today() -> dict:
    st = db.get_settings()
    today = _day_row()
    _, due_total = _due_sorted(9999)
    new_left = max(0, st["new_per_day"] - today["new_kp"])
    new_available = len([k for k in CONTENT.order if k not in _all_cards()])
    reviews_left = max(0, st["review_per_day"] - today["reviews"])
    est_minutes = round(due_total * 0.55 + new_left * 4.5, 0)
    with db.db() as conn:
        views_today = conn.execute(
            "SELECT COUNT(*) AS c FROM concept_log WHERE day = ?", (_today(),)
        ).fetchone()["c"]
    return {
        "date": _today(),
        "due_total": due_total,
        "due_today": min(due_total, reviews_left) if due_total else 0,
        "new_left": new_left,
        "new_available": new_available,
        "reviews_done": today["reviews"],
        "new_done": today["new_kp"],
        "accuracy": round(today["correct"] / today["total"], 3) if today["total"] else 0,
        "minutes": round(today["minutes"], 1),
        "goal": st["daily_goal"],
        "goal_progress": min(1.0, today["reviews"] / st["daily_goal"]) if st["daily_goal"] else 0,
        "streak": _streak(),
        "est_minutes": int(est_minutes),
        "learned_total": len(_all_cards()),
        "concept_views_today": views_today,
        "concept_per_round": st["concept_per_round"],
    }
