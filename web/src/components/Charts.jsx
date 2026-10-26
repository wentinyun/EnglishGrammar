import React from "react";

/** 环形进度 */
export function Ring({ value = 0, size = 132, stroke = 9, color = "#7c93ff", label }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div className="big-ring" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#202836" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${(c * pct) / 100} ${c}`}
        />
      </svg>
      <div className="pct">{label ?? `${Math.round(pct)}%`}</div>
    </div>
  );
}

/** 七维掌握度雷达 */
export function Radar({ items = [], size = 300 }) {
  const n = items.length || 1;
  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2 - 66;
  const angle = (i) => -Math.PI / 2 + (i * 2 * Math.PI) / n;
  const point = (i, v) => {
    const rr = (r * Math.max(0, Math.min(100, v))) / 100;
    return [cx + rr * Math.cos(angle(i)), cy + rr * Math.sin(angle(i))];
  };
  const rings = [0.25, 0.5, 0.75, 1];
  const poly = items.map((it, i) => point(i, it.mastery).join(",")).join(" ");

  return (
    <svg width="100%" viewBox={`0 0 ${size} ${size}`} style={{ display: "block" }}>
      {rings.map((k, ri) => (
        <polygon
          key={ri}
          points={items
            .map((_, i) => {
              const rr = r * k;
              return `${cx + rr * Math.cos(angle(i))},${cy + rr * Math.sin(angle(i))}`;
            })
            .join(" ")}
          fill="none"
          stroke="#232b39"
          strokeWidth="1"
        />
      ))}
      {items.map((_, i) => (
        <line
          key={i}
          x1={cx}
          y1={cy}
          x2={cx + r * Math.cos(angle(i))}
          y2={cy + r * Math.sin(angle(i))}
          stroke="#1e2633"
          strokeWidth="1"
        />
      ))}
      <polygon points={poly} fill="rgba(124,147,255,0.18)" stroke="#7c93ff" strokeWidth="1.8" />
      {items.map((it, i) => {
        const [x, y] = point(i, it.mastery);
        return <circle key={i} cx={x} cy={y} r="3" fill="#7c93ff" />;
      })}
      {items.map((it, i) => {
        const a = angle(i);
        const cos = Math.cos(a);
        const rawX = cx + (r + 20) * cos;
        const ly = cy + (r + 20) * Math.sin(a);
        const anchor = Math.abs(cos) < 0.25 ? "middle" : cos > 0 ? "start" : "end";
        const lx = Math.max(6, Math.min(size - 6, rawX));
        return (
          <text key={i} x={lx} y={ly + 3} fill="#8b98ab" fontSize="10.5" textAnchor={anchor}>
            {it.name}
          </text>
        );
      })}
    </svg>
  );
}

/** 每日热力图（按周列排布） */
export function Heatmap({ days = [] }) {
  const first = days.length ? new Date(days[0].day + "T00:00:00") : new Date();
  const pad = first.getDay(); // 0 = 周日
  const cells = [];
  for (let i = 0; i < pad; i++) cells.push(null);
  days.forEach((d) => cells.push(d));
  const level = (n) => {
    if (!n) return 0;
    if (n < 8) return 1;
    if (n < 20) return 2;
    if (n < 40) return 3;
    return 4;
  };
  return (
    <div
      style={{
        display: "grid",
        gridTemplateRows: "repeat(7, 1fr)",
        gridAutoFlow: "column",
        gap: 3,
      }}
    >
      {cells.map((c, i) => (
        <i
          key={i}
          data-l={c ? level(c.reviews) : 0}
          title={c ? `${c.day} · ${c.reviews} 题${c.new ? ` · 新学 ${c.new}` : ""}` : ""}
        />
      ))}
    </div>
  );
}

/** 预测柱状图 */
export function Forecast({ items = [] }) {
  const max = Math.max(5, ...items.map((i) => i.count));
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 6, height: 108 }}>
      {items.map((it, i) => (
        <div key={i} style={{ flex: 1, textAlign: "center" }} title={`${it.label} · ${it.count} 个`}>
          <div
            style={{
              height: `${(it.count / max) * 78}px`,
              minHeight: it.count ? 3 : 0,
              background: i === 0 && it.count ? "#ef6b6b" : "linear-gradient(180deg,#7c93ff,#4c63c9)",
              borderRadius: "3px 3px 0 0",
              opacity: it.count ? 1 : 0.35,
              transition: "height .3s",
            }}
          />
          <div style={{ fontSize: 9.5, color: "#6b7688", marginTop: 5 }}>{it.label}</div>
        </div>
      ))}
    </div>
  );
}

/** 水平条 */
export function BarRow({ label, value, max = 100, color = "#7c93ff", right }) {
  const pct = max ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div style={{ marginBottom: 9 }}>
      <div className="row between" style={{ fontSize: 12, marginBottom: 4 }}>
        <span className="muted">{label}</span>
        <span style={{ color, fontVariantNumeric: "tabular-nums" }}>{right ?? Math.round(value)}</span>
      </div>
      <div className="bar">
        <i style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}
