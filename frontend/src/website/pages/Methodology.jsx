import React from "react";
import WebsiteShell from "../WebsiteShell";
import "../style.css";

/**
 * Phase J.2 — Methodology page (Pattern D).
 *
 * Exception to the 5-Layer pyramid: long-form, end-to-end reading,
 * NO CTA, first-person plural voice. The audience is a senior reader
 * willing to spend 8–12 minutes. No screenshots, no diagrams.
 * Restrained Calibri body in a single 720px column. Section breaks
 * are 1px --rule lines, never boxes.
 */
export default function MethodologyPage() {
  return (
    <WebsiteShell
      title="Methodology — how Akki is built and the choices behind it"
      description="A first-person account of how the Akki platform is built — the constraints we accepted, the inventions we made, and the trade-offs we did not."
      pathname="/methodology"
    >
      <article className="website-section website-section--narrow" data-testid="methodology-article">
        <span className="website-label">Methodology · First-person account</span>
        <h1 style={{ fontSize: 44 }}>How Akki is built, and the choices behind it.</h1>
        <span className="website-rule" />
        <p style={{ fontFamily: "Georgia, 'Times New Roman', serif", fontStyle: "italic", fontSize: 18, color: "#2A3441" }}>
          A reading of the things we got right, the things we got wrong, and the ones
          we are still working through. Eight minutes. No diagrams.
        </p>

        <h2 style={{ marginTop: 56 }}>We did not start from “how do we add AI”.</h2>
        <p>
          We started from the question senior people actually ask: “why can’t I think
          with this thing the way I think with a smart colleague?” That question turns
          out to be a privacy question, an audit question, and a workflow question —
          three at once. We refused to answer it as a chat product.
        </p>
        <p>
          A chat product treats the conversation as the unit of work. For an executive
          or a non-executive director, the unit of work is the decision: a paper to
          sign off, a follow-up to send, a board cycle to close. The chat is the
          residue. Useful, but residue.
        </p>

        <hr className="website-section-divider" />

        <h2>The Privacy Wall came first.</h2>
        <p>
          Before we let any model touch a customer’s prompt, we built a three-layer
          de-identification engine: a regex pass that catches the high-confidence
          patterns, a Presidio + spaCy pass that catches the proper nouns, and an
          LLM-fallback judge that closes the gaps. Then we wrote a separate
          architectural guard — the Privacy Wall — that field-projects every
          cross-board read and refuses queries that don’t constrain by tenant.
        </p>
        <p>
          The implication: a non-executive director who sits on five boards cannot
          accidentally leak from one to another even if they wanted to. The wall
          enforces this in code, not in policy.
        </p>

        <hr className="website-section-divider" />

        <h2>We invented Solva because chat is not how senior people reason.</h2>
        <p>
          Solva is a four-mode reasoning surface — seek clarity, develop strategy,
          simulate hypothesis, get perspective. Before any answer, it runs a frame
          audit and surfaces the audit gaps. If the grounding is thin, it refuses to
          speculate — and the refusal itself is an exportable artefact, watermarked
          and audit-tracked.
        </p>
        <p>
          We treat the frame audit and the refusal artefact as the most important
          things Solva does. Most products optimise for a confident-sounding answer.
          We optimise for a defensible one.
        </p>

        <hr className="website-section-divider" />

        <h2>The chat audit chain is hash-linked.</h2>
        <p>
          Every chat turn is appended to a hash-chained audit log
          (<code style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13 }}>row_hash = SHA256(prev_hash + canonical_payload)</code>),
          and the export bundles a Python verifier so auditors can prove the chain
          end-to-end without trusting our infrastructure. Genesis is fixed.
        </p>

        <hr className="website-section-divider" />

        <h2>What we did not do.</h2>
        <p>
          We did not build customer-data fine-tuning. We did not build embeddings
          that persist across tenants. We did not build a marketplace of plugins.
          We did not build a public chat surface. Each of these was a design choice,
          not a missing feature.
        </p>
        <p>
          We are also conservative about model loyalty. The platform routes calls to
          three providers — Claude, Gemini, GPT — with direct streaming where the
          keys are present and proxy fallback when they’re not. If a provider
          regresses, the work continues.
        </p>

        <hr className="website-section-divider" />

        <h2>The unresolved questions.</h2>
        <p>
          We do not yet have a clean answer for board observability across tenants
          that respects director privacy — the metadata layer is helpful but partial.
          We do not yet have a fully automated master-key rotation for the Privacy
          Wall envelope; today it is a planned-outage operation. These are the things
          we are working through with the founding cohort.
        </p>

        <p style={{ marginTop: 56, fontStyle: "italic", color: "#6B7480", fontSize: 14 }}>
          — The team
        </p>
      </article>
    </WebsiteShell>
  );
}
