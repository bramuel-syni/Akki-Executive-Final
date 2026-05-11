/**
 * Website v7 — /methodology  (palette migration only, copy preserved).
 *
 * Exception to the 5-Layer pyramid: long-form, end-to-end reading, no
 * CTA, first-person plural voice. Restrained narrative in a 720px
 * column. Section breaks are 1px graphite-light lines.
 */
import React from "react";
import WebsiteShell from "../WebsiteShell";

export default function MethodologyPage() {
  return (
    <WebsiteShell
      title="Methodology — how Akki is built and the choices behind it"
      description="A first-person account of how the Akki workspace is built — the constraints we accepted, the inventions we made, and the trade-offs we did not."
      pathname="/methodology"
    >
      <article className="website-section website-section--narrow" data-testid="methodology-article">
        <p className="kicker">METHODOLOGY · FIRST-PERSON ACCOUNT</p>
        <h1 className="hero" style={{ fontSize: "clamp(34px, 4.5vw, 52px)" }}>
          How Akki is built, and the choices behind it.
        </h1>
        <span className="website-rule" />
        <p className="dek">
          A reading of the things we got right, the things we got wrong, and the ones
          we are still working through. Eight minutes. No diagrams.
        </p>

        <h2 className="section" style={{ marginTop: 56 }}>We did not start from “how do we add AI”.</h2>
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

        <span className="website-rule--full" />

        <h2 id="synisense" className="section" style={{ marginTop: 56 }}>Synisense came first.</h2>
        <p>
          Before we let any model touch a customer’s prompt, we built a three-layer
          anonymisation engine: a regex pass that catches the high-confidence
          patterns, a Presidio + spaCy pass that catches the proper nouns, and a
          small-model judge that closes the gaps. Then we wrote a separate
          architectural guard — the Privacy Wall — that field-projects every
          cross-board read and refuses queries that don’t constrain by tenant.
        </p>
        <p>
          The implication: a non-executive director who sits on five boards cannot
          accidentally cross from one to another even if they wanted to. The wall
          enforces this in code, not in policy.
        </p>

        <span className="website-rule--full" />

        <h2 id="solva" className="section" style={{ marginTop: 56 }}>We invented Solva because chat is not how senior people reason.</h2>
        <p>
          Solva is a four-mode reasoning surface — seek clarity, develop strategy,
          simulate hypothesis, see perspectives. Before any answer, it runs a frame
          audit and surfaces the audit gaps. If the grounding is thin, it refuses to
          speculate — and the refusal itself is an exportable artefact, watermarked
          and audit-tracked.
        </p>
        <p>
          We treat the frame audit and the refusal artefact as the most important
          things Solva does. Most products optimise for a confident-sounding answer.
          We optimise for a defensible one.
        </p>

        <span className="website-rule--full" />

        <h2 id="determinism" className="section" style={{ marginTop: 56 }}>The chat audit chain is hash-linked.</h2>
        <p>
          Every chat turn is appended to a hash-chained audit log
          (<code style={{ fontFamily: "var(--mono)", fontSize: 13, background: "rgba(122,46,46,0.06)", padding: "1px 6px" }}>
            row_hash = SHA256(prev_hash + canonical_payload)
          </code>),
          and the export bundles a Python verifier so auditors can prove the chain
          end-to-end without trusting our infrastructure. Genesis is fixed.
        </p>

        <span className="website-rule--full" />

        <h2 id="journal" className="section" style={{ marginTop: 56 }}>What we did not do.</h2>
        <p>
          We did not build customer-data fine-tuning. We did not build embeddings
          that persist across tenants. We did not build a marketplace of plugins.
          We did not build a public chat surface. Each of these was a design choice,
          not a missing feature.
        </p>
        <p>
          We are also conservative about model loyalty. The workspace routes calls to
          three providers — Claude, Gemini, GPT — with direct streaming where the
          keys are present and proxy fallback when they’re not. If a provider
          regresses, the work continues.
        </p>

        <span className="website-rule--full" />

        <h2 id="monitor" className="section" style={{ marginTop: 56 }}>The unresolved questions.</h2>
        <p>
          We do not yet have a clean answer for board observability across tenants
          that respects director privacy — the metadata layer is helpful but partial.
          We do not yet have a fully automated master-key rotation for the Privacy
          Wall envelope; today it is a planned-outage operation. These are the things
          we are working through with the founding cohort.
        </p>

        <p style={{ marginTop: 56, fontStyle: "italic", color: "var(--graphite)", fontSize: 14 }}>
          — The team
        </p>
      </article>
    </WebsiteShell>
  );
}
