import React from "react";
import { Link } from "react-router-dom";
import WebsiteShell from "../WebsiteShell";
import EvidencePanel from "../components/EvidencePanel";
import "../style.css";

/**
 * Phase K (2026-05-12) — Audience page: For Exco.
 * Pattern C (audience). The visitor is a COO / CFO / CRO / senior
 * leadership-team member who prepares board material — distinct from
 * the executive who runs the cycle (/for-executives) and the NED who
 * sits on it (/for-non-executive-directors).
 */
export default function ForExcoPage() {
  return (
    <WebsiteShell
      title="For Exco — Akki for senior leadership preparing the board"
      description="How Akki fits the working day of the COO, CFO, CRO and senior leadership-team members preparing material for the board."
      pathname="/for-exco"
    >
      <section className="website-section website-section--narrow">
        <span className="website-label">For Exco</span>
        <h1>For the senior leadership team preparing what the board will read.</h1>
        <span className="website-rule" />
        <p style={{ fontFamily: "Georgia, serif", fontStyle: "italic", fontSize: 18, color: "#2A3441" }}>
          The CFO drafting the going-concern paragraph. The COO writing the
          operational risk note. The CRO turning four colour-coded heatmaps into
          two paragraphs of judgement.
        </p>

        <h2 style={{ marginTop: 56 }}>Three moments Exco recognises.</h2>
        <div style={{ display: "grid", gap: 28, marginTop: 24 }}>
          <div data-testid="for-exco-l2-pack">
            <h3>The board pack that lands together.</h3>
            <p>
              Each Exco member contributes a section. Akki holds the cross-document
              consistency — when the CFO's number doesn't match the COO's, the
              system surfaces it before the chair finds it.
            </p>
          </div>
          <div data-testid="for-exco-l2-papers">
            <h3>Papers that survive scrutiny.</h3>
            <p>
              Deterministic DOCX and PPTX renders, sensitivity-banded, validator-checked,
              hash-stamped. The paper you sent is provably the paper that left the
              system.
            </p>
          </div>
          <div data-testid="for-exco-l2-followups">
            <h3>The week after.</h3>
            <p>
              Cycle Manager threads the board's follow-ups back to the specific Exco
              member who owns each item. Outbound under opaque alias, inbound
              automatically routed to the right person.
            </p>
          </div>
        </div>

        <EvidencePanel
          kind="work_studio_diff"
          caption="A cross-document inconsistency Akki flagged before sign-off. Anonymised; the live flag persists with byte hashes and validator notes."
          testId="for-exco-evidence"
        />

        <p style={{ color: "#6B7480", fontSize: 14, marginTop: 24 }}>
          Read about the choices behind Akki — <Link to="/methodology" className="website-link-inline">Methodology</Link>.
        </p>
        <div style={{ marginTop: 36 }}>
          <Link to="/sandbox" className="website-cta-primary" data-testid="for-exco-cta">Try the sandbox</Link>
        </div>
      </section>
    </WebsiteShell>
  );
}
