/**
 * SharedArtefact — public read-only viewer for documents shared via
 * AKKI's "Share with the Chair" flow.
 *
 * Accessible without auth. Lands a non-AKKI director directly on the
 * document they were sent, instead of bouncing them to signin.
 *
 *  - Fetches /api/public/studio/read/{token} (which records the view)
 *  - Editorial cream/oxblood surface, no app chrome
 *  - Decks: render slides. Briefings: render opening + items.
 *  - Footer: "Your read has been recorded" + optional "Open in AKKI →"
 *    if the viewer is already authenticated (detected via /auth/me).
 */
import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import axios from "axios";
import Logo from "@/components/brand/Logo";
import { Button } from "@/components/ui/button";
import {
  ShieldCheck, Loader2, AlertTriangle, ArrowUpRight, Eye,
} from "lucide-react";

const BACKEND = process.env.REACT_APP_BACKEND_URL || "";

const SENS_TONE = {
  public:       "text-emerald-800 bg-emerald-50 border-emerald-200",
  internal:     "text-amber-900 bg-amber-50 border-amber-200",
  confidential: "text-orange-900 bg-orange-50 border-orange-200",
  restricted:   "text-red-900 bg-red-50 border-red-200",
};

export default function SharedArtefact() {
  const { token } = useParams();
  const [state, setState] = useState({ loading: true, data: null, error: null });
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    if (!token) return;
    let live = true;
    (async () => {
      try {
        const { data } = await axios.get(`${BACKEND}/api/public/studio/read/${token}`);
        if (live) setState({ loading: false, data, error: null });
      } catch (err) {
        if (!live) return;
        const status = err?.response?.status;
        const detail = err?.response?.data?.detail || "Couldn't load this document.";
        setState({
          loading: false,
          data: null,
          error: { status, detail },
        });
      }
    })();
    return () => { live = false; };
  }, [token]);

  // Best-effort: detect if the viewer is an authed AKKI user. If so,
  // we surface an "Open in AKKI" affordance so they can jump into the
  // full app surface.
  useEffect(() => {
    axios.get(`${BACKEND}/api/auth/me`, { withCredentials: true })
      .then(() => setAuthed(true))
      .catch(() => setAuthed(false));
  }, []);

  return (
    <div className="min-h-screen bg-[var(--cream)] text-[var(--ink)] relative overflow-hidden">
      {/* Phase 11 ITEM A — diagonal watermark. Fixed-position, pointer-
          events-none so it never intercepts clicks. Recipient email is
          baked in so screenshot-lift leaves the trail.  */}
      {state.data?.watermark && (
        <Watermark
          recipient={state.data.watermark.recipient}
          label={state.data.watermark.label}
          expiresAt={state.data.watermark.expires_at}
        />
      )}
      <header className="border-b border-[var(--rule)] relative z-10">
        <div className="max-w-[800px] mx-auto px-6 md:px-8 py-5 flex items-center justify-between">
          <Logo />
          <span className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--accent)] flex items-center gap-1.5">
            <ShieldCheck className="w-3 h-3" /> Shared with you · Synisense-shielded
          </span>
        </div>
      </header>

      <main className="max-w-[800px] mx-auto px-6 md:px-8 py-10 md:py-14 relative z-10" data-testid="shared-artefact-page">
        {state.loading && (
          <div className="flex items-center gap-2 text-[13px] text-[var(--muted)] italic" data-testid="shared-loading">
            <Loader2 className="w-4 h-4 animate-spin" /> Opening the document…
          </div>
        )}

        {state.error && (
          <ErrorPanel status={state.error.status} detail={state.error.detail} />
        )}

        {state.data && (
          <ArtefactBody data={state.data} authed={authed} />
        )}
      </main>
    </div>
  );
}

function Watermark({ recipient, label, expiresAt }) {
  // Diagonal repeating watermark. pointer-events:none so it never blocks
  // clicks on the underlying article; mix-blend so it reads on both cream
  // and white cards. Recipient email is in every tile so a screenshot
  // carries provenance.
  const tile = `${label || "AKKI · read-only"} · ${recipient || ""}`;
  const tiles = new Array(24).fill(0);
  return (
    <div
      className="pointer-events-none fixed inset-0 z-[5] select-none overflow-hidden"
      aria-hidden="true"
      data-testid="shared-watermark"
    >
      <div
        className="absolute inset-0 flex flex-wrap items-start gap-10"
        style={{
          transform: "rotate(-22deg) translateY(-8%) translateX(-8%)",
          width: "140%",
          opacity: 0.08,
        }}
      >
        {tiles.map((_, i) => (
          <span
            key={i}
            className="text-[13px] font-mono uppercase tracking-[0.22em] text-[var(--ink)] whitespace-nowrap"
          >
            {tile}
          </span>
        ))}
      </div>
      {expiresAt && (
        <span className="absolute bottom-3 right-4 text-[9.5px] font-mono uppercase tracking-[0.2em] text-[var(--muted)]/80">
          Link expires {new Date(expiresAt).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}
        </span>
      )}
    </div>
  );
}

function ErrorPanel({ status, detail }) {
  const title =
    status === 410 ? "This share link has expired." :
    status === 404 ? "The document is no longer available." :
    status === 400 ? "This share link isn't valid." :
                      "We couldn't open this share.";
  return (
    <section className="bg-white border border-[var(--rule)] rounded-sm p-8" data-testid="shared-error">
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-6 h-6 text-[var(--accent)] mt-1 shrink-0" />
        <div>
          <h1 className="akki-serif text-[22px] text-[var(--ink)] leading-tight mb-2">
            {title}
          </h1>
          <p className="text-[13.5px] text-[var(--deep)] leading-relaxed">
            {detail}
            {" "}
            If this was sent to you by mistake, please reply to the sender —
            they can mint a fresh link.
          </p>
        </div>
      </div>
    </section>
  );
}

function ArtefactBody({ data, authed }) {
  const tone = SENS_TONE[data.sensitivity?.classification] || SENS_TONE.internal;
  const created = data.created_at
    ? new Date(data.created_at).toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" })
    : null;

  return (
    <article data-testid="shared-artefact-body" className="relative z-10">
      <header className="mb-8">
        <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--accent)] mb-3">
          {data.shared_by_name ? `Shared by ${data.shared_by_name}` : "Shared with you"}
          {data.context_name ? ` · ${data.context_name}` : null}
        </p>
        <h1 className="akki-serif text-[32px] md:text-[38px] text-[var(--ink)] leading-[1.1] tracking-tight mb-3">
          {data.content?.title}
        </h1>
        {data.content?.subtitle && (
          <p className="text-[15px] text-[var(--deep)] leading-relaxed mb-4">
            {data.content.subtitle}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-2 mb-3">
          {data.sensitivity?.label && (
            <span
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-sm border text-[10px] uppercase tracking-[0.14em] ${tone}`}
              data-testid={`shared-sensitivity-${data.sensitivity.classification}`}
              title={(data.sensitivity.reasons || []).join(" · ") || "No specific signals"}
            >
              {data.sensitivity.label}
            </span>
          )}
          {created && (
            <span className="text-[11px] text-[var(--muted)] tabular-nums">
              Produced {created}
            </span>
          )}
          <span className="text-[11px] text-[var(--muted)] italic">
            {data.kind === "deck" ? "Deck" : "Briefing"} · read-only
          </span>
        </div>
        {data.share_message && (
          <blockquote className="mt-5 pl-4 border-l-2 border-[var(--accent)] italic text-[14.5px] text-[var(--deep)] max-w-[60ch]">
            “{data.share_message}”
            {data.shared_by_name && (
              <span className="block mt-1 not-italic text-[11px] uppercase tracking-[0.14em] text-[var(--muted)]">
                — {data.shared_by_name}
              </span>
            )}
          </blockquote>
        )}
        {data.content?.research_question && (
          <p className="text-[12.5px] text-[var(--muted)] italic mt-5">
            Research question: {data.content.research_question}
          </p>
        )}
      </header>

      {data.kind === "deck" && (
        <DeckContent slides={data.content?.slides || []} />
      )}
      {data.kind === "briefing" && (
        <BriefingContent
          opening={data.content?.opening_paragraph}
          items={data.content?.items || []}
        />
      )}

      <footer className="mt-12 pt-6 border-t border-[var(--rule)]" data-testid="shared-footer">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-[11.5px] text-[var(--muted)]">
            <Eye className="w-3.5 h-3.5" />
            Your read has been recorded and the exposure score on this document updated.
          </div>
          {authed && (
            <Link
              to={data.kind === "deck" ? `/app/decks/${data.artefact_id}` : "/app/prepare"}
              className="inline-flex items-center gap-1.5 text-[11.5px] uppercase tracking-[0.16em] text-[var(--accent)] hover:underline"
              data-testid="shared-open-in-akki"
            >
              Open in AKKI <ArrowUpRight className="w-3 h-3" />
            </Link>
          )}
          {!authed && (
            <Link
              to="/sandbox"
              className="text-[11.5px] uppercase tracking-[0.16em] text-[var(--accent)] hover:underline"
              data-testid="shared-try-akki"
            >
              Try AKKI in 60 seconds →
            </Link>
          )}
        </div>
      </footer>
    </article>
  );
}

function DeckContent({ slides }) {
  return (
    <section className="space-y-5" data-testid="shared-deck-slides">
      {slides.map((s, i) => (
        <div
          key={s.n || i}
          className="bg-white border border-[var(--rule)] rounded-sm p-6"
          data-testid={`shared-deck-slide-${s.n || i + 1}`}
        >
          <p className="text-[10px] uppercase tracking-[0.16em] text-[var(--muted)]">
            Slide {String(s.n || i + 1).padStart(2, "0")}
          </p>
          <h2 className="akki-serif text-[20px] text-[var(--ink)] mt-1 mb-3 leading-snug">
            {s.title}
          </h2>
          {s.body_md && (
            <div className="text-[14.5px] text-[var(--deep)] leading-relaxed whitespace-pre-wrap">
              {s.body_md}
            </div>
          )}
        </div>
      ))}
    </section>
  );
}

function BriefingContent({ opening, items }) {
  return (
    <section className="space-y-6" data-testid="shared-briefing-content">
      {opening && (
        <div className="bg-white border border-[var(--rule)] rounded-sm p-6">
          <p className="akki-serif text-[16.5px] text-[var(--ink)] leading-relaxed whitespace-pre-wrap">
            {opening}
          </p>
        </div>
      )}
      {items.map((it, i) => (
        <div
          key={i}
          className="bg-white border border-[var(--rule)] rounded-sm p-6"
          data-testid={`shared-briefing-item-${i + 1}`}
        >
          <h2 className="akki-serif text-[19px] text-[var(--ink)] leading-snug mb-3">
            {it.title}
          </h2>
          {it.body && (
            <p className="text-[14.5px] text-[var(--deep)] leading-relaxed whitespace-pre-wrap mb-3">
              {it.body}
            </p>
          )}
          {it.why_it_matters && (
            <div className="mt-3 pt-3 border-t border-[var(--rule)]">
              <p className="text-[10.5px] uppercase tracking-[0.16em] text-[var(--accent)] mb-1.5">
                Why it matters
              </p>
              <p className="text-[13.5px] text-[var(--deep)] leading-relaxed">
                {it.why_it_matters}
              </p>
            </div>
          )}
          {Array.isArray(it.questions_for_management) && it.questions_for_management.length > 0 && (
            <div className="mt-3 pt-3 border-t border-[var(--rule)]">
              <p className="text-[10.5px] uppercase tracking-[0.16em] text-[var(--muted)] mb-1.5">
                Questions for management
              </p>
              <ul className="text-[13.5px] text-[var(--deep)] leading-relaxed space-y-1 list-disc list-inside marker:text-[var(--accent)]">
                {it.questions_for_management.map((q, qi) => <li key={qi}>{q}</li>)}
              </ul>
            </div>
          )}
        </div>
      ))}
    </section>
  );
}
