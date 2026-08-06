import { useEffect, useState } from "react";
import { api } from "./api";
import "./App.css";

export default function App() {
  const [pile, setPile] = useState(null);
  const [pileName, setPileName] = useState("Vendor Contracts");
  const [documents, setDocuments] = useState([]);
  const [selectedDocIds, setSelectedDocIds] = useState([]);
  const [ruleText, setRuleText] = useState("");
  const [rules, setRules] = useState([]);
  const [run, setRun] = useState(null);
  const [steps, setSteps] = useState([]);
  const [findings, setFindings] = useState([]);
  const [cost, setCost] = useState(null);
  const [deliverable, setDeliverable] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function refreshRunState(runId) {
    const [r, s, f, c] = await Promise.all([
      api.getRun(runId),
      api.getRunSteps(runId),
      api.getRunFindings(runId),
      api.getRunCost(runId),
    ]);
    setRun(r);
    setSteps(s);
    setFindings(f);
    setCost(c);
  }

  async function withBusy(fn) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const handleCreatePile = () =>
    withBusy(async () => {
      const p = await api.createPile(pileName, "contract");
      setPile(p);
      setDocuments([]);
      setRules([]);
      setRun(null);
      setSteps([]);
      setFindings([]);
      setCost(null);
      setDeliverable(null);
    });

  const handleAddRule = () =>
    withBusy(async () => {
      if (!ruleText.trim()) return;
      await api.addRule(pile.id, ruleText.trim());
      setRuleText("");
      setRules(await api.listRules(pile.id));
    });

  const handleUpload = (e) =>
    withBusy(async () => {
      const file = e.target.files[0];
      if (!file) return;
      await api.uploadDocument(pile.id, file);
      setDocuments(await api.listPileDocuments(pile.id));
    });

  const toggleDoc = (id) =>
    setSelectedDocIds((prev) => (prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]));

  const handleStartRun = () =>
    withBusy(async () => {
      const r = await api.startRun(pile.id, selectedDocIds);
      await refreshRunState(r.id);
    });

  const handleResume = () => withBusy(() => api.resumeRun(run.id).then(() => refreshRunState(run.id)));

  const handleDecide = (findingId, decision) =>
    withBusy(async () => {
      const reason = decision === "reject" ? window.prompt("Reason for rejecting? (optional)") || null : null;
      await api.decideFinding(findingId, decision, reason);
      setFindings(await api.getRunFindings(run.id));
    });

  const handleCommit = () =>
    withBusy(async () => {
      await api.commitRun(run.id);
      await refreshRunState(run.id);
      setDeliverable(await api.getDeliverable(pile.id));
    });

  useEffect(() => {
    if (pile) {
      api.listPileDocuments(pile.id).then(setDocuments);
      api.listRules(pile.id).then(setRules);
    }
  }, [pile]);

  return (
    <div className="app">
      <header>
        <h1>DocPile Agent — Review Console</h1>
        <p className="subtitle">
          SuperDocs Round 2 · Task 1 · human-gated agentic system over a document pile
        </p>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <section className="card">
        <h2>1. Pile</h2>
        {!pile ? (
          <div className="row">
            <input value={pileName} onChange={(e) => setPileName(e.target.value)} placeholder="Pile name" />
            <button disabled={busy} onClick={handleCreatePile}>Create pile</button>
          </div>
        ) : (
          <div className="row">
            <span>
              <strong>{pile.name}</strong> · version {pile.version} · id <code>{pile.id.slice(0, 8)}</code>
            </span>
            <button disabled={busy} onClick={() => setPile(null)}>Switch pile</button>
          </div>
        )}
      </section>

      {pile && (
        <>
          <section className="card">
            <h2>2. Rules (optional)</h2>
            <div className="row">
              <input
                style={{ flex: 1 }}
                value={ruleText}
                onChange={(e) => setRuleText(e.target.value)}
                placeholder="e.g. payment terms must not exceed 30 days"
              />
              <button disabled={busy} onClick={handleAddRule}>Add rule</button>
            </div>
            <ul>
              {rules.map((r) => <li key={r.id}>{r.text}</li>)}
            </ul>
          </section>

          <section className="card">
            <h2>3. Documents</h2>
            <input type="file" onChange={handleUpload} disabled={busy} />
            <ul className="doc-list">
              {documents.map((d) => (
                <li key={d.id}>
                  <label>
                    <input
                      type="checkbox"
                      checked={selectedDocIds.includes(d.id)}
                      onChange={() => toggleDoc(d.id)}
                    />
                    {d.filename} <span className={`status status-${d.status}`}>{d.status}</span>
                  </label>
                </li>
              ))}
            </ul>
            <button disabled={busy || selectedDocIds.length === 0} onClick={handleStartRun}>
              Start run with {selectedDocIds.length} document(s)
            </button>
          </section>
        </>
      )}

      {run && (
        <section className="card">
          <h2>4. Run {run.id.slice(0, 8)}</h2>
          <p>
            Status: <strong className={`status status-${run.status}`}>{run.status}</strong>
            {run.error && <span className="error-inline"> — {run.error}</span>}
          </p>
          {run.status === "running" && (
            <button disabled={busy} onClick={handleResume}>Resume (simulate restart after crash)</button>
          )}

          <h3>Stages</h3>
          <ol className="steps">
            {steps.map((s) => (
              <li key={s.id} className={`step step-${s.status}`}>
                <strong>{s.stage_name}</strong> — {s.status}
                {s.decision && <em> (decision: {s.decision})</em>}
              </li>
            ))}
          </ol>

          <h3>Findings — the human gate</h3>
          {findings.length === 0 && <p>No findings yet.</p>}
          <ul className="findings">
            {findings.map((f) => (
              <li key={f.id} className={`finding finding-${f.kind}`}>
                <div className="finding-head">
                  <span className="kind">{f.kind}</span>
                  <span className={`status status-${f.status}`}>{f.status}</span>
                </div>
                <p>{f.description}</p>
                {f.proposed_resolution && <p className="proposal">Proposed: {f.proposed_resolution}</p>}
                {f.status === "pending" && (
                  <div className="row">
                    <button disabled={busy} onClick={() => handleDecide(f.id, "approve")}>Approve</button>
                    <button disabled={busy} onClick={() => handleDecide(f.id, "reject")}>Reject</button>
                  </div>
                )}
                {f.decision_reason && <p className="reason">Reason: {f.decision_reason}</p>}
              </li>
            ))}
          </ul>

          {run.status === "awaiting_gate" && (
            <button disabled={busy} onClick={handleCommit} className="commit-btn">
              Commit deliverable
            </button>
          )}

          {cost && (
            <>
              <h3>Cost</h3>
              <table className="cost-table">
                <thead>
                  <tr><th>Stage</th><th>Calls</th><th>Tokens in</th><th>Tokens out</th><th>USD</th><th>ms</th></tr>
                </thead>
                <tbody>
                  {cost.by_stage.map((r) => (
                    <tr key={r.stage}>
                      <td>{r.stage}</td><td>{r.call_count}</td><td>{r.tokens_in}</td>
                      <td>{r.tokens_out}</td><td>${r.usd_cost.toFixed(4)}</td><td>{r.duration_ms}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p>Total: {cost.total_tokens} tokens · ${cost.total_usd_cost.toFixed(4)} · {cost.total_duration_ms}ms</p>
            </>
          )}
        </section>
      )}

      {deliverable && (
        <section className="card">
          <h2>5. Committed deliverable — version {deliverable.version_number}</h2>
          <p>Changed sections: {deliverable.changed_sections.map((c) => c.section).join(", ") || "none"}</p>
          <p>Carried over untouched: {deliverable.carried_over_sections.map((c) => c.section).join(", ") || "none"}</p>
          <pre className="deliverable-json">{JSON.stringify(deliverable.content, null, 2)}</pre>
        </section>
      )}
    </div>
  );
}
