import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { Ring } from "../components/Charts.jsx";

const TYPE_LABEL = {
  choice: "选择",
  fill: "填空",
  correct: "改错",
  order: "重组",
  translate: "翻译",
};

const MODE_LABEL = { learn: "学习", review: "复习", train: "训练", grow: "生长", concept: "回看" };

function Stem({ text }) {
  const parts = String(text || "").split("___");
  return (
    <span>
      {parts.map((p, i) => (
        <span key={i}>
          {p}
          {i < parts.length - 1 && <span className="blank"> </span>}
        </span>
      ))}
    </span>
  );
}

export default function Session({ id, nav, toast, refreshPlan, onMode }) {
  const [s, setS] = useState(null);
  const [choice, setChoice] = useState(null);
  const [answer, setAnswer] = useState("");
  const [picked, setPicked] = useState([]);
  const [result, setResult] = useState(null);
  const [hint, setHint] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [summary, setSummary] = useState(null);
  const [busy, setBusy] = useState(false);
  const t0 = useRef(Date.now());
  const finishedRef = useRef(false);

  useEffect(() => {
    let alive = true;
    api
      .session(id)
      .then((d) => {
        if (!alive) return;
        setS(d);
        onMode?.(d.mode);
      })
      .catch((e) => toast(e.message));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    if (s?.finished && !finishedRef.current) {
      finishedRef.current = true;
      api
        .finish(id)
        .then((r) => {
          setSummary(r.summary || r);
          refreshPlan?.();
        })
        .catch(() => {});
    }
  }, [s?.finished, id, refreshPlan]);

  const reset = () => {
    setChoice(null);
    setAnswer("");
    setPicked([]);
    setResult(null);
    setHint(false);
    setRevealed(false);
    t0.current = Date.now();
  };

  const submit = async () => {
    if (busy || !s?.item?.drill) return;
    const d = s.item.drill;
    const val =
      d.type === "choice" ? choice : d.type === "order" ? picked.join(" ") : answer;
    if (!val || !String(val).trim()) {
      toast("先作答再提交");
      return;
    }
    setBusy(true);
    try {
      const r = await api.answer(id, {
        drill_id: d.id,
        answer: String(val),
        latency_ms: Date.now() - t0.current,
        hint_used: hint,
      });
      setResult(r.result);
      setS(r);
    } catch (e) {
      toast(e.message);
    } finally {
      setBusy(false);
    }
  };

  const advance = async () => {
    try {
      const r = await api.advance(id);
      setS(r);
      reset();
    } catch (e) {
      toast(e.message);
    }
  };

  const rate = async (r) => {
    try {
      const out = await api.recall(id, s.item.kp_id, r);
      setS(out);
      reset();
    } catch (e) {
      toast(e.message);
    }
  };

  if (!s) return <div className="loading">准备中…</div>;

  if (s.finished && !result) {
    return <Summary s={s} summary={summary} nav={nav} />;
  }

  const item = s.item;
  const done = s.pos;
  const total = s.total;

  return (
    <div className="session">
      <div className="s-head">
        <button className="btn sm ghost" onClick={() => nav("today")}>
          ← 退出
        </button>
        <div className="s-progress">
          <i style={{ width: `${total ? (done / total) * 100 : 0}%` }} />
        </div>
        <span className="tiny muted" style={{ fontVariantNumeric: "tabular-nums" }}>
          {done}/{total}
        </span>
        <span className="chip">{MODE_LABEL[s.mode] || s.mode}</span>
        {s.mode === "concept" ? (
          <span className="chip green">
            已看 {s.pos}/{total} 个
          </span>
        ) : (
          <span className="chip green">
            {s.answered ? Math.round((s.hits / s.answered) * 100) : 0}% 正确
          </span>
        )}
      </div>

      {item.kind === "concept" && (
        <ConceptView item={item} onNext={advance} mode={s.mode} />
      )}

      {item.kind === "recall" && (
        <RecallView
          item={item}
          revealed={revealed}
          onReveal={() => setRevealed(true)}
          onRate={rate}
          onSkip={advance}
        />
      )}

      {item.kind === "drill" && (
        <div className="q-card">
          <div className="row between" style={{ marginBottom: 10 }}>
            <div className="q-type">
              {TYPE_LABEL[item.drill.type] || item.drill.type} · {item.kp.chapter_name}
              {item.drill.generated && <span className="gen-badge">变式</span>}
            </div>
            <div className="tiny muted">
              {item.kp.title} {item.block_total ? `· ${item.index_in_block}/${item.block_total}` : ""}
            </div>
          </div>

          <div className="q-stem">
            <Stem text={item.drill.stem} />
          </div>

          {item.drill.type === "choice" && (
            <div className="options">
              {item.drill.options.map((o, i) => {
                let cls = "opt";
                if (!result && choice === o) cls += " sel";
                if (result) {
                  if (o === result.answer) cls += " ok";
                  else if (o === choice) cls += " bad";
                }
                return (
                  <button key={o} className={cls} onClick={() => !result && setChoice(o)} disabled={!!result}>
                    <span className="key">{String.fromCharCode(65 + i)}</span>
                    <span>{o}</span>
                  </button>
                );
              })}
            </div>
          )}

          {(item.drill.type === "fill" || item.drill.type === "correct") && (
            <input
              className="input"
              style={{ fontSize: 16, padding: "13px 14px" }}
              placeholder={item.drill.type === "fill" ? "填入答案" : "写出改正后的完整句子"}
              value={answer}
              disabled={!!result}
              onChange={(e) => setAnswer(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !result && submit()}
              autoFocus
            />
          )}

          {item.drill.type === "translate" && (
            <textarea
              className="input answer-box"
              placeholder="写出英文译文，标点与大小写不严格判定"
              value={answer}
              disabled={!!result}
              onChange={(e) => setAnswer(e.target.value)}
            />
          )}

          {item.drill.type === "order" && (
            <OrderInput
              tokens={item.drill.tokens}
              picked={picked}
              setPicked={setPicked}
              disabled={!!result}
            />
          )}

          {item.drill.hint && !result && (
            <div style={{ marginTop: 12 }}>
              {hint ? (
                <div className="tiny" style={{ color: "var(--warn)" }}>
                  提示：{item.drill.hint}
                </div>
              ) : (
                <button className="btn sm ghost" onClick={() => setHint(true)}>
                  给一点提示
                </button>
              )}
            </div>
          )}

          {result && <ResultPanel result={result} />}

          <div className="row" style={{ marginTop: 18 }}>
            {!result ? (
              <>
                <button className="btn primary" onClick={submit} disabled={busy}>
                  提交
                </button>
                <span className="tiny muted">回车也可提交</span>
              </>
            ) : (
              <button
                className="btn primary"
                onClick={() => {
                  reset();
                }}
                autoFocus
              >
                下一题
              </button>
            )}
            <button className="btn ghost sm right" onClick={() => nav("today")}>
              先到这里
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------------- 概念讲解 ---------------- */

function ConceptView({ item, onNext, mode }) {
  const c = item.concept;
  const reading = mode === "concept";
  return (
    <div className="q-card">
      <div className="concept">
        <div className="q-type">{reading ? "回看 · 讲解" : "学习 · 讲解"}</div>
        <h3>{item.kp.title}</h3>
        <div className="brief">
          {item.kp.level1_name} · {item.kp.chapter_name} · {item.kp.brief}
        </div>

        <div className="concept-summary">{c.summary}</div>

        {c.sections.map((s, i) => (
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
          <h4>例句对照</h4>
          {c.examples.map((ex, i) => (
            <div key={i} className={`ex ${ex.ok ? "ok" : "bad"}`}>
              <span className="mark">{ex.ok ? "✓" : "✕"}</span>
              <div>
                <div className="en">{ex.en}</div>
                <div className="zh">{ex.zh}</div>
                {ex.note && <div className="note">{ex.note}</div>}
              </div>
            </div>
          ))}
        </div>

        {c.pitfalls?.length > 0 && (
          <div className="sec">
            <h4>易错点</h4>
            {c.pitfalls.map((p, i) => (
              <div className="pit" key={i}>
                <div>
                  <span className="w">{p.wrong}</span>
                </div>
                <div>
                  <span className="r">{p.right}</span>
                </div>
                <div className="why">{p.why}</div>
              </div>
            ))}
          </div>
        )}

        {c.contrast?.withTitle && (
          <div className="contrast">
            与 <b>{c.contrast.withTitle}</b> 的区别：{c.contrast.diff}
          </div>
        )}

        {c.mnemonic && <div className="mnemonic">记忆锚点：{c.mnemonic}</div>}

        <div className="row" style={{ marginTop: 22 }}>
          <button className="btn primary" onClick={onNext}>
            {reading ? "看完了，下一个 →" : "开始训练 →"}
          </button>
          <span className="tiny muted">
            {reading ? "回看只读不打分，不影响这条规则的复习排期" : "先理解规则，再进入题目，不要靠语感蒙"}
          </span>
        </div>
      </div>
    </div>
  );
}

/* ---------------- 复习回忆 ---------------- */

function RecallView({ item, revealed, onReveal, onRate, onSkip }) {
  const r = item.review;
  return (
    <div className="q-card">
      <div className="recall">
        <div className="q-type">复习 · 主动回忆</div>
        <h3>{item.kp.title}</h3>
        <div className="hint">
          先别展开。心里把这条规则讲一遍：判定标准是什么、最容易错在哪。
          <br />
          讲不出来，就给自己低分——评分会直接决定下次出现的时间。
        </div>
        {item.lapses > 0 && (
          <div className="tiny" style={{ color: "var(--warn)", marginBottom: 10 }}>
            这个知识点已经遗忘 {item.lapses} 次
          </div>
        )}
        {!revealed ? (
          <button className="btn primary" onClick={onReveal}>
            展开复习卡
          </button>
        ) : (
          <div className="reveal">
            <ul className="core-list">
              {r.core.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
            <div className="trigger">识别信号：{r.trigger}</div>
            {r.quickCheck?.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <div className="tiny muted" style={{ marginBottom: 6 }}>
                  快速自检（点一下看答案）
                </div>
                {r.quickCheck.map((q, i) => (
                  <QC key={i} q={q} />
                ))}
              </div>
            )}
            <div className="tiny muted" style={{ marginTop: 18, textAlign: "center" }}>
              刚才的回忆有多清楚？
            </div>
            <div className="rate-grid">
              <button className="rate" data-r="1" onClick={() => onRate(1)}>
                <b>模糊</b>
                <span>想不起来</span>
              </button>
              <button className="rate" data-r="2" onClick={() => onRate(2)}>
                <b>吃力</b>
                <span>勉强想起</span>
              </button>
              <button className="rate" data-r="3" onClick={() => onRate(3)}>
                <b>记得</b>
                <span>基本清楚</span>
              </button>
              <button className="rate" data-r="4" onClick={() => onRate(4)}>
                <b>熟练</b>
                <span>张口就来</span>
              </button>
            </div>
            <div className="center" style={{ marginTop: 10 }}>
              <button className="btn sm ghost" onClick={onSkip}>
                不评了，直接做题
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function QC({ q }) {
  const [open, setOpen] = useState(false);
  return (
    <div
      onClick={() => setOpen((o) => !o)}
      style={{
        padding: "8px 11px",
        border: "1px solid var(--line-soft)",
        borderRadius: 9,
        marginBottom: 6,
        cursor: "pointer",
        fontSize: 13,
        background: "var(--panel-2)",
      }}
    >
      <div className="row between">
        <span>{q.q}</span>
        <span className="tiny muted">{open ? "收起" : "看答案"}</span>
      </div>
      {open && (
        <div style={{ marginTop: 6, color: "var(--ok)", fontSize: 12.5 }}>{q.a}</div>
      )}
    </div>
  );
}

/* ---------------- 题目控件 ---------------- */

function OrderInput({ tokens, picked, setPicked, disabled }) {
  const used = picked.map((p) => p);
  return (
    <div>
      <div className="tokens" style={{ minHeight: 58, marginBottom: 10 }}>
        {picked.length === 0 && (
          <span className="tiny muted" style={{ padding: "4px 2px" }}>
            按顺序点击下方词组
          </span>
        )}
        {picked.map((p, i) => (
          <button
            key={`${p}-${i}`}
            className="token in-answer"
            onClick={() => !disabled && setPicked(picked.filter((_, j) => j !== i))}
          >
            {p}
          </button>
        ))}
      </div>
      <div className="tokens" style={{ borderStyle: "solid" }}>
        {tokens.map((t, i) => {
          const count = used.filter((x) => x === t).length;
          const totalSame = tokens.filter((x) => x === t).length;
          const disabledToken = count >= totalSame;
          return (
            <button
              key={`${t}-${i}`}
              className={`token ${disabledToken ? "used" : ""}`}
              onClick={() => !disabled && !disabledToken && setPicked([...picked, t])}
            >
              {t}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function ResultPanel({ result }) {
  const ok = result.correct;
  return (
    <div className={`result ${ok ? "ok" : "bad"}`}>
      <div className="head">
        <span>{ok ? "✓" : "✕"}</span>
        <span>{ok ? "正确" : "不对"}</span>
        {!ok && result.partial > 0 && result.partial < 1 && (
          <span className="chip gold">命中 {Math.round(result.partial * 100)}%</span>
        )}
      </div>
      {!ok && result.answer && <div className="ans">{result.answer}</div>}
      {ok && result.type === "translate" && result.answer && (
        <div className="ans">{result.answer}</div>
      )}
      {result.feedback && <div className="tiny" style={{ color: "var(--warn)" }}>{result.feedback}</div>}
      <div className="explain" style={{ marginTop: 8 }}>
        {result.explain}
      </div>
      {result.trap && <div className="trap">干扰项：{result.trap}</div>}
    </div>
  );
}

/* ---------------- 结算 ---------------- */

function Summary({ s, summary, nav }) {
  const sm = summary || s.summary || {};
  const acc = Math.round((sm.accuracy || 0) * 100);

  if (sm.mode === "concept") {
    return (
      <div className="q-card">
        <div className="summary">
          <h3>回看结束</h3>
          <div className="sm">
            读完 {sm.kp_count || 0} 个知识点的讲解 · 用时 {sm.minutes || 0} 分钟
          </div>
          <div className="tiny muted" style={{ marginBottom: 18 }}>
            这次只是回看：不打分、也不改变复习排期。想把规则真正钉住，还是得做题。
          </div>
          <div className="row wrap" style={{ justifyContent: "center", gap: 8 }}>
            <button className="btn" onClick={() => nav("curriculum")}>
              去课程做题
            </button>
            <button className="btn" onClick={() => nav("stats")}>
              学习报告
            </button>
            <button className="btn primary" onClick={() => nav("today")}>
              回到今日
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="q-card">
      <div className="summary">
        <Ring value={acc} size={132} stroke={9} color={acc >= 80 ? "#3ecf8e" : acc >= 60 ? "#e8b256" : "#ef6b6b"} />
        <h3>{acc >= 80 ? "这一组很稳" : acc >= 60 ? "过关，但还有漏洞" : "先回去看讲解"}</h3>
        <div className="sm">
          {MODE_LABEL[sm.mode] || sm.mode}结束 · 用时 {sm.minutes || 0} 分钟
        </div>
        <div className="sum-grid">
          <div className="stat tight">
            <div className="k">知识点</div>
            <div className="v" style={{ fontSize: 22 }}>{sm.kp_count || 0}</div>
          </div>
          <div className="stat tight">
            <div className="k">作答</div>
            <div className="v" style={{ fontSize: 22 }}>{sm.answered || 0}</div>
          </div>
          <div className="stat tight">
            <div className="k">正确</div>
            <div className="v" style={{ fontSize: 22 }}>{sm.hits || 0}</div>
          </div>
          <div className="stat tight">
            <div className="k">正确率</div>
            <div className="v" style={{ fontSize: 22 }}>{acc}%</div>
          </div>
        </div>
        <div className="row" style={{ justifyContent: "center" }}>
          <button className="btn" onClick={() => nav("errors")}>
            看错题
          </button>
          <button className="btn" onClick={() => nav("stats")}>
            学习报告
          </button>
          <button className="btn primary" onClick={() => nav("today")}>
            回到今日
          </button>
        </div>
      </div>
    </div>
  );
}
