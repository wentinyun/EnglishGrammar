import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { useAsync } from "../hooks.js";

export default function Settings({ toast, refreshPlan, nav, start }) {
  const { data, loading } = useAsync(() => api.settings(), []);
  const [form, setForm] = useState(null);
  const fileRef = useRef(null);

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  const set = (k, v) => setForm({ ...form, [k]: v });

  const save = async () => {
    try {
      await api.saveSettings(form);
      toast("已保存");
      refreshPlan?.();
    } catch (e) {
      toast(e.message);
    }
  };

  const exportData = async () => {
    const d = await api.exportData();
    const blob = new Blob([JSON.stringify(d, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `grammar-backup-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
    toast("已导出备份");
  };

  const importData = async (file) => {
    try {
      const text = await file.text();
      const json = JSON.parse(text);
      if (!window.confirm("导入会覆盖当前全部学习记录，确定继续？")) return;
      await api.importData(json);
      toast("导入完成");
      window.location.reload();
    } catch (e) {
      toast(`导入失败：${e.message}`);
    }
  };

  if (loading || !form) return <div className="loading">读取设置…</div>;

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>我的</h2>
          <p>这些参数直接决定记忆曲线的节奏，改动会立刻影响后续排期</p>
        </div>
        <button className="btn primary" onClick={save}>
          保存
        </button>
      </div>

      <div className="quick-nav">
        {[
          ["errors", "错题本", "按知识点聚合，专项重练"],
          ["exam", "考试模式", "中考 / 高考 / 四六级 / 考研 / 雅思"],
          ["topology", "成长拓扑", "看依赖关系与下一站"],
          ["stats", "学习报告", "留存率、热力图、遗忘预警"],
        ].map(([id, title, desc]) => (
          <button key={id} className="qn-item" onClick={() => nav?.(id)}>
            <b>{title}</b>
            <span>{desc}</span>
          </button>
        ))}
        <button className="qn-item" onClick={() => start?.({ mode: "concept" })}>
          <b>概念回看</b>
          <span>只读讲解，不打分</span>
        </button>
      </div>

      <div className="grid g2">
        <div className="card">
          <b>记忆曲线</b>
          <div className="tiny muted" style={{ marginBottom: 14 }}>
            目标留存率越高，复习越频繁。90% 是通行默认值。
          </div>

          <label className="tiny muted">目标留存率</label>
          <div className="row" style={{ margin: "6px 0 16px" }}>
            {[0.85, 0.9, 0.95].map((r) => (
              <button
                key={r}
                className={`chip-filter ${Number(form.retention) === r ? "on" : ""}`}
                onClick={() => set("retention", r)}
              >
                {Math.round(r * 100)}%
              </button>
            ))}
          </div>

          <label className="tiny muted">每日新学知识点上限</label>
          <input
            className="input"
            type="number"
            min="0"
            max="30"
            value={form.new_per_day}
            onChange={(e) => set("new_per_day", Number(e.target.value))}
            style={{ margin: "6px 0 14px" }}
          />

          <label className="tiny muted">每日复习上限</label>
          <input
            className="input"
            type="number"
            min="0"
            max="300"
            value={form.review_per_day}
            onChange={(e) => set("review_per_day", Number(e.target.value))}
            style={{ margin: "6px 0 14px" }}
          />

          <label className="tiny muted">每日目标题量（用于进度环）</label>
          <input
            className="input"
            type="number"
            min="5"
            max="300"
            value={form.daily_goal}
            onChange={(e) => set("daily_goal", Number(e.target.value))}
            style={{ margin: "6px 0 0" }}
          />
        </div>

        <div className="card">
          <b>训练强度</b>
          <div className="tiny muted" style={{ marginBottom: 14 }}>
            新学与复习各配几道题。题越多单次越牢，但耗时更长。
          </div>

          <label className="tiny muted">新学每个知识点的题量</label>
          <input
            className="input"
            type="number"
            min="2"
            max="7"
            value={form.learn_drills}
            onChange={(e) => set("learn_drills", Number(e.target.value))}
            style={{ margin: "6px 0 14px" }}
          />

          <label className="tiny muted">复习每个知识点的题量</label>
          <input
            className="input"
            type="number"
            min="1"
            max="7"
            value={form.review_drills}
            onChange={(e) => set("review_drills", Number(e.target.value))}
            style={{ margin: "6px 0 14px" }}
          />

          <label className="row" style={{ gap: 8, cursor: "pointer", marginTop: 4 }}>
            <input
              type="checkbox"
              checked={!!form.show_hint}
              onChange={(e) => set("show_hint", e.target.checked)}
            />
            <span className="tiny">允许请求提示（使用提示后本题按「吃力」计）</span>
          </label>

          <div className="divider" />

          <label className="tiny muted">变式题</label>
          <div className="seg" style={{ margin: "8px 0 8px" }}>
            {[
              ["off", "只用固定题"],
              ["mix", "每点 1 道"],
              ["half", "各占一半"],
              ["only", "全部变式"],
            ].map(([v, label]) => (
              <button
                key={v}
                className={form.variant_mode === v ? "on" : ""}
                onClick={() => set("variant_mode", v)}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="tiny muted" style={{ lineHeight: 1.7 }}>
            变式题由模板算出题干与答案（主语 × 动词 × 时间状语 × 宾语组合），判分仍按精确匹配。
            固定题是主干，变式用来防止「记住题面而不是规则」。
          </div>

          <div className="divider" />

          <label className="row" style={{ gap: 8, cursor: "pointer", alignItems: "flex-start" }}>
            <input
              type="checkbox"
              style={{ marginTop: 2 }}
              checked={!!form.prereq_gate}
              onChange={(e) => set("prereq_gate", e.target.checked)}
            />
            <span className="tiny" style={{ lineHeight: 1.6 }}>
              严格前置锁定
            </span>
          </label>
          <div className="tiny muted" style={{ marginTop: 4, lineHeight: 1.7 }}>
            开启后，前置没过的知识点不能直接学（学习模式会自动跳过并提示缺哪几个）。
            关闭只是提示，允许越级。复习不受前置限制。
          </div>

          <div className="divider" />

          <label className="tiny muted">概念回看 · 每轮几个</label>
          <div className="seg" style={{ margin: "8px 0 8px" }}>
            {[4, 6, 8, 12].map((n) => (
              <button
                key={n}
                className={Number(form.concept_per_round) === n ? "on" : ""}
                onClick={() => set("concept_per_round", n)}
              >
                {n} 个
              </button>
            ))}
          </div>
          <div className="tiny muted" style={{ lineHeight: 1.7 }}>
            「只看讲解」时一轮排几个点。它按记忆曲线挑最快会忘的，但只读不打分、也不改变复习排期——
            想真正记住还是得做题。
          </div>

          <div className="divider" />

          <div className="tiny muted">
            当前配置：每天最多 {form.new_per_day} 个新知识点、{form.review_per_day} 次复习，
            目标留存率 {Math.round(form.retention * 100)}%。
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 14 }}>
        <b>数据与备份</b>
        <div className="tiny muted" style={{ marginBottom: 14 }}>
          所有进度都存在本机 data/grammar.db。导出 JSON 可在换电脑或重装后完整恢复。
        </div>
        <div className="row wrap">
          <button className="btn" onClick={exportData}>
            导出备份
          </button>
          <button className="btn" onClick={() => fileRef.current?.click()}>
            导入备份
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="application/json"
            style={{ display: "none" }}
            onChange={(e) => e.target.files?.[0] && importData(e.target.files[0])}
          />
          <button
            className="btn danger right"
            onClick={async () => {
              if (!window.confirm("清空全部学习进度（卡片、记录、错题）？不可撤销，建议先导出备份。")) return;
              await api.reset("all");
              toast("已重置");
              window.location.reload();
            }}
          >
            重置全部进度
          </button>
        </div>
      </div>

      <div className="card" style={{ marginTop: 14 }}>
        <b>这套系统怎么算「学会」</b>
        <div className="tiny muted" style={{ lineHeight: 1.9, marginTop: 8 }}>
          掌握度 = 30% 记忆稳定度 + 30% 近期正确率 + 15% 题目覆盖 + 25% 当前可回忆概率。
          <br />
          记忆稳定度用 FSRS-4.5 计算：答对延长、答错缩短，连续答错 4 次标记为「顽固」并强制重讲。
          <br />
          复习时自评与实测取更保守的一方，避免「自我感觉良好」把复习排期推得太远。
        </div>
      </div>
    </div>
  );
}
