# Trust Center — De-identification counting methodology

**Status:** authoritative reference for Shield's two complementary views.
**Scope:** the in-product transparency note added 2026-05-25 under sprint chunk (d).
**No behavior change** — this is purely documentation of an existing field.

---

## Why two numbers exist

Trust Center surfaces two complementary de-identification counts for every chat session:

1. **Session-level headline counter** — the "Identifiers shielded" tile at the top of the session view. Source: `synisense_audit_log.de_id_summary` (or the equivalent aggregate computed by the audit query layer when the chat was recorded live).
2. **Per-turn drill-down** — the count shown inside each per-turn evidence row. Source: the audit row written at the time the turn was processed.

These two are **not** redundant. They answer **different questions**, against the same underlying audit chain.

| View | Question it answers | What gets counted |
| --- | --- | --- |
| Session-level (`de_id_summary`) | "How many distinct identifiers did Shield touch in any role across this session?" | Every place Shield processed data for the session — turn input PLUS historical context replay PLUS grounding material |
| Per-turn drill-down | "How many identifiers did Shield touch at this exact turn boundary?" | Only what Shield processed at the turn itself |

Because session-level counts everything Shield touched (including historical context + grounding replay), the session total is a **superset** of the sum of per-turn counts. The difference is not a bug; it reflects that Shield's protection extends beyond just the user's turn input.

---

## Why the session total is the *right* number for the headline

Real LLM calls don't just see the user's current turn — they see:

- The user's input text for this turn (counted per-turn).
- The chat's full historical context replayed on every turn so the model has continuity (counted in the session total but NOT per-turn).
- Grounding material — uploaded documents, citations, search snippets — re-passed on every turn the user wants the model to consider it (counted in the session total but NOT per-turn).

If we showed only the per-turn sum on the headline, an auditor would systematically under-count Shield's actual coverage. The session total is the honest answer to *"How much of your sensitive data did Shield touch this session?"* — which is the headline question.

---

## Why both views are kept

An auditor drilling into a specific turn needs the turn-local count to verify a claim like *"at 09:14:22 UTC, Shield masked 3 person names"*. The session-level total would over-count for that question because it would include the context replay around that turn.

Trust Center therefore keeps **both** and labels them clearly:

- Session-level headline tile carries an `Info` affordance (lucide-react `Info` icon → click → popover) that explains the gap.
- Per-turn detail section carries a one-line note immediately under the heading that points back at the session total.

The popover and inline note are required structural elements per the DOM-unconditional rendering rule (`/app/memory/sprints/T1_T5_HORIZONTAL_SPRINT_CLOSEOUT.md` §5.1). They render unconditionally regardless of whether the chat has any redacted turns.

---

## Underlying audit-log fields

The fields are stable across the Shield v1.x audit chain. See `services/synisense/audit.py` and `services/trust_center.py` for the writers + readers.

| Audit field | Populated by | Read by |
| --- | --- | --- |
| `synisense_audit_log.de_id_summary` | `services/synisense/audit.py::write_audit_with_chain` (session-level aggregate computed across the chain) | `routers/trust_center.py::get_session_promise` → `data.promise_summary.identifiers_shielded_total` |
| `synisense_audit_log.turn_metadata.deidentified_pii_classes` | Same writer, per-turn entry | `routers/trust_center.py::get_session_promise` → `data.turns[*]` |
| `synisense_audit_log.de_id_summary.by_class` | Aggregate of all per-class counts across the session | `routers/trust_center.py::get_session_promise` → `data.promise_summary.by_class` |

**No migration was performed.** The methodology note is UI-only — the underlying numbers and writers are unchanged.

---

## Final UI wording (verbatim — anchored for test assertions)

### Popover content (testid: `tc-deidsummary-info-content`)

Heading: **"How this count is built"**

Body:

> Session totals count every place Shield touched data — including historical context and grounding replay for this session. Per-turn totals below count only what Shield processed at each specific turn.
>
> Both views are factually accurate to their question; expect the session total to be a superset of the sum of per-turn counts.

### Per-turn drill-down inline note (testid: `tc-perturn-deviation-note`)

> Per-turn counts. Session totals above may be larger because they include historical context and grounding replay.

### Required keyphrase anchors (for stable test assertions)

The popover content MUST always contain (case-insensitive):

- `"Session totals"` — anchors the source-of-truth phrasing.
- `"per-turn"` — anchors the contrast.
- `"superset"` — the audit-anchor word that captures the math.
- `"historical context"` — anchors what's included in the session view.
- `"grounding replay"` — anchors the other inclusion.

The per-turn note MUST contain (case-insensitive):

- `"Session totals above"` — points the user back to the headline.
- `"historical context"` and `"grounding replay"` — same audit-anchor phrases.

---

## What this change is NOT

- **NOT** a schema change. `synisense_audit_log.de_id_summary` keeps its existing shape.
- **NOT** a recount. No audit row was rewritten.
- **NOT** a behavioral change to `services/synisense/deidentifier.py`, `services/synisense/canonical.py`, `services/synisense/audit.py`, `routers/trust_center.py`, or any other guardrail file.
- **NOT** a backfill. Past sessions keep their existing numbers; the popover simply explains why those numbers look the way they do.

This is pure transparency.

---

## Audit standards reference

The methodology note satisfies the following standards-mapping that Trust Center already exposes in the page footer:

- **SOC2 CC4** — Monitoring activities: counter methodology is now self-documenting from inside the product.
- **GDPR Art. 5(2)** — Accountability principle: the controller (operator of Akki) can demonstrate that the headline number is computed honestly and the auditor can drill in to verify.
- **NIST AI RMF Map-3.4** — Risks of AI-generated content tracked & documented: the difference between session-level and per-turn coverage is now visible to the user without leaving the product.
- **EU AI Act Art. 50** — Transparency obligations: the in-product affordance makes the counter's question + answer plain-language for non-technical stakeholders.

---

## Change history

- **2026-05-25** — chunk (d) closure. Added `<DeIdSummaryInfoPopover />` next to the "Identifiers shielded" Counter and the `tc-perturn-deviation-note` one-liner under "Per-turn detail". No backend change. Logged in `/app/memory/sprints/D_LOG.md`.
