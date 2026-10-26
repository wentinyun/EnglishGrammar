"""后端冒烟测试：不启 HTTP，直接跑会话引擎全流程。"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

import db  # noqa: E402

# 用独立测试库，避免污染真实学习记录
TEST_DB = ROOT / "data" / "test_smoke.db"
if TEST_DB.exists():
    TEST_DB.unlink()
db.DB_PATH = TEST_DB
db.DATA_DIR = TEST_DB.parent

db.init_db()
from content import CONTENT  # noqa: E402

CONTENT.load()
import session  # noqa: E402
import stats  # noqa: E402
import exam as exam_mod  # noqa: E402


def run_session(mode: str, kp_ids=None, limit=None):
    s = session.build(mode, kp_ids, limit)
    steps = 0
    while s["item"] and steps < 200:
        item = s["item"]
        steps += 1
        if item["kind"] == "drill":
            _row, state = session._load(s["id"])
            d = session._drill_of(state, item["drill"]["id"])
            ans = d["answer"]
            s = session.answer(s["id"], d["id"], str(ans), 4200)
        elif item["kind"] == "recall":
            s = session.recall(s["id"], item["kp_id"], 3)
        else:
            s = session.advance(s["id"])
    return session.finish(s["id"])


def main() -> None:
    print(f"内容: {len(CONTENT.order)} 知识点 / {len(CONTENT.drills)} 题 / {len(CONTENT.levels)} 一级分类")

    r1 = run_session("learn", limit=3)
    print("learn  ->", r1["summary"])

    r2 = run_session("review")
    print("review ->", r2["summary"])

    ov = stats.overview()
    print("overview:", {k: ov[k] for k in ("learned", "mastered", "due_now", "avg_mastery", "accuracy", "streak")})

    w = stats.weak(3)
    print("weak:", [x["title"] for x in w])

    r = stats.retention()
    print("retention:", r["buckets"], "avg", r["avg"])

    # 复习到期检查
    cards = session._all_cards()
    print("cards:", len(cards), "示例:", list(cards.values())[0]["state"],
          round(list(cards.values())[0]["stability"], 2))

    e = exam_mod.start("gaokao", 10)
    print("exam paper:", len(e["questions"]), "题; 首题:", e["questions"][0]["type"])
    res = exam_mod.submit(e["id"], {q["id"]: CONTENT.drills[q["id"]]["answer"] for q in e["questions"]})
    print("exam result:", res["score"], res["grade"], len(res["details"]))

    er = stats.errors(5)
    print("errors:", er["total_unresolved"], "| 变式题:", sum(1 for i in er["items"] if i["generated"]))

    # 判分抽样：故意答错
    d = CONTENT.drills[CONTENT.order[0] and CONTENT.kps[CONTENT.order[0]]["drills"][0]["id"]]
    from grade import grade as g

    print("grade wrong:", g(d, "___nonsense___")["correct"])

    # 概念回看：只发讲解、不发题、不动排期
    cards_before = {k: (v["stability"], v["difficulty"], v["reps"], v["due_at"])
                    for k, v in session._all_cards().items()}
    cv = session.build("concept")
    kinds, viewed = set(), 0
    while True:
        st = session.get(cv["id"])
        if st["finished"]:
            break
        kinds.add(st["item"]["kind"])
        if st["item"]["kind"] == "concept":
            viewed += 1
            session.advance(cv["id"])
        else:  # 概念模式不该出现别的题型
            raise SystemExit(f"concept 模式出现了 {st['item']['kind']}")
    csm = session.finish(cv["id"])["summary"]

    cards_after = {k: (v["stability"], v["difficulty"], v["reps"], v["due_at"])
                   for k, v in session._all_cards().items()}
    with db.db() as conn:
        logged = conn.execute("SELECT COUNT(*) AS c FROM concept_log").fetchone()["c"]
    print(f"concept: {cv['total']} 点 / 读到 {viewed} / 题型 {kinds} / 排期未变 {cards_before == cards_after}"
          f" / 记录 {logged} / 用时 {csm['minutes']} 分")

    print("OK")


if __name__ == "__main__":
    main()
