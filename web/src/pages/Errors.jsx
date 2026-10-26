import { useMemo, useState } from "react";
import { api } from "../api.js";
import { useAsync } from "../hooks.js";

export default function Errors({ start, toast }) {
  const { loading, data } = useAsync(() => api.errors(200), []);
  const [onlyOpen, setOnlyOpen] = useState(true);
  const [open, setOpen] = useState({});
  const [filter, setFilter] = useState("");

  const groups = useMemo(() => {
    if (!data) return [];
    const m = new Map();
    data.items
      .filter((e) => (onlyOpen ? !e.resolved : true))
      .filter((e) => !filter || (e.kp_title + e.stem).toLowerCase().includes(filter.toLowerCase()))
      .forEach((e) => {
        const g = m.get(e.kp_id) || {
          kp_id: e.kp_id,
          kp_title: e.kp_title,
          level1_name: e.level1_name,
          chapter_name: e.chapter_name,
          items: [],
        };
        g.items.push(e);
        m.set(e.kp_id, g);
      });
    return [...m.values()].sort((a, b) => b.items.length - a.items.length);
  }, [data, onlyOpen, filter]);

  if (loading) return <div className="loading">读取错题本…</div>;

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>错题本</h2>
          <p>
            {data ? `未解决 ${data.total_unresolved} 条` : ""} · 按知识点聚合，可直接生成专项重练
          </p>
        </div>
        <div className="row">
          <button
            className="btn sm danger"
            onClick={async () => {
              if (!window.confirm("清空全部错题记录？此操作不可撤销。")) return;
              await api.clearErrors();
              toast("已清空");
              window.location.reload();
            }}
          >
            清空
          </button>
        </div>
      </div>

      <div className="toolbar">
        <input
          className="input search"
          placeholder="搜索题目或知识点…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <button className={`chip-filter ${onlyOpen ? "on" : ""}`} onClick={() => setOnlyOpen(true)}>
          未解决
        </button>
        <button className={`chip-filter ${!onlyOpen ? "on" : ""}`} onClick={() => setOnlyOpen(false)}>
          全部
        </button>
        <span className="tiny muted right">{groups.length} 个知识点</span>
      </div>

      {groups.length === 0 && (
        <div className="empty">
          <div className="em">◇</div>
          <div>还没有错题</div>
          <div className="tiny" style={{ marginTop: 6 }}>
            做题时答错会自动收进这里；答对同题会自动标记为已解决
          </div>
        </div>
      )}

      {groups.map((g) => (
        <div className="card" key={g.kp_id} style={{ marginBottom: 10 }}>
          <div className="row between">
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 600 }}>
                {g.kp_title} <span className="chip red">{g.items.length}</span>
              </div>
              <div className="tiny muted">
                {g.level1_name} · {g.chapter_name}
              </div>
            </div>
            <button
              className="btn sm"
              onClick={() => start({ mode: "train", kp_ids: [g.kp_id] })}
            >
              专项重练
            </button>
          </div>

          <div style={{ marginTop: 10 }}>
            {g.items.slice(0, 3).map((e) => {
              const isOpen = open[e.id];
              return (
                <div key={e.id} style={{ borderTop: "1px solid var(--line-soft)", padding: "9px 0" }}>
                  <div
                    className="row between"
                    style={{ cursor: "pointer" }}
                    onClick={() => setOpen({ ...open, [e.id]: !isOpen })}
                  >
                    <span className="tiny" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {e.stem}
                    </span>
                    <span className="tiny muted">{isOpen ? "收起" : "展开"}</span>
                  </div>
                  {isOpen && (
                    <div style={{ marginTop: 6 }}>
                      <div className="ua">你的答案：{e.user_answer || "（空）"}</div>
                      <div className="ca">正确答案：{e.correct_answer}</div>
                      <div className="tiny muted" style={{ marginTop: 5 }}>
                        {e.explain}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
            {g.items.length > 3 && (
              <div className="tiny muted" style={{ paddingTop: 6 }}>
                另有 {g.items.length - 3} 道同类错题
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
