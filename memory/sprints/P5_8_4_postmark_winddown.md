# P5.8.4 — Postmark wind-down inventory + scrub plan (2026-02)

## Verbatim Postmark reference inventory

### Env vars (`backend/.env`)
| Line | Var | Disposition (this phase) |
|---|---|---|
| 62 | `POSTMARK_SERVER_TOKEN=b5713080-...` | **KEEP** (one cycle, for rollback). Mark deprecated in surrounding comment. |
| 63 | `POSTMARK_WEBHOOK_SECRET=c04b327c553c...` | **KEEP** (one cycle). Note: leaked-secret-rotation concern is addressed separately in P5.7.3 memo — current value ≠ leaked value. |
| 71 | `POSTMARK_USE_HMAC=false` | **KEEP** (one cycle). |
| 81 | `POSTMARK_BASIC_AUTH_USER=zy7Yym3uHloLWWJT` | **KEEP** (one cycle). |

Also present (and required active): `INBOUND_PROVIDER` (NEW — Phase P5.8.1). Default `sendgrid`. To roll back to Postmark, set `INBOUND_PROVIDER=postmark` and restart.

### `.env.example` (template for new deploys)
| Line | Content | Disposition |
|---|---|---|
| 22 | `# SendGrid (replaces Postmark — see DEPLOY_READINESS.md)` | KEEP — already correct |
| 36 | `# Optional: legacy Postmark vars (now unused — safe to leave empty or remove)` | KEEP — already correct |
| 38-42 | Commented-out POSTMARK_* lines | KEEP commented — these are documentation for operators rolling back |

`.env.example` is already correctly stating "Postmark is replaced by SendGrid". No edit needed.

### Active backend code
| File:Line | Reference | Disposition |
|---|---|---|
| `backend/routers/inbound_email.py:1-1158` | Postmark inbound handler (HMAC, Basic, URL-secret ladder), normalisation, dispatcher | **KEEP** behind `INBOUND_PROVIDER=postmark|both`. Already 410's when `INBOUND_PROVIDER=sendgrid` (default). |
| `backend/routers/inbound_email.py:834-857` | `@router.post("/postmark")` endpoint (already returns 410) | **KEEP** — the 410 + migration-note is the user-visible deprecation surface. |
| `backend/server.py:279-285` | Back-compat mount of `/api/webhooks/postmark/inbound` | **KEEP** — same 410 behaviour. |
| `backend/server.py:541-572` | Boot guard that requires `POSTMARK_*` env in production | **KEEP** — guards the rollback path; harmless when `INBOUND_PROVIDER=sendgrid`. |
| `backend/server.py:606+` | Postmark inbound CSP allow-list entries | KEEP — no harm in leaving the allow-list permissive. |

### Active frontend code (Postmark-mentioning copy)
| File:Line | Reference | Disposition |
|---|---|---|
| `frontend/src/components/settings/InboundEmailPanel.jsx:10` | Docstring "first-class document via the Postmark inbound webhook" | **EDIT** — replace "Postmark" with "SendGrid Inbound Parse" |
| `frontend/src/components/settings/InboundEmailPanel.jsx:69` | UI copy "administrator enables Postmark inbound" | **EDIT** — generalise to "SendGrid Inbound Parse" |
| `frontend/src/pages/cycle/CycleDraftJournal.jsx:6` | Docstring "sends via Postmark" | **EDIT** — outbound is SendGrid, was always SendGrid in this codepath; docstring was stale. |

### Docs / `docs/PRODUCT_REVIEW.md` etc
| File | Reference | Disposition |
|---|---|---|
| `docs/CODE_INVENTORY_2026-05-05.md:115` | "resend 2.29.0 (outbound), Postmark webhooks" | **STALE** — the inventory is from a prior date. Leave as historical record. Next inventory pass will reflect SendGrid. |
| `docs/CODE_INVENTORY_2026-05-05.md:218-230` | Section "3.18 Inbound Email (Postmark)" | **STALE** — same as above. |
| `docs/PRODUCT_REVIEW.md` | Postmark webhook URL secret leak entry (current commit redacted) | **NO ACTION** unless user wants the history scrub (see §History scrub below). |

### Test files
`backend/tests/test_postmark_inbound_phase_b.py` + cached test ids in `.pytest_cache/` reference Postmark. These tests still pass against the (now-410'd) legacy endpoint when `INBOUND_PROVIDER=postmark`. **KEEP** as a rollback regression suite for one cycle.

## File edits this phase

Applied as part of P5.8.4 (small, low-risk doc fixes only):

1. `frontend/src/components/settings/InboundEmailPanel.jsx` — docstring + UI copy "Postmark" → "SendGrid Inbound Parse"
2. `frontend/src/pages/cycle/CycleDraftJournal.jsx` — docstring "sends via Postmark" → "sends via SendGrid"

All other Postmark references retained for the one-cycle rollback window.

## History scrub command (PROPOSED — awaits user go-ahead)

The leaked Postmark webhook secret (`vuecv7ZVnaWSICYqF2J0yumaLsuhZBHj`, per P5.7.3) lives in 2-3 historic commits of `docs/PRODUCT_REVIEW.md`. The current commit has it redacted; clones still carry the raw value in history.

**Recommended command (BFG Repo-Cleaner — single-replace, deterministic):**

```bash
# 1. Clone a fresh mirror of the repo.
git clone --mirror /path/to/origin akki-mirror.git

# 2. Run BFG with the replacement file.
echo "vuecv7ZVnaWSICYqF2J0yumaLsuhZBHj==>***REDACTED-P5.8.4-HISTORY-SCRUB***" > replacements.txt
bfg --replace-text replacements.txt akki-mirror.git

# 3. Prune the dead refs + verify the secret is gone from every blob.
cd akki-mirror.git
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git log --all -p | grep -F "vuecv7ZVnaWSICYqF2J0yumaLsuhZBHj"   # expect: no output

# 4. Force-push to origin.
git push --force --all
git push --force --tags
```

**Alternative (no BFG dependency — `git filter-repo`):**

```bash
pip install git-filter-repo
git filter-repo --replace-text <(echo "vuecv7ZVnaWSICYqF2J0yumaLsuhZBHj==>***REDACTED-P5.8.4-HISTORY-SCRUB***")
git push --force --all
git push --force --tags
```

## Impact of running the scrub

- **All commit hashes after the first touched commit rewrite.** PR references / external links to commit hashes break.
- **All collaborators MUST re-clone.** Existing local clones will fail to pull cleanly. The reflog on local machines still contains the leaked value until manually purged.
- **CI / deployment pipelines tied to specific commit hashes (Vercel etc.) need to be re-triggered against the new HEAD.**
- **The leaked secret is already dead** (P5.7.3 confirmed current `.env` value ≠ leaked value). The scrub is cosmetic / hygiene, not urgent risk mitigation.

## Awaiting user go-ahead

**This is a destructive history operation. I have NOT executed it.** Surface the proposed command, impact, and recommend the user run it themselves (or grant explicit go-ahead in the next message). I'll execute on confirmation.

**Recommended:** do the scrub once Postmark is fully retired (i.e. after one rollback cycle with `INBOUND_PROVIDER=sendgrid` confirmed clean). Until then, keeping the legacy code paths is more valuable than the cosmetic cleanup.
