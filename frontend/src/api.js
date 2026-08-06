const BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: options.body instanceof FormData ? {} : { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `${res.status} ${res.statusText}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  createPile: (name, domain) => request("/piles", { method: "POST", body: JSON.stringify({ name, domain }) }),
  listPileDocuments: (pileId) => request(`/piles/${pileId}/documents`),
  addRule: (pileId, text) => request(`/piles/${pileId}/rules`, { method: "POST", body: JSON.stringify({ text }) }),
  listRules: (pileId) => request(`/piles/${pileId}/rules`),
  uploadDocument: (pileId, file) => {
    const form = new FormData();
    form.append("file", file);
    return request(`/piles/${pileId}/documents`, { method: "POST", body: form });
  },
  startRun: (pileId, documentIds) =>
    request(`/piles/${pileId}/runs`, { method: "POST", body: JSON.stringify({ document_ids: documentIds }) }),
  resumeRun: (runId) => request(`/runs/${runId}/resume`, { method: "POST" }),
  getRun: (runId) => request(`/runs/${runId}`),
  getRunSteps: (runId) => request(`/runs/${runId}/steps`),
  getRunFindings: (runId) => request(`/runs/${runId}/findings`),
  decideFinding: (findingId, decision, reason) =>
    request(`/findings/${findingId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, actor: "human", reason }),
    }),
  commitRun: (runId) => request(`/runs/${runId}/commit`, { method: "POST" }),
  getRunCost: (runId) => request(`/runs/${runId}/cost`),
  getDeliverable: (pileId) => request(`/piles/${pileId}/deliverable`),
};
