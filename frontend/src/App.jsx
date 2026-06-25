import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import "./App.css";

const TABS = [
  { id: "dashboard", label: "Dashboard" },
  { id: "pipeline", label: "Run Pipeline" },
  { id: "companies", label: "Companies" },
  { id: "followups", label: "Follow-ups" },
  { id: "memory", label: "Memory" },
];

function StatCard({ label, value }) {
  return (
    <div className="stat-card">
      <div className="value">{value ?? "—"}</div>
      <div className="label">{label}</div>
    </div>
  );
}

function Alert({ type, message, onClose }) {
  if (!message) return null;
  return (
    <div className={`alert alert-${type}`}>
      {message}
      {onClose && (
        <button
          type="button"
          onClick={onClose}
          style={{ float: "right", background: "none", padding: 0, color: "inherit" }}
        >
          ×
        </button>
      )}
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState("dashboard");
  const [stats, setStats] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [followUps, setFollowUps] = useState([]);
  const [memories, setMemories] = useState([]);
  const [loading, setLoading] = useState(false);
  const [alert, setAlert] = useState(null);

  const [pipelineForm, setPipelineForm] = useState({
    company_name: "",
    domain: "",
    industry: "",
    schedule_follow_up: true,
  });
  const [pipelineResult, setPipelineResult] = useState(null);
  const [memoryQuery, setMemoryQuery] = useState("");
  const [harmisAction, setHarmisAction] = useState("");
  const [harmisReply, setHarmisReply] = useState(null);
  const [gptEnabled, setGptEnabled] = useState(null);

  const showError = (e) => setAlert({ type: "error", message: e.message });
  const showSuccess = (msg) => setAlert({ type: "success", message: msg });

  const refreshStats = useCallback(async () => {
    try {
      setStats(await api.stats());
    } catch (e) {
      showError(e);
    }
  }, []);

  const refreshCompanies = useCallback(async () => {
    try {
      setCompanies(await api.companies());
    } catch (e) {
      showError(e);
    }
  }, []);

  const refreshFollowUps = useCallback(async () => {
    try {
      setFollowUps(await api.followUps());
    } catch (e) {
      showError(e);
    }
  }, []);

  const loadDetail = useCallback(async (id) => {
    setSelectedId(id);
    setLoading(true);
    try {
      setDetail(await api.company(id));
    } catch (e) {
      showError(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshStats();
    refreshCompanies();
    refreshFollowUps();
    api.health().then((h) => setGptEnabled(h.gpt_enabled)).catch(() => setGptEnabled(false));
  }, [refreshStats, refreshCompanies, refreshFollowUps]);

  const runPipeline = async (e) => {
    e.preventDefault();
    setLoading(true);
    setPipelineResult(null);
    try {
      const body = {
        ...pipelineForm,
        domain: pipelineForm.domain || null,
        industry: pipelineForm.industry || null,
      };
      const result = await api.runPipeline(body);
      setPipelineResult(result);
      showSuccess(`Pipeline completed for ${result.company.name}`);
      refreshStats();
      refreshCompanies();
      refreshFollowUps();
    } catch (e) {
      showError(e);
    } finally {
      setLoading(false);
    }
  };

  const searchMemory = async (e) => {
    e.preventDefault();
    if (!memoryQuery.trim()) return;
    setLoading(true);
    try {
      setMemories(await api.memory(memoryQuery));
    } catch (e) {
      showError(e);
    } finally {
      setLoading(false);
    }
  };

  const processFollowUps = async () => {
    setLoading(true);
    try {
      const processed = await api.processFollowUps();
      showSuccess(`Processed ${processed.length} follow-up(s)`);
      refreshFollowUps();
      refreshStats();
    } catch (e) {
      showError(e);
    } finally {
      setLoading(false);
    }
  };

  const askHarmis = async (e) => {
    e.preventDefault();
    if (!harmisAction.trim()) return;
    try {
      const res = await api.harmis(harmisAction);
      setHarmisReply(res.response);
    } catch (e) {
      showError(e);
    }
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="logo">
          Hermes <span>BD</span>
        </div>
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`nav-btn ${tab === t.id ? "active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </aside>

      <main className="main">
        <Alert
          type={alert?.type}
          message={alert?.message}
          onClose={() => setAlert(null)}
        />

        {tab === "dashboard" && (
          <>
            <header className="header">
              <h1>Dashboard</h1>
              <p>Autonomous Business Development Agent overview</p>
            </header>
            <div className="stats-grid">
              <StatCard label="Companies" value={stats?.companies} />
              <StatCard label="Contacts" value={stats?.contacts} />
              <StatCard label="Proposals" value={stats?.proposals} />
              <StatCard label="Follow-ups" value={stats?.follow_ups} />
              <StatCard label="Pending" value={stats?.pending_follow_ups} />
            </div>
            <div className="card">
              <h2>Quick actions</h2>
              <div className="actions">
                <button type="button" className="btn-primary" onClick={() => setTab("pipeline")}>
                  Run BD Pipeline
                </button>
                <button type="button" className="btn-secondary" onClick={processFollowUps} disabled={loading}>
                  Process Due Follow-ups
                </button>
                <button type="button" className="btn-secondary" onClick={() => { refreshStats(); refreshCompanies(); }}>
                  Refresh
                </button>
              </div>
            </div>
            <div className="card">
              <h2>Harmis</h2>
              <form onSubmit={askHarmis}>
                <div className="form-group">
                  <label>Action</label>
                  <input
                    value={harmisAction}
                    onChange={(e) => setHarmisAction(e.target.value)}
                    placeholder="e.g. is closing deals"
                  />
                </div>
                <button type="submit" className="btn-secondary">Ask Harmis</button>
              </form>
              {harmisReply && <p className="harmis-box" style={{ marginTop: "1rem" }}>{harmisReply}</p>}
            </div>
          </>
        )}

        {tab === "pipeline" && (
          <>
            <header className="header">
              <h1>Run Pipeline</h1>
              <p>Research → Discovery → Proposal → CRM → Follow-up</p>
              {gptEnabled === false && (
                <p className="alert alert-error" style={{ marginTop: "0.75rem" }}>
                  GPT is off — results will be generic templates. Set OPENAI_API_KEY in .env and restart the API.
                </p>
              )}
              {gptEnabled === true && (
                <p className="alert alert-info" style={{ marginTop: "0.75rem" }}>
                  GPT is on — pipeline takes about 15–30 seconds.
                </p>
              )}
            </header>
            <div className="card">
              <form onSubmit={runPipeline}>
                <div className="form-row">
                  <div className="form-group">
                    <label>Company name *</label>
                    <input
                      required
                      value={pipelineForm.company_name}
                      onChange={(e) => setPipelineForm({ ...pipelineForm, company_name: e.target.value })}
                      placeholder="PST AG (not a URL)"
                    />
                  </div>
                  <div className="form-group">
                    <label>Domain</label>
                    <input
                      value={pipelineForm.domain}
                      onChange={(e) => setPipelineForm({ ...pipelineForm, domain: e.target.value })}
                      placeholder="pst.ag"
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label>Industry</label>
                  <input
                    value={pipelineForm.industry}
                    onChange={(e) => setPipelineForm({ ...pipelineForm, industry: e.target.value })}
                    placeholder="Fintech, SaaS, Healthcare..."
                  />
                </div>
                <div className="checkbox-row">
                  <input
                    type="checkbox"
                    id="followup"
                    checked={pipelineForm.schedule_follow_up}
                    onChange={(e) => setPipelineForm({ ...pipelineForm, schedule_follow_up: e.target.checked })}
                  />
                  <label htmlFor="followup" style={{ margin: 0, textTransform: "none" }}>
                    Schedule follow-up
                  </label>
                </div>
                <button type="submit" className="btn-primary" disabled={loading}>
                  {loading ? "Running GPT agents (15–30s)…" : "Run full pipeline"}
                </button>
              </form>
            </div>
            {pipelineResult && (
              <div className="card">
                <h2>Result — {pipelineResult.company.name}</h2>
                <div className="steps">
                  {pipelineResult.steps?.map((s) => (
                    <span key={s.agent} className="step-pill">{s.agent}: {s.status}</span>
                  ))}
                </div>
                <p style={{ marginTop: "1rem", fontWeight: 600 }}>{pipelineResult.proposal?.subject}</p>
                <pre className="proposal-body">{pipelineResult.proposal?.body}</pre>
                <p style={{ marginTop: "0.75rem", color: "var(--muted)", fontSize: "0.85rem" }}>
                  {pipelineResult.contacts?.length} contacts · Follow-up:{" "}
                  {pipelineResult.follow_up
                    ? new Date(pipelineResult.follow_up.scheduled_at).toLocaleString()
                    : "none"}
                </p>
              </div>
            )}
          </>
        )}

        {tab === "companies" && (
          <>
            <header className="header">
              <h1>Companies</h1>
              <p>CRM records from PostgreSQL</p>
            </header>
            <div className="detail-grid">
              <div className="card">
                <h2>All companies ({companies.length})</h2>
                <div className="company-list">
                  {companies.length === 0 && <p className="empty">No companies yet. Run a pipeline.</p>}
                  {companies.map((c) => (
                    <div
                      key={c.id}
                      className={`company-item ${selectedId === c.id ? "selected" : ""}`}
                      onClick={() => loadDetail(c.id)}
                      onKeyDown={(e) => e.key === "Enter" && loadDetail(c.id)}
                      role="button"
                      tabIndex={0}
                    >
                      <div>
                        <div className="name">{c.name}</div>
                        <div className="meta">{c.industry || "—"} · {c.domain || "no domain"}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="card">
                <h2>Details</h2>
                {loading && <p className="loading">Loading…</p>}
                {!loading && !detail && <p className="empty">Select a company</p>}
                {!loading && detail && (
                  <>
                    <p><strong>{detail.company.name}</strong></p>
                    <p style={{ color: "var(--muted)", fontSize: "0.9rem", margin: "0.5rem 0 1rem" }}>
                      {detail.company.description}
                    </p>
                    {detail.company.pain_points?.length > 0 && (
                      <p style={{ fontSize: "0.85rem", marginBottom: "1rem" }}>
                        Pain points: {detail.company.pain_points.join(", ")}
                      </p>
                    )}
                    <h3 style={{ fontSize: "0.85rem", color: "var(--muted)", marginBottom: "0.5rem" }}>CONTACTS</h3>
                    {detail.contacts.map((c) => (
                      <div key={c.id} className="contact-row">
                        <strong>{c.name}</strong> — {c.title}
                        {c.decision_maker && <span className="badge badge-dm" style={{ marginLeft: "0.5rem" }}>DM</span>}
                        <div style={{ fontSize: "0.8rem", color: "var(--muted)" }}>{c.email}</div>
                      </div>
                    ))}
                    {detail.proposals?.[0] && (
                      <>
                        <h3 style={{ fontSize: "0.85rem", color: "var(--muted)", margin: "1rem 0 0.5rem" }}>PROPOSAL</h3>
                        <p style={{ fontWeight: 600, fontSize: "0.9rem" }}>{detail.proposals[0].subject}</p>
                        <pre className="proposal-body">{detail.proposals[0].body}</pre>
                      </>
                    )}
                  </>
                )}
              </div>
            </div>
          </>
        )}

        {tab === "followups" && (
          <>
            <header className="header">
              <h1>Follow-ups</h1>
              <p>Scheduled outreach automation</p>
            </header>
            <div className="actions" style={{ marginBottom: "1rem" }}>
              <button type="button" className="btn-primary" onClick={processFollowUps} disabled={loading}>
                Process due follow-ups
              </button>
              <button type="button" className="btn-secondary" onClick={refreshFollowUps}>Refresh</button>
            </div>
            <div className="card">
              {followUps.length === 0 && <p className="empty">No follow-ups scheduled</p>}
              {followUps.map((f) => (
                <div key={f.id} className="follow-row">
                  <span className={`badge badge-${f.status === "pending" ? "pending" : "sent"}`}>{f.status}</span>
                  <span style={{ marginLeft: "0.5rem", fontSize: "0.85rem", color: "var(--muted)" }}>
                    {new Date(f.scheduled_at).toLocaleString()} · {f.channel}
                  </span>
                  <pre className="proposal-body" style={{ marginTop: "0.5rem" }}>{f.message}</pre>
                </div>
              ))}
            </div>
          </>
        )}

        {tab === "memory" && (
          <>
            <header className="header">
              <h1>Long-term Memory</h1>
              <p>Search agent memories (PostgreSQL full-text)</p>
            </header>
            <div className="card">
              <form onSubmit={searchMemory}>
                <div className="form-group">
                  <label>Search query</label>
                  <input
                    value={memoryQuery}
                    onChange={(e) => setMemoryQuery(e.target.value)}
                    placeholder="Stripe, fintech, proposal..."
                  />
                </div>
                <button type="submit" className="btn-primary" disabled={loading}>Search</button>
              </form>
            </div>
            <div className="card">
              {memories.length === 0 && <p className="empty">No results. Try a search.</p>}
              {memories.map((m) => (
                <div key={m.id} className="memory-item">
                  <div className="type">{m.entity_type}</div>
                  <div>{m.content}</div>
                  {m.created_at && (
                    <div style={{ fontSize: "0.75rem", color: "var(--muted)", marginTop: "0.25rem" }}>
                      {new Date(m.created_at).toLocaleString()}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
