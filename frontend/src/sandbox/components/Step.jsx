import React from "react";
import { Link } from "react-router-dom";

/**
 * SandboxStep — renders one of four 90-second moments. Step ORDER is
 * reordered by Q6 emphasis per Brief v6 §2:
 *   - Q6 emphasises "Structured thinking"     → Solva first
 *   - Q6 emphasises "Cross-cutting insight"   → Pulse first
 *   - Q6 emphasises "Document drafted"        → Work Studio first
 *   - Q6 emphasises "Visibility across cycle" → Cycle first
 *   - Default                                 → Solva first
 */
const CAPABILITIES = {
  solva:        { label: "Solva",         reveal: "That is Solva — reasoning with the work, not on top of it." },
  pulse:        { label: "Pulse",         reveal: "That is Pulse — quiet attention, never an alarm." },
  work_studio:  { label: "Work Studio",   reveal: "That is Work Studio — it finds the inconsistency you would have missed." },
  cycle:        { label: "Cycle Manager", reveal: "That is Cycle Manager — the work has somewhere to land." },
};

function stepOrderForEmphasis(emphasis) {
  const order = ["solva", "pulse", "work_studio", "cycle"];
  const first = emphasis && emphasis[0];
  if (first === "Cross-cutting insight") return ["pulse", "solva", "work_studio", "cycle"];
  if (first === "Document drafted")     return ["work_studio", "solva", "pulse", "cycle"];
  if (first === "Visibility across cycle") return ["cycle", "solva", "pulse", "work_studio"];
  return order;
}

function ConversionRow() {
  return (
    <div className="sb-conversion" data-testid="sandbox-conversion-row">
      <span>This is Akki, working for you on a sample tenant.</span>
      <Link to="/cohort">Request early access</Link>
      <Link to="/contact">Talk to the team</Link>
    </div>
  );
}

export default function SandboxStep({ session, stepIndex, onNext }) {
  const art = session.artefacts || {};
  const emphasis = ((art.visitor_profile || {}).emphasis) || [];
  const order = stepOrderForEmphasis(emphasis);
  const capKey = order[stepIndex] || order[0];
  const cap = CAPABILITIES[capKey];

  let body = null;
  if (capKey === "solva") {
    body = (
      <div>
        <h2>{art.solva_opening_question || "What is the cleanest narrative for the board?"}</h2>
        <p style={{ color: "var(--sb-muted)" }}>Materials Akki pulled for this question:</p>
        {(art.solva_session_materials || []).map((m, i) => (
          <div key={i} className="sb-tile" data-testid={`sandbox-step-solva-material-${i}`}>
            <div className="sb-tile-meta">{m.kind || "material"}</div>
            <h3>{m.title}</h3>
            <p className="sb-tile-body">{m.body}</p>
          </div>
        ))}
      </div>
    );
  } else if (capKey === "pulse") {
    body = (
      <div>
        <h2>What is worth attention right now.</h2>
        <p style={{ color: "var(--sb-muted)" }}>Three signals Akki is watching for the {((art.visitor_profile || {}).role || "executive").toLowerCase()}.</p>
        {(art.pulse_signals || []).map((s, i) => (
          <div key={i} className="sb-tile" data-testid={`sandbox-step-pulse-signal-${i}`}>
            <div className="sb-tile-meta">{s.type || "signal"} · confidence {Math.round((s.confidence || 0) * 100)}%</div>
            <h3>{s.headline}</h3>
            <p className="sb-tile-body">{s.snippet}</p>
          </div>
        ))}
      </div>
    );
  } else if (capKey === "work_studio") {
    body = (
      <div>
        <h2>Two drafts. One inconsistency.</h2>
        <p style={{ color: "var(--sb-muted)" }}>Akki found a number that doesn't match between these documents.</p>
        {(art.work_studio_source || []).map((d, i) => (
          <div key={i} className="sb-tile" data-testid={`sandbox-step-ws-doc-${i}`}>
            <div className="sb-tile-meta">
              {d.has_inconsistency ? <span style={{ color: "var(--sb-severity)" }}>flagged</span> : "reference"}
            </div>
            <h3>{d.title}</h3>
            <p className="sb-tile-body">{d.body}</p>
          </div>
        ))}
      </div>
    );
  } else if (capKey === "cycle") {
    body = (
      <div>
        <h2>How this lands in the cycle.</h2>
        <p style={{ color: "var(--sb-muted)" }}>Akki places the conversation into the reporting cycle.</p>
        <h3 style={{ marginTop: 24 }}>Agenda</h3>
        <ul style={{ paddingLeft: 20, color: "var(--sb-slate)" }}>
          {((art.cycle_manager_view || {}).agenda_items || []).map((a, i) => (
            <li key={i} style={{ marginBottom: 6 }} data-testid={`sandbox-step-cycle-agenda-${i}`}>{a}</li>
          ))}
        </ul>
        <h3 style={{ marginTop: 24 }}>Follow-ups</h3>
        <ul style={{ paddingLeft: 20, color: "var(--sb-slate)" }}>
          {((art.cycle_manager_view || {}).follow_ups || []).map((f, i) => (
            <li key={i} style={{ marginBottom: 6 }} data-testid={`sandbox-step-cycle-followup-${i}`}>{f}</li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <div className="sb-shell sb-shell--wide" data-testid={`sandbox-step-${stepIndex}`}>
      <span className="sb-label">{stepIndex + 1} of 4 · {cap.label}</span>
      <span className="sb-rule" />
      {body}
      <p className="sb-step-reveal" data-testid={`sandbox-step-${stepIndex}-reveal`}>
        {cap.reveal}
      </p>
      {stepIndex >= 1 && <ConversionRow />}
      <div style={{ marginTop: 32, textAlign: "right" }}>
        <button type="button" className="sb-cta-primary" onClick={onNext}
          data-testid={`sandbox-step-${stepIndex}-next`}>
          {stepIndex === 3 ? "See the close" : "Continue"}
        </button>
      </div>
    </div>
  );
}
