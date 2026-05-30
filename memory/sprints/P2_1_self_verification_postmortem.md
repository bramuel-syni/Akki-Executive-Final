# P2.1 self-verification postmortem (2026-02)

The P2 dispatch return claimed all 14 slices shipped clean. Independent
tester verification found 2 hard fails + 1 warn + 1 unverifiable. This
note records what my self-check did instead of what would have caught
each miss, and the one process change I commit to going forward.

## The 4 misses

### B.1 — Security headers missing on HTML responses (HARD FAIL)

What my self-check did: `curl -sI` against `/api/health/composite` only.
Saw 5/6 headers (CSP gated to HTML by my own code), claimed pass.

What would have caught it: a `curl -sI` against the HTML route (`/`,
`/signin`, `/help`) showing the Express layer serves the HTML and was
not touched by FastAPI middleware. The middleware was structurally
incapable of touching HTML — I treated "backend test passed" as
"production response correct" without confirming the same URL the
browser hits actually carried the headers.

### C.2/C.3 — Wiki sidebar shows 13 not 16 (HARD FAIL)

What my self-check did: counted manifest entries (16), confirmed disk
files (16), claimed pass.

What would have caught it: a DOM trace at `/help` while signed-in as
the non-admin tester profile. The 3 missing entries are admin-only and
correctly filtered for non-admins — by-design behaviour. But my return
asserted "16 articles total in the wiki" without scoping the claim to
admin sessions. The miss was about the precision of the claim, not the
code.

### D.2 — Status page 414px overflow (WARN)

What my self-check did: queried `[data-testid]` selectors and
confirmed they existed at 414px. Did not measure
`scrollWidth - clientWidth`.

What would have caught it: an explicit overflow probe at each viewport
— the canonical measure. Existence of testids says nothing about
layout overflow. (Re-measured: zero overflow on all 4 viewports
post-fix; defensive `min-w-0` + `flex-wrap` + `overflow-x-hidden`
applied as belt-and-braces.)

### B.3 — ErrorBoundary unverifiable (HUMAN_REQUIRED)

What my self-check did: confirmed the boundary code exists in the
repo and is mounted at the root. Did not exercise it.

What would have caught it: a deliberate test-throw inside the
boundary at runtime, then a DOM trace confirming the fallback UI
rendered. I assumed "code exists + mounted" implies "behaviour
verified" — those are different claims. Verification needs the
behaviour to be exercised under conditions that match the failure
mode it guards.

## The one process change

**For every UI/HTTP claim in a return, exercise the exact surface a
user/tester would touch — not a proxy.** Concretely:

- HTTP header claims → `curl -sI` against the public preview URL on
  every URL pattern in scope (HTML root, HTML sub-pages, API). Not
  TestClient.
- Layout claims → measure (`scrollWidth`, computed style, etc.) at
  every named viewport. Not "selector exists".
- Behaviour claims (boundary catches, retry fires, etc.) → exercise
  the trigger condition in a live trace. Not "code review".
- Count/visibility claims → run the trace as every role mentioned in
  scope (admin, viewer, signed-out). Not manifest inspection.

This is the rule the dispatch already implied; I treated it as
"trace when feasible" rather than "trace on every behavioural claim".
The corrected rule is the second.

## P4 corrections — repeated misses (2026-02 P5)

Independent tester verification on P4 found two more hard fails of the
same pattern this postmortem was written to break. Both passed my
self-check the first time round and shipped with the "delivered" label.

### Miss 1 — Admin "magic link is copyable" claim (P4.B → P5.1)

What my self-check did: read the JSX, confirmed `setPinnedLinks(...)`
ran in the approve handler, eyeballed the `<code data-testid="...-
magic-link-url">` element rendered inside `items.map(...)`. Declared
shipped.

What actually happened on the live preview: the panel rendered for
~1.5s while the toast was up, then disappeared. After the approve
action the component calls `load()` to refresh the row list; the
default filter is "received"; the just-approved row no longer matches
"received"; React unmounts the row; the pinned panel (rendered as a
child of that row) goes with it. A tester clicking through the actual
queue saw a one-shot toast and zero ability to copy.

What would have caught it: a Playwright trace that not only verified
the testid existed on initial render but waited the full
`load()`-refresh cycle (~1s post-submit) and re-queried. The DOM after
the refresh was empty for the magic-link-url selector. JSX
inspection cannot catch React state that lives at parent-component
scope but renders as a child of a dynamically-filtered list. P5.1 fix
moved the panel into a sibling section above the row list.

### Miss 2 — `/welcome/{token}` consume "redirects to /app" (P4.D → P5.2)

What my self-check did: the consume backend returned
`{redirect: "/app/work-studio"}`; the frontend consume handler called
`navigate(redirect)`. Both pieces visible. Declared shipped.

What actually happened on the live preview: the consume response set
HttpOnly cookies, but the AuthContext snapshot inside the SPA was
`account === false` (the value captured when the user landed on
/welcome unauthenticated). The `<Gated>` wrapper around /app/work-
studio checked AuthContext, saw `account === false`, and bounced to
/signin BEFORE the AuthContext bootstrap saw the new cookies. The
user ended up on /signin with no understanding why.

What would have caught it: a Playwright trace that hit
/welcome/{token}, set a password, submitted, then asserted the FINAL
URL (after all redirects settle) is /app/work-studio (or /app/first-
session for new accounts) — NOT a partial check that the consume
response carried the right `redirect` value. The two are different
claims: backend returned the right value AND frontend honoured it
without a race-condition bounce. P5.2 fix swaps `navigate(redirect)`
for `window.location.href = redirect` so the page reboots and
AuthContext re-runs bootstrap against the live cookies.

## The second process change — same shape, broader scope

Both misses were the SAME structural failure mode that B.3 +
C.2/C.3 + D.2 sit in: **claiming behaviour without exercising the
behaviour as a user would experience it across the full settle
window**. The first postmortem said "trace on every behavioural
claim". I demonstrably interpreted that as "trace the moment when
the claim CAN be true" rather than "trace and wait for any
asynchronous refresh, state-context reconciliation, or filter
reapplication to settle".

The corrected, sharper rule:

- After every state-changing UI action, **wait for every dependent
  refetch / filter reapplication / context bootstrap to complete**
  before asserting the post-action DOM. Concretely: for any handler
  that re-runs a `load()` / `bootstrap()` / `refetch()`, wait at
  least one full network round trip plus React commit cycle
  (~1-2s on the preview) before measuring.
- For any URL claim, wait for `window.location.href` to stop
  changing for at least 500ms (the redirect-chain settle window)
  before asserting the final path.
- For any panel/banner mounted as a child of a dynamic list, also
  verify it survives a re-render that changes the parent list
  membership.
- The DOM scan must be the LAST step of the trace, not an
  intermediate spot-check. Anything that runs after the scan can
  invalidate the scan's claim.

This rule is now locked. Future P-phase dispatches that touch UI
state must structure their self-verification trace AROUND the
post-action settle window, not the click moment.
