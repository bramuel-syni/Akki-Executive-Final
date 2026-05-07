# NED-Side Cycle Manager — Design Document

**Status:** Design only. No implementation in this build.
**Decision:** D-003 (founder override on MEMO Item 3 scope).
**Phase:** D — produced alongside the Executive Cycle Manager rewire (Phase D).
**Author:** AKKI engineering, 2026-05-07.
**Audience:** PM, design lead, and the engineering team scoping the post-Phase-D NED workstream.

---

## 1. Why this exists

MEMO Item 3 deliberately scopes the Cycle Manager rewire to the **Executive flow** — the executive's drafting engine for the next board reporting cycle. The same memo flags the **NED-side journey** ("catch-up and cycle monitoring") as a related but distinct workstream the PM was asked to scope as a follow-on.

Founder override **D-003** moved the design forward into Phase D so we don't lose the architectural alignment between the two journeys. This document is the deliverable. It outlines:

1. The NED catch-up journey (preparing for an upcoming board)
2. The cycle-monitoring journey (post-meeting follow-up + minutes consumption)
3. How NED-side surfaces consume the Executive Cycle's outputs
4. Trust + data-isolation rules that govern the NED-side reads
5. Out-of-scope items kept distinct from this design

It does not specify endpoints, schemas, or UI components. Those are downstream of this scoping decision. It does fix the **shape** of the NED journey so engineering can size and sequence the build.

---

## 2. The NED on AKKI — who they are, what they need

A NED on AKKI is a non-executive director sitting on one or more boards. Their job is **judgement on direction**, not delivery. They need:

- A **fast catch-up before each board meeting** — what changed since the last time they engaged, what's material, what isn't.
- A **signal-quality view of the operating reality** — not a dashboard of metrics, but a curated read of risk, opportunity, and recommendation flowing from the Executive's cycle.
- A **post-meeting trail** that closes the loop: minutes, decisions, follow-up commitments, and any open questions they raised that still need an answer.

The Executive flow generates most of the substantive material the NED needs. The NED-side surfaces are therefore mostly **read-and-react** rather than authoring. Authoring on the NED side is constrained to:
- Private notes on a board pack (the NED's own running judgement, never shared back to the Executive).
- Questions the NED wants to raise in the meeting or carry forward.
- Mark-up against an executive's draft answers ("ready to discuss" / "needs sharpening" / "not yet" — the NED's view, kept private until they choose to share).

---

## 3. Journey 1 — NED catch-up (pre-board)

### 3.1 Intent
> "I have a board meeting on Thursday. Get me ready in 30 minutes."

### 3.2 Surfaces in scope

Three surfaces, in this order:

**a. Briefing pre-read.** The NED sees the Executive's most recent **Draft Compilation Output** for this board, rendered in the same restraint-voice editorial pattern as the executive's drawer (Phase E pattern, Phase C.1 width). The NED can read straight through, mark sections as *understood* / *want to discuss* / *not yet*, and add private notes against any section. Marks and notes are NED-private — they do not flow back to the executive, do not appear in the executive's audit trail, and are never used to retrain anything.

**b. Questions to ask.** A short, AKKI-curated list of questions the NED should consider raising. Sources:
- The executive's storyline (Phase D scoreboard), specifically the *weak* and *missing* items.
- The Pulse signals from the active context, filtered to *critical* and *new* freshness only (Phase F).
- Open questions surfaced from prior minutes that have not been answered in the new pack.

The list is short by design — five to seven questions, not twenty. Each question carries the source signal as a citation chip the NED can click to see the underlying material.

**c. Signals worth digging into.** A second, narrower list of signals that didn't surface as questions but that AKKI flags as worth a closer look — usually because a related signal moved during the cycle, or because the NED's own past notes have flagged this topic. Same restraint-voice — short list, citations on every line.

### 3.3 What AKKI does NOT do here

- AKKI does not produce a "read this for the meeting" auto-summary that competes with the executive's draft compilation. The compilation is the canonical artefact. AKKI's job on the NED side is to help the NED **engage with** it, not replace it.
- AKKI does not auto-generate questions the NED is "supposed" to ask. The list is curated — AKKI surfaces what looks material, the NED decides what to raise.
- AKKI does not score the NED's preparation. Catch-up is a private surface.

---

## 4. Journey 2 — Cycle monitoring (during + post-board)

### 4.1 Intent
> "The meeting just happened. What was decided, what's outstanding, what changed?"

### 4.2 Surfaces in scope

**a. Minutes consumption.** When the executive uploads minutes (or these arrive via the inbound forwarding alias), the NED gets:
- A single-pane reader showing the minutes against the previous Draft Compilation Output side-by-side. AKKI marks where the meeting **landed differently** from the draft (a deferred decision, a changed action, a new commitment) — these diffs are the high-value reads.
- A **commitments list** auto-extracted from the minutes — who owns what, by when. This list is read-only on the NED side.
- A **decisions log** — the resolutions and material judgements made, citation-ready against the minutes paragraphs.

**b. Open questions ledger.** The NED's questions from the meeting (whether self-marked from the catch-up surface or flagged in the minutes) are tracked here until they are answered. Each row carries:
- Question text + cycle context.
- Owner on the executive side (auto-derived from the agenda item the question was raised against).
- Status: *open* / *partly answered* / *answered* / *closed without answer*.
- Latest material that AKKI thinks bears on it (linked from the Document Journal).

**c. Cycle drift signal.** A slow-moving read on whether the cycle is trending **toward** or **away from** the executive's previously stated direction. This is a single-line read with two or three pieces of evidence; not a dashboard. Sources are the Executive's Draft Compilation Outputs across cycles plus the Pulse signal stream.

---

## 5. Consuming the Executive Cycle — read contracts

The NED-side surfaces **read** the same data the Executive flow writes. There are no NED-only writes to the Executive's collections. The contract:

| NED surface | Reads from | Read shape |
|---|---|---|
| Briefing pre-read | `db.work_studio_exports` (kind=report, source=cycle_compilation), `db.cycle_agendas` | Latest complete compilation for a context the NED has membership on. |
| Questions to ask | `db.cycle_agendas` (items+readiness rollup), `db.signals` (active context), `db.solva_v2_sessions` (any open questions tagged `from_signal`) | Curated subset, max 7 items. |
| Signals worth digging into | `db.signals` (active context only — Privacy Wall floor) | Filtered to "needs attention" heuristics. |
| Minutes consumption | `db.documents` (kind=minutes), `db.work_studio_exports` (last cycle's compilation) | Latest minutes plus the prior compilation, side-by-side. |
| Commitments + decisions log | Auto-extracted from minutes via the existing minutes pipeline (`backend/routers/prepare.py:minutes/*`) | Same extracted-fact rows the executive sees. |
| Open questions ledger | `db.cycle_followups` (sent), `db.audit_log` (questions raised) | Joined view; NED-side annotations stored separately (NED-private — see §6). |
| Cycle drift signal | `db.work_studio_exports` historical, `db.signals` historical | Aggregation; cached. |

The shape above means the NED-side build is mostly **new endpoints that read from existing collections** plus a small NED-private collection for the catch-up annotations.

---

## 6. Trust + data-isolation rules

These rules are non-negotiable. They come straight off the Privacy Wall design (paused but its contracts hold) and the existing context-membership posture.

### 6.1 NED-private writes are NED-private

Every NED catch-up annotation, mark, private note, and question-mark-status update writes to a **NED-private** collection (`db.ned_annotations`, scoped to `account_id` + `context_id`). Executives in the same context **must never** see these annotations. This is enforced by:

- The endpoint never resolving annotations except for `account_id == current_user.id`.
- The annotations never appearing in any aggregate or audit row visible to anyone except the NED themselves.
- The annotations being excluded from any LLM grounding pulled into the executive's flow.

### 6.2 Cross-context membership is the Privacy Wall floor

A NED who sits on three boards has three context memberships. Their catch-up surface for **board A** must not surface signals, minutes, or commitments from **board B** under any circumstance, even if both contexts are owned by the same parent organisation. The **`X-Active-Context` header** is the only authority for which board the NED is currently looking at — same posture every other surface in the app already uses.

Cross-context aggregation (e.g. "across the three boards I sit on, what are the common signals?") is **deferred to the Privacy Wall workstream**. The NED-side build does **not** ship cross-context features until that workstream lands.

### 6.3 Read-only reads do not bleed into write surfaces

The NED's catch-up reads do not cause writes on any executive-side collection. Specifically:

- Marking a section "want to discuss" does not write anything to `db.documents` or `db.work_studio_exports`.
- Adding a private note does not increment any view counter the executive can see.
- Flagging a question as "open" on the NED ledger does not create a new follow-up draft for the executive — that decision remains the executive's.

### 6.4 The audit trail respects role boundaries

NED actions land in `db.audit_log` with `actor_role: "ned"` and `surface: "ned_*"`. The executive's audit-trail UI filters these out by default. The platform admin audit view shows everything. This matches the existing per-tab role gating (`require_role("ned")` / `require_role("executive")`) used throughout the app.

---

## 7. Sequencing — what to build, in what order

If engineering takes this design forward, the sensible build order is:

1. **NED-private annotations** — `db.ned_annotations` + the small set of endpoints to write/read against an artefact id. This is the foundation; every catch-up surface depends on it.
2. **Briefing pre-read** — the read-only page that renders the executive's last compilation with the annotations layered on top. No new content generation.
3. **Questions-to-ask surface** — the curated list with citations. Reads from agenda + signals; no new collections.
4. **Open questions ledger** — joins `cycle_followups` and `audit_log` rows; NED-private annotations layer on top.
5. **Minutes consumption + diff** — most engineering-heavy. Reuses the existing minutes pipeline; the diff view is new.
6. **Cycle drift signal** — last because it depends on accumulated history.

Each surface ships behind a feature flag on the NED home page so the rollout can be staged.

---

## 8. Out of scope for this design (and why)

- **Cross-context aggregation** — deferred to Privacy Wall (D-003 boundary).
- **NED-side writing back to the executive's draft** — explicitly not a feature. The executive's voice is the executive's. The NED can raise questions; they can't edit the draft.
- **Auto-summaries of the briefing pre-read** — already covered by the executive's compilation. AKKI does not produce a competing read.
- **Calendar integration for board meetings** — deferred to the Organisational tier, same as Cycle Manager invites (D-001 boundary).
- **NED-side OAuth / inbound mail aliases** — same.
- **Re-scoring the executive's contributions from the NED side** — explicitly not a feature. Scoring is the executive's tool for their own cycle; surfacing it to the NED would change its purpose.

---

## 9. Open design questions (for the next workstream lead)

- Does the NED catch-up reset between boards in a portfolio? Yes per `X-Active-Context`, but the cycle drift signal might benefit from a small portfolio-level read (which would require Privacy Wall). Document the limitation; defer the read.
- How long do NED-private annotations live? Recommendation: indefinitely while the membership exists, deletable on demand by the NED. Hard-deleted when membership ends.
- Should the question-to-ask surface support voice notes (verbal capture instead of text)? No — would compete with chat and add complexity. Text-only at launch.
- Do we ship a separate NED home page or extend the role-aware home dispatcher? Extend the dispatcher (`pages/AppHome.jsx` already routes to `HomeNed.jsx`) — the catch-up surfaces become widgets on that page, plus full-page links.

---

**End of design document.** No code changes accompany this file.
