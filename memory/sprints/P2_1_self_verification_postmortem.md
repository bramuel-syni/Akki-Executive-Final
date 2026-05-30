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
