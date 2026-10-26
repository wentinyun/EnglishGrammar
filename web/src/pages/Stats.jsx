import { api } from "../api.js";
import { useAsync, pct } from "../hooks.js";
import { Radar, Heatmap, Forecast, BarRow } from "../components/Charts.jsx";

export default function Stats() {
  const ov = useAsync(() => api.overview(), []);
  const heat = useAsync(() => api.heatmap(154), []);
  const fc = useAsync(() => api.forecast(14), []);
  const ret = useAsync(() => api.retention(), []);
  const weak = useAsync(() => api.weak(10), []);

  const o = ov.data;

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>学习报告</h2>
          <p>掌握度由记忆稳定度、近期正确率、题目覆盖与当前可回忆概率四项合成</p>
        </div>
        <span className="chip blue">FSRS-4.5</span>
      </div>

      <div className="grid g4">
        <div className="stat">
          <div className="k">已学 / 总数</div>
          <div className="v">
            {o ? o.learned : "—"}
            <small>/ {o ? o.total_kp : "—"}</small>
          </div>
          <div className="sub">{o ? `覆盖率 ${pct(o.learned / o.total_kp)}` : ""}</div>
        </div>
        <div className="stat">
          <div className="k">平均掌握度</div>
          <div className="v">{o ? o.avg_mastery : "—"}</div>
          <div className="sub">{o ? `已掌握 ${o.mastered} 个` : ""}</div>
        </div>
        <div className="stat">
          <div className="k">累计正确率</div>
          <div className="v">{o ? pct(o.accuracy) : "—"}</div>
          <div className="sub">{o ? `${o.answers_total} 题 · ${o.minutes_total} 分钟` : ""}</div>
        </div>
        <div className="stat">
          <div className="k">学习节奏</div>
          <div className="v">
            {o ? o.streak : "—"}
            <small>天连续</small>
          </div>
          <div className="sub">{o ? `共活跃 ${o.active_days} 天` : ""}</div>
        </div>
      </div>

      {o && (
        <div className="tiny muted" style={{ marginTop: 10 }}>
          讲解回看 {o.concept_reads || 0} 次 · 覆盖 {o.concept_kps || 0} 个知识点
          （只读，不计入复习次数与正确率）
        </div>
      )}

      <div className="grid g2" style={{ marginTop: 14 }}>
        <div className="card">
          <b>七维掌握度</b>
          <div className="tiny muted" style={{ marginBottom: 4 }}>
            取已学知识点的平均值
          </div>
          {o ? <Radar items={o.levels} size={320} /> : <div className="skeleton" style={{ height: 320 }} />}
        </div>

        <div className="card">
          <b>分类明细</b>
          <table className="plain" style={{ marginTop: 8 }}>
            <thead>
              <tr>
                <th>分类</th>
                <th>已学</th>
                <th>掌握度</th>
                <th>到期</th>
              </tr>
            </thead>
            <tbody>
              {(o?.levels || []).map((l) => (
                <tr key={l.id}>
                  <td>{l.name}</td>
                  <td className="muted">
                    {l.learned}/{l.total}
                  </td>
                  <td style={{ fontVariantNumeric: "tabular-nums" }}>
                    <div className="row" style={{ gap: 8 }}>
                      <div className="mini-bar" style={{ width: 46 }}>
                        <i style={{ width: `${l.mastery}%`, background: l.mastery >= 80 ? "var(--ok)" : "var(--accent)" }} />
                      </div>
                      {l.mastery}
                    </div>
                  </td>
                  <td className="muted">{l.due || 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card" style={{ marginTop: 14 }}>
        <div className="row between" style={{ marginBottom: 12 }}>
          <b>未来 14 天复习量预测</b>
          <span className="tiny muted">首列为今天（含逾期）</span>
        </div>
        {fc.data ? <Forecast items={fc.data} /> : <div className="skeleton" style={{ height: 108 }} />}
      </div>

      <div className="grid g2" style={{ marginTop: 14 }}>
        <div className="card">
          <b>可回忆概率分布</b>
          <div className="tiny muted" style={{ marginBottom: 12 }}>
            低于 70% 说明该复习了
          </div>
          {ret.data &&
            Object.entries(ret.data.buckets).map(([k, v]) => (
              <BarRow
                key={k}
                label={`${k}%`}
                value={v}
                max={Math.max(1, ...Object.values(ret.data.buckets))}
                color={k === "0-50" ? "#ef6b6b" : k === "50-70" ? "#e8b256" : k === "70-85" ? "#7c93ff" : "#3ecf8e"}
                right={`${v} 个`}
              />
            ))}
        </div>

        <div className="card">
          <b>学习热力图</b>
          <div className="tiny muted" style={{ marginBottom: 12 }}>
            近 22 周每日作答量
          </div>
          {heat.data ? <Heatmap days={heat.data} /> : <div className="skeleton" style={{ height: 120 }} />}
        </div>
      </div>

      <div className="card" style={{ marginTop: 14 }}>
        <b>需要补强的知识点</b>
        <table className="plain" style={{ marginTop: 8 }}>
          <thead>
            <tr>
              <th>知识点</th>
              <th>分类</th>
              <th>正确率</th>
              <th>掌握度</th>
              <th>遗忘次数</th>
            </tr>
          </thead>
          <tbody>
            {(weak.data || []).map((k) => (
              <tr key={k.id}>
                <td>{k.title}</td>
                <td className="muted">
                  {k.level1_name} · {k.chapter_name}
                </td>
                <td style={{ color: k.accuracy < 0.7 ? "var(--bad)" : "var(--text)" }}>{pct(k.accuracy)}</td>
                <td>{k.mastery}</td>
                <td className="muted">{k.lapses}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {weak.data && weak.data.length === 0 && <div className="tiny muted">暂无数据</div>}
      </div>
    </div>
  );
}
