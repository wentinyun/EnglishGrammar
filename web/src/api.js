const BASE = "";

async function request(path, options = {}) {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const j = await res.json();
      msg = j.detail || msg;
    } catch (_) {
      /* ignore */
    }
    throw new Error(msg);
  }
  return res.json();
}

const post = (path, body) =>
  request(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  curriculum: () => request("/api/curriculum"),
  kp: (id) => request(`/api/kp/${encodeURIComponent(id)}`),
  progress: () => request("/api/progress"),
  plan: () => request("/api/plan"),
  overview: () => request("/api/stats/overview"),
  heatmap: (days = 182) => request(`/api/stats/heatmap?days=${days}`),
  forecast: (days = 14) => request(`/api/stats/forecast?days=${days}`),
  retention: () => request("/api/stats/retention"),
  weak: (limit = 12) => request(`/api/stats/weak?limit=${limit}`),

  start: (body) => post("/api/session/start", body),
  session: (id) => request(`/api/session/${id}`),
  answer: (id, body) => post(`/api/session/${id}/answer`, body),
  recall: (id, kpId, rating) => post(`/api/session/${id}/recall`, { kp_id: kpId, rating }),
  advance: (id) => post(`/api/session/${id}/advance`),
  finish: (id) => post(`/api/session/${id}/finish`),

  errors: (limit = 120) => request(`/api/errors?limit=${limit}`),
  clearErrors: () => post("/api/errors/clear"),

  topology: (granularity = "chapter") => request(`/api/topology?granularity=${granularity}`),
  frontier: (limit = 8) => request(`/api/topology/frontier?limit=${limit}`),
  pathTo: (kpId) => request(`/api/topology/path/${encodeURIComponent(kpId)}`),

  examProfiles: () => request("/api/exam/profiles"),
  examHistory: () => request("/api/exam/history"),
  examStart: (profile, count) => post("/api/exam/start", { profile, count }),
  exam: (id) => request(`/api/exam/${id}`),
  examSubmit: (id, answers) => post(`/api/exam/${id}/submit`, { answers }),

  settings: () => request("/api/settings"),
  saveSettings: (patch) => post("/api/settings", patch),
  exportData: () => request("/api/export"),
  importData: (data) => post("/api/import", { data }),
  reset: (scope) => post(`/api/reset?scope=${scope}`),
};
