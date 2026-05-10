/**
 * Phase C.3 — Source picker.
 *
 * Lists compose-able sources for Work Studio: completed Solva sessions,
 * chat artefacts, and a disabled chip for cycle compilations (Phase D).
 *
 * Reads from existing endpoints (no backend change):
 *   GET /api/solva/v2/sessions?status=completed
 *   GET /api/chats?limit=…
 *
 * Click a source → fires `onPick({source_type, source_id, label, sub_label})`
 * which the parent uses to open the Compose drawer.
 */
import React, { useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Loader2, AlertCircle, MessageSquare, Brain, ScrollText, ChevronRight, Lock,
} from "lucide-react";

const SUBMODULE_LABEL = {
  seek_clarity: "Seek Clarity",
  develop_strategy: "Develop Strategy",
  simulate_hypothesis: "Simulate Hypothesis",
  get_perspective: "See Different Perspectives",
};

function firstLine(s) {
  if (!s) return "";
  const t = String(s).trim();
  const i = t.indexOf("\n");
  return i === -1 ? t : t.slice(0, i);
}

function shortDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  } catch { return "—"; }
}

function Section({ title, count, hint, children }) {
  return (
    <section className="mb-8" data-testid={`source-section-${title.toLowerCase().replace(/\s+/g, "-")}`}>
      <header className="flex items-baseline justify-between mb-2">
        <div>
          <h2 className="akki-serif text-[18px] text-[var(--ink)] font-medium">{title}</h2>
          <p className="text-[12px] text-[var(--muted)] mt-0.5">{hint}</p>
        </div>
        {count != null && (
          <span className="text-[11px] uppercase tracking-[0.16em] font-mono text-[var(--muted)]">
            {count} {count === 1 ? "source" : "sources"}
          </span>
        )}
      </header>
      {children}
    </section>
  );
}

function SourceRow({ icon: Icon, kicker, title, sub, onClick, testId, disabled, disabledTitle }) {
  return (
    <button
      type="button"
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      title={disabled ? disabledTitle : undefined}
      className={`w-full text-left border rounded-md bg-white px-4 py-3 flex items-start gap-3 transition-colors ${
        disabled
          ? "border-[var(--rule)] opacity-60 cursor-not-allowed"
          : "border-[var(--rule)] hover:border-[var(--accent)] hover:bg-[var(--cream-deep)]/40"
      }`}
      data-testid={testId}
    >
      <Icon className="w-4 h-4 text-[var(--deep)] shrink-0 mt-1" strokeWidth={1.7} />
      <div className="min-w-0 flex-1">
        {kicker && (
          <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">{kicker}</p>
        )}
        <p className="akki-serif text-[14.5px] text-[var(--ink)] leading-snug truncate">{title || "Untitled"}</p>
        {sub && <p className="text-[12px] text-[var(--muted)] mt-1 truncate">{sub}</p>}
      </div>
      {disabled ? (
        <Lock className="w-3.5 h-3.5 text-[var(--muted)] shrink-0 mt-1.5" />
      ) : (
        <ChevronRight className="w-3.5 h-3.5 text-[var(--muted)] shrink-0 mt-1.5" />
      )}
    </button>
  );
}

export default function SourcePicker({ onPick, contextId }) {
  const [solva, setSolva] = useState({ items: [], loading: true, error: null });
  const [chats, setChats] = useState({ items: [], loading: true, error: null });

  useEffect(() => {
    let cancelled = false;
    setSolva({ items: [], loading: true, error: null });
    api.get("/solva/v2/sessions", { params: { status: "completed" } })
      .then(({ data }) => {
        if (cancelled) return;
        const items = (data?.items || []).slice(0, 30);
        setSolva({ items, loading: false, error: null });
      })
      .catch((e) => { if (!cancelled) setSolva({ items: [], loading: false, error: apiErrorMessage(e) }); });
    return () => { cancelled = true; };
  }, [contextId]);

  useEffect(() => {
    let cancelled = false;
    setChats({ items: [], loading: true, error: null });
    api.get("/chats", { params: { limit: 25 } })
      .then(({ data }) => {
        if (cancelled) return;
        const items = (data?.items || data?.chats || data || []).filter(
          (c) => !c.deleted_at && (c.title || "").trim().length > 0,
        );
        setChats({ items, loading: false, error: null });
      })
      .catch((e) => { if (!cancelled) setChats({ items: [], loading: false, error: apiErrorMessage(e) }); });
    return () => { cancelled = true; };
  }, [contextId]);

  return (
    <div data-testid="work-studio-source-picker">
      <Section
        title="Solva sessions"
        count={solva.items.length}
        hint="Completed sessions you can compose into a board-grade artefact."
      >
        {solva.loading ? (
          <div className="text-[var(--muted)] text-[13px] flex items-center gap-2 px-1 py-2">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading sessions…
          </div>
        ) : solva.error ? (
          <div className="text-[12.5px] text-amber-900 bg-amber-50 border border-amber-100 rounded-md px-3 py-2 flex items-center gap-2">
            <AlertCircle className="w-3.5 h-3.5" /> {solva.error}
          </div>
        ) : solva.items.length === 0 ? (
          <p className="text-[12.5px] text-[var(--muted)] italic px-1 py-2">
            No completed Solva sessions yet. Run one through synthesis and reflection — that's the standard source for a board memo.
          </p>
        ) : (
          <ul className="space-y-2" data-testid="source-list-solva">
            {solva.items.map((s) => (
              <li key={s.id}>
                <SourceRow
                  icon={Brain}
                  kicker={`${SUBMODULE_LABEL[s.submodule] || s.submodule || "Solva"} · ${shortDate(s.completed_at || s.updated_at)}`}
                  title={firstLine(s.intent) || "(no intent recorded)"}
                  sub={s.cluster_label || null}
                  onClick={() => onPick({
                    source_type: "solva_session",
                    source_id: s.id,
                    label: firstLine(s.intent) || "Solva session",
                    sub_label: SUBMODULE_LABEL[s.submodule] || s.submodule,
                  })}
                  testId={`source-row-solva-${s.id}`}
                />
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section
        title="Chat artefacts"
        count={chats.items.length}
        hint="Chats with assistant content. Composes into a memo via Seek-Clarity-shaped envelope."
      >
        {chats.loading ? (
          <div className="text-[var(--muted)] text-[13px] flex items-center gap-2 px-1 py-2">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading chats…
          </div>
        ) : chats.error ? (
          <div className="text-[12.5px] text-amber-900 bg-amber-50 border border-amber-100 rounded-md px-3 py-2 flex items-center gap-2">
            <AlertCircle className="w-3.5 h-3.5" /> {chats.error}
          </div>
        ) : chats.items.length === 0 ? (
          <p className="text-[12.5px] text-[var(--muted)] italic px-1 py-2">
            No chats with content yet.
          </p>
        ) : (
          <ul className="space-y-2" data-testid="source-list-chats">
            {chats.items.map((c) => (
              <li key={c.id}>
                <SourceRow
                  icon={MessageSquare}
                  kicker={`Chat · ${shortDate(c.updated_at || c.created_at)}`}
                  title={c.title || "Untitled chat"}
                  sub={c.model || null}
                  onClick={() => onPick({
                    source_type: "chat_artefact",
                    source_id: c.id,
                    label: c.title || "Chat artefact",
                    sub_label: c.model || "Chat",
                  })}
                  testId={`source-row-chat-${c.id}`}
                />
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section
        title="Cycle compilations"
        hint="Ships once a cycle completes a full agenda → minutes → boardpack arc."
      >
        <SourceRow
          icon={ScrollText}
          kicker="Cycle compilation"
          title="Available once a cycle ships in Phase D"
          sub="The cycle aggregator is wired but compose isn't routed yet."
          disabled
          disabledTitle="available once a cycle ships in Phase D"
          testId="source-row-cycle-disabled"
        />
      </Section>
    </div>
  );
}
