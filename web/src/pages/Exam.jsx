import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { useAsync, useNow, pct } from "../hooks.js";
import { Ring, BarRow } from "../components/Charts.jsx";

function fmt(ms) {
  const s = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(s / 60);
  return `${String(m).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export default function Exam({ toast }) {
  const profiles = useAsync(() => api.examProfiles(), []);
  const [exam, setExam] = useState(null);
  const [answers, setAnswers] = useState({});
  const [picked, setPicked] = useState({});
  const [cur, setCur] = useState(0);
  const [result, setResult] = useState(null);
  const [starting, setStarting] = useState(false);
  const now = useNow(1000);

  const startExam = async (p) => {
    setStarting(true);
    try {
      const e = await api.examStart(p.id);
      setExam(e);
      setAnswers({});
      setPicked({});
      setCur(0);
      setResult(null);
    } catch (e) {
      toast(e.message);
    } finally {
      setStarting(false);
    }
  };

  const submit = async () => {
    if (!exam) return;
    const unanswered = exam.questions.filter((q) => !String(answers[q.id] || "").trim()).length;
    if (unanswered > 0 && !window.confirm(`还有 ${unanswered} 题未作答，确定交卷？`)) return;
    try {
      const r = await api.examSubmit(exam.id, answers);
      setResult(r);
      window.scrollTo({ top: 0 });
    } catch (e) {
      toast(e.message);
    }
  };

  if (result) {
    return (
      <Result
        result={result}
        exam={exam}
        onRetry={() => {
          setExam(null);
          setResult(null);
        }}
      />
    );
  }

  if (!exam) {
    return (
      <div>
        <div className="page-head">
          <div>
            <h2>考试模式</h2>
            <p>按考试类型加权抽题，限时作答，整卷判分。考完的错题会自动进入错题本。</p>
          </div>
        </div>
        {profiles.loading && <div className="loading">加载中…</div>}
        <div className="grid g3">
          {(profiles.data || []).map((p) => (
            <div className="card" key={p.id}>
              <div className="row between">
                <b style={{ fontSize: 16 }}>{p.name}</b>
                <span className="chip">{p.count} 题</span>
              </div>
              <div className="tiny muted" style={{ marginTop: 6, minHeight: 34 }}>
                {p.desc}
              </div>
              <div className="row between" style={{ marginTop: 14 }}>
                <span className="tiny muted">{p.minutes} 分钟</span>
                <button className="btn sm primary" disabled={starting} onClick={() => startExam(p)}>
                  开始
                </button>
              </div>
            </div>
          ))}
        </div>
        <History />
      </div>
    );
  }

  const q = exam.questions[cur];
  const left = new Date(exam.deadline).getTime() - now;
  const doneCount = exam.questions.filter((x) => String(answers[x.id] || "").trim()).length;

  return (
    <div className="session">
      <div className="s-head">
        <button className="btn sm ghost" onClick={() => window.confirm("退出后本卷不保留，确定？") && setExam(null)}>
          ← 退出
        </button>
        <span className="chip">{exam.profile_name}</span>
        <span className="tiny muted">
          已答 {doneCount}/{exam.questions.length}
        </span>
        <span className={`timer right ${left < 300000 ? "warn" : ""}`}>{fmt(left)}</span>
      </div>

      <div className="q-card">
        <div className="row between" style={{ marginBottom: 12 }}>
          <div className="q-type">
            第 {cur + 1} 题 · {exam.questions[cur].type === "choice" ? "选择" : exam.questions[cur].type === "fill" ? "填空" : exam.questions[cur].type === "correct" ? "改错" : exam.questions[cur].type === "order" ? "重组" : "翻译"}
          </div>
          <span className="tiny muted">{q.kp_title}</span>
        </div>

        <div className="q-stem">
          {String(q.stem)
            .split("___")
            .map((p, i, arr) => (
              <span key={i}>
                {p}
                {i < arr.length - 1 && <span className="blank"> </span>}
              </span>
            ))}
        </div>

        {q.type === "choice" && (
          <div className="options">
            {q.options.map((o, i) => (
              <button
                key={o}
                className={`opt ${answers[q.id] === o ? "sel" : ""}`}
                onClick={() => setAnswers({ ...answers, [q.id]: o })}
              >
                <span className="key">{String.fromCharCode(65 + i)}</span>
                <span>{o}</span>
              </button>
            ))}
          </div>
        )}

        {(q.type === "fill" || q.type === "correct") && (
          <input
            className="input"
            style={{ fontSize: 16, padding: "13px 14px" }}
            value={answers[q.id] || ""}
            onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })}
          />
        )}

        {q.type === "translate" && (
          <textarea
            className="input answer-box"
            value={answers[q.id] || ""}
            onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })}
          />
        )}

        {q.type === "order" && (
          <OrderQ
            q={q}
            picked={picked[q.id] || []}
            setPicked={(arr) => {
              setPicked({ ...picked, [q.id]: arr });
              setAnswers({ ...answers, [q.id]: arr.join(" ") });
            }}
          />
        )}

        <div className="row" style={{ marginTop: 20 }}>
          <button className="btn" disabled={cur === 0} onClick={() => setCur(cur - 1)}>
            上一题
          </button>
          <button
            className="btn primary"
            disabled={cur === exam.questions.length - 1}
            onClick={() => setCur(cur + 1)}
          >
            下一题
          </button>
          <button className="btn right" onClick={submit}>
            交卷
          </button>
        </div>
      </div>

      <div className="card" style={{ marginTop: 14 }}>
        <div className="tiny muted" style={{ marginBottom: 8 }}>
          答题卡
        </div>
        <div className="exam-nav">
          {exam.questions.map((x, i) => (
            <button
              key={x.id}
              className={`${String(answers[x.id] || "").trim() ? "done" : ""} ${i === cur ? "cur" : ""}`}
              onClick={() => setCur(i)}
            >
              {i + 1}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function OrderQ({ q, picked, setPicked }) {
  return (
    <div>
      <div className="tokens" style={{ minHeight: 54, marginBottom: 10 }}>
        {picked.length === 0 && <span className="tiny muted">按顺序点击词组</span>}
        {picked.map((p, i) => (
          <button key={i} className="token in-answer" onClick={() => setPicked(picked.filter((_, j) => j !== i))}>
            {p}
          </button>
        ))}
      </div>
      <div className="tokens" style={{ borderStyle: "solid" }}>
        {q.tokens.map((t, i) => {
          const used = picked.filter((x) => x === t).length;
          const totalSame = q.tokens.filter((x) => x === t).length;
          return (
            <button
              key={i}
              className={`token ${used >= totalSame ? "used" : ""}`}
              onClick={() => used < totalSame && setPicked([...picked, t])}
            >
              {t}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function Result({ result, exam, onRetry }) {
  const wrong = result.details.filter((d) => !d.correct);
  const byType = useMemo(() => {
    const m = {};
    result.details.forEach((d) => {
      m[d.type] = m[d.type] || { total: 0, ok: 0 };
      m[d.type].total += 1;
      if (d.correct) m[d.type].ok += 1;
    });
    return m;
  }, [result]);

  return (
    <div className="session">
      <div className="q-card">
        <div className="summary">
          <Ring
            value={result.score}
            size={132}
            color={result.score >= 80 ? "#3ecf8e" : result.score >= 60 ? "#e8b256" : "#ef6b6b"}
            label={String(result.score)}
          />
          <h3>{result.grade}</h3>
          <div className="sm">
            {exam.profile_name} · 答对 {result.hits}/{result.total}
          </div>
        </div>

        <div style={{ marginTop: 8 }}>
          <div className="tiny muted" style={{ marginBottom: 8 }}>
            分类得分
          </div>
          {result.levels.map((l) => (
            <BarRow
              key={l.id}
              label={`${l.name}（${l.correct}/${l.total}）`}
              value={l.rate * 100}
              color={l.rate >= 0.8 ? "#3ecf8e" : l.rate >= 0.6 ? "#e8b256" : "#ef6b6b"}
              right={pct(l.rate)}
            />
          ))}
        </div>

        <div className="divider" />

        <div className="tiny muted" style={{ marginBottom: 8 }}>
          题型表现
        </div>
        <div className="row wrap">
          {Object.entries(byType).map(([k, v]) => (
            <span key={k} className="chip">
              {k} {v.ok}/{v.total}
            </span>
          ))}
        </div>

        <div className="row" style={{ marginTop: 22 }}>
          <button className="btn primary" onClick={onRetry}>
            再考一次
          </button>
        </div>
      </div>

      {wrong.length > 0 && (
        <div className="card" style={{ marginTop: 14 }}>
          <div className="row between" style={{ marginBottom: 10 }}>
            <b>错题解析（{wrong.length}）</b>
            <span className="tiny muted">已自动加入错题本</span>
          </div>
          {wrong.map((d) => (
            <div className="err-item" key={d.id}>
              <div className="row between">
                <span className="chip">{d.level1_name}</span>
                <span className="tiny muted">{d.kp_title}</span>
              </div>
              <div className="stem">{d.stem}</div>
              <div className="ua">你的答案：{d.user_answer || "（空）"}</div>
              <div className="ca">正确答案：{d.expected}</div>
              <div className="tiny muted" style={{ marginTop: 6 }}>
                {d.explain}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function History() {
  const { data } = useAsync(() => api.examHistory(), []);
  if (!data || !data.length) return null;
  return (
    <div className="card" style={{ marginTop: 14 }}>
      <b>模考记录</b>
      <table className="plain" style={{ marginTop: 8 }}>
        <thead>
          <tr>
            <th>时间</th>
            <th>类型</th>
            <th>得分</th>
            <th>结果</th>
          </tr>
        </thead>
        <tbody>
          {data.map((h) => (
            <tr key={h.id}>
              <td className="muted">{h.started_at.replace("T", " ").slice(5, 16)}</td>
              <td>{h.profile}</td>
              <td style={{ fontVariantNumeric: "tabular-nums" }}>{h.score ?? "—"}</td>
              <td>
                <span className={`chip ${h.score >= 80 ? "green" : h.score >= 60 ? "gold" : "red"}`}>
                  {h.grade || "未交卷"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
