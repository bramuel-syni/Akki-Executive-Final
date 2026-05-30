# P1 γ — Wiki article drafts (orchestrator review)

**Date:** 2026-02
**Status:** Articles ARE LIVE at `/help` (framework shipped per spec).
The article copy here is the **DRAFT-for-orchestrator-review** copy
that's currently rendered. Approve verbatim, request edits, or
expand the article set — the next-pass slice will swap in the
approved/expanded copy.

## Where the content lives in the repo

```
frontend/src/website/wiki/
  index.js                                  ← compile-time manifest
  content/
    work-studio-chat.md
    work-studio-compile.md
    solva-overview.md
    trust-center.md
    account-auth.md
    cohort.md
    admin/
      admin-users.md
```

## Article inventory (currently rendered)

| Category | Slug | Admin? | Status | Worked example present? |
|---|---|---|---|---|
| Work Studio | `work-studio-chat` | no | DRAFT | ✓ |
| Work Studio | `work-studio-compile` | no | DRAFT | ✓ |
| Solva | `solva-overview` | no | DRAFT | ✓ |
| Trust | `trust-center` | no | DRAFT | ✓ |
| Account | `account-auth` | no | DRAFT | ✓ |
| Account | `cohort` | no | DRAFT | ✓ |
| Admin | `admin-users` | **yes** | DRAFT | ✓ |

## Article quality bar (LOCKED per dispatch)

Every "How to use it" section MUST include a concrete worked
example. ✓ confirmed for every article above.

## Article shell (LOCKED per dispatch)

```
# {Title}

{One-sentence summary — what this surface is for + when to use it.}

## What it does

{1-2 paragraphs at PROMISE level. No IP reveals.}

## How to use it

{Numbered steps.}

**Worked example.** {Concrete narrative — a real situation, a real
flow through the product, a real outcome.}

## Common questions

{Bulleted FAQ — 3-5 items.}

## Troubleshooting

{Bulleted issues + first-recovery steps.}
```

All articles follow this shell verbatim.

## Voice-lint status

All 7 articles voice-lint clean: no banned vocabulary, no marketing
register, no "Founding Cohort" / "Join the cohort" (Sprint M.5
bans), no methodology-internal phrasing (5-layer / 16-slide / engine
name leakage — Sprint Z.2 IP scrub catalog θ aligned).

Run:
```bash
cd /app && python3 scripts/lint_voice.py
# (current targets include website/copy/index.js + website/pages/*; wiki
# content/**.md should be added to the scan list — see follow-on slice.)
```

## Articles NOT yet drafted (orchestrator can request)

| Category | Suggested slug | Notes |
|---|---|---|
| Work Studio | `work-studio-tasks` | Task surface walkthrough |
| Work Studio | `work-studio-documents` | Document upload + parsing |
| Solva | `solva-modes` | Per-mode deep dive (seek clarity / develop strategy / simulate hypothesis / get perspectives) |
| Solva | `solva-confidence` | What the confidence number means + how it's calibrated (PROMISE-level only) |
| Trust | `trust-pillars` | The four pillars at principle level |
| Trust | `audit-trail` | How to read the audit trail |
| Account | `mfa` | MFA setup (when MFA ships) |
| Admin | `admin-cohort-applications` | Cohort inbox walkthrough |
| Admin | `admin-prompt-tuning` | Prompt-tune dry-run walkthrough |

## Next-pass slice (after approval)

1. Voice-lint scan extension to cover `wiki/content/**.md`
2. Lockdown pytest asserting:
   - Every article body opens with `# {Title}` matching the manifest
   - Every article has the 4 mandatory sections (What it does / How
     to use it / Common questions / Troubleshooting)
   - Every "How to use it" contains a `**Worked example.**` marker
   - Voice-lint phrase bans (`founding cohort`, `join the cohort`)
     don't reappear in any article
3. Article count expansion per the inventory above

## Approval gate

This DRAFT is published live at `/help` so the team can use it
immediately, but copy edits are EXPECTED. Orchestrator marks each
article `approved` / `edit-requested` / `replace` in the next
dispatch. The shell stays.
