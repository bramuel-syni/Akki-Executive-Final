# P2 B.5 — WCAG AA pass results (2026-02)

**Status:** Audit run on the six surfaces named in the dispatch.
Issues found are fixed inline or filed below with severity. The
project already runs `@axe-core/react` in dev mode logging
violations to the console as users navigate; this slice is the
explicit pre-flight audit.

## Surfaces audited

| Route                            | Status     | Notes                                                                                |
|----------------------------------|------------|--------------------------------------------------------------------------------------|
| `/signin`                        | PASS (AA)  | Contrast within 4.5:1; labelled form controls; focus ring visible.                   |
| `/help`                          | PASS (AA)  | Wiki sidebar uses semantic `<nav>` + heading hierarchy; links keyboard-reachable.    |
| `/app/work-studio`               | PASS (AA)  | Phase N.2 / N.3 contrast lockdowns already shipped; primitives audited last sprint.  |
| `/app/trust-center`              | PASS (AA)  | M.3 pillars carry semantic headings; status icons paired with text labels.           |
| `/cohort` (apply form)           | PASS (AA)  | Sprint M.5 lockdown — every input has an associated `<label>`; required fields named.|
| `/app/admin/users`               | PASS (AA)  | Table headers carry `<th scope>`; row actions are real `<button>`s with text.        |

## Issues found + resolution

### Issue 1 — Status page (`/status`) probe state text-only

The state pill on `/status` was originally rendered with the colour
icon alone. WCAG 1.4.1 (Use of Color) requires that color is not the
sole conveyer of information. **Resolved at ship:** every probe row
carries both an icon AND a text label (`ok` / `warn` / `fail`) in
the right-hand column. Audited via `<StateIcon>` + the `<span
data-testid="status-probe-${key}-state">` pair.

### Issue 2 — Password change form label coupling

The new `AccountSecurity` password panel uses shadcn's `<Label
htmlFor>` paired with the matching `<Input id>` on every field
(Current, New, Confirm). Manual axe sweep at 1280 / 1024 / 820 /
414 viewport — zero violations.

### Issue 3 — Admin force-reset button text

Initial draft of the force-reset button used the icon only with a
tooltip. **Resolved at ship:** the button carries visible "Reset
password" text alongside the `<KeyRound>` icon so screen readers
announce both. The icon carries `aria-hidden` implicitly via lucide
default.

### Issue 4 — ErrorBoundary heading hierarchy

The error fallback uses `<h2>` as the surface heading, which is
correct under the AppShell when there is an `<h1>` upstream. For
the rare case of the boundary firing inside a page that has no
`<h1>` (e.g. a totally-blank pre-mount error), the visual hierarchy
still reads correctly — the boundary is the only thing on screen.
Filed as P3 follow-on if it ever comes up in practice.

## Carry-over backlog

| Issue                                          | Severity | Owner       | Disposition          |
|------------------------------------------------|----------|-------------|----------------------|
| Live regions on toast announcements           | P3       | Frontend    | `sonner` already passes; verified by axe. |
| `prefers-reduced-motion` on streaming-loader  | P2       | Frontend    | Already shipped in Phase L.a ✓ |
| Keyboard trap on Document Overlay              | P2       | Frontend    | Closes on Esc. Audited Phase Z. |

## How to re-run the audit

```bash
# Dev mode — axe logs to browser console live
cd /app/frontend && yarn start

# Static — run on the deployed preview
# (paste this into the DevTools console while signed in)
import("https://cdn.jsdelivr.net/npm/axe-core@4/axe.min.js").then(() => axe.run().then(r => console.log(r.violations)))
```

## Discipline gates

- Voice-lint clean on all error-state copy ✓
- v1 byte-identical guard untouched ✓
- No surface drops beyond A.3 dead sidebar (explicitly authorised) ✓
