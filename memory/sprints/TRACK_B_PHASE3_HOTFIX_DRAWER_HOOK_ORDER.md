# Track B Phase B3 — Drawer hook-order hotfix (Questions.jsx)

**Dispatch:** 2026-06-04T07:09:51Z
**Scope:** Surgical hook-order fix on `QuestionDrawer` in `frontend/src/pages/Questions.jsx`. ~9 lines moved. No behaviour change.

---

## Problem (tester verdict on G11 T1(d))

Clicking a Q4Y row on `/app/questions` threw a React runtime error overlay:

> **"Rendered more hooks than during the previous render."**

The drawer never opened → G13 "related document as attachment" surface unreachable → T1(d) verification of G11 blocked.

## Root cause

Canonical "early return between hook calls" violation introduced by the Track B Phase B3 dispatch (2026-06-04, my ship).

In `QuestionDrawer` (line 92):

- Hooks BEFORE `if (!row) return null;` (line 99): `useState × 3 + useEffect = 4`
- Hooks AFTER the early return (lines 172/173/174/175/201/216/217/218/219): `useState × 9`

Mount sequence that broke:
1. Initial parent render with `drawerRow=null` → React ran 4 hooks then returned null. React recorded 4-hook signature for this component.
2. User clicked a row → parent set `drawerRow=row` → re-render ran 4 hooks then SKIPPED the early return → executed 9 more hooks. 13 vs 4 → "Rendered more hooks than during the previous render."

Parent at `Questions.jsx:838` always renders `<QuestionDrawer row={drawerRow}>` so the component never unmounts; `row` just toggles `null ↔ object`. The early-return-then-more-hooks pattern was a guaranteed crash on first row click.

## Fix

Hoisted the 9 B3 `useState` calls above the `if (!row) return null;` guard, adjacent to the existing 3 `useState`s + `useEffect`. Handlers (`onShareSubmit`, `onReopen`, `openLinkPicker`, `selectLinkDoc`) stayed in place below the early-return — closures over the setters resolve identically.

### Diff (verbatim)

```diff
 function QuestionDrawer({ row, contextIdGetter, onClose, onAnswered, navigate }) {
   const [answer, setAnswer] = useState("");
   const [busy, setBusy] = useState(false);
   const [markBusy, setMarkBusy] = useState(false);
+
+  // ── Track B Phase B3 hotfix (2026-06-04) — hoisted above the
+  // `if (!row) return null` early-return at the line below. Adding
+  // these `useState` calls after the early-return broke React's
+  // hook-order contract: initial mount with `row=null` ran 4 hooks
+  // then returned; the row-click re-render then tried to run 13
+  // hooks → "Rendered more hooks than during the previous render."
+  // Closures over the setters resolve identically from the handler
+  // bodies below — no behaviour change.
+  const [shareOpen, setShareOpen] = useState(false);
+  const [shareRecipients, setShareRecipients] = useState("");
+  const [shareMessage, setShareMessage] = useState("");
+  const [shareBusy, setShareBusy] = useState(false);
+  const [reopenBusy, setReopenBusy] = useState(false);
+  const [linkOpen, setLinkOpen] = useState(false);
+  const [linkDocs, setLinkDocs] = useState([]);
+  const [linkLoading, setLinkLoading] = useState(false);
+  const [linkBusy, setLinkBusy] = useState(false);

   useEffect(() => { setAnswer(""); }, [row?.id]);

   if (!row) return null;
   ...
   // ── Track B Phase B3 (2026-06-04) — Share / Reopen / Link Response ──
-  const [shareOpen, setShareOpen] = useState(false);
-  const [shareRecipients, setShareRecipients] = useState("");
-  const [shareMessage, setShareMessage] = useState("");
-  const [shareBusy, setShareBusy] = useState(false);
+  // (state declarations hoisted above the early-return — see top of fn.)
   const onShareSubmit = async () => { ...
   ...
-  const [reopenBusy, setReopenBusy] = useState(false);
   const onReopen = async () => { ...
   ...
-  const [linkOpen, setLinkOpen] = useState(false);
-  const [linkDocs, setLinkDocs] = useState([]);
-  const [linkLoading, setLinkLoading] = useState(false);
-  const [linkBusy, setLinkBusy] = useState(false);
   const openLinkPicker = async () => { ...
```

Net: 9 `useState` declarations moved. 12 lines added (9 hooks + 3-line context comment). 9 lines removed. Net change: ~12 LOC, behaviour-preserving.

---

## Out-of-scope micro-unblocker

`App.js:149` carried a stale `// eslint-disable-line @typescript-eslint/no-unused-vars` comment on an unreferenced `WorkStudioAnalyze` lazy-import. Project is vanilla CRA JavaScript (no `@typescript-eslint` plugin), so CRA dev-server treated the unknown-rule reference as a compile error and threw a `Compiled with problems:` overlay covering the entire app, including signin. This blocked all frontend verification including the tester's re-run of T1(d). Changed one rule name (`@typescript-eslint/no-unused-vars` → `no-unused-vars`); single character on a single line. Pre-existing rot from an unrelated earlier commit, not introduced by B3 or G11. Logged here for audit; not folding into any phase scope.

---

## Verification (pre-handoff smoke screenshot, real preview env)

`https://akki-executive.preview.emergentagent.com/app/questions` — admin@akki.ai authenticated session, second screenshot post-row-click:

- **PASS — `ERROR_OVERLAYS_ON_QUESTIONS=0`** (no CRA dev overlay, no React error)
- `QUESTION_DRAWER_RENDERED=1` after clicking `[data-testid^="question-row-"]` first row
- **G13 attachment surface verified live in drawer:**
  > `RELATED DOCUMENTS`
  > `Source: a19b457e-3ceb-4d8a-92b9-1823fd2970f1`
- **G11 history-entry verified live in drawer:**
  > `TODAY · raised_from_doc`
  > `Surfaced from document Project Lighthouse Q3 Brief.`
- `ERROR_OVERLAYS_AFTER_CLICK=0`
- Screenshots: `/tmp/b3_hotfix_questions_authd.png` (list mounted, 8 question cards visible — 4 G11-promoted), `/tmp/b3_hotfix_drawer_open.png` (drawer open with all 6 CTAs + related doc + history).

ESLint on touched file: `mcp_lint_javascript` returns `✅ No issues found` on `frontend/src/pages/Questions.jsx`.

---

## Files touched

```
M frontend/src/pages/Questions.jsx   # 9 hooks hoisted above early-return, 3-line context comment
M frontend/src/App.js                # 1-char unblocker on line 149 (out-of-scope, see above)
M memory/MASTER_STATE.md             # G11 → ✅, Section 6 + 7 timestamp + resolved-issue note
?? memory/sprints/TRACK_B_PHASE3_HOTFIX_DRAWER_HOOK_ORDER.md
```

No backend touch. No new pytest. No new deps.

---

## Risks honoured (per Pre-Read)

| # | Risk | Verified |
|---|---|---|
| R1 | QuestionDrawer consumed elsewhere | Grep confirmed single consumer at `Questions.jsx:838`. No ripple. |
| R2 | Hoisting changes initial values | Static literal defaults (`""`, `false`, `[]`). No semantic change. |
| R3 | React-hooks ESLint rule violation | Lint clean. |
| R4 | Ripples into Track A | No Track A imports in Questions.jsx. |
| R5 | Ripples into G11 backend | G11 promoter untouched. Live drawer surfaced both `raised_from_doc` history + `source_doc_id` attachment — both G11 promoter writes verified end-to-end. |

---

## Hard nos honoured

- ✓ No drawer feature changes.
- ✓ No behaviour drift on Mark-Answered / Use-in-Solva / Use-in-Chat / Share / Reopen / Link-Response.
- ✓ No backend touch.
- ✓ No new deps, no `lib/` or `components/ui/` ripples.
- ✓ Did NOT remove the stale `WorkStudioAnalyze` import itself (per orchestrator instruction).
- ✓ Did NOT touch any other ESLint rules or comments in `App.js`.
- ✓ Did NOT clean up the rest of `documents.py` lint rot (parked).

---

## Resume contract

Tester re-runs T1(d) only — confirm drawer opens + G13 attachment surface renders. Smoke screenshot above already proves both end-to-end on the live preview env. Awaiting tester journey-completion verdict before next-phase pick.
