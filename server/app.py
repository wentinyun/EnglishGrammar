"""FastAPI 入口：内容 + 学习引擎 + 统计 + 考试，并托管构建后的前端。"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import db
import exam as exam_mod
import session as sess
import stats
import topology
from content import CONTENT, ContentError

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "web" / "site"

app = FastAPI(title="英语语法全景学习系统", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    try:
        CONTENT.load()
    except ContentError as e:
        raise RuntimeError(str(e))


# ---------------------------------------------------------------- 请求体

class StartReq(BaseModel):
    mode: str = "learn"
    kp_ids: list[str] | None = None
    limit: int | None = None
    level1: str | None = None
    chapter: str | None = None


class AnswerReq(BaseModel):
    drill_id: str
    answer: str = ""
    latency_ms: int = 0
    hint_used: bool = False


class RecallReq(BaseModel):
    kp_id: str
    rating: int


class ExamStartReq(BaseModel):
    profile: str
    count: int | None = None


class ExamSubmitReq(BaseModel):
    answers: dict[str, str] = {}


class SettingsReq(BaseModel):
    retention: float | None = None
    new_per_day: int | None = None
    review_per_day: int | None = None
    learn_drills: int | None = None
    review_drills: int | None = None
    daily_goal: int | None = None
    show_hint: bool | None = None
    prereq_gate: bool | None = None
    variant_mode: str | None = None
    concept_per_round: int | None = None


class ImportReq(BaseModel):
    data: dict


# ---------------------------------------------------------------- 内容

@app.get("/api/health")
def health():
    return {"ok": True, "kps": len(CONTENT.order), "drills": len(CONTENT.drills)}


@app.get("/api/curriculum")
def curriculum():
    prog = stats.kp_progress()
    tree = CONTENT.tree()
    for lv in tree:
        for ch in lv["chapters"]:
            ch["points"] = [
                {**CONTENT.brief(kp_id), **{k: prog[kp_id][k] for k in ("status", "mastery", "due_at", "tried")}}
                for kp_id in ch["points"]
            ]
    return {
        "levels": tree,
        "counts": {
            "total": len(CONTENT.order),
            "drills": len(CONTENT.drills),
            "chapters": sum(len(lv["chapters"]) for lv in CONTENT.levels),
        },
    }


@app.get("/api/kp/{kp_id}")
def kp_detail(kp_id: str):
    if kp_id not in CONTENT.kps:
        raise HTTPException(404, "知识点不存在")
    prog = stats.kp_progress().get(kp_id)
    return {
        **CONTENT.public_kp(kp_id),
        "progress": prog,
        "stats": stats.kp_detail_stats(kp_id),
    }


@app.get("/api/progress")
def progress():
    return stats.kp_progress()


# ---------------------------------------------------------------- 会话

@app.post("/api/session/start")
def session_start(req: StartReq):
    if req.mode not in ("learn", "review", "train", "grow", "concept"):
        raise HTTPException(400, "mode 必须是 learn / review / train / grow / concept")
    try:
        out = sess.build(req.mode, req.kp_ids, req.limit, req.level1, req.chapter)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, str(e))
    if not out["total"]:
        if req.mode == "concept":
            raise HTTPException(409, "还没有学过的知识点，先学一个再来回看")
        skipped = out.get("skipped") or []
        if skipped:
            detail = "；".join(f"《{s['title']}》缺 {('、'.join(s['blocked_by']))}" for s in skipped[:3])
            raise HTTPException(409, f"前置未完成，已拦下：{detail}")
        raise HTTPException(409, "没有可安排的内容：可能今天的新学/复习配额已用完")
    return out


@app.get("/api/session/{sid}")
def session_get(sid: str):
    try:
        return sess.get(sid)
    except KeyError:
        raise HTTPException(404, "会话不存在")


@app.post("/api/session/{sid}/answer")
def session_answer(sid: str, req: AnswerReq):
    try:
        return sess.answer(sid, req.drill_id, req.answer, req.latency_ms, req.hint_used)
    except KeyError:
        raise HTTPException(404, "会话不存在")
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/session/{sid}/recall")
def session_recall(sid: str, req: RecallReq):
    try:
        return sess.recall(sid, req.kp_id, req.rating)
    except KeyError:
        raise HTTPException(404, "会话不存在")


@app.post("/api/session/{sid}/advance")
def session_advance(sid: str):
    try:
        return sess.advance(sid)
    except KeyError:
        raise HTTPException(404, "会话不存在")


@app.post("/api/session/{sid}/finish")
def session_finish(sid: str):
    try:
        return sess.finish(sid)
    except KeyError:
        raise HTTPException(404, "会话不存在")


@app.get("/api/plan")
def plan():
    return sess.plan_today()


# ---------------------------------------------------------------- 成长拓扑

@app.get("/api/topology")
def topology_graph(granularity: str = "chapter"):
    if granularity not in ("chapter", "point"):
        raise HTTPException(400, "granularity 必须是 chapter 或 point")
    return {**topology.graph(granularity), "summary": topology.summary()}


@app.get("/api/topology/frontier")
def topology_frontier(limit: int = 8, include_learning: bool = False):
    return topology.frontier(limit, include_learning)


@app.get("/api/topology/path/{kp_id}")
def topology_path(kp_id: str):
    try:
        return topology.path_to(kp_id)
    except KeyError:
        raise HTTPException(404, "知识点不存在")


# ---------------------------------------------------------------- 统计

@app.get("/api/stats/overview")
def overview():
    return stats.overview()


@app.get("/api/stats/heatmap")
def heatmap(days: int = 182):
    return stats.heatmap(days)


@app.get("/api/stats/forecast")
def forecast(days: int = 14):
    return stats.forecast(days)


@app.get("/api/stats/retention")
def retention():
    return stats.retention()


@app.get("/api/stats/weak")
def weak(limit: int = 20):
    return stats.weak(limit)


@app.get("/api/errors")
def errors(limit: int = 200, kp_id: str | None = None):
    return stats.errors(limit, kp_id)


@app.post("/api/errors/clear")
def errors_clear():
    return stats.reset("errors")


# ---------------------------------------------------------------- 考试

@app.get("/api/exam/profiles")
def exam_profiles():
    return exam_mod.list_profiles()


@app.get("/api/exam/history")
def exam_history(limit: int = 20):
    return exam_mod.history(limit)


@app.post("/api/exam/start")
def exam_start(req: ExamStartReq):
    try:
        return exam_mod.start(req.profile, req.count)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/exam/{eid}")
def exam_get(eid: str):
    try:
        return exam_mod.get(eid)
    except KeyError:
        raise HTTPException(404, "试卷不存在")


@app.post("/api/exam/{eid}/submit")
def exam_submit(eid: str, req: ExamSubmitReq):
    try:
        return exam_mod.submit(eid, req.answers)
    except KeyError:
        raise HTTPException(404, "试卷不存在")


# ---------------------------------------------------------------- 设置与备份

@app.get("/api/variants/info")
def variants_info():
    import variants as variants_mod
    kps = variants_mod.supported()
    sample = []
    for kp in kps[:3]:
        sample.extend(variants_mod.make(kp, 1, seed="preview"))
    return {
        "supported": len(kps),
        "total_kp": len(CONTENT.order),
        "kps": kps,
        "sample": [{"kp_id": d["kp_id"], "type": d["type"], "stem": d["stem"]} for d in sample],
    }


@app.get("/api/settings")
def settings_get():
    return db.get_settings()


@app.post("/api/settings")
def settings_set(req: SettingsReq):
    patch = {k: v for k, v in req.dict().items() if v is not None}
    if patch.get("variant_mode") not in (None, "off", "mix", "half", "only"):
        raise HTTPException(400, "variant_mode 只能是 off / mix / half / only")
    if patch.get("concept_per_round") is not None:
        n = int(patch["concept_per_round"])
        if not 3 <= n <= 30:
            raise HTTPException(400, "concept_per_round 需要在 3 到 30 之间")
    return db.save_settings(patch)


@app.get("/api/export")
def export():
    return JSONResponse(stats.export_all())


@app.post("/api/import")
def import_data(req: ImportReq):
    try:
        return stats.import_all(req.data)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/reset")
def reset(scope: str = "all"):
    return stats.reset(scope)


# ---------------------------------------------------------------- 前端

if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        target = DIST / full_path
        if full_path and target.is_file():
            return FileResponse(target)
        return FileResponse(DIST / "index.html")
else:
    @app.get("/")
    def no_frontend():
        return {"message": "前端尚未构建。请执行 cd web && npm install && npm run build"}
