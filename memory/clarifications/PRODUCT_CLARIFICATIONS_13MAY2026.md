# Product Clarifications — 13 May 2026

> 17 product-owner decision items surfaced during the 13 May QA review.
> For each item the team applied a **best-guess default** so the QA-fix
> sprint is not build-blocked, and now needs explicit PO sign-off.
>
> Shareable in markdown. Reply against each item under "Awaiting PO
> response" to lock the answer; the team will then update implementations
> and SYSTEM_STATE §6 as autonomous-decisions-confirmed.

---

## How to read this doc

* **Question** — the raw ambiguity, phrased so a fresh reader can answer.
* **QA reference** — which findings depend on this decision.
* **Default applied** — what the implementation currently assumes (or will assume) until you respond.
* **Rationale** — one-line "why this default makes sense for now".
* **Dependent QA findings** — the QA report items that won't be fully closed until you weigh in.
* **Awaiting PO response** — leave-blank placeholder for your answer.

---

## 1 — Bell icon function

**Question**
The top-bar bell currently routes to the Brief Review Centre. QA testers expected a notifications / mentions feed (assignments, @-mentions, system updates). What should the bell *do*?

**QA reference**
MS-R01.

**Default applied**
Bell shows a notifications drawer (assignments + @-mentions + system updates). Brief Review Centre keeps its own dedicated entry point in the workspace nav.

**Rationale**
Bell icon conventionally means "what's new for me?". Re-purposing it for Brief Review violates user expectation; the QA finding came from a tester who interpreted it the conventional way.

**Dependent QA findings**
MS-R01.

**Awaiting PO response**: _(blank — pending)_

---

## 2 — Contributors recognition on Work Studio

**Question**
A user "is a contributor" on a brief / pack — by what criteria? Editor? Assignee? Author of the source document? All of the above?

**QA reference**
Work Studio (WS) clarifications block.

**Default applied**
Contributor = anyone who (a) edited the artefact, OR (b) was explicitly assigned to it, OR (c) is listed as a contributor on a source document that was used to compile the artefact.

**Rationale**
Most generous reasonable definition; matches how most board-pack workflows acknowledge supporting authors.

**Dependent QA findings**
WS clarifications.

**Awaiting PO response**: _(blank — pending)_

---

## 3 — "The rail" naming

**Question**
WS-R03 says "Board Pack appears on the rail" but new users don't know what "the rail" refers to. Should the noun stay, or rename?

**QA reference**
WS-R03.

**Default applied**
Rename "the rail" → **"the Compilation panel"** in copy across the product. Keep the right-side sticky position.

**Rationale**
"Compilation panel" is self-describing; "rail" is internal jargon.

**Dependent QA findings**
WS-R03.

**Awaiting PO response**: _(blank — pending)_

---

## 4 — Composer Review → Approve workflow

**Question**
The Composer currently shows a Review CTA which keeps the user in the composer with a follow-up Approve CTA. Is Review meant to be a read-only validation step, and is Approve the "ship it" commit?

**QA reference**
Composer clarifications block.

**Default applied**
Review = read-only validation view (shows the rendered artefact with no edit affordances). Approve = commits the artefact to `compiled` status and writes an audit-trail row.

**Rationale**
Two-step gate (read → confirm) prevents accidental publishes; matches the Cycle approve flow already in production.

**Dependent QA findings**
Composer.

**Awaiting PO response**: _(blank — pending)_

---

## 5 — "Daily Review" and "public" meaning

**Question**
The Composer references a "Daily Review" surface and a "public" attribute. What do those mean to a user?

**QA reference**
Composer clarifications block.

**Default applied**
* **Daily Review** = a per-user inbox listing artefacts awaiting the user's review today (with snooze + skip + review CTAs).
* **public** = visible to everyone in the workspace (vs `personal` = visible only to the author until shared).

**Rationale**
Matches how the Cycle module already uses similar nouns; reduces new-vocabulary load.

**Dependent QA findings**
Composer.

**Awaiting PO response**: _(blank — pending)_

---

## 6 — Document → Work Studio transition

**Question**
When does an uploaded document show up in Work Studio? Always? Only after a Brief is created? Only after explicit promotion?

**QA reference**
WS general.

**Default applied**
A document appears under the Work Studio Briefing tab **once a Brief has been generated from it**. Uploaded-only documents stay in Document Journal until then. After Brief generation, surface a toast: *"Document now available in Work Studio Briefing."*

**Rationale**
Avoids cluttering Work Studio with raw uploads; keeps Document Journal as the source-of-truth for the raw asset; Brief generation is the natural pivot point.

**Dependent QA findings**
WS general.

**Awaiting PO response**: _(blank — pending)_

---

## 7 — Pulse Save vs Bookmark

**Question**
Pulse offers both Save and Bookmark actions. What's the distinction? Are both needed?

**QA reference**
Pulse (general).

**Default applied**
* **Save** = persistent personal note attached to the signal ("this matters to me; surface it again later"). Pinned to a user-specific saved view.
* **Bookmark** = quick reference for the current session only; cleared on log-out or after 24 h.

**Recommendation**: if the distinction is too thin for users, **collapse to Bookmark only** (one verb, one mental model). Recommend collapse.

**Rationale**
QA finding flagged user confusion. Two actions that look identical create cognitive overhead. Collapse is the safer default.

**Dependent QA findings**
Pulse.

**Awaiting PO response**: _(blank — pending)_

---

## 8 — Pulse Freshness double-layer

**Question**
Freshness appears both as a top-level filter AND as an option within another filter dropdown. Is that intentional, or a layered-iteration bug?

**QA reference**
Pulse.

**Default applied**
Layered-iteration bug. **Keep the top-level Freshness filter; remove the redundant option from the dropdown.**

**Rationale**
A filter that's also an option inside another filter never reads correctly — users will not predict the intersection. Single source of truth is the right pattern.

**Dependent QA findings**
Pulse.

**Awaiting PO response**: _(blank — pending)_

---

## 9 — Pulse Archive mechanism

**Question**
An Archived tab exists in Pulse but there's no clear archive action anywhere. How does a signal get archived?

**QA reference**
Pulse.

**Default applied**
Add an **Archive** affordance to the signal detail drawer (sitting alongside Resolve). Archiving moves the signal to the Archived tab; Unarchive returns it to the active list.

**Rationale**
Resolve = the matter is closed. Archive = the matter is irrelevant or out of scope, hide without judging it. Both have product value; both deserve explicit affordances.

**Dependent QA findings**
Pulse.

**Awaiting PO response**: _(blank — pending)_

---

## 10 — Pulse "High" badge meaning

**Question**
The "High" badge appears on some signals. High what? Priority? Confidence? Relevance?

**QA reference**
Pulse.

**Default applied**
**High Confidence** — the AI's confidence on the signal's relevance + accuracy combined. (Not user-priority, not severity.)

**Rationale**
Pulse signals are AI-surfaced; the most useful thing to tell the user is "how sure is the engine?". Severity is implicit in the category badge.

**Dependent QA findings**
Pulse.

**Awaiting PO response**: _(blank — pending)_

---

## 11 — Pulse "Across Other Boards"

**Question**
The "Across Other Boards" surface — what's its intended function?

**QA reference**
Pulse.

**Default applied**
A pivot on the active signal that shows how the same signal / topic surfaces in the user's **other workspaces** (cross-portfolio insight). Read-only — clicking through to another workspace is opt-in.

**Rationale**
For a user wearing multiple board hats (advisor / NED across companies), seeing "this concern is appearing in 3 of your other boards too" is a unique value-add only AKKI can offer.

**Dependent QA findings**
Pulse.

**Awaiting PO response**: _(blank — pending)_

---

## 12 — Monitor Performance Score vs Current Score naming

**Question**
Monitor shows both "Performance Score" and "Current Score" in different places. Are they the same thing?

**QA reference**
Monitor.

**Default applied**
Same metric, two names from layered iteration. **Collapse to "Current Score" everywhere.** "Performance Score" is the legacy term and gets phased out.

**Rationale**
The score IS computed at the current moment from current inputs — "Current Score" is the more honest label.

**Dependent QA findings**
Monitor.

**Awaiting PO response**: _(blank — pending)_

---

## 13 — Monitor: should objective status be manually editable?

**Question**
Objective status is currently auto-computed from score + probability + target. Should an owner be able to override it manually?

**QA reference**
Monitor.

**Default applied**
**Yes** — owner can override the auto-computed status, but the override is logged to an audit trail (who, when, old → new value, reason text field). Auto-recompute resumes the moment the owner clears the override.

**Rationale**
Auto-compute is correct for 95% of cases but board owners need an escape hatch (e.g. "score is technically green but I know this is amber based on a private conversation"). Audit trail keeps the system honest.

**Dependent QA findings**
Monitor.

**Awaiting PO response**: _(blank — pending)_

---

## 14 — Monitor "Around the Goals"

**Question**
What's "Around the Goals" supposed to show?

**QA reference**
Monitor.

**Default applied**
A contextual section under each goal showing: (a) recent activity touching that goal, (b) the goal's contributors, (c) linked Pulse signals (signals that the AI thinks relate to this goal).

**Rationale**
Goals don't live in isolation — they're surrounded by the work, people, and signals that feed them. "Around the Goals" surfaces that adjacency without making the user hunt for it.

**Dependent QA findings**
Monitor.

**Awaiting PO response**: _(blank — pending)_

---

## 15 — Cycle Manager Scoreboard — CTA after poor score

**Question**
When a cycle item gets a poor score, what should the reviewer do next? The scoreboard surfaces the score but the next-action isn't obvious.

**QA reference**
Cycle.

**Default applied**
Two CTAs surface when a poor score lands:
1. **"Request rework"** — ships the item back to the original contributor with a notes field for the reviewer to explain what needs to change.
2. **"Mark as accepted with caveats"** — keeps the item in the cycle but flags it amber with a caveat note attached.

**Rationale**
Real-world board cycles need both options. "Reject" is too binary; everything-passes is too lax.

**Dependent QA findings**
Cycle.

**Awaiting PO response**: _(blank — pending)_

---

## 16 — Akki Chat scope — what can it access?

**Question**
What does Akki Chat have access to when answering a user's question?

**QA reference**
Chat.

**Default applied**
Within the **active workspace context only**, Chat can access: documents, briefs, cycles, pulse signals, monitor objectives. **All PII passes through Synisense Shield** before LLM exposure. Chat cannot see other workspaces, cannot see other users' personal drafts, cannot see deleted records.

**Rationale**
Same privacy promise the rest of the product makes; predictable scope. Cross-workspace queries would require the "Across Other Boards" pattern (item 11) which is opt-in.

**Dependent QA findings**
Chat.

**Awaiting PO response**: _(blank — pending)_

---

## 17 — Document tagging — how to tag a team member on upload?

**Question**
A tester asked how to tag a team member when uploading a document. Currently there's no affordance.

**QA reference**
Document Journal.

**Default applied**
Add a **"Tag contributors"** multi-select to the upload modal. The source list is the `team_catalogue` collection (added in Patch 2B.1). Tagged contributors are stored on the document and surface (a) on the document detail drawer, (b) in the Workspace listing row metadata, (c) carry over to any Brief generated from the document.

**Rationale**
Tagging is the bridge between document upload and contributor recognition (item 2). Same underlying source-of-truth.

**Dependent QA findings**
Document Journal.

**Awaiting PO response**: _(blank — pending)_

---

## Status legend

| Item | Default applied | PO response received? |
|---|---|---|
| 1 — Bell icon | ✅ | ⏳ |
| 2 — Contributors recognition | ✅ | ⏳ |
| 3 — "The rail" naming | ✅ | ⏳ |
| 4 — Composer Review → Approve | ✅ | ⏳ |
| 5 — Daily Review + public meaning | ✅ | ⏳ |
| 6 — Document → Work Studio transition | ✅ | ⏳ |
| 7 — Pulse Save vs Bookmark | ✅ | ⏳ |
| 8 — Pulse Freshness double-layer | ✅ | ⏳ |
| 9 — Pulse Archive mechanism | ✅ | ⏳ |
| 10 — Pulse "High" badge | ✅ | ⏳ |
| 11 — Pulse "Across Other Boards" | ✅ | ⏳ |
| 12 — Performance vs Current Score | ✅ | ⏳ |
| 13 — Objective status override | ✅ | ⏳ |
| 14 — Around the Goals | ✅ | ⏳ |
| 15 — Scoreboard CTA after poor score | ✅ | ⏳ |
| 16 — Chat scope | ✅ | ⏳ |
| 17 — Document tagging | ✅ | ⏳ |
| 18 — Committee-level ownership on objectives/projects | ✅ | ⏳ |

— end —

---

## 18. Committee-level ownership on objectives/projects (NEW · added 2026-05-13 during Chunk 6.5-REVISED Task F)

**Context.** Chunk 6.5-REVISED Task F shipped a new Monitor Owner-filter tab strip driven by a `$lookup` against `db.accounts.declared_role`. The canonical owner-role list includes individual roles (CEO / CFO / COO / CCO / CTO / CRO / CIO) plus two committee labels:

- **Audit Committee**
- **Risk Committee**

These last two are committees, not individual roles. With the current `owner_account_id → accounts.declared_role` derivation, a tab named "Audit Committee" only appears if a person's `declared_role` literally equals "Audit Committee" — which is unlikely. `declared_role` in this codebase is typically `executive`, `ned`, `reportee`, or `dual`. **In practice today, none of the canonical CEO-CIO tabs will appear** unless someone is declared with those specific role strings.

**Question for PO.** Should objectives/projects support a separate, optional committee-ownership field — i.e. `owner_committee: Optional[str]` — that lives alongside `owner_account_id`? Three concrete options:

- **(a)** Add `owner_committee` as an optional editable field on the create/edit forms. The Owner tab strip then unions individual-role-derived tabs with committee tabs derived from this new field. (Closest to current PO direction but introduces an editable field, which the original Chunk 6.5-REVISED constraint discouraged.)
- **(b)** Model committee-level review as a separate "review forum" / "review path" attribute distinct from ownership entirely. Tabs only ever reflect individual ownership. Committees surface via a separate UI surface.
- **(c)** Drop "Audit Committee" and "Risk Committee" from the canonical owner-role list. Tabs are individual-role-only. (Simplest; loses the editorial distinction.)

**Default behaviour until resolved**: tabs are emitted only for canonical labels with non-zero counts. "Audit Committee" / "Risk Committee" tabs will simply not appear unless some account is declared with one of those role strings. This is fail-safe but might not match user expectation.

| Asked? | Answered? |
|--------|----------|
| ✅ | ⏳ |

