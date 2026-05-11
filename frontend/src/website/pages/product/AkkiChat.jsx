import React from "react";
import { Link } from "react-router-dom";
import WebsiteShell from "../../WebsiteShell";
import EvidencePanel from "../../components/EvidencePanel";
import "../../style.css";

export default function ProductChatPage() {
  return (
    <WebsiteShell
      title="Akki Chat — trust-first multi-model chat"
      description="Three providers, real per-token streaming, hash-chained audit log with offline verifier."
      pathname="/product/akki-chat"
    >
      <section className="website-section website-section--narrow">
        <span className="website-label">Product · Akki Chat</span>
        <h1>The chat surface for people who will be audited.</h1>
        <span className="website-rule" />
        <p style={{ fontFamily: "Georgia, serif", fontStyle: "italic", fontSize: 18, color: "#2A3441" }}>
          Claude, Gemini, GPT. Every turn appended to a hash-chained audit log.
          Synisense Shield runs before any model sees a single character.
        </p>

        <h2 style={{ marginTop: 56 }}>Three commitments inside one surface.</h2>
        <div style={{ display: "grid", gap: 28, marginTop: 24 }}>
          <div><h3>Direct streaming.</h3><p>All three providers stream direct to the browser. No buffering, no proxy lag.</p></div>
          <div><h3>Hash-chained audit.</h3><p>Every turn is a row in an append-only chain. The export bundles a Python verifier so auditors validate without trusting us.</p></div>
          <div><h3>Two-pass discipline.</h3><p>Classifier → provider → four-check. The model says less, but says it more carefully. Hallucinated citations are dropped.</p></div>
        </div>

        <EvidencePanel kind="chat_audit" caption="Live audit metric strip from Akki Chat. Counts come from db.synisense_runs and update as redactions accumulate." />

        <p style={{ color: "#6B7480", fontSize: 14, marginTop: 24 }}>
          Read about the choices behind Akki Chat — <Link to="/methodology" className="website-link-inline">Methodology</Link>.
        </p>
        <div style={{ marginTop: 36 }}>
          <Link to="/sandbox" className="website-cta-primary">Try the sandbox</Link>
        </div>
      </section>
    </WebsiteShell>
  );
}
