import { api } from "../api.js";
import { useAsync, pct } from "../hooks.js";
import { Heatmap, Radar, Ring, BarRow } from "../components/Charts.jsx";

function greeting() {
  const h = new Date().getHours();
  if (h < 6) return "夜深了，少量复习就好";
  if (h < 11) return "早上好，先做一组到期复习";
  if (h < 14) return "中午好，来一组短练习";
  if (h < 18) return "下午好，适合推进新知识点";
  if (h < 23) return "晚上好，把今天的复习清完";
  return "快休息了，做几道题收尾";
}

export default function Today({ nav, start, plan }) {
  const ov = useAsync(() => api.overview(), []);
  const heat = useAsync(() => api.heatmap(154), []);
  const weak = useAsync(() => api.weak(5), []);
  const ret = useAsync(() => api.retention(), []);

  const o = ov.data;
  const p = plan;

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>{greeting()}</h2>
          <p>
            {p
              ? `${p.due_today} 个知识点到期 · ${p.new_left} 个新知识点可学 · 预计 ${p.est_minutes} 分钟`
              : "正在读取今日计划"}
          </p>
        </div>
        <div className="row">
          <span className="chip blue">记忆曲线调度中</span>
          {o && <span className="chip">{o.total_kp} 个知识点</span>}
        </div>
      </div>

      <div className="hero">
        <div className="row between wrap" style={{ alignItems: "flex-start", gap: 24 }}>
          <div style={{ flex: 1, minWidth: 260 }}>
            <h3>今天的闭环：复习 → 训练 → 新学</h3>
            <div className="meta">
              每个知识点都走「讲解 → 训练 → 复习卡 → 复习训练」，答错会自动重排到记忆曲线的更早位置。
            </div>
            <div className="plan-grid">
              <div className="plan-item">
                <div className="n">{p ? p.due_today : "—"}</div>
                <div className="l">到期复习</div>
              </div>
              <div className="plan-item">
                <div className="n">{p ? p.new_left : "—"}</div>
                <div className="l">可学新知识点</div>
              </div>
              <div className="plan-item">
                <div className="n">{p ? p.est_minutes : "—"}</div>
                <div className="l">预计分钟</div>
              </div>
            </div>
            <div className="hero-actions">
              <button
                className="btn primary"
                disabled={!p || p.due_today === 0}
                onClick={() => start({ mode: "review" })}
              >
                开始复习
              </button>
              <button
                className="btn"
                disabled={!p || p.new_left === 0}
                onClick={() => start({ mode: "learn" })}
              >
                学习新知识点
              </button>
              <button className="btn ghost" onClick={() => nav("curriculum")}>
                自选知识点
              </button>
              <button
                className="btn ghost"
                disabled={!p || !p.learned_total}
                title="只读讲解，不打分、不改复习排期"
                onClick={() => start({ mode: "concept" })}
              >
                只看讲解
              </button>
              <button className="btn ghost" onClick={() => nav("errors")}>
                错题本
              </button>
              <button className="btn ghost" onClick={() => nav("exam")}>
                考试模式
              </button>
            </div>
            {p && p.concept_views_today > 0 && (
              <div className="tiny muted" style={{ marginTop: 10 }}>
                今天已回看 {p.concept_views_today} 个知识点 · 不计入复习次数
              </div>
            )}
            {p && p.due_today === 0 && p.new_left > 0 && (
              <div className="tiny muted" style={{ marginTop: 12 }}>
                目前没有到期复习。按记忆曲线，强行重复不如推进新内容 + 明天按时复习。
              </div>
            )}
          </div>
          <div style={{ flex: "none" }}>
            <Ring value={(p?.goal_progress || 0) * 100} color="#3fc8c0" size={120} stroke={8} />
            <div className="tiny muted center" style={{ marginTop: 6 }}>
              今日目标 {p ? `${p.reviews_done}/${p.goal}` : "—"} 题
            </div>
          </div>
        </div>
      </div>

      <div className="grid g4" style={{ marginTop: 14 }}>
        <div className="stat">
          <div className="k">已学知识点</div>
          <div className="v">
            {o ? o.learned : "—"}
            <small>/ {o ? o.total_kp : "—"}</small>
          </div>
          <div className="sub">{o ? `未学 ${o.unlearned} 个` : ""}</div>
        </div>
        <div className="stat">
          <div className="k">已掌握</div>
          <div className="v">{o ? o.mastered : "—"}</div>
          <div className="sub">{o ? `平均掌握度 ${o.avg_mastery}` : ""}</div>
        </div>
        <div className="stat">
          <div className="k">24 小时内到期</div>
          <div className="v">{o ? o.due_24h : "—"}</div>
          <div className="sub">{o ? `当前已到期 ${o.due_now}` : ""}</div>
        </div>
        <div className="stat">
          <div className="k">总正确率</div>
          <div className="v">{o ? pct(o.accuracy) : "—"}</div>
          <div className="sub">{o ? `累计 ${o.answers_total} 题 · ${o.minutes_total} 分钟` : ""}</div>
        </div>
      </div>

      <div className="grid g2" style={{ marginTop: 14 }}>
        <div className="card">
          <div className="row between" style={{ marginBottom: 8 }}>
            <b>分类掌握度</b>
            <button className="btn sm ghost" onClick={() => nav("stats")}>
              学习报告
            </button>
          </div>
          {o ? <Radar items={o.levels} size={300} /> : <div style={{ height: 300 }} />}
        </div>

        <div className="card">
          <div className="row between" style={{ marginBottom: 12 }}>
            <b>遗忘预警</b>
            <span className="tiny muted">可回忆概率低于 80%</span>
          </div>
          {ret.data && ret.data.at_risk.length ? (
            ret.data.at_risk.slice(0, 6).map((k) => (
              <div
                key={k.kp_id}
                style={{ padding: "7px 0", borderBottom: "1px solid var(--line-soft)", cursor: "pointer" }}
                onClick={() => start({ mode: "review", kp_ids: [k.kp_id] })}
              >
                <div className="row between" style={{ fontSize: 13 }}>
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {k.title}
                  </span>
                  <span style={{ color: k.r < 0.6 ? "var(--bad)" : "var(--warn)", fontVariantNumeric: "tabular-nums" }}>
                    {Math.round(k.r * 100)}%
                  </span>
                </div>
                <div className="tiny muted">
                  {k.level1_name} · {k.chapter_name}
                </div>
              </div>
            ))
          ) : (
            <div className="empty" style={{ padding: "24px 0" }}>
              <div className="em">◌</div>
              <div className="tiny">暂无即将遗忘的知识点</div>
            </div>
          )}
          {ret.data && (
            <div style={{ marginTop: 12 }}>
              <BarRow
                label="平均可回忆概率"
                value={ret.data.avg * 100}
                color="#3fc8c0"
                right={`${Math.round(ret.data.avg * 100)}%`}
              />
            </div>
          )}
        </div>
      </div>

      <div className="card" style={{ marginTop: 14 }}>
        <div className="row between" style={{ marginBottom: 14 }}>
          <b>学习热力图</b>
          <div className="legend">
            <span>
              <i style={{ background: "#1a212d" }} />
              无
            </span>
            <span>
              <i style={{ background: "rgba(124,147,255,.35)" }} />
              少
            </span>
            <span>
              <i style={{ background: "rgba(124,147,255,.6)" }} />
              中
            </span>
            <span>
              <i style={{ background: "#7c93ff" }} />
              多
            </span>
          </div>
        </div>
        {heat.data ? <Heatmap days={heat.data} /> : <div className="skeleton" style={{ height: 120 }} />}
        <div className="row between" style={{ marginTop: 12 }}>
          <span className="tiny muted">
            {o ? `累计活跃 ${o.active_days} 天 · 连续 ${o.streak} 天` : ""}
          </span>
          <span className="tiny muted">{heat.data ? `${heat.data.length} 天` : ""}</span>
        </div>
      </div>

      <div className="card" style={{ marginTop: 14 }}>
        <div className="row between" style={{ marginBottom: 12 }}>
          <b>优先补强</b>
          <span className="tiny muted">按错误率、遗忘程度与顽固标记排序</span>
        </div>
        {weak.data && weak.data.length ? (
          weak.data.map((k) => (
            <div
              key={k.id}
              className="row between"
              style={{ padding: "9px 0", borderBottom: "1px solid var(--line-soft)" }}
            >
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 13.5, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {k.title}
                </div>
                <div className="tiny muted">
                  {k.level1_name} · {k.chapter_name} · 正确率 {pct(k.accuracy)} · 掌握 {k.mastery}
                </div>
              </div>
              <button className="btn sm" onClick={() => start({ mode: "train", kp_ids: [k.id] })}>
                专项练
              </button>
            </div>
          ))
        ) : (
          <div className="empty" style={{ padding: "24px 0" }}>
            <div className="em">◇</div>
            <div className="tiny">还没有练习数据，先学一个知识点</div>
          </div>
        )}
      </div>
    </div>
  );
}
