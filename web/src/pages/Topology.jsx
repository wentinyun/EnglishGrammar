import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api.js";
import { useAsync } from "../hooks.js";
import Portal from "../portal.jsx";

const L1 = {
  morph: { name: "词法", color: "#7c93ff" },
  tense_voice: { name: "时态语态", color: "#3fc8c0" },
  syntax: { name: "句法", color: "#b48ef0" },
  nonfinite: { name: "非谓语", color: "#e8b256" },
  clause: { name: "从句", color: "#4fa8f0" },
  special: { name: "特殊句式", color: "#ef6b6b" },
  collocation: { name: "搭配", color: "#3ecf8e" },
};
const L1_ORDER = Object.keys(L1);
const colorOf = (id) => (L1[id.split(".")[0]] || {}).color || "#7c93ff";

const STATE_LABEL = {
  ready: "可学",
  locked: "未解锁",
  learning: "学习中",
  mastered: "已掌握",
};

const FILTERS = [
  { id: "all", label: "全部" },
  { id: "ready", label: "现在能学" },
  { id: "locked", label: "未解锁" },
  { id: "learning", label: "学习中" },
  { id: "mastered", label: "已掌握" },
];

const METRIC = {
  chapter: { W: 148, H: 60, VG: 9, HG: 14, COLG: 42, ROWS: 999 },
  point: { W: 170, H: 52, VG: 7, HG: 10, COLG: 40, ROWS: 24 },
};
const PAD_L = 24;
const PAD_T = 58;
const PAD_R = 24;
const PAD_B = 24;

/* ------------------------------------------------------------------ 布局 */

function buildLayout(nodes, edges, gran) {
  const m = METRIC[gran];
  const idx = new Map(nodes.map((n, i) => [n.id, i]));
  const l1i = (id) => L1_ORDER.indexOf(id.split(".")[0]);

  const parentsOf = new Map();
  for (const e of edges) {
    if (!parentsOf.has(e.to)) parentsOf.set(e.to, []);
    parentsOf.get(e.to).push(e.from);
  }

  const byDepth = new Map();
  for (const n of nodes) {
    if (!byDepth.has(n.depth)) byDepth.set(n.depth, []);
    byDepth.get(n.depth).push(n);
  }
  const plan = [...byDepth.keys()]
    .sort((a, b) => a - b)
    .map((d) => {
      const items = byDepth
        .get(d)
        .slice()
        .sort((a, b) => l1i(a.id) - l1i(b.id) || idx.get(a.id) - idx.get(b.id));
      const sub = Math.max(1, Math.ceil(items.length / m.ROWS));
      const rows = Math.ceil(items.length / sub);
      return { d, items, sub, rows, h: rows * (m.H + m.VG) - m.VG };
    });

  const maxH = Math.max(...plan.map((p) => p.h));
  const pos = new Map();
  const cols = [];
  let x = PAD_L;

  for (const p of plan) {
    const w = p.sub * (m.W + m.HG) - m.HG;
    // 重心对齐：把这一列的中心对到父节点中心的平均值上，避免顶部大块空白、
    // 同时让连线尽量水平（交叉最少）
    let sum = 0;
    let k = 0;
    for (const n of p.items) {
      for (const pid of parentsOf.get(n.id) || []) {
        const pp = pos.get(pid);
        if (pp) {
          sum += pp.y + pp.h / 2;
          k += 1;
        }
      }
    }
    const target = k ? sum / k : PAD_T + p.h / 2;
    const lo = PAD_T;
    const hi = PAD_T + maxH - p.h;
    const y0 = Math.round(Math.min(Math.max(target - p.h / 2, lo), Math.max(lo, hi)));

    p.items.forEach((n, i) => {
      const c = i % p.sub;
      const r = Math.floor(i / p.sub);
      pos.set(n.id, { x: x + c * (m.W + m.HG), y: y0 + r * (m.H + m.VG), w: m.W, h: m.H });
    });
    cols.push({ d: p.d, x, w, count: p.items.length });
    x += w + m.COLG;
  }
  return {
    pos,
    cols,
    width: x - m.COLG + PAD_R,
    height: PAD_T + maxH + PAD_B,
    nodeH: m.H,
    nodeW: m.W,
  };
}

function edgePath(a, b, hNode) {
  const x1 = a.x + a.w;
  const y1 = a.y + hNode / 2;
  const x2 = b.x;
  const y2 = b.y + hNode / 2;
  const dx = Math.max(26, Math.abs(x2 - x1) * 0.42);
  if (x2 <= x1) {
    // 回边：绕过节点右侧再折回，避免与大部队混在一起
    const k = Math.min(70, Math.abs(y2 - y1) * 0.3 + 34);
    return `M${x1},${y1} C${x1 + k},${y1} ${x1 + k},${(y1 + y2) / 2} ${(x1 + x2) / 2},${(y1 + y2) / 2} C${x2 - k},${(y1 + y2) / 2} ${x2 - k},${y2} ${x2},${y2}`;
  }
  return `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`;
}

/* ------------------------------------------------------------------ 页面 */

export default function Topology({ start, param }) {
  // #/topology/point 直接进知识点级；#/l1.chapter 打开章节；#/l1.chapter.kp 打开知识点
  const deepKp = param && param.includes(".") ? param : null;
  const deepIsPoint = deepKp ? deepKp.split(".").length >= 3 : false;
  const [gran, setGran] = useState(deepIsPoint || param === "point" ? "point" : "chapter");
  const [filter, setFilter] = useState("all");
  const [zoom, setZoom] = useState(0.9);
  const [hover, setHover] = useState(null);
  const [sel, setSel] = useState(null);
  const [onlyLinked, setOnlyLinked] = useState(true);
  const scrollRef = useRef(null);


  const { loading, data, error } = useAsync(() => api.topology(gran), [gran]);
  const front = useAsync(() => api.frontier(4), []);
  const cfg = useAsync(() => api.settings(), []);
  // prereq_gate 只影响「学习」模式：关着就是纯提示，开着才会跳过被锁的点
  const gate = String(cfg.data?.prereq_gate ?? "0") === "1" || cfg.data?.prereq_gate === true;

  const nodes = data?.nodes || [];
  const edges = data?.edges || [];
  const lay = useMemo(() => (nodes.length ? buildLayout(nodes, edges, gran) : null), [nodes, edges, gran]);

  useEffect(() => {
    if (!deepKp || !nodes.length) return;
    const n = nodes.find((x) => x.id === deepKp);
    if (n) setSel({ id: n.id, node: n });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deepKp, nodes.length]);

  useEffect(() => {
    if (!lay || !scrollRef.current) return;
    const box = scrollRef.current;
    const fit = Math.min(1, Math.max(0.6, +((box.clientWidth - 14) / lay.width).toFixed(2)));
    setZoom(fit);
    box.scrollLeft = 0;
    box.scrollTop = 0;
  }, [lay]);

  const adjacency = useMemo(() => {
    const map = new Map();
    const add = (a, b) => {
      if (!map.has(a)) map.set(a, new Set());
      map.get(a).add(b);
    };
    for (const e of edges) {
      add(e.from, e.to);
      add(e.to, e.from);
    }
    return map;
  }, [edges]);

  const focus = sel?.id || hover;
  const linked = focus ? adjacency.get(focus) : null;

  const matchFilter = (n) => {
    if (filter === "all") return true;
    if (filter === "locked") return n.state === "locked";
    return n.state === filter;
  };

  const runGrow = () => start({ mode: "grow", limit: 4 });

  if (loading) return <div className="loading">正在计算依赖图…</div>;
  if (error)
    return (
      <div className="empty">
        <div className="em">!</div>
        <div>加载失败：{error.message}</div>
      </div>
    );

  const sm = data.summary;

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>成长拓扑</h2>
          <p>
            {sm.points} 个知识点之间有 {sm.edges} 条依赖边，最深 {sm.max_depth + 1} 层。
            {gate
              ? "已开启严格前置锁定：带锁的点在学习时会被跳过，先打通前置。"
              : "带锁的只表示前置还没学，是地图上的提示、不拦你；课程页想学哪个都能直接选。"}
          </p>
        </div>
        <span className="chip blue">依赖图</span>
      </div>

      <div className="grid g4" style={{ marginBottom: 14 }}>
        <Tile label="已解锁" value={`${sm.unlocked}`} sub={`共 ${sm.points} 点`} tone="blue" />
        <Tile label="现在能学" value={`${sm.counts.ready}`} sub="前置已全部满足" tone="green" />
        <Tile label="已掌握" value={`${sm.counts.mastered}`} sub={`学过 ${sm.learned} 点`} tone="purple" />
        <Tile label="未解锁" value={`${sm.counts.locked}`} sub="前置还没学" tone="gold" />
      </div>

      <section className="card tight" style={{ marginBottom: 14 }}>
        <div className="row between" style={{ marginBottom: 10 }}>
          <div>
            <h3 style={{ margin: 0, fontSize: 15 }}>下一站</h3>
            <div className="tiny muted" style={{ marginTop: 3 }}>
              按「学完能解锁多少后续」排序，不是按章节顺序
            </div>
          </div>
          <button className="btn sm primary" onClick={runGrow} disabled={!sm.counts.ready}>
            按拓扑生长 4 点
          </button>
        </div>

        {front.loading && <div className="skeleton" style={{ height: 92 }} />}
        {front.data && front.data.length === 0 && (
          <div className="tiny muted" style={{ padding: "10px 0" }}>
            所有知识点都已解锁。剩下的就是按记忆曲线复习了。
          </div>
        )}
        <div className="front-row">
          {(front.data || []).map((f, i) => (
            <button key={f.id} className="front-card" onClick={() => setSel({ id: f.id, node: f, fromFront: true })}>
              <div className="row between">
                <span className="tiny" style={{ color: colorOf(f.id) }}>
                  {f.level1_name} · {f.chapter_name}
                </span>
                <span className="tiny muted">#{i + 1}</span>
              </div>
              <div className="fc-title">{f.title}</div>
              <div className="fc-why">{f.why}</div>
              <div className="row between" style={{ marginTop: 8 }}>
                <span className="chip">第 {f.depth + 1} 层</span>
                <span className="tiny muted">{f.drill_count} 题</span>
              </div>
            </button>
          ))}
        </div>
      </section>

      <div className="toolbar topo-toolbar">
        <div className="seg">
          <button className={gran === "chapter" ? "on" : ""} onClick={() => { setGran("chapter"); setSel(null); }}>
            章节 · {sm.chapters}
          </button>
          <button className={gran === "point" ? "on" : ""} onClick={() => { setGran("point"); setSel(null); }}>
            知识点 · {sm.points}
          </button>
        </div>
        {FILTERS.map((f) => (
          <button
            key={f.id}
            className={`chip-filter ${filter === f.id ? "on" : ""}`}
            onClick={() => setFilter(f.id)}
          >
            {f.label}
          </button>
        ))}
        <label className="tiny muted row" style={{ gap: 6, cursor: "pointer" }}>
          <input type="checkbox" checked={onlyLinked} onChange={(e) => setOnlyLinked(e.target.checked)} />
          高亮依赖
        </label>
        <div className="row right" style={{ gap: 4 }}>
          <button className="btn sm ghost" onClick={() => setZoom((z) => Math.max(0.5, +(z - 0.1).toFixed(2)))}>
            −
          </button>
          <span className="tiny muted" style={{ width: 38, textAlign: "center" }}>
            {Math.round(zoom * 100)}%
          </span>
          <button className="btn sm ghost" onClick={() => setZoom((z) => Math.min(1.5, +(z + 0.1).toFixed(2)))}>
            +
          </button>
          <button
            className="btn sm ghost"
            onClick={() => {
              const box = scrollRef.current;
              if (!box || !lay) return;
              setZoom(Math.min(1, Math.max(0.5, +((box.clientWidth - 18) / lay.width).toFixed(2))));
            }}
          >
            适应宽度
          </button>
        </div>
      </div>

      <div className="legend">
        {L1_ORDER.map((k) => (
          <span key={k} className="lg">
            <i style={{ background: L1[k].color }} />
            {L1[k].name}
          </span>
        ))}
        <span className="lg split">状态</span>
        <span className="lg">
          <i className="dot ready" />可学
        </span>
        <span className="lg">
          <i className="dot locked" />未解锁
        </span>
        <span className="lg">
          <i className="dot learning" />学习中
        </span>
        <span className="lg">
          <i className="dot mastered" />已掌握
        </span>
      </div>

      <div className="topo-scroll" ref={scrollRef}>
        <div
          className="topo-canvas"
          style={{ width: lay.width * zoom, height: lay.height * zoom }}
        >
          <div
            className="topo-inner"
            style={{ width: lay.width, height: lay.height, transform: `scale(${zoom})` }}
          >
            <svg className="topo-edges" width={lay.width} height={lay.height}>
              {lay.cols.map((c) => (
                <g key={c.d}>
                  <rect
                    x={c.x - 10}
                    y={PAD_T - 14}
                    width={c.w + 20}
                    height={lay.height - PAD_T - PAD_B + 20}
                    rx="12"
                    fill="rgba(255,255,255,0.016)"
                  />
                  <text x={c.x} y={PAD_T - 24} fill="#6b7688" fontSize="11">
                    第 {c.d + 1} 层 · {c.count} 点
                  </text>
                </g>
              ))}
              {edges.map((e, i) => {
                const a = lay.pos.get(e.from);
                const b = lay.pos.get(e.to);
                if (!a || !b) return null;
                const on = focus && (e.from === focus || e.to === focus);
                const dim = focus && onlyLinked && !on;
                return (
                  <path
                    key={i}
                    d={edgePath(a, b, lay.nodeH)}
                    className={`topo-edge ${on ? "on" : ""} ${dim ? "dim" : ""} ${e.back ? "back" : ""}`}
                  />
                );
              })}
            </svg>

            {nodes.map((n) => {
              const p = lay.pos.get(n.id);
              if (!p) return null;
              const okFilter = matchFilter(n);
              const isFocus = focus === n.id;
              const isLinked = linked && linked.has(n.id);
              const dim = (!okFilter || (focus && onlyLinked && !isFocus && !isLinked));
              return (
                <div
                  key={n.id}
                  className={`topo-node ${n.state} ${isFocus ? "focus" : ""} ${dim ? "dim" : ""}`}
                  style={{
                    left: p.x,
                    top: p.y,
                    width: p.w,
                    height: p.h,
                    borderColor: isFocus ? colorOf(n.id) : undefined,
                  }}
                  onMouseEnter={() => setHover(n.id)}
                  onMouseLeave={() => setHover(null)}
                  onClick={() => setSel({ id: n.id, node: n })}
                  title={n.title}
                >
                  <i className="bar" style={{ background: colorOf(n.id) }} />
                  {gran === "chapter" ? (
                    <>
                      <div className="tn-top">
                        <span className="tn-title">{n.title}</span>
                        {n.state === "locked" && <span className="lock">🔒</span>}
                      </div>
                      <div className="tn-sub">
                        {n.learned}/{n.count} 点 · {STATE_LABEL[n.state] || n.state}
                      </div>
                      <div className="tn-bar">
                        <i style={{ width: `${n.mastery}%` }} />
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="tn-top">
                        <span className="tn-title small">{n.title}</span>
                        {n.state === "locked" && <span className="lock">🔒</span>}
                      </div>
                      <div className="tn-foot">
                        <span>{STATE_LABEL[n.state] || n.state}</span>
                        {n.unlocks > 0 && <span className="unl">↗{n.unlocks}</span>}
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="tiny muted" style={{ marginTop: 10 }}>
        线的方向是「先 → 后」。把鼠标放到节点上会只点亮与它直接相关的依赖；
        点节点看前置、解锁范围和到达路径。↗ 后面是学完它能解锁的后续知识点数。
      </div>

      {sel && (
        <NodeModal
          sel={sel}
          gran={gran}
          start={start}
          onClose={() => setSel(null)}
          onOpenPoint={(id) => {
            setGran("point");
            setSel({ id });
          }}
        />
      )}
    </div>
  );
}

function Tile({ label, value, sub, tone }) {
  return (
    <div className={`card tight tile ${tone}`}>
      <div className="tiny muted">{label}</div>
      <div className="tv">{value}</div>
      <div className="tiny muted">{sub}</div>
    </div>
  );
}

/* ------------------------------------------------------------------ 详情 */

function NodeModal({ sel, gran, start, onClose, onOpenPoint }) {
  const isChapter = gran === "chapter" && sel.node && sel.node.points;
  const node = sel.node || null;
  const pathQ = useAsync(
    () => (isChapter ? Promise.resolve(null) : api.pathTo(sel.id)),
    [sel.id, isChapter]
  );
  const kpQ = useAsync(
    () => (isChapter ? Promise.resolve(null) : api.kp(sel.id)),
    [sel.id, isChapter]
  );

  const todo = (pathQ.data?.steps || []).filter((s) => s.state === "todo");
  const readyPoints = isChapter ? node.points.filter((p) => p.state === "ready") : [];
  const learnedPoints = isChapter
    ? node.points.filter((p) => p.state === "learning" || p.state === "mastered")
    : [];

  return (
    <Portal>
        <div className="modal-mask" onClick={onClose}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <div style={{ minWidth: 0 }}>
                <div className="tiny" style={{ color: colorOf(sel.id) }}>
                  {isChapter ? `${node.level1_name} · 第 ${node.depth + 1} 层` : `${node?.level1_name} · ${node?.chapter_name}`}
                </div>
                <h3 style={{ margin: "3px 0 0", fontSize: 18 }}>
                  {node?.title || kpQ.data?.title || (isChapter ? "" : "载入中…")}
                </h3>
                <div className="tiny muted" style={{ marginTop: 4 }}>
                  {isChapter
                    ? `${node.count} 个知识点 · 已学 ${node.learned} · ${STATE_LABEL[node.state]}`
                    : `第 ${node?.depth + 1} 层 · ${STATE_LABEL[node?.state] || ""} · 掌握度 ${Math.round(node?.mastery || 0)}%`}
                </div>
              </div>
              <button className="btn sm ghost" onClick={onClose}>
                关闭
              </button>
            </div>

            <div className="modal-body">
              {isChapter ? (
                <>
                  {node.blocked_names?.length > 0 && (
                    <div className="warn-box" style={{ marginTop: 0, marginBottom: 12 }}>
                      本章还有知识点被前置锁住，需要先过：{node.blocked_names.join("、")}
                    </div>
                  )}
                  <div className="tiny muted" style={{ marginBottom: 8 }}>
                    本章知识点（点标题可跳到知识点级拓扑）
                  </div>
                  <div className="tp-list">
                    {node.points.map((p) => (
                      <button key={p.id} className="tp-row" onClick={() => onOpenPoint(p.id)}>
                        <span className={`kp-dot ${p.state === "mastered" ? "mastered" : p.state === "learning" ? "review" : "new"}`} />
                        <span className="tp-title">{p.title}</span>
                        {p.blocked_by.length > 0 && (
                          <span className="lock-inline" title={`需先学：${p.blocked_by.join("、")}`}>
                            🔒
                          </span>
                        )}
                        <span className="tiny muted right" style={{ width: 28, textAlign: "right" }}>
                          {Math.round(p.mastery)}
                        </span>
                      </button>
                    ))}
                  </div>

                </>
              ) : (
                <>
                  {!node && <div className="skeleton" style={{ height: 60 }} />}
                  {node && <div className="tp-brief">{node.brief}</div>}

                  {node && node.blocked_by?.length > 0 && (
                    <div className="warn-box">
                      前置未完成：{node.blocked_by.join("、")}
                      <span className="tiny" style={{ display: "block", marginTop: 4, opacity: 0.85 }}>
                        {gate
                          ? "已开启严格前置锁定，学习模式会自动跳过这个点。"
                          : "这只是提示，不拦你——点「学这个」照样能学。"}
                      </span>
                    </div>
                  )}

                  {node && (
                    <div className="tp-meta">
                      <div>
                        <span className="tiny muted">学完解锁</span>
                        <b>{node.unlocks} 点</b>
                      </div>
                      <div>
                        <span className="tiny muted">训练题</span>
                        <b>{node.drill_count} 道</b>
                      </div>
                      <div>
                        <span className="tiny muted">掌握度</span>
                        <b>{Math.round(node.mastery)}%</b>
                      </div>
                    </div>
                  )}

                  {pathQ.loading && <div className="skeleton" style={{ height: 80, marginTop: 12 }} />}
                  {pathQ.data && pathQ.data.total > 0 && (
                    <div style={{ marginTop: 14 }}>
                      <div className="row between">
                        <h4 style={{ margin: 0, fontSize: 13.5 }}>到这里要过的路</h4>
                        <span className="tiny muted">
                          {pathQ.data.done}/{pathQ.data.total} 已过 · 约 {pathQ.data.minutes} 分钟
                        </span>
                      </div>
                      <div className="path-steps">
                        {pathQ.data.steps.map((s, i) => (
                          <div key={s.id} className={`path-step ${s.state}`}>
                            <span className="idx">{i + 1}</span>
                            <span className="pt">{s.title}</span>
                            {s.state === "done" ? (
                              <span className="chip green tiny">已过</span>
                            ) : (
                              <span className="chip tiny">待学</span>
                            )}
                          </div>
                        ))}
                      </div>
                      {todo.length > 0 && (
                        <button
                          className="btn sm"
                          style={{ marginTop: 10 }}
                          onClick={() => {
                            onClose();
                            start({ mode: "learn", kp_ids: todo.slice(0, 4).map((s) => s.id) });
                          }}
                        >
                          按顺序学这 {Math.min(4, todo.length)} 个前置
                        </button>
                      )}
                    </div>
                  )}

                  {kpQ.data && (
                    <div className="sec" style={{ marginTop: 14 }}>
                      <h4>要点速览</h4>
                      <ul className="core-list">
                        {kpQ.data.review.core.slice(0, 4).map((c, i) => (
                          <li key={i}>{c}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              )}
            </div>

            <div className="modal-foot">
              <span className="tiny muted">
                {isChapter ? `${readyPoints.length} 个可学` : node ? `${node.drill_count} 道题` : ""}
              </span>
              <div className="row right">
                {isChapter ? (
                  <>
                    <button
                      className="btn sm"
                      disabled={!learnedPoints.length}
                      onClick={() => { onClose(); start({ mode: "review", kp_ids: learnedPoints.map((p) => p.id) }); }}
                    >
                      复习本章已学 {learnedPoints.length}
                    </button>
                    <button
                      className="btn sm primary"
                      disabled={!readyPoints.length}
                      onClick={() => { onClose(); start({ mode: "learn", kp_ids: readyPoints.map((p) => p.id) }); }}
                    >
                      学这章可学点
                    </button>
                  </>
                ) : (
                  <>
                    <button className="btn sm" onClick={() => { onClose(); start({ mode: "train", kp_ids: [sel.id] }); }}>
                      只做训练
                    </button>
                    <button className="btn sm" onClick={() => { onClose(); start({ mode: "review", kp_ids: [sel.id] }); }}>
                      复习
                    </button>
                    <button className="btn sm primary" onClick={() => { onClose(); start({ mode: "learn", kp_ids: [sel.id] }); }}>
                      学这个
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
    </Portal>
  );
}
