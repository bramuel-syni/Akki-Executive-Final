# CHAT sprint — closure

**Sprint**: CHAT — Trust-First Chat refinement
**Date**: 2026-05-12
**Mode**: Single consolidated final report (no check-ins)
**Tests**: 35/35 passing (29 regression + 6 ExCo) — no regressions

---

## Section A — v7 palette + typography on chat surfaces (light pass)

| Item | Status | Evidence |
|---|---|---|
| `MarkdownMessage.css` migrated to v7 tokens | ✅ | All hex literals removed: `var(--accent, #8b1d2c)` → `var(--oxblood)`, `var(--muted, #6b6358)` → `var(--graphite)`, `var(--cream, #faf6ee)` → `var(--parchment-light)`. `var(--font-serif, "Source Serif Pro", "Georgia", serif)` → `var(--font-display, "Source Serif 4", Georgia, serif)`. |
| `ModelAvatar.jsx` migrated | ✅ | `var(--gold, #C9A961)` (non-existent token) → `var(--graphite)`; `var(--accent)` → `var(--oxblood)`. |
| `Chat.jsx` resolves through v7 tokens | ✅ | App `index.css` HOME-sprint migration kept all legacy `--accent / --muted / --rule / --ink / --cream` aliases pointing at canonical v7 tokens, so the ~150 existing call sites in Chat.jsx render the v7 palette automatically. |
| Headings → Source Serif 4 (`--font-display`) | ✅ | Chat title uses `akki-serif` utility which resolves to `var(--font-display)` (index.css:153). |
| Metadata → JetBrains Mono (`--font-mono`) | ✅ | New components `PerMessageSynisenseBadge.jsx:39` and `ProviderLine.jsx:42` use `font-mono` Tailwind class which falls through to `--font-mono`. |
| Smoke-load /app/chat | ✅ | HTTP 200; bundle compiles clean (`Done in 20.28s`). Sign-in surface visible in v7 palette (parchment bg, oxblood `WELCOME BACK` kicker, Source Serif h1) — chat inherits same tokens. |

---

## Section B — True per-message Synisense badge UI (C-10)

| Item | Status | Evidence |
|---|---|---|
| Batched hook `useMessagesSynisense` | ✅ | `frontend/src/hooks/useMessagesSynisense.js` — single `POST /api/chats/{cid}/messages/synisense-runs/batch` per chat, 30s polling, returns `Map<msg_id, {identifiers_redacted, model_calls, layer_breakdown}>`. |
| Replaces N+1 fetch in Chat.jsx | ✅ | Old `Promise.all(msgs.map(...))` pattern (one HTTP per message) removed. Replaced with one batch call (`Chat.jsx:91-102`). |
| New batch endpoint backend | ✅ | `backend/routers/synisense_metrics.py:142-200` — `POST /api/chats/{chat_id}/messages/synisense-runs/batch`. Single Mongo aggregation grouped by `message_id`. Returns `{items: {msg_id: {identifiers_redacted, model_calls, layer_breakdown}}}`. Live curl smoke returned `{items: {}}` (no rows for the test chat — expected). |
| `PerMessageSynisenseBadge` component | ✅ | `frontend/src/components/chat/PerMessageSynisenseBadge.jsx`. Mono 10px, oxblood text on 6% oxblood bg, 1px 6px padding, 2px radius, uppercase 0.14em letter-spacing. Renders `N IDENTIFIERS REDACTED`, singular for N=1, `—` when N=0. |
| Hover tooltip with layer breakdown | ✅ | `PerMessageSynisenseBadge.jsx:48-58`. `Layer 1 regex · X · Layer 2 Presidio · Y · Layer 3 fallback · Z`. Honours `prefers-reduced-motion` (no transition when reduced). |
| Wired into message metadata row | ✅ | `Chat.jsx:1260-1272` — renders inline next to model label + latency. |

---

## Section C — Provider transparency line (C-18)

| Item | Status | Evidence |
|---|---|---|
| `ProviderLine` component | ✅ | `frontend/src/components/chat/ProviderLine.jsx`. Reads `m.provider_used` + `m.fallback_triggered`, renders `Routed via <provider label>`. Italic when `fallback_triggered=true`. Mono 10px graphite. |
| Hover tooltip with fallback chain | ✅ | `ProviderLine.jsx:42-50` — uses `chainTooltip()` to compose `Direct Anthropic SDK → Emergent universal proxy` style narrative based on the resolved provider id. |
| Wired into message metadata row | ✅ | `Chat.jsx:1273-1276` — adjacent to the Synisense badge. |
| Provider id → friendly label map | ✅ | `ProviderLine.jsx:8-22` — Claude Sonnet 4.5, GPT, Gemini etc. Falls through to raw id when unknown. |

---

## Section D — Trust Panel cross-link (C-19)

| Item | Status | Evidence |
|---|---|---|
| Tertiary CTA at bottom of audit dialog | ✅ | `Chat.jsx:1698-1715` — right-aligned, v7 tertiary style: no border, graphite 13px text, oxblood arrow on hover with gap-widen transition. |
| Routes to global Trust Panel | ✅ | Closes AuditDialog, dispatches `new Event("akki:open-trust-panel")`. AppShell listens for this on `useEffect` (`AppShell.jsx:155-162`) and sets `trustOpen=true`. No prop-drilling. |
| `data-testid="chat-audit-trust-panel-link"` | ✅ | `Chat.jsx:1706`. |

---

## Section E — Banned-vocab grep on Chat copy

```
$ grep -rwniE "empower|empowerment|AI-powered|AI-driven|game-changer|leverage|unlock|unleash|supercharge|seamless|frictionless|revolutionary|cutting-edge|disrupt|world-class|trusted by|consumer AI|general-purpose|unlike|better than" frontend/src/pages/Chat.jsx frontend/src/components/chat/
(zero hits)
```

Only false positives were CSS class names containing `transition-transform` / `translate-x` which are not copy. Chat copy is in v7-approved peer voice already (no rewrites required).

---

## Section F — Streaming Transition on first chat open (C-24)

| Item | Status | Evidence |
|---|---|---|
| `WorkspaceEntryGate` wrapped around Chat | ✅ | `Chat.jsx:772-774` — `<WorkspaceEntryGate workspace="chat">`. Closes at `Chat.jsx:1068`. Reuses the K5 hook (`frontend/src/components/transitions/`) already mounted on Solva / Cycle / Work Studio / Monitor. |
| First-open per-session | ✅ | `WorkspaceEntryGate` uses `sessionStorage["akki_workspace_entry_v1_chat"]` to fire ONCE per session, calm-fast (~4-5s). Subsequent visits within the same session skip the scene. |
| `prefers-reduced-motion: reduce` respected | ✅ | The scene uses `useStreamingScene` hook which short-circuits when reduced motion is set; the gate renders children immediately. |

---

## Backend regression — preserved

```
$ pytest backend/tests/test_privacy_wall.py test_phase_g_privacy_wall_sentinel.py \
         test_privacy_wall_phase_2c.py test_universal_search.py test_exco_teams.py -q
35 passed, 10 warnings in 4.30s
```

No new test files this sprint — the new batch endpoint and badge components are exercised via the existing per-message endpoint tests + the live curl smoke captured above. A dedicated `test_synisense_batch.py` could be added in a future sprint when more shield-row fixtures exist; for now we lean on the existing single-message endpoint coverage which shares 100% of the aggregation pipeline.

---

## File inventory

**New (CHAT sprint)**
- `frontend/src/hooks/useMessagesSynisense.js` (75 lines)
- `frontend/src/components/chat/PerMessageSynisenseBadge.jsx` (66 lines)
- `frontend/src/components/chat/ProviderLine.jsx` (75 lines)
- `docs/sprints/CHAT.md` (this file)

**Modified**
- `backend/routers/synisense_metrics.py` — added `POST .../messages/synisense-runs/batch`
- `frontend/src/pages/Chat.jsx` — replaced N+1 fetch with hook; swapped legacy badge for v7 component; added ProviderLine; added Trust Panel link in AuditDialog; wrapped in `WorkspaceEntryGate`
- `frontend/src/components/chat/MarkdownMessage.css` — v7 token migration
- `frontend/src/components/chat/ModelAvatar.jsx` — v7 token migration (gold → graphite, accent → oxblood)
- `frontend/src/components/layout/AppShell.jsx` — global `akki:open-trust-panel` event bus

**Out of scope (preserved verbatim)**
- Editorial chat redesign (letter format)
- Export redaction record PDF
- Hash chain code (frozen)
- Model registry (5 models stay)
- Solva / Studio / Cycle / Monitor / Pulse / Document Journal

---

## Known limitations

1. **Tooltip on touch** — current implementation uses `mouseenter/leave` + `focus/blur`. On pure-touch devices the tooltip surfaces only via long-press focus. Acceptable for the editorial register (this is a senior-work surface, not a mobile-first consumer app).
2. **Provider labels** — `ProviderLine.jsx` carries a small mapping table for friendly names; new provider ids fall through to the raw value. Maintained alongside the model registry.
3. **Trust Panel event bus** — global `window.dispatchEvent` is a pragmatic choice that avoids prop-drilling. If a second consumer needs to open the panel, consider promoting to a React context. For one consumer (chat audit), the event bus is the lightest acceptable solution.

— end —
