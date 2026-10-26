"""成长拓扑：把 prereq 依赖图变成一张能走的地图。

设计要点
--------
1. **点级深度**用最长前置链计算（DAG，已校验无环）。深度就是「第几层」，同一层
   的知识点彼此无依赖，可以任意顺序学。
2. **章级深度**不能直接按最长链算：知识点之间互有引用（A 章的某点依赖 B 章，
   B 章另一点又依赖 A 章），章级会出现环。正确处理是把强连通分量（SCC）缩成
   一个超节点，在缩点后的 DAG 上算最长链，同一 SCC 的章节共享同一层。
3. **状态**只有四种：locked（前置未学）/ ready（可学）/ learning（学过未掌握）
   / mastered。locked 只由「前置是否从未学过」决定，不因为前置遗忘而重新上锁
   —— 否则用户会被反复弹回原点，那是最劝退的设计。
4. **解锁价值** = 该点传递闭包上的后置节点数。它是「先学哪个」的排序依据：
   同样可学，先学能开出更多路的那一个。
"""
from __future__ import annotations

from functools import lru_cache

from content import CONTENT

# ---------------------------------------------------------------- 图结构缓存

_cache: dict = {}


def _build_point_graph() -> dict:
    ids = list(CONTENT.order)
    idx = {k: i for i, k in enumerate(ids)}
    parents: dict[str, list[str]] = {}
    children: dict[str, list[str]] = {k: [] for k in ids}
    for k in ids:
        pre = [p for p in (CONTENT.kps[k].get("prereq") or []) if p in idx]
        parents[k] = pre
        for p in pre:
            children[p].append(k)

    # 最长链深度（DAG，迭代实现避免递归深度问题）
    depth: dict[str, int] = {}
    indeg = {k: len(parents[k]) for k in ids}
    ready = [k for k in ids if indeg[k] == 0]
    for k in ready:
        depth[k] = 0
    order: list[str] = []
    while ready:
        u = ready.pop()
        order.append(u)
        for v in children[u]:
            depth[v] = max(depth.get(v, 0), depth[u] + 1)
            indeg[v] -= 1
            if indeg[v] == 0:
                ready.append(v)
    if len(order) != len(ids):  # 理论上不会发生，内容校验会先拦下
        raise RuntimeError("成长拓扑检测到循环依赖，请检查 content 的 prereq")

    # 传递后置（解锁价值）：按逆拓扑序累加，集合运算
    desc: dict[str, set[str]] = {k: set() for k in ids}
    for u in reversed(order):
        for v in children[u]:
            desc[u].add(v)
            desc[u] |= desc[v]

    # 传递前置（去某点需要先过哪些）：正向拓扑累加
    anc: dict[str, set[str]] = {k: set() for k in ids}
    for u in order:
        for v in children[u]:
            anc[v] |= anc[u]
            anc[v].add(u)

    return {
        "ids": ids,
        "parents": parents,
        "children": children,
        "depth": depth,
        "desc": desc,
        "anc": anc,
        "max_depth": max(depth.values()) if depth else 0,
    }


def _point_graph() -> dict:
    key = ("point", len(CONTENT.order))
    if _cache.get("key") != key:
        _cache.clear()
        _cache["key"] = key
        _cache["point"] = _build_point_graph()
    return _cache["point"]


# ---------------------------------------------------------------- 章级图（SCC 缩点）


def _build_chapter_graph() -> dict:
    """章级图：先把同章内的边折叠掉，再对章间边做 SCC 缩点后算层。"""
    g = _point_graph()
    nodes = []          # [(level1, slug)]
    node_of: dict[str, tuple[str, str]] = {}
    for lv in CONTENT.levels:
        for ch in lv["chapters"]:
            cid = (lv["id"], ch["slug"])
            nodes.append(cid)
            for kp_id in ch["points"]:
                node_of[kp_id] = cid

    weight: dict[tuple, int] = {}
    for u in g["ids"]:
        for v in g["children"][u]:
            a, b = node_of[u], node_of[v]
            if a == b:
                continue
            weight[(a, b)] = weight.get((a, b), 0) + 1

    adj: dict[tuple, list[tuple]] = {c: [] for c in nodes}
    radj: dict[tuple, list[tuple]] = {c: [] for c in nodes}
    for (a, b) in weight:
        adj[a].append(b)
        radj[b].append(a)

    # Tarjan 强连通分量
    index: dict[tuple, int] = {}
    low: dict[tuple, int] = {}
    on_stack: dict[tuple, bool] = {}
    stack: list[tuple] = []
    scc_of: dict[tuple, int] = {}
    sccs: list[list[tuple]] = []
    counter = [0]

    def strong(v: tuple) -> None:  # 迭代版 Tarjan
        work = [(v, 0)]
        while work:
            node, pi = work.pop()
            if pi == 0:
                index[node] = low[node] = counter[0]
                counter[0] += 1
                stack.append(node)
                on_stack[node] = True
            else:
                # 孩子处理完回来，回填 low
                child = adj[node][pi - 1]
                low[node] = min(low[node], low[child])
            recurse = False
            for i in range(pi, len(adj[node])):
                w = adj[node][i]
                if w not in index:
                    work.append((node, i + 1))
                    work.append((w, 0))
                    recurse = True
                    break
                if on_stack.get(w):
                    low[node] = min(low[node], index[w])
            if recurse:
                continue
            if low[node] == index[node]:
                comp = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    scc_of[w] = len(sccs)
                    comp.append(w)
                    if w == node:
                        break
                sccs.append(comp)

    for c in nodes:
        if c not in index:
            strong(c)

    # 缩点后算层
    n_comp = len(sccs)
    cadj: dict[int, set[int]] = {i: set() for i in range(n_comp)}
    cpar: dict[int, set[int]] = {i: set() for i in range(n_comp)}
    for (a, b) in weight:
        ca, cb = scc_of[a], scc_of[b]
        if ca != cb:
            cadj[ca].add(cb)
            cpar[cb].add(ca)

    cdepth = {i: 0 for i in range(n_comp)}
    for _ in range(n_comp + 1):
        changed = False
        for ca in range(n_comp):
            for cb in cadj[ca]:
                if cdepth[cb] < cdepth[ca] + 1:
                    cdepth[cb] = cdepth[ca] + 1
                    changed = True
        if not changed:
            break

    chapter_depth = {c: cdepth[scc_of[c]] for c in nodes}

    # 只保留「向前」的边用于绘制，回边（同层/逆向）单独标记
    edges = []
    for (a, b), w in weight.items():
        edges.append({
            "from": f"{a[0]}.{a[1]}",
            "to": f"{b[0]}.{b[1]}",
            "weight": w,
            "back": chapter_depth[a] >= chapter_depth[b],
        })

    return {
        "nodes": nodes,
        "node_of": node_of,
        "chapter_depth": chapter_depth,
        "edges": edges,
        "weight": weight,
        "scc_size": {c: len(sccs[scc_of[c]]) for c in nodes},
        "cycles": [s for s in sccs if len(s) > 1],
    }


def chapter_graph() -> dict:
    key = ("chapter", len(CONTENT.order))
    if _cache.get("key") != key:
        _point_graph()
    if "chapter" not in _cache:
        _cache["chapter"] = _build_chapter_graph()
    return _cache["chapter"]


# ---------------------------------------------------------------- 状态

def _level_names() -> dict[str, str]:
    return {lv["id"]: lv["name"] for lv in CONTENT.levels}


def _progress() -> dict[str, dict]:
    from stats import kp_progress
    return kp_progress()


def node_states(progress: dict[str, dict] | None = None) -> dict[str, dict]:
    g = _point_graph()
    prog = progress or _progress()
    states: dict[str, dict] = {}
    for k in g["ids"]:
        p = prog.get(k) or {"status": "new", "mastery": 0}
        learned = p["status"] != "new"
        blockers = [b for b in g["parents"][k] if (prog.get(b) or {}).get("status", "new") == "new"]
        if not learned and blockers:
            state = "locked"
        elif not learned:
            state = "ready"
        elif p["status"] == "mastered":
            state = "mastered"
        else:
            state = "learning"
        states[k] = {
            "state": state,
            "mastery": round(p["mastery"], 1),
            "status": p["status"],
            "blocked_by": blockers,
            "unlocks": len(g["desc"][k]),
            "depth": g["depth"][k],
        }
    return states


# ---------------------------------------------------------------- 对外：整图

def graph(granularity: str = "chapter", include_states: bool = True) -> dict:
    prog = _progress() if include_states else None
    st = node_states(prog) if include_states else {}

    if granularity == "chapter":
        cg = chapter_graph()
        pol = {}
        for lv in CONTENT.levels:
            for ch in lv["chapters"]:
                pts = ch["points"]
                pol[(lv["id"], ch["slug"])] = pts
        nodes = []
        for (lv_id, slug) in cg["nodes"]:
            pts = pol[(lv_id, slug)]
            kids = [st[p] for p in pts] if st else []
            learned = sum(1 for x in kids if x["state"] in ("learning", "mastered"))
            mastered = sum(1 for x in kids if x["state"] == "mastered")
            ready = sum(1 for x in kids if x["state"] == "ready")
            locked = sum(1 for x in kids if x["state"] == "locked")
            mastery = sum(x["mastery"] for x in kids) / len(kids) if kids else 0
            ch_meta = CONTENT.chapter_of[slug]
            # 章级状态：有可学点就能进；全锁定才是 locked
            if ready:
                state = "ready"
            elif locked:
                state = "locked"
            elif mastered == len(pts):
                state = "mastered"
            elif learned:
                state = "learning"
            else:
                state = "ready"
            # 章级前置：在别的章里、且还没学的点所属的章
            blocker_ids = sorted({
                f"{cg['node_of'][b][0]}.{cg['node_of'][b][1]}"
                for p in pts for b in (st[p]["blocked_by"] if st else [])
                if cg["node_of"][b] != (lv_id, slug)
            })
            blockers = blocker_ids
            blocker_names = [CONTENT.chapter_of[b.split(".")[1]]["name"] for b in blocker_ids]
            nodes.append({
                "id": f"{lv_id}.{slug}",
                "title": ch_meta["name"],
                "level1": lv_id,
                "level1_name": _level_names()[lv_id],
                "depth": cg["chapter_depth"][(lv_id, slug)],
                "count": len(pts),
                "learned": learned,
                "mastered": mastered,
                "ready": ready,
                "locked": locked,
                "mastery": round(mastery, 1),
                "state": state,
                "blocked_by": blockers,
                "blocked_names": blocker_names,
                "unlocks": len({e["to"] for e in cg["edges"] if e["from"] == f"{lv_id}.{slug}"}),
                "scc": cg["scc_size"][(lv_id, slug)],
                "points": [
                    {
                        "id": p,
                        "title": CONTENT.kps[p]["title"],
                        "state": (st.get(p) or {}).get("state", "ready"),
                        "mastery": (st.get(p) or {}).get("mastery", 0),
                        "blocked_by": [
                            CONTENT.kps[b]["title"] for b in (st.get(p) or {}).get("blocked_by", [])
                        ],
                    }
                    for p in pts
                ],
            })
        edges = cg["edges"]
        stages = _stage_meta([n["depth"] for n in nodes])
        return {
            "granularity": "chapter",
            "nodes": nodes,
            "edges": edges,
            "stages": stages,
            "max_depth": max((n["depth"] for n in nodes), default=0),
            "cycle_groups": [[f"{a[0]}.{a[1]}" for a in s] for s in cg["cycles"]],
        }

    # 点级
    g = _point_graph()
    nodes = []
    for k in g["ids"]:
        b = CONTENT.brief(k)
        node = {
            **b,
            "depth": g["depth"][k],
            "parents": g["parents"][k],
            "children": g["children"][k],
            **(st[k] if st else {"state": "unknown", "mastery": 0, "blocked_by": [],
                                  "unlocks": len(g["desc"][k])}),
        }
        if st:
            node["blocked_id"] = node["blocked_by"]
            node["blocked_by"] = [CONTENT.kps[x]["title"] for x in node["blocked_by"]]
        nodes.append(node)
    edges = []
    for u in g["ids"]:
        for v in g["children"][u]:
            edges.append({"from": u, "to": v, "weight": 1, "back": g["depth"][u] >= g["depth"][v]})
    return {
        "granularity": "point",
        "nodes": nodes,
        "edges": edges,
        "stages": _stage_meta([n["depth"] for n in nodes]),
        "max_depth": g["max_depth"],
    }


def _stage_meta(depths: list[int]) -> list[dict]:
    from collections import Counter
    cnt = Counter(depths)
    out = []
    for d in sorted(cnt):
        out.append({"depth": d, "count": cnt[d]})
    return out


# ---------------------------------------------------------------- 对外：下一站

def frontier(limit: int = 8, include_learning: bool = False) -> list[dict]:
    """现在就能学、且最值得先学的点。

    排序：解锁价值优先（学它能开出多少后续），其次层级浅的优先，最后按内容顺序。
    """
    g = _point_graph()
    states = node_states()
    prog = _progress()
    pool = []
    for k in g["ids"]:
        s = states[k]
        if s["state"] != "ready":
            continue
        if s["status"] != "new" and not include_learning:
            continue
        pool.append(k)
    pool.sort(key=lambda k: (-states[k]["unlocks"], states[k]["depth"], CONTENT.kps[k]["ord"]))
    out = []
    for k in pool[:limit]:
        b = CONTENT.brief(k)
        out.append({
            **b,
            "depth": g["depth"][k],
            "state": "ready",
            "mastery": states[k]["mastery"],
            "blocked_by": [],
            "unlocks": states[k]["unlocks"],
            "ready_after": _ready_after(prog, k),
            "why": _why(k, states[k], prog),
        })
    return out


def _ready_after(prog: dict, kp_id: str) -> int:
    """学完这一个，能立刻多出几个可学点。"""
    g = _point_graph()
    return sum(
        1 for v in g["children"][kp_id]
        if (prog.get(v) or {}).get("status", "new") == "new"
        and all((prog.get(b) or {}).get("status", "new") != "new" for b in g["parents"][v])
    )


def _why(kp_id: str, s: dict, prog: dict) -> str:
    n = s["unlocks"]
    if n >= 8:
        return f"枢纽点：掌握后解锁 {n} 个后续知识点"
    ready = _ready_after(prog, kp_id)
    if ready >= 3:
        return f"学完立刻多出 {ready} 个可学点"
    if n:
        return f"解锁 {n} 个后续知识点"
    return "链条末端：不再阻塞别的知识点"


# ---------------------------------------------------------------- 对外：路径

def path_to(kp_id: str) -> dict:
    """去某个知识点需要先过哪些点，按可执行顺序排好。"""
    g = _point_graph()
    if kp_id not in CONTENT.kps:
        raise KeyError(kp_id)
    prog = _progress()
    need = set(g["anc"][kp_id])
    seq = [k for k in g["ids"] if k in need]
    # 按拓扑深度排序，同层保持内容顺序，天然可执行
    seq.sort(key=lambda k: (g["depth"][k], CONTENT.kps[k]["ord"]))
    steps = []
    done = 0
    for k in seq:
        st = (prog.get(k) or {}).get("status", "new")
        if st != "new":
            done += 1
        steps.append({**CONTENT.brief(k), "depth": g["depth"][k], "status": st,
                      "state": "done" if st != "new" else "todo"})
    return {
        "target": CONTENT.brief(kp_id),
        "total": len(seq),
        "done": done,
        "steps": steps,
        "minutes": int(len(seq) * 6 + 6),
    }


# ---------------------------------------------------------------- 对外：概览

def summary() -> dict:
    g = _point_graph()
    states = node_states()
    cg = chapter_graph()
    cnt = {"locked": 0, "ready": 0, "learning": 0, "mastered": 0}
    for s in states.values():
        cnt[s["state"]] += 1
    learned = cnt["learning"] + cnt["mastered"]
    return {
        "points": len(g["ids"]),
        "edges": sum(len(v) for v in g["children"].values()),
        "chapters": len(cg["nodes"]),
        "chapter_edges": len([e for e in cg["edges"] if not e["back"]]),
        "max_depth": g["max_depth"],
        "unlocked": cnt["ready"] + learned,
        "learned": learned,
        "counts": cnt,
        "progress": round(learned / max(1, len(g["ids"])), 3),
        "roots": len([k for k in g["ids"] if not g["parents"][k]]),
    }
