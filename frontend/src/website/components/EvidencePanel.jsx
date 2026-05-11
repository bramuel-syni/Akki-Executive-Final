import React from "react";

/**
 * Phase J.2 — 5-Layer Pyramid Evidence Panel (Layer 3).
 *
 * The Website Experience Architecture v1 is explicit: Layer 3 must
 * show a REAL artefact, not a mock. Where a real screenshot from the
 * running app isn't yet feasible (the Phase J.2 budget didn't allow
 * authenticated screen captures), we render "real-looking but
 * anonymised artefacts as HTML" — explicitly permitted by the spec.
 *
 * Every variant is editorial, monochrome, and grounded in the actual
 * data shapes the live product persists.
 */
export default function EvidencePanel({ kind, caption, testId }) {
  return (
    <figure style={{ margin: "32px 0", padding: 0 }} data-testid={testId || `evidence-${kind}`}>
      <div
        style={{
          background: "#FAFAF5",
          border: "1px solid #D8D2C5",
          padding: "24px 28px",
          fontFamily: "Calibri, 'Helvetica Neue', Arial, sans-serif",
          fontSize: 14,
          lineHeight: 1.5,
          color: "#0F1419",
        }}
      >
        {kind === "solva_trace" && <SolvaTrace />}
        {kind === "audit_log" && <AuditLog />}
        {kind === "pulse_card" && <PulseCard />}
        {kind === "board_pack" && <BoardPack />}
        {kind === "work_studio_diff" && <WorkStudioDiff />}
        {kind === "cycle_agenda" && <CycleAgenda />}
        {kind === "document_journal" && <DocumentJournal />}
        {kind === "chat_audit" && <ChatAudit />}
        {kind === "monitor_signals" && <MonitorSignals />}
      </div>
      {caption && (
        <figcaption
          style={{
            fontFamily: "Georgia, 'Times New Roman', serif",
            fontStyle: "italic",
            fontSize: 13,
            color: "#6B7480",
            marginTop: 10,
            maxWidth: "60ch",
          }}
        >
          {caption}
        </figcaption>
      )}
    </figure>
  );
}

const label = { fontSize: 11, letterSpacing: "0.15em", textTransform: "uppercase", color: "#6B7480", marginBottom: 6 };
const row = { display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid #EDE7D6" };
const mono = { fontFamily: "'JetBrains Mono', Menlo, monospace", fontSize: 12, color: "#2A3441" };

function SolvaTrace() {
  return (
    <div>
      <div style={label}>Solva · frame audit · trace excerpt</div>
      <p style={{ margin: 0, ...mono }}>solva.session.7c9a · mode=develop_strategy · t+04s</p>
      <p style={{ margin: "12px 0 4px", fontStyle: "italic", color: "#2A3441" }}>
        Reading the agenda. Holding back from an answer.
      </p>
      <p style={{ margin: 0 }}>
        The board pack frames this as a treasury question. The follow-ups thread suggests
        it is a covenant question. Before I draft, I need to test that frame: is the chair
        asking about liquidity, or about the lender relationship?
      </p>
      <p style={{ margin: "12px 0 0", ...mono, color: "#8B6F3E" }}>
        → audit_gap recorded: ambiguous frame · awaiting human resolution
      </p>
    </div>
  );
}

function AuditLog() {
  return (
    <div>
      <div style={label}>Chat audit · hash-chained · verifier ready</div>
      <div style={{ ...mono, marginTop: 4 }}>
        <div style={row}>
          <span>row.0042</span>
          <span>prev_hash a3f1…c2b9</span>
        </div>
        <div style={row}>
          <span>row.0043</span>
          <span>prev_hash 8d44…017e</span>
        </div>
        <div style={row}>
          <span>row.0044</span>
          <span>prev_hash f29c…b8a1</span>
        </div>
      </div>
      <p style={{ margin: "12px 0 0", fontSize: 12, color: "#6B7480" }}>
        Each row = SHA256(prev_hash + canonical(payload)). Genesis literal is fixed.
        Auditors verify the chain with one Python file.
      </p>
    </div>
  );
}

function PulseCard() {
  return (
    <div>
      <div style={label}>Pulse · signal card · type=regulatory</div>
      <p style={{ margin: "8px 0 4px", fontFamily: "Georgia, serif", fontSize: 17, fontWeight: 700 }}>
        Regulatory consultation enters final window.
      </p>
      <p style={{ margin: 0, color: "#2A3441" }}>
        Comment window closes in 3 days; two peer responses already filed.
      </p>
      <p style={{ margin: "12px 0 0", ...mono, color: "#6B7480" }}>
        confidence 0.82 · first seen 8h ago · same-context only · no LLM in feed render
      </p>
    </div>
  );
}

function BoardPack() {
  return (
    <div>
      <div style={label}>Work Studio · board pack section 3 · anonymised</div>
      <p style={{ margin: "6px 0 6px", fontFamily: "Georgia, serif", fontWeight: 700, fontSize: 16 }}>
        3.2 Regulatory — consultation reply (draft v3)
      </p>
      <p style={{ margin: 0, color: "#2A3441" }}>
        We propose to argue for a £5m disclosure threshold and a 30-day reporting window,
        in line with the trade body's submission filed last week.
      </p>
      <p style={{ margin: "12px 0 0", ...mono, color: "#6B7480" }}>
        sha256 a3f1d2…c2b9 · byte-deterministic · sensitivity: CONFIDENTIAL
      </p>
    </div>
  );
}

function WorkStudioDiff() {
  return (
    <div>
      <div style={label}>Work Studio · cross-document inconsistency</div>
      <p style={{ margin: "6px 0 4px", fontWeight: 700 }}>Draft v1 (consultation reply)</p>
      <p style={{ margin: 0, color: "#2A3441" }}>“£5m threshold, 30-day window.”</p>
      <p style={{ margin: "12px 0 4px", fontWeight: 700 }}>Board memo (proposed response)</p>
      <p style={{ margin: 0, color: "#2A3441" }}>“£10m threshold, 45-day window.”</p>
      <p style={{ margin: "12px 0 0", color: "#8B2E2E", ...mono }}>… flagged: numeric mismatch between two committed drafts</p>
    </div>
  );
}

function CycleAgenda() {
  return (
    <div>
      <div style={label}>Cycle Manager · agenda · Q3 board meeting</div>
      <ul style={{ margin: "6px 0 0", paddingLeft: 18, color: "#2A3441" }}>
        <li>Regulatory consultation — board sign-off (GC)</li>
        <li>Succession watch — chair's note (NomCo)</li>
        <li>Q3 results — going-concern statement (CFO)</li>
        <li>Cyber posture — peer incident review (CISO)</li>
      </ul>
      <p style={{ margin: "12px 0 0", ...mono, color: "#6B7480" }}>
        4 items · 3 follow-ups outstanding · inbound replies threaded under opaque cycle alias
      </p>
    </div>
  );
}

function DocumentJournal() {
  return (
    <div>
      <div style={label}>Document Journal · reading lane · anonymised</div>
      <p style={{ margin: "4px 0", fontFamily: "Georgia, serif" }}>“Q3 forecasts indicate compression of £18m…”</p>
      <p style={{ ...mono, color: "#6B7480", margin: "12px 0 0" }}>
        paragraph_anchor: p_07 · doc=board_pack_q3.pdf · sensitivity: CONFIDENTIAL
      </p>
      <p style={{ ...mono, color: "#8B6F3E", margin: 0 }}>
        + 1 commentary · + 2 highlights · chat back-reference · "ask Akki" deep-link
      </p>
    </div>
  );
}

function ChatAudit() {
  return (
    <div>
      <div style={label}>Akki Chat · audit metric strip · live</div>
      <div style={{ display: "flex", gap: 36, marginTop: 8 }}>
        <div>
          <div style={{ fontFamily: "Georgia, serif", color: "#8B6F3E", fontSize: 22 }}>12</div>
          <div style={label}>Identifiers redacted</div>
        </div>
        <div>
          <div style={{ fontFamily: "Georgia, serif", color: "#8B6F3E", fontSize: 22 }}>5</div>
          <div style={label}>Model calls</div>
        </div>
        <div>
          <div style={{ fontSize: 12, color: "#2A3441", marginTop: 4 }}>
            7 regex · 4 Presidio · 1 LLM-fallback
          </div>
          <div style={label}>Layers won</div>
        </div>
      </div>
      <p style={{ margin: "12px 0 0", fontStyle: "italic", color: "#2A3441" }}>
        “This conversation passed through three layers of redaction before any AI saw it.
        12 identifiers — names, emails, account numbers and similar — were masked
        deterministically across 5 model calls. Nothing left your tenant.”
      </p>
    </div>
  );
}

function MonitorSignals() {
  return (
    <div>
      <div style={label}>Monitor · goals-at-risk · role-scoped</div>
      <div style={{ display: "flex", gap: 48 }}>
        <div>
          <div style={{ fontFamily: "Georgia, serif", color: "#8B6F3E", fontSize: 28 }}>3</div>
          <div style={label}>High-confidence risks</div>
        </div>
        <div>
          <div style={{ fontFamily: "Georgia, serif", color: "#8B6F3E", fontSize: 28 }}>2</div>
          <div style={label}>Opportunities surfaced</div>
        </div>
      </div>
      <p style={{ margin: "12px 0 0", color: "#6B7480", fontSize: 12 }}>
        Per-role function whitelist active. Older risks beyond the 50-signal window
        accessible via search.
      </p>
    </div>
  );
}
