const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(data?.detail || res.statusText || "Request failed");
  }
  return data;
}

export const api = {
  health: () => request("/health"),
  stats: () => request("/stats"),
  companies: (limit = 50) => request(`/companies?limit=${limit}`),
  company: (id) => request(`/companies/${id}`),
  runPipeline: (body) =>
    request("/pipeline", { method: "POST", body: JSON.stringify(body) }),
  research: (body) =>
    request("/companies/research", { method: "POST", body: JSON.stringify(body) }),
  memory: (q, limit = 20) =>
    request(`/memory?q=${encodeURIComponent(q)}&limit=${limit}`),
  followUps: (pendingOnly = false) =>
    request(`/follow-ups?pending_only=${pendingOnly}`),
  processFollowUps: () => request("/follow-ups/process", { method: "POST" }),
  proposals: () => request("/proposals"),
  harmis: (action) =>
    request("/harmis", { method: "POST", body: JSON.stringify({ action }) }),
  screenCV: (body) =>
    request("/cv/screen", { method: "POST", body: JSON.stringify(body) }),
  screenCVFile: (jobDescription, file) => {
    const form = new FormData();
    form.append("job_description", jobDescription);
    form.append("cv_file", file);
    return fetch(`${BASE}/cv/screen/file`, { method: "POST", body: form }).then(async (res) => {
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || res.statusText || "Upload failed");
      return data;
    });
  },
  createCode: (body) =>
    request("/code", { method: "POST", body: JSON.stringify(body) }),
};
