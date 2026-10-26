import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import Today from "./pages/Today.jsx";
import Curriculum from "./pages/Curriculum.jsx";
import Session from "./pages/Session.jsx";
import Exam from "./pages/Exam.jsx";
import Errors from "./pages/Errors.jsx";
import Stats from "./pages/Stats.jsx";
import Topology from "./pages/Topology.jsx";
import Settings from "./pages/Settings.jsx";

const NAV = [
  { id: "today", label: "今日", ico: "◐" },
  { id: "curriculum", label: "课程体系", ico: "▤" },
  { id: "topology", label: "成长拓扑", ico: "◈" },
  { id: "exam", label: "考试模式", ico: "✎" },
  { id: "errors", label: "错题本", ico: "⚑" },
  { id: "stats", label: "学习报告", ico: "◔" },
  { id: "settings", label: "设置", ico: "⚙" },
];

// 手机底部标签栏：五个主入口，错题与考试从「今日」和「我的」进
const TABS = [
  { id: "today", label: "今日", path: "M4 11.2 12 4l8 7.2V20a1 1 0 0 1-1 1h-4.6v-6.4H9.6V21H5a1 1 0 0 1-1-1z" },
  { id: "curriculum", label: "课程", path: "M4 5.5h7.2M4 12h7.2M4 18.5h7.2M14.6 5.5h5.4M14.6 12h5.4M14.6 18.5h5.4" },
  { id: "topology", label: "拓扑", path: "M12 4.6v4.2M6 19.2v-3.4h12v3.4M12 8.8a2.1 2.1 0 1 0 0-4.2 2.1 2.1 0 0 0 0 4.2zM6 21.3a2.1 2.1 0 1 0 0-4.2 2.1 2.1 0 0 0 0 4.2zM18 21.3a2.1 2.1 0 1 0 0-4.2 2.1 2.1 0 0 0 0 4.2z" },
  { id: "stats", label: "报告", path: "M5 19.4V12M12 19.4V6M19 19.4v-11" },
  { id: "settings", label: "我的", path: "M12 12.4a3.9 3.9 0 1 0 0-7.8 3.9 3.9 0 0 0 0 7.8zM4.6 20.6c.6-3.6 3.6-5.7 7.4-5.7s6.8 2.1 7.4 5.7" },
];

const TITLE = {
  today: "今日",
  curriculum: "课程体系",
  topology: "成长拓扑",
  exam: "考试模式",
  errors: "错题本",
  stats: "学习报告",
  settings: "我的",
  session: "学习中",
};

function TabIcon({ d }) {
  return (
    <svg className="m-ico" viewBox="0 0 24 24" width="23" height="23" aria-hidden="true">
      <path d={d} fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function readHash() {
  const raw = window.location.hash.replace(/^#\/?/, "");
  const [name, param] = raw.split("/");
  if (!name || (!NAV.some((n) => n.id === name) && name !== "session")) return { name: "today" };
  return name === "session" ? { name: "session", sessionId: param } : { name, param };
}

export default function App() {
  const [route, setRoute] = useState(readHash);
  const [plan, setPlan] = useState(null);
  const [toast, setToast] = useState("");
  // 会话页的顶栏标题跟着模式走：学习 / 复习 / 训练 / 回看
  const [sessionMode, setSessionMode] = useState("");

  useEffect(() => {
    const onHash = () => setRoute(readHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const nav = useCallback((name, params = {}) => {
    setRoute({ name, ...params });
    const hash = params.sessionId ? `#/${name}/${params.sessionId}` : `#/${name}`;
    if (window.location.hash !== hash) window.history.replaceState(null, "", hash);
    window.scrollTo({ top: 0 });
  }, []);

  const refreshPlan = useCallback(() => {
    api.plan().then(setPlan).catch(() => {});
  }, []);

  useEffect(() => {
    refreshPlan();
  }, [refreshPlan, route.name]);

  const showToast = (msg) => {
    setToast(msg);
    window.clearTimeout(showToast._t);
    showToast._t = window.setTimeout(() => setToast(""), 2400);
  };

  const start = async (body) => {
    try {
      const s = await api.start(body);
      nav("session", { sessionId: s.id });
    } catch (e) {
      showToast(e.message);
    }
  };

  const page = () => {
    switch (route.name) {
      case "curriculum":
        return <Curriculum nav={nav} start={start} toast={showToast} />;
      case "topology":
        return <Topology nav={nav} start={start} toast={showToast} param={route.param} />;
      case "session":
        return (
          <Session
            id={route.sessionId}
            nav={nav}
            toast={showToast}
            refreshPlan={refreshPlan}
            onMode={setSessionMode}
          />
        );
      case "exam":
        return <Exam nav={nav} toast={showToast} />;
      case "errors":
        return <Errors nav={nav} start={start} toast={showToast} />;
      case "stats":
        return <Stats />;
      case "settings":
        return <Settings toast={showToast} refreshPlan={refreshPlan} nav={nav} start={start} />;
      default:
        return <Today nav={nav} start={start} plan={plan} />;
    }
  };

  const focus = route.name === "session";
  const SESSION_TITLE = { learn: "学习中", grow: "生长", review: "复习", train: "训练", concept: "回看" };
  const pageTitle =
    route.name === "session"
      ? SESSION_TITLE[sessionMode] || "学习中"
      : TITLE[route.name] || "英语语法全景";

  return (
    <div className={`layout${focus ? " focus" : ""}`}>
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <div>
            <h1>英语语法全景</h1>
            <span>Grammar OS</span>
          </div>
        </div>
        <nav className="nav">
          {NAV.map((n) => (
            <button
              key={n.id}
              className={route.name === n.id ? "active" : ""}
              onClick={() => nav(n.id)}
            >
              <span className="ico">{n.ico}</span>
              {n.label}
            </button>
          ))}
        </nav>
        <div className="side-foot">
          <div className="row between">
            <span>连续打卡</span>
            <b style={{ fontSize: 14 }}>{plan ? `${plan.streak || 0} 天` : "—"}</b>
          </div>
          <div className="row between" style={{ marginTop: 6 }}>
            <span>今日待复习</span>
            <b style={{ fontSize: 14 }}>{plan ? plan.due_today : "—"}</b>
          </div>
          <div className="row between" style={{ marginTop: 6 }}>
            <span>今日进度</span>
            <b style={{ fontSize: 14 }}>{plan ? `${plan.reviews_done}/${plan.goal}` : "—"}</b>
          </div>
        </div>
      </aside>

      <header className="m-topbar">
        <div className="mt-left">
          {focus ? (
            <button className="mt-back" onClick={() => nav("today")} aria-label="退出">
              <svg viewBox="0 0 24 24" width="20" height="20">
                <path d="M15 5 8 12l7 7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          ) : (
            <span className="brand-mark sm" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
          )}
          <b>{pageTitle}</b>
        </div>
        <div className="mt-right">
          {plan && plan.due_today > 0 && !focus && (
            <span className="chip gold tiny">待复习 {plan.due_today}</span>
          )}
          {plan && <span className="mt-streak">🔥 {plan.streak || 0}</span>}
        </div>
      </header>

      <main className="main">
        <div className="page-in" key={route.name + (route.sessionId || "")}>
          {page()}
        </div>
      </main>

      <nav className="m-tabbar">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`m-tab${route.name === t.id ? " on" : ""}`}
            onClick={() => nav(t.id)}
          >
            <TabIcon d={t.path} />
            <span>{t.label}</span>
            {t.id === "today" && plan && plan.due_today > 0 && <i className="m-dot" />}
          </button>
        ))}
      </nav>

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
