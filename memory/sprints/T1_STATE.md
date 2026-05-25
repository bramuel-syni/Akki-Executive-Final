# T1 State (in-progress)

## Reconciliation findings (vs brief)
- **Toast utility**: `@/hooks/use-toast.js` + `@/components/ui/toaster.jsx` already in tree (shadcn). REUSE, do NOT create new.
- **T1.2 — `T:*` tags AMBIGUOUS**: `grep -rn 'T:\*'` returns 0 hits in `frontend/src/` and `backend/`. The literal substring is not in source. Three possibilities:
  1. Server-side rendering bleed (an LLM template producing `T:1`, `T:2`, etc. that the docstring captioned as `T:*`)
  2. A Markdown directive that the renderer isn't stripping (e.g. shortcode)
  3. Visual artifact from a placeholder image stamp
  Need user to share the literal text from Figure 7 (or screenshot caption) before fixing. **Surfacing in closeout.**
- All other 5 tasks: file paths + data-testids confirmed on disk.

## Per-task status

| Task | Scope | Status | Files | Evidence |
|---|---|---|---|---|
| T1.1 | Chat input fixed-bottom + responsive | todo | `frontend/src/pages/Chat.jsx` | — |
| T1.2 | Remove `T:*` tags | **BLOCKED — ambiguity** | tbd | grep negative; need user input |
| T1.3 | Context switch → Home | todo | `frontend/src/contexts/ContextSwitch*.jsx` + AppShell.jsx switcher | — |
| T1.4 | Generate Brief button visibility | todo | `frontend/src/components/reading/ReadingTopBar.jsx:100` | — |
| T1.5 | All documents → journal route | todo | `frontend/src/components/home/AllDocumentsButton.jsx` + `HeroDocActions.jsx` | — |
| T1.6 | Add to Cycle: stop the error | todo | `frontend/src/components/documents/DocumentRoutingActions.jsx:125` | — |

## Test files planned
- `backend/tests/test_t1_navigation.py` — context-switch redirect; All-docs navigation
- Frontend smoke + screenshots via existing Playwright harness pattern
