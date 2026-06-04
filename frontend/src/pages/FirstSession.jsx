/*
 * First Session — Advisory 5 / Phase 4.
 *
 * Replaces the legacy 7-question Onboarding. State machine lives on the
 * backend (`db.accounts.first_session`); this component hydrates from
 * `GET /api/me/first-session` and drives through 4 steps:
 *
 *   intake  — 3 questions (role, primary_context_name, top_of_mind)
 *   door    — 3 cards (email / upload / solve)
 *   working — polling for the artefact to land
 *   done    — rhythm explanation + single artefact CTA
 *
 * No tour, no tooltips, no percent-complete bars, no spinners. Editorial
 * register throughout: oxblood CTAs, cream surface, Georgia serif heads.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api, apiErrorMessage } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Upload as UploadIcon, Mail as MailIcon, HelpCircle as SolveIcon, Copy as CopyIcon, ArrowLeft, ArrowRight, Target as CycleIcon, Sparkles as DemoIcon } from "lucide-react";

const ROLE_OPTIONS = [
  { value: "executive", label: "Executive" },
  { value: "ned", label: "Non-Executive Director" },
  { value: "chair", label: "Chair" },
  { value: "dual", label: "Dual (Exec + NED)" },
];

// ---------------------------------------------------------------------------
// Shell — single 720-max-width column, cream background, editorial.
// ---------------------------------------------------------------------------
function Shell({ children }) {
  return (
    <div className="min-h-screen bg-[var(--cream)] px-4 md:px-8 py-8 md:py-14">
      <div className="akki-w-narrow" data-testid="first-session-shell">
        {children}
      </div>
    </div>
  );
}

function Overline({ children }) {
  return (
    <p className="akki-overline text-[10.5px] tracking-[0.22em] text-[var(--muted)] mb-3">
      {children}
    </p>
  );
}

function H1({ children }) {
  return (
    <h1 className="akki-serif text-[28px] md:text-[34px] leading-[1.2] text-[var(--ink)] font-normal mb-3">
      {children}
    </h1>
  );
}

function SubHead({ children }) {
  return (
    <p className="text-[14px] md:text-[15px] text-[var(--muted)] mb-8 max-w-[60ch]">
      {children}
    </p>
  );
}

function SkipLink({ onSkip }) {
  return (
    <button
      type="button"
      onClick={onSkip}
      className="text-[12px] text-[var(--muted)] hover:text-[var(--ink)] underline-offset-2 hover:underline"
      data-testid="first-session-skip"
    >
      Skip first session
    </button>
  );
}

// ---------------------------------------------------------------------------
// STEP 1 — Intake
// ---------------------------------------------------------------------------
function FirstSessionIntake({ initial, onSubmitted, onSkip }) {
  const [role, setRole] = useState(initial?.role || "");
  const [name, setName] = useState(initial?.primary_context_name || "");
  const [tom, setTom] = useState(initial?.top_of_mind || "");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const ready = role && name.trim().length >= 1 && tom.trim().length >= 1;

  const submit = useCallback(async () => {
    if (!ready || saving) return;
    setSaving(true);
    setErr("");
    try {
      const { data } = await api.post("/me/first-session/intake", {
        role,
        primary_context_name: name.trim(),
        top_of_mind: tom.trim(),
      });
      onSubmitted(data.state);
    } catch (e) {
      setErr(apiErrorMessage(e, "Couldn't save your answers. Please try again."));
    } finally {
      setSaving(false);
    }
  }, [ready, saving, role, name, tom, onSubmitted]);

  return (
    <div data-testid="first-session-intake">
      <Overline>FIRST SESSION</Overline>
      <H1>Three questions and we begin.</H1>
      <SubHead>AKKI starts where you start. Tell us the bare minimum and we'll move.</SubHead>

      {/* Q1 — Role */}
      <div className="mb-7">
        <label className="block akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)] mb-3">
          WHICH BEST DESCRIBES YOUR ROLE?
        </label>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2" role="radiogroup" aria-label="Your role">
          {ROLE_OPTIONS.map((o) => (
            <button
              key={o.value}
              type="button"
              role="radio"
              aria-checked={role === o.value}
              onClick={() => setRole(o.value)}
              className={`text-left px-4 py-3 border text-[14px] transition-colors ${
                role === o.value
                  ? "border-[var(--accent)] bg-white text-[var(--ink)]"
                  : "border-[var(--border,#e2d9cf)] bg-transparent text-[var(--ink)] hover:bg-white"
              }`}
              data-testid={`first-session-role-${o.value}`}
            >
              {o.label}
            </button>
          ))}
        </div>
      </div>

      {/* Q2 — Primary context name */}
      <div className="mb-7">
        <label htmlFor="fs-ctx-name" className="block akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)] mb-2">
          WHAT'S THE PRIMARY BOARD OR COMPANY YOU SIT ON?
        </label>
        <Input
          id="fs-ctx-name"
          value={name}
          maxLength={80}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Acme Holdings"
          className="bg-white border-[var(--border,#e2d9cf)] text-[15px]"
          data-testid="first-session-context-name"
        />
      </div>

      {/* Q3 — Top of mind */}
      <div className="mb-8">
        <label htmlFor="fs-tom" className="block akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)] mb-2">
          WHAT'S ON YOUR MIND FOR THE NEXT MEETING? ONE SENTENCE.
        </label>
        <Textarea
          id="fs-tom"
          value={tom}
          maxLength={240}
          onChange={(e) => setTom(e.target.value)}
          rows={3}
          placeholder="e.g. Q3 is off plan and I need a fast read on whether it is structural or timing."
          className="bg-white border-[var(--border,#e2d9cf)] text-[15px] resize-none"
          data-testid="first-session-top-of-mind"
        />
        <p className="text-[11px] text-[var(--muted)] mt-1 text-right">{tom.length} / 240</p>
      </div>

      {err && (
        <p className="text-[13px] text-[var(--severity)] mb-4" data-testid="first-session-error">{err}</p>
      )}

      <div className="flex items-center justify-between">
        <SkipLink onSkip={onSkip} />
        <button
          type="button"
          disabled={!ready || saving}
          onClick={submit}
          className={`akki-overline tracking-[0.16em] text-[11px] px-5 py-3 text-white bg-[var(--accent)] transition-colors ${
            ready && !saving
              ? "hover:bg-[var(--accent)]/90"
              : "bg-[var(--accent)]/70 cursor-not-allowed"
          }`}
          data-testid="first-session-intake-submit"
        >
          {saving ? "SAVING YOUR ANSWERS…" : "BEGIN →"}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// STEP 2 — Door
// ---------------------------------------------------------------------------
function InboundAddressBlock() {
  const [addr, setAddr] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get("/inbound/address");
        if (!cancelled) setAddr(data.address);
      } catch {
        if (!cancelled) setAddr(null);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const onCopy = async () => {
    if (!addr) return;
    try {
      await navigator.clipboard.writeText(addr);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // fallback: tiny toast
      toast.message("Couldn't copy — select and copy manually.");
    }
  };

  return (
    <div className="mt-3">
      {addr ? (
        <div
          className="flex items-center gap-2 bg-[var(--cream)] border border-[var(--border,#e2d9cf)] px-3 py-2"
          data-testid="first-session-inbound-address"
        >
          <code className="text-[13px] md:text-[14px] font-mono text-[var(--ink)] break-all flex-1">
            {addr}
          </code>
          <button
            type="button"
            onClick={onCopy}
            className="text-[11px] akki-overline tracking-[0.16em] text-[var(--muted)] hover:text-[var(--ink)] flex items-center gap-1"
            aria-label="Copy inbound address"
            data-testid="first-session-inbound-copy"
          >
            <CopyIcon size={12} />
            {copied ? "COPIED" : "COPY"}
          </button>
        </div>
      ) : (
        <p className="text-[12px] text-[var(--muted)]">Your inbound address will appear here shortly.</p>
      )}
    </div>
  );
}

function DoorCard({ testId, icon, heading, body, cta, children, onClick, disabled, dim, note }) {
  const Icon = icon;
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`block w-full text-left border bg-white p-5 md:p-6 transition-colors ${
        dim ? "opacity-75" : ""
      } border-[var(--border,#e2d9cf)] hover:border-[var(--accent)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/40 disabled:cursor-not-allowed`}
      data-testid={testId}
    >
      <div className="flex items-start gap-3 mb-2">
        <Icon size={18} className="text-[var(--accent)] mt-[2px] shrink-0" />
        <h3 className="akki-serif text-[18px] md:text-[20px] text-[var(--ink)] font-normal leading-tight">
          {heading}
        </h3>
      </div>
      <p className="text-[13.5px] md:text-[14px] text-[var(--muted)] leading-[1.55] mb-2">
        {body}
      </p>
      {children}
      {note && <p className="text-[11.5px] text-[var(--muted)] italic mt-2">{note}</p>}
      {cta && (
        <p className="akki-overline tracking-[0.16em] text-[11px] text-[var(--accent)] mt-3 flex items-center gap-1">
          {cta} <ArrowRight size={12} />
        </p>
      )}
    </button>
  );
}

function FirstSessionDoor({ intake, onDoorChosen, onSkip, refreshAuth }) {
  const navigate = useNavigate();
  const [picking, setPicking] = useState(null); // which door is in-flight

  const choose = useCallback(async (door) => {
    if (picking) return;
    setPicking(door);
    try {
      const res = await api.post("/me/first-session/choose-door", { door });
      if (door === "solve") {
        // Backend flipped status → completed. Refresh AuthContext BEFORE
        // navigating so `FirstSessionGuard` on `/app/solva` sees the new
        // state and doesn't bounce us back here (Phase 4.1 fix). Note:
        // the door key remains "solve" to keep prior intake records
        // matchable; only the navigation target reflects the Phase 13.1
        // rename.
        //
        // J4 (2026-05-25, G30 ratified) — pass the de-identified Q3
        // intake answer as `?starter=` so the Solva framing surface
        // pre-populates the composer per spec §3 Stage 6 step 1.
        // `intake.top_of_mind` is the Shield-redacted value persisted
        // by J1's G18 wiring, NEVER the raw text.
        try { if (refreshAuth) await refreshAuth(); } catch { /* noop */ }
        const starter = intake?.top_of_mind || "";
        const q = starter ? `?starter=${encodeURIComponent(starter)}` : "";
        navigate(`/app/solva${q}`);
        return;
      }
      if (door === "demo") {
        // J2 (G22 ratified) — backend stamped `seed_marker_visible_for`
        // on the DEMO_T5_BACKLOG rows and flipped status → completed.
        // Track B Phase B1b (2026-06-04) — re-dispatch per Onboarding
        // QA item 6: the verbatim ask is "I think the user should land
        // on the Home Page", not Cycle Manager. App.js:435 mounts
        // `<Route path="/app" element={<AppHome />} />` — that is the
        // canonical Home route (there is no /app/home alias). Updated
        // accordingly. The demo backlog rows remain visible from the
        // Home → Cycle Manager link by virtue of the seed-marker stamp
        // the backend just made.
        try { if (refreshAuth) await refreshAuth(); } catch { /* noop */ }
        navigate("/app");
        return;
      }
      if (door === "upload") {
        // P0-B Card 2 (2026-02) — Door B per Spec G21. Navigate to the
        // Document Journal with the `?upload=1` flag — AppShell reads
        // the flag on mount and opens the shared UploadModal (the same
        // "ADD TO DOCUMENT JOURNAL" surface used by every other Akki
        // entry point). Previous behaviour landed on
        // `FirstSessionWorking` which polled `/me/review-queue` forever
        // and never gave the user any upload UI.
        try { if (refreshAuth) await refreshAuth(); } catch { /* noop */ }
        navigate("/app/documents?upload=1");
        return;
      }
      if (door === "cycle") {
        // J2 (G21) — Door A was originally routed to the T5 Cycle
        // Setup Wizard. Track B Phase B1b (2026-06-04) — re-dispatch
        // per Onboarding QA item 4: the verbatim ask is "I think the
        // user should be redirected to the Task Manager Module shown
        // in figure 3", NOT the Cycle Setup Wizard. App.js:446 mounts
        // `<Route path="/app/task-manager" element={<TaskManager />} />`
        // — that is the canonical Task Manager surface. The
        // `intake_seed=1` query param is dropped because the Task
        // Manager doesn't consume it (it was a Cycle Setup Wizard
        // concept); intake stays persisted on the account doc and is
        // available via `/me/first-session` if the surface ever wants
        // to read it.
        try { if (refreshAuth) await refreshAuth(); } catch { /* noop */ }
        navigate("/app/task-manager");
        return;
      }
      onDoorChosen(door);
    } catch (e) {
      toast.error(apiErrorMessage(e, "Couldn't register your choice — please retry."));
      setPicking(null);
    }
  }, [picking, intake, navigate, onDoorChosen, refreshAuth]);

  const isMobile = typeof window !== "undefined" && window.innerWidth < 768;

  return (
    <div data-testid="first-session-door">
      <Overline>STEP 2 OF 4</Overline>
      <H1>Four ways to begin.</H1>
      <SubHead>Pick whichever's closest at hand. AKKI can take it from any of these.</SubHead>

      <div className={`flex flex-col gap-3 md:gap-4 ${isMobile ? "" : ""}`}>
        {/* Door A — Cycle (G21) */}
        <DoorCard
          testId="first-session-door-cycle"
          icon={CycleIcon}
          heading="Create your first cycle."
          body="Set up a board or committee cycle in two minutes. Invite your team, choose the readiness target, and AKKI keeps the cadence."
          cta="Set up a cycle"
          onClick={() => choose("cycle")}
          disabled={picking && picking !== "cycle"}
        />

        {/* Door B — Upload (existing) */}
        <DoorCard
          testId="first-session-door-upload"
          icon={UploadIcon}
          heading="Upload a document."
          body="PDF, DOCX, or text up to 25 MB. AKKI extracts, classifies, and surfaces signals."
          cta="Upload now"
          onClick={() => choose("upload")}
          disabled={picking && picking !== "upload"}
          dim={isMobile}
          note={isMobile ? "Easier from desktop." : null}
        />

        {/* Door C — Ask Akki (existing solve door, retained semantics) */}
        <DoorCard
          testId="first-session-door-solve"
          icon={SolveIcon}
          heading="Ask Akki something."
          body="Take the sentence you just gave us into a 4-phase Solva session. AKKI surfaces, deepens, synthesises, locks in."
          cta="Ask Akki"
          onClick={() => choose("solve")}
          disabled={picking && picking !== "solve"}
        />

        {/* Door D — Demo (G22) */}
        <DoorCard
          testId="first-session-door-demo"
          icon={DemoIcon}
          heading="Try the demo."
          body="Skip the setup and walk straight into a sample board cycle with seeded papers, contributors, and a compiled board pack."
          cta="Try the demo"
          onClick={() => choose("demo")}
          disabled={picking && picking !== "demo"}
        />
      </div>

      <div className="mt-8 flex items-center justify-between">
        <SkipLink onSkip={onSkip} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// STEP 3 — Working
// ---------------------------------------------------------------------------
function Pulse() {
  return (
    <div className="flex items-center gap-1.5 mt-6" aria-hidden="true" data-testid="first-session-pulse">
      <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] akki-pulse-gold"></span>
      <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)]/60 akki-pulse-gold" style={{ animationDelay: "200ms" }}></span>
      <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)]/40 akki-pulse-gold" style={{ animationDelay: "400ms" }}></span>
    </div>
  );
}

function FirstSessionWorking({ door, onArtefactReady, onSkip }) {
  const startRef = useRef(Date.now());
  const [elapsed, setElapsed] = useState(0);
  const pollRef = useRef(null);

  // Poll for a landed artefact.
  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      if (cancelled) return;
      try {
        if (door === "email" || door === "upload") {
          // Look for the most recent inbound_queue doc or new document/briefing
          // in any of my contexts. Easiest: ask /me/review-queue — if there's
          // any pending briefing or inbound doc, treat that as the artefact.
          const { data } = await api.get("/me/review-queue?limit=1");
          const item = (data?.items || [])[0];
          if (item) {
            const kind = item.kind === "inbound_doc" ? "briefing" : item.kind;
            // inbound docs get surfaced as briefings once approved; for the
            // first-session happy-path we surface whichever exists first.
            if (item.kind === "briefing") {
              onArtefactReady({ kind: "briefing", id: item.id });
            } else {
              // Inbound doc — still counts as "something landed". We
              // auto-mark first session complete with this id as a
              // pseudo-briefing; backend complete() validates existence.
              onArtefactReady({ kind: "briefing", id: item.id });
            }
            return;
          }
        }
      } catch { /* soft-fail, keep polling */ }
      const since = Math.floor((Date.now() - startRef.current) / 1000);
      setElapsed(since);
      pollRef.current = setTimeout(poll, 5000);
    };
    poll();

    return () => {
      cancelled = true;
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, [door, onArtefactReady]);

  const title =
    door === "email"
      ? "Watching for your email."
      : door === "upload"
        ? "Reading the document."
        : "Working…";

  const body =
    door === "email"
      ? "Once your forwarded email arrives, AKKI will extract, classify, and draft a first briefing. You'll pick up right here."
      : "AKKI is extracting text, pulling signals, and drafting a short briefing. A minute or two, usually less.";

  const minutes = Math.floor(elapsed / 60);
  const showStall = minutes >= 5;

  return (
    <div data-testid="first-session-working">
      <Overline>STEP 3 OF 4</Overline>
      <H1>{title}</H1>
      <SubHead>{body}</SubHead>
      <Pulse />

      {showStall && (
        <div className="mt-10 border-t border-[var(--border,#e2d9cf)] pt-5">
          <p className="text-[13px] text-[var(--muted)] mb-3">
            Still nothing? Don't wait — head home, and AKKI will catch up when the email lands.
          </p>
          <button
            type="button"
            onClick={onSkip}
            className="text-[12px] text-[var(--muted)] hover:text-[var(--ink)] underline-offset-2 hover:underline"
            data-testid="first-session-working-skip"
          >
            Take me home — AKKI will catch up →
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// STEP 4 — Done
// ---------------------------------------------------------------------------
function FirstSessionDone({ artefact }) {
  const navigate = useNavigate();
  const [addr, setAddr] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/inbound/address");
        setAddr(data.address);
      } catch { /* noop */ }
    })();
  }, []);

  const artefactLabel = artefact?.kind === "solve_session" ? "Solva session" : "briefing";
  const artefactHref =
    artefact?.kind === "solve_session"
      ? `/app/solva?session=${artefact.id}`
      : `/app/prepare?briefing=${artefact?.id || ""}`;

  return (
    <div data-testid="first-session-done">
      <Overline>FIRST SESSION COMPLETE</Overline>
      <H1>Here's what's now set up.</H1>

      <div className="space-y-6 md:space-y-7 mb-10 mt-8">
        <div>
          <p className="akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)] mb-1">
            YOUR INBOUND ADDRESS
          </p>
          <p className="text-[14px] md:text-[15px] text-[var(--ink)] font-mono break-all mb-1">
            {addr || "…"}
          </p>
          <p className="text-[13px] text-[var(--muted)]">
            Forward anything to AKKI. It files automatically.
          </p>
        </div>
        <div>
          <p className="akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)] mb-1">YOUR HOME</p>
          <p className="text-[13px] text-[var(--muted)]">
            Cross-board stream of what changed since you last visited.
          </p>
        </div>
        <div>
          <p className="akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)] mb-1">YOUR DAILY REVIEW</p>
          <p className="text-[13px] text-[var(--muted)]">
            AKKI drafts; you approve once a day. The badge appears top-right when something's waiting.
          </p>
        </div>
      </div>

      <p className="text-[14px] italic text-[var(--ink)] mb-8">
        I'll see you when something arrives.
      </p>

      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => navigate("/app")}
          className="text-[12px] text-[var(--muted)] hover:text-[var(--ink)] underline-offset-2 hover:underline"
          data-testid="first-session-done-home"
        >
          <ArrowLeft size={12} className="inline mr-1" /> Go to home
        </button>
        {artefact?.id && (
          <button
            type="button"
            onClick={() => navigate(artefactHref)}
            className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white akki-overline tracking-[0.16em] text-[11px] px-5 py-3"
            data-testid="first-session-done-artefact"
          >
            OPEN YOUR {artefactLabel.toUpperCase()} →
          </button>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Root page
// ---------------------------------------------------------------------------
export default function FirstSession() {
  const { bootstrap, account } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [state, setState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [initialPrefill, setInitialPrefill] = useState(null);

  // Hydrate + auto-start. Also read sandbox pre-fill passed via location.state.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get("/me/first-session");
        if (cancelled) return;
        if (data.state?.status === "completed" || data.state?.status === "skipped") {
          navigate("/app", { replace: true });
          return;
        }
        // Pre-fill from location.state (sandbox conversion path).
        const prefill = location.state?.prefill || null;
        setInitialPrefill(prefill);
        // Make sure backend is in_progress so existing context is ensured.
        if (data.state?.status === "not_started") {
          const started = await api.post("/me/first-session/start");
          setState(started.data.state);
        } else {
          setState(data.state);
        }
      } catch (e) {
        toast.error(apiErrorMessage(e, "Couldn't load First Session."));
        navigate("/app", { replace: true });
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onIntakeSubmitted = useCallback(async (newState) => {
    setState(newState);
    // Hardening Step 2 (2026-05-25, P3/J2.3 false-green fix) —
    // `bootstrap()` re-fetches `/auth/me` so `account.first_session`
    // is fresh after the intake POST mutated it server-side. The
    // prior `refreshContexts()` only refreshed the contexts list,
    // leaving the AuthContext's `account.first_session.{intake,
    // current_step}` stale → any subsequent route guard would see
    // pre-intake state. Same J2.3 recurrence as the choose-door fix.
    try { await bootstrap(); } catch { /* noop */ }
  }, [bootstrap]);

  const onDoorChosen = useCallback((door) => {
    setState((prev) => ({ ...(prev || {}), current_step: "working", door_taken: door }));
  }, []);

  const onArtefactReady = useCallback(async (artefact) => {
    try {
      const { data } = await api.post("/me/first-session/complete", { artefact });
      setState(data.state);
      // Hardening Step 2 (P3/J2.3) — `bootstrap()` updates
      // `account.first_session.status: "completed"` so the
      // FirstSessionGuard at `/app/*` sees the new state and
      // doesn't bounce back to /app/first-session.
      try { await bootstrap(); } catch { /* noop */ }
    } catch (e) {
      // If the artefact couldn't be validated, don't block — take user home
      // with the partial state. We log the error softly.
      toast.error(apiErrorMessage(e, "Couldn't finalise — heading home."));
      navigate("/app", { replace: true });
    }
  }, [bootstrap, navigate]);

  const onSkip = useCallback(async () => {
    try {
      await api.post("/me/first-session/skip");
      // Hardening Step 2 (P3/J2.3) — `bootstrap()` updates
      // `account.first_session.status: "skipped"` so the
      // FirstSessionGuard at `/app/*` doesn't redirect back.
      try { await bootstrap(); } catch { /* noop */ }
    } catch { /* noop */ }
    navigate("/app", { replace: true });
  }, [navigate, bootstrap]);

  const step = state?.current_step || "intake";

  if (loading || !state) {
    return (
      <Shell>
        <p className="akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)] animate-pulse">
          Opening your first session…
        </p>
      </Shell>
    );
  }

  return (
    <Shell>
      {step === "intake" && (
        <FirstSessionIntake
          // Phase R.1 (2026-05-27) — Cohort users land here from the
          // magic-link consume with `account.logo_name` already stamped.
          // Feed that as the context-name pre-fill so the wizard's 2nd
          // question is one-confirm away. Order: server-saved partial
          // > sandbox-conversion prefill > cohort invite logo_name.
          initial={state.intake || initialPrefill || (
            account?.cohort_tag && account?.logo_name
              ? { primary_context_name: account.logo_name }
              : null
          )}
          onSubmitted={onIntakeSubmitted}
          onSkip={onSkip}
        />
      )}
      {step === "door" && (
        <FirstSessionDoor
          intake={state.intake}
          onDoorChosen={onDoorChosen}
          onSkip={onSkip}
          refreshAuth={bootstrap}
        />
      )}
      {step === "working" && (
        <FirstSessionWorking
          door={state.door_taken}
          onArtefactReady={onArtefactReady}
          onSkip={onSkip}
        />
      )}
      {step === "done" && (
        <FirstSessionDone artefact={state.artefact} />
      )}
      {/* Hidden account email marker so tests can assert who we're flowing */}
      <span data-testid="first-session-account-email" className="sr-only">
        {account?.email}
      </span>
      {/* Phase R.1 (2026-05-27) — Test-only DOM hook surfacing the
          account's trial_status. Hidden visually via sr-only +
          aria-hidden so it has zero UX impact. Mirrors the same hook
          on AppShell so cohort users on /app/first-session can also
          be verified via Playwright. R.5 will render trial_status
          visibly and REMOVE both copies. */}
      <span
        className="sr-only"
        aria-hidden="true"
        data-testid="trial-status"
      >
        {account?.trial_status || ""}
      </span>
    </Shell>
  );
}
