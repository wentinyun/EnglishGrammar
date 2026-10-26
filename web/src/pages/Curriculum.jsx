import { useMemo, useState } from "react";
import { api } from "../api.js";
import { useAsync, pct } from "../hooks.js";
import Portal from "../portal.jsx";

const STATUS = {
  new: { label: "未学", cls: "" },
  review: { label: "复习中", cls: "blue" },
  mastered: { label: "已掌握", cls: "green" },
  relearning: { label: "重学中", cls: "gold" },
  leech: { label: "顽固", cls: "red" },
};

const FILTERS = [
  { id: "all", label: "全部" },
  { id: "new", label: "未学" },
  { id: "due", label: "待复习" },
  { id: "weak", label: "偏弱" },
  { id: "mastered", label: "已掌握" },
  { id: "leech", label: "顽固" },
];

export default function Curriculum({ start, toast }) {
  const { loading, data, error } = useAsync(() => api.curriculum(), []);
  const [lv, setLv] = useState(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [open, setOpen] = useState({});
  const [sel, setSel] = useState([]);
  const [preview, setPreview] = useState(null);

  const levels = data?.levels || [];
  const cur = levels.find((l) => l.id === lv) || levels[0];

  const levelStats = (l) => {
    const pts = l.chapters.flatMap((c) => c.points);
    const learned = pts.filter((p) => p.status !== "new").length;
    const mastery = learned
      ? Math.round(pts.filter((p) => p.status !== "new").reduce((s, p) => s + p.mastery, 0) / learned)
      : 0;
    return { total: pts.length, learned, mastery };
  };

  const match = (p, chapName) => {
    if (query && !(p.title + p.brief + chapName).toLowerCase().includes(query.toLowerCase())) return false;
    const due = p.due_at && new Date(p.due_at) <= new Date();
    if (filter === "new") return p.status === "new";
    if (filter === "due") return due;
    if (filter === "mastered") return p.status === "mastered";
    if (filter === "leech") return p.status === "leech";
    if (filter === "weak") return p.status !== "new" && p.mastery < 60;
    return true;
  };

  const visible = useMemo(() => {
    if (!cur) return [];
    return cur.chapters
      .map((c) => ({ ...c, points: c.points.filter((p) => match(p, c.name)) }))
      .filter((c) => c.points.length);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cur, query, filter]);

  const toggle = (id) =>
    setSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  const toggleChapter = (slug) => setOpen((o) => ({ ...o, [slug]: !o[slug] }));

  const visibleIds = visible.flatMap((c) => c.points.map((p) => p.id));

  const run = (mode) => {
    if (!sel.length) return;
    start({ mode, kp_ids: sel });
  };

  if (loading) return <div className="loading">正在装载课程体系…</div>;
  if (error)
    return (
      <div className="empty">
        <div className="em">!</div>
        <div>加载失败：{error.message}</div>
      </div>
    );

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>课程体系</h2>
          <p>
            {data.counts.total} 个知识点 · {data.counts.chapters} 个章节 · {data.counts.drills} 道训练题，任选一个区间开始
          </p>
        </div>
        <span className="chip blue">三级分类</span>
      </div>

      <div className="curriculum">
        <div className="lv-list">
          {levels.map((l) => {
            const st = levelStats(l);
            return (
              <button
                key={l.id}
                className={`lv-item ${cur && cur.id === l.id ? "active" : ""}`}
                onClick={() => {
                  setLv(l.id);
                  setQuery("");
                  setFilter("all");
                }}
              >
                <span>{l.name}</span>
                <span className="cnt">
                  {st.learned}/{st.total}
                </span>
              </button>
            );
          })}
          <div className="tiny muted" style={{ padding: "8px 12px" }}>
            学完即进入记忆曲线，到期自动出现在「今日」。
          </div>
        </div>

        <div>
          <div className="toolbar">
            <input
              className="input search"
              placeholder="搜索知识点…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            {FILTERS.map((f) => (
              <button
                key={f.id}
                className={`chip-filter ${filter === f.id ? "on" : ""}`}
                onClick={() => setFilter(f.id)}
              >
                {f.label}
              </button>
            ))}
            <button
              className="btn sm ghost right"
              onClick={() => setSel(sel.length === visibleIds.length ? [] : visibleIds)}
            >
              {sel.length === visibleIds.length && visibleIds.length ? "取消全选" : "全选可见"}
            </button>
          </div>

          {visible.length === 0 && (
            <div className="empty">
              <div className="em">◌</div>
              <div>这个筛选条件下没有知识点</div>
            </div>
          )}

          {visible.map((c) => {
            const isOpen = open[c.slug] ?? true;
            const learned = c.points.filter((p) => p.status !== "new").length;
            return (
              <div key={c.slug} className={`chapter ${isOpen ? "open" : ""}`}>
                <header onClick={() => toggleChapter(c.slug)}>
                  <span className="caret">▶</span>
                  <h4>{c.name}</h4>
                  <span className="chip">{c.points.length} 点</span>
                  <span className="tiny muted right">
                    已学 {learned}/{c.points.length}
                  </span>
                </header>
                {isOpen && (
                  <div className="kp-list">
                    {c.points.map((p) => {
                      const st = STATUS[p.status] || STATUS.new;
                      const due = p.due_at && new Date(p.due_at) <= new Date();
                      return (
                        <div
                          key={p.id}
                          className={`kp-row ${sel.includes(p.id) ? "sel" : ""}`}
                          onClick={() => toggle(p.id)}
                        >
                          <span className={`kp-dot ${p.status}`} />
                          <div style={{ minWidth: 0, flex: 1 }}>
                            <div className="t">{p.title}</div>
                            <div className="b">{p.brief}</div>
                          </div>
                          {due && <span className="chip gold">到期</span>}
                          {p.tags?.slice(0, 1).map((t) => (
                            <span key={t} className="chip">
                              {t}
                            </span>
                          ))}
                          <div className="row" style={{ width: 78, justifyContent: "flex-end", gap: 6 }}>
                            <div className="mini-bar">
                              <i style={{ width: `${p.mastery}%`, background: p.mastery >= 80 ? "var(--ok)" : "var(--accent)" }} />
                            </div>
                            <span className="tiny muted" style={{ width: 26, textAlign: "right" }}>
                              {Math.round(p.mastery)}
                            </span>
                          </div>
                          <span className={`chip ${st.cls}`}>{st.label}</span>
                          <button
                            className="btn sm ghost"
                            onClick={(e) => {
                              e.stopPropagation();
                              setPreview(p);
                            }}
                          >
                            讲解
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {sel.length > 0 && (
        <div className="selbar">
          <span style={{ fontWeight: 600 }}>已选 {sel.length} 个知识点</span>
          <span className="tiny muted">按记忆曲线自动安排</span>
          <div className="row right">
            <button className="btn sm ghost" onClick={() => setSel([])}>
              清空
            </button>
            <button className="btn sm" onClick={() => run("train")}>
              只做训练
            </button>
            <button className="btn sm" onClick={() => run("review")}>
              复习
            </button>
            <button className="btn sm primary" onClick={() => run("learn")}>
              学习
            </button>
          </div>
        </div>
      )}

      {preview && (
        <PreviewModal
          kp={preview}
          onClose={() => setPreview(null)}
          onStart={(mode) => {
            setPreview(null);
            start({ mode, kp_ids: [preview.id] });
          }}
        />
      )}
    </div>
  );
}

function PreviewModal({ kp, onClose, onStart }) {
  const { loading, data } = useAsync(() => api.kp(kp.id), [kp.id]);
  return (
    <Portal>
        <div className="modal-mask" onClick={onClose}>
        <div className="modal" onClick={(e) => e.stopPropagation()}>
          <div className="modal-head">
            <div style={{ minWidth: 0 }}>
              <div className="tiny muted">
                {kp.level1_name} · {kp.chapter_name}
              </div>
              <h3 style={{ margin: "2px 0 0", fontSize: 17 }}>{kp.title}</h3>
            </div>
            <button className="btn sm ghost" onClick={onClose}>
              关闭
            </button>
          </div>
          <div className="modal-body">
            {loading && <div className="skeleton" style={{ height: 160 }} />}
            {data && (
              <>
                <div className="concept-summary" style={{ marginTop: 0 }}>{data.concept.summary}</div>
                {data.concept.sections.map((s, i) => (
                  <div className="sec" key={i}>
                    <h4>{s.h}</h4>
                    {s.p && <p>{s.p}</p>}
                    {s.bullets && (
                      <ul>
                        {s.bullets.map((b, j) => (
                          <li key={j}>{b}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
                <div className="sec">
                  <h4>复习卡</h4>
                  <ul className="core-list">
                    {data.review.core.map((c, i) => (
                      <li key={i}>{c}</li>
                    ))}
                  </ul>
                </div>
              </>
            )}
          </div>
          <div className="modal-foot">
            <span className="tiny muted">{data ? `${data.drills.length} 道训练题` : ""}</span>
            <div className="row right">
              <button className="btn sm" onClick={() => onStart("train")}>
                做训练
              </button>
              <button className="btn sm" onClick={() => onStart("review")}>
                复习
              </button>
              <button className="btn sm primary" onClick={() => onStart("learn")}>
                从头学
              </button>
            </div>
          </div>
        </div>
      </div>
    </Portal>
  );
}
