/**
 * TaskListing — Phase F.2 (2026-05-26) · F.3 patched 2026-05-26.
 *
 * Phase Y (2026-02 fork-resume) — Task cards now compose the shared
 * `<StrategicRow>` primitive so every Task card matches the Monitor
 * goal row layout pixel-for-pixel (chip placement, single-line
 * description, owner avatars integrated into the metadata row,
 * readiness as a right-anchored ScoreBar with narrative).
 *
 * Renders the list of task cards for the active sort tab. Calls
 * `GET /api/tasks?state=<tab>`. Each card carries: TASK chip · title ·
 * status/needs-input chips · readiness ScoreBar · owner avatars +
 * due date + needs-input flag in the metadata row · objective as the
 * description slot.
 *
 * F.3: clicking a task card sets `?task_id=<id>` on the URL — the
 * `<TaskDrawer>` mounted on TaskManager opens automatically.
 */
import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Loader2, Calendar, Users, Inbox } from "lucide-react";
import { toast } from "sonner";
import StrategicRow from "@/components/strategic_row/StrategicRow";
// P5.17 — origin chip + source-message modal for inbox-routed tasks.
import OriginChip from "@/components/origin/OriginChip";
import SourceMessageModal from "@/components/origin/SourceMessageModal";


function fmtDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleDateString(); } catch { return iso; }
}


function StatusPill({ state }) {
  const map = {
    active: { label: "Active", cls: "text-[var(--ink)] bg-[var(--cream-deep)] border-[var(--rule)]" },
    draft:  { label: "Draft",  cls: "text-[var(--oxblood)] bg-[rgba(122,46,46,0.10)] border-[rgba(122,46,46,0.20)]" },
    closed: { label: "Closed", cls: "text-[var(--muted)] bg-[var(--parchment)] border-[var(--rule)]" },
  };
  const m = map[state] || map.active;
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded-sm text-[10px] uppercase tracking-[0.14em] font-mono border ${m.cls}`}
      data-testid={`task-card-status-${state}`}
    >
      {m.label}
    </span>
  );
}


// Phase Y / Decision 2 (2026-02 fork-resume) — Task readiness bar follows
// the same RAG vocabulary Monitor uses for the Performance score bar.
function readinessBarClass(score) {
  if (score == null) return "bg-[var(--rule)]";
  if (score >= 70) return "bg-emerald-500";
  if (score >= 40) return "bg-amber-500";
  return "bg-rose-500";
}

function readinessNarrative(score) {
  if (score == null) return "Readiness not yet computed.";
  if (score >= 85) return "Ready to compile. Inputs complete.";
  if (score >= 60) return "On the way. A few inputs still pending.";
  if (score >= 30) return "Half-ready. Needs more contributor input.";
  return "Early stage. Most inputs still missing.";
}


function ContributorAvatars({ team }) {
  const first = (team || []).slice(0, 4);
  const extra = Math.max(0, (team || []).length - first.length);
  if (first.length === 0) {
    return <span className="text-[11px] italic text-[var(--muted)]">No team</span>;
  }
  return (
    <div className="flex -space-x-1.5">
      {first.map((m, i) => (
        <span
          key={i}
          title={m.name || m.email}
          className="w-5 h-5 rounded-full bg-[var(--cream-deep)] border border-white text-[9.5px] font-mono flex items-center justify-center text-[var(--ink)]"
        >
          {(m.name || m.email || "?").slice(0, 1).toUpperCase()}
        </span>
      ))}
      {extra > 0 && (
        <span className="w-5 h-5 rounded-full bg-[var(--parchment)] border border-white text-[9.5px] font-mono flex items-center justify-center text-[var(--muted)]">
          +{extra}
        </span>
      )}
    </div>
  );
}


export default function TaskListing({ contextId, state, refreshKey, originFilter }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [, setParams] = useSearchParams();
  const { account } = useAuth();
  const myEmail = (account?.email || "").toLowerCase();
  // P5.17 — modal state for source-message preview.
  const [previewOrigin, setPreviewOrigin] = useState(null);

  useEffect(() => {
    let dead = false;
    setLoading(true);
    const params = { state };
    if (contextId) params.context_id = contextId;
    // P5.17 — pass `origin` query when filter is narrower than "all".
    if (originFilter && originFilter !== "all") params.origin = originFilter;
    api.get("/tasks", { params })
      .then(({ data }) => { if (!dead) setTasks(Array.isArray(data) ? data : []); })
      .catch((e) => {
        if (!dead) { setTasks([]); toast.error(apiErrorMessage(e)); }
      })
      .finally(() => { if (!dead) setLoading(false); });
    return () => { dead = true; };
  }, [contextId, state, refreshKey, originFilter]);

  // F.3: card click opens the drawer via `?task_id=<id>`.
  const openTask = (taskId) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("task_id", taskId);
      return next;
    }, { replace: false });
  };

  if (loading) {
    return (
      <div
        className="text-[12px] text-[var(--muted)] inline-flex items-center gap-1.5"
        data-testid="task-listing-loading"
      >
        <Loader2 className="w-3 h-3 animate-spin" /> Loading…
      </div>
    );
  }
  if (tasks.length === 0) {
    return (
      <div className="text-center py-12" data-testid={`task-listing-empty-${state}`}>
        <Inbox className="w-6 h-6 text-[var(--muted)] mx-auto mb-2" strokeWidth={1.5} />
        <p className="text-[12.5px] italic text-[var(--muted)]">
          {state === "active" && "No active tasks. Click \u201CSet up new task\u201D to get started."}
          {state === "draft" && "No draft tasks. Drafts you save without commissioning land here."}
          {state === "closed" && "No closed tasks yet."}
        </p>
      </div>
    );
  }

  return (
    <>
      <ul className="space-y-3" data-testid="task-listing-list">
        {tasks.map((t) => {
        // Wave 4.1 (2026-05-27) — "Needs your input" attention pill
        // surfaces when this user is on the team and still owes input.
        const me = myEmail
          ? (t.team || []).find((m) => (m.email || "").toLowerCase() === myEmail)
          : null;
        const needsInput = me && ["not_started", "in_progress"].includes(me.status || "not_started");
        // Active rows carry the brand-purple highlight on the card
        // wrapper border (W4.1 lock — see test_wave4_task_listing.py).
        const isActiveRow = t.state === "active";

        // ── StrategicRow slot composition ──────────────────────────
        // categoryChip — Phase Y constant "TASK" marker (mirrors
        // Monitor row's category placement). Brand-purple via
        // Tailwind-config short name (Wave 4.2.followup.2 compliant).
        const categoryChip = (
          <span
            className="inline-block px-1.5 py-0.5 rounded-sm text-[9.5px] uppercase tracking-wider border bg-ned-purple/10 text-[var(--ink)] border-ned-purple/20"
            data-testid={`task-card-category-${t.id}`}
          >
            Task
          </span>
        );

        // statusChip — needsInput pill (left, source-order first per
        // W4_1b) + StatusPill + P5.17 origin chip when applicable.
        const statusChip = (
          <>
            {needsInput && (
              <span
                className="inline-flex items-center gap-1.5 text-[10.5px] font-mono uppercase tracking-[0.14em] px-1.5 py-0.5 rounded-sm bg-amber-50 text-amber-800"
                data-testid={`task-card-needs-your-input-${t.id}`}
              >
                Needs your input
              </span>
            )}
            <StatusPill state={t.state} />
            <OriginChip
              origin={t.origin}
              onClick={setPreviewOrigin}
              testid={`task-card-origin-chip-${t.id}`}
            />
          </>
        );

        // rightSideScores — readiness as a ScoreBar (label + bar +
        // value + narrative underneath). Single score for tasks vs
        // Monitor's Performance + Probability pair.
        const rightSideScores = [{
          label:     "Readiness",
          value:     typeof t.readiness_score === "number" ? t.readiness_score : null,
          barClass:  readinessBarClass(t.readiness_score),
          narrative: readinessNarrative(t.readiness_score),
          testId:    `task-card-readiness-${t.id}`,
        }];

        // metadataChildren — owner avatar cluster (integrated into
        // the metadata row, no longer dangling under the title) +
        // due date. Same gap rhythm as Monitor.
        const metadataChildren = (
          <>
            <span
              className="inline-flex items-center gap-1.5"
              data-testid={`task-card-team-${t.id}`}
            >
              <Users className="w-3 h-3 text-[var(--muted)]" strokeWidth={1.7} />
              <ContributorAvatars team={t.team} />
            </span>
            {t.due_date && (
              <span
                className="inline-flex items-center gap-1 text-[var(--muted)]"
                data-testid={`task-card-due-${t.id}`}
              >
                <Calendar className="w-3 h-3" strokeWidth={1.7} />
                {fmtDate(t.due_date)}
              </span>
            )}
            {t.compile_session?.active && t.compile_session?.current_stage && (
              <span
                className="inline-flex items-center gap-1.5 text-[10.5px] font-mono uppercase tracking-[0.14em] px-1.5 py-0.5 rounded-sm bg-[rgba(122,46,46,0.08)] text-[var(--oxblood)]"
                data-testid={`task-card-compile-pill-${t.id}`}
              >
                Compile · {(t.compile_session.current_stage || "").replace(/_/g, " ")}
              </span>
            )}
          </>
        );

        return (
          <li
            key={t.id}
            data-card-kind="task"
            data-active-highlight={isActiveRow ? "true" : "false"}
            className={[
              "border bg-white rounded-sm transition-colors",
              isActiveRow
                ? "border-[color:var(--ned-purple)]/40 hover:border-[color:var(--ned-purple)]"
                : "border-[var(--rule)] hover:border-[var(--ink)]",
            ].join(" ")}
          >
            <StrategicRow
              categoryChip={categoryChip}
              statusChip={statusChip}
              title={t.name || "Untitled task"}
              rightSideScores={rightSideScores}
              metadataChildren={metadataChildren}
              description={t.objective}
              onClick={() => openTask(t.id)}
              testId={`task-card-${t.id}`}
              isLast={true}
            />
          </li>
        );
      })}
      </ul>
      {previewOrigin && (
        <SourceMessageModal
          origin={previewOrigin}
          onClose={() => setPreviewOrigin(null)}
          isSuperadmin={!!account?.is_superadmin}
        />
      )}
    </>
  );
}
