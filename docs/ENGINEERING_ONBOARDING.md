# AKKI — Engineering Onboarding

> **Audience:** engineers picking up the AKKI codebase.
> **Sister doc:** `docs/DEPLOYMENT.md` is the ops/release runbook. Read this first; that one before your first commit to `main`.
> **Scope:** how to run the app, how the code is organised, how to ship without breaking it.
> **Last updated:** alongside the Phase B.3 streaming cutover.

---

## 1. Overview

AKKI is a board-grade workspace for **NEDs, CEOs, CFOs and Executive Committee members**. The product helps an executive (or a non-executive director who sits on multiple boards) prepare for, run and follow up on board cycles — generating signals from documents, composing briefings, running structured reasoning sessions ("Solva"), and producing deck/report exports the board would actually use.

**Tone constraint (non-negotiable in any UI copy):** FT-style, financial-analyst-grade. **No** of: "leverage", "empower", "unlock", "game-changer", "AI-powered". Any new UI text passes through `services/two_pass.py:find_banned_word()` before it lands.

**Build status (May 2026):**

- ✅ **Phase A** — multi-tenant auth, MFA, contexts/memberships/invitations
- ✅ **Phase B** — chat (multi-model, two-pass + four-check + voice violation, hash-chained audit, **real direct-stream tokens** as of B.3)
- ✅ **Phase C** — Work Studio (aggregates listing, side-drawer, 5-button bar, deterministic DOCX/PPTX/PDF export, Enhance + Continue-in-Chat)
- ✅ **Phase D** — Cycle Manager Executive flow (Agenda → Team → Contributions → Scoreboard → Follow-ups → Compilation). NED-side ships as design only (`docs/NED_CYCLE_MANAGER_DESIGN.md`).
- ✅ **Phase E** — Document Journal rewire (BM25 search, single-drawer, homepage entry-point)
- ✅ **Phase F** — Pulse same-context signal feed
- 🟡 **Phase G** — Solva 2×2 picker (UX brand "Solva v3"; backend stays `solva_v2` — see §6)
- 🟡 **Phase H** — UI width tokens (`akki-w-narrow|medium|wide`)
- 🚧 **Cross-context Pulse + Privacy Wall §2c** — deliberately deferred
- 🚧 **Production deployment scaffolding** — runbook + CI in `docs/DEPLOYMENT.md`; first cutover not yet executed

---

## 2. Stack at a glance

| Layer | Tech |
|---|---|
| Runtime | Python 3.11, Node 20 |
| Backend | FastAPI 0.110 + Motor 3.3 (async Mongo) + Pydantic v2 + APScheduler 3.10 + bcrypt + PyJWT + boto3 |
| Frontend | React 19 (CRA + CRACO 7) + TailwindCSS 3.4 + Radix UI + react-router 7 + axios 1.8 |
| Database | MongoDB 6+ (dev: local; prod: Azure Cosmos DB for MongoDB vCore) |
| Storage | S3-compatible (`services/storage_service.py`); dev = local disk, prod = MinIO on the same VM |
| LLM proxy | `emergentintegrations` (Anthropic / OpenAI / Gemini via Emergent Universal Key) |
| LLM direct (Phase B.3) | `anthropic.AsyncAnthropic` for Claude streaming, `google.genai` for Gemini streaming |
| Privacy | Synisense Shield = regex → Presidio (spaCy) → LLM-fallback ladder (`services/synisense/*`) |
| PDF | WeasyPrint 60+ (Cairo+Pango) |
| DOCX/PPTX | `python-docx`, `python-pptx` |
| Email | Resend (outbound), Postmark (inbound) |
| Process supervision | supervisor (dev pod); systemd + docker compose v2 (prod) |

Two architectural rules that drive everything else:

- **Two-pass + four-check** in chat (`services/two_pass.py`). Every model reply is first classified, then generated, then post-checked against banned words / refusal templates / voice violations.
- **Synisense Shield** sits in `llm_service.call_llm` (`backend/llm_service.py:163`). **Every** outbound LLM call passes through it. PII is shielded outbound and the response is rehydrated locally — the LLM never sees raw PII.

---

## 3. Local dev preinstall

### macOS (Homebrew)

```bash
# Tooling
brew install python@3.11 node@20 yarn mongodb-community pyenv nvm
brew services start mongodb-community

# WeasyPrint native deps
brew install cairo pango gdk-pixbuf libffi shared-mime-info

# (optional) Docker Desktop if you want to mirror prod locally
brew install --cask docker
```

### Ubuntu / Debian

```bash
sudo apt update && sudo apt install -y \
  python3.11 python3.11-venv python3-pip \
  build-essential pkg-config \
  libxml2-dev libxslt1-dev libffi-dev libssl-dev \
  libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
  shared-mime-info fonts-dejavu-core fonts-noto-core \
  libjpeg-turbo8-dev zlib1g-dev libpng-dev \
  curl ca-certificates

# MongoDB Community 6+
# (follow https://www.mongodb.com/docs/manual/installation/ for your distro)

# Node 20 via nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
nvm install 20 && nvm use 20

# Yarn (corepack manages the version pinned in package.json)
corepack enable
corepack prepare yarn@1.22.22 --activate

# (optional) Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker
```

---

## 4. Repo clone + first run

```bash
git clone <repo-url> akki
cd akki

# ── Backend env ─────────────────────────────────────────────────────────
cp .env.example backend/.env
# Edit backend/.env. Minimum fields to populate for local dev:
#   MONGO_URL=mongodb://localhost:27017
#   DB_NAME=akki_dev
#   JWT_SECRET=<openssl rand -hex 32>
#   EMERGENT_LLM_KEY=<your dev universal key>
#   SYNISENSE_MASTER_KEY=<openssl rand -hex 32>     # one-shot — never rotate
#   SYNISENSE_ALLOW_INSECURE=true                   # ONLY in dev
#   ALLOW_UNSAFE_UPLOADS=true                       # ONLY in dev (no clamav daemon)
#   STORAGE_BACKEND=local
# Optional for direct streaming (Phase B.3):
#   ANTHROPIC_API_KEY=...                           # for direct Claude streaming
#   GEMINI_API_KEY=...                              # for direct Gemini streaming
#   CHAT_STREAMING_MODE=direct_stream

# Sandbox accounts (admin/viewer/Julius) live in memory/test_credentials.md.

# ── Backend Python deps ────────────────────────────────────────────────
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt --extra-index-url \
  https://d33sy5i8bnduwe.cloudfront.net/simple/
# anthropic was added in Phase B.3; it's already in requirements.txt.

# spaCy NLP model used by Synisense Presidio engine (~600 MB one-shot)
python -m spacy download en_core_web_lg

# ── Frontend ───────────────────────────────────────────────────────────
cd frontend
yarn install --frozen-lockfile
echo 'REACT_APP_BACKEND_URL=http://localhost:8001' > .env
echo 'WDS_SOCKET_PORT=0' >> .env
cd ..

# ── Run (two terminals) ────────────────────────────────────────────────
# Terminal 1
source .venv/bin/activate
cd backend && uvicorn server:app --reload --host 0.0.0.0 --port 8001

# Terminal 2
cd frontend && yarn start
```

If you have the supervisor pattern from the dev pod, `sudo supervisorctl start all` boots backend + frontend + mongod + minio + clamd at once.

Smoke test:

```bash
curl http://localhost:8001/api/health        # {"status":"ok","db":"up"}
open http://localhost:3000                   # land on /signin
# log in with admin@akki.ai / AkkiAdmin2026!  (see memory/test_credentials.md)
```

---

## 5. Codebase tour

```
backend/
├── server.py                         # FastAPI app, CORS, startup guards, APScheduler crons, admin seed
├── core.py                           # Mongo client, JWT/bcrypt helpers, X-Active-Context dependency
├── llm_service.py                    # The single chokepoint: every LLM call routes through call_llm()
├── llm_tier_quota.py                 # Per-account/day deep-tier quota
├── bm25.py                           # In-memory BM25 (Document Journal + Work Studio grounding)
├── services/
│   ├── two_pass.py                   # Canonical prompts + banned-words regex + four-check templates
│   ├── llm_streaming.py              # Phase B.3: direct Anthropic + Gemini streaming + proxy fallback
│   ├── work_studio_export.py         # Deterministic DOCX/PPTX/PDF renderers
│   ├── privacy_wall.py               # project_for_pulse / project_audit_row guards
│   ├── clamav_service.py             # TCP client to clamd
│   ├── storage_service.py            # LocalDisk + S3 (MinIO/AWS) backends
│   ├── synisense/                    # Three-layer PII engine (regex → Presidio → LLM fallback)
│   │   └── pipeline.py, encryption.py, llm_fallback.py, presidio_engine.py, regex_recognisers.py
│   └── solva_v2/                     # Reasoning state machine + 6 engines (per submodule)
├── routers/                          # 56 routers, all prefix=/api
│   ├── auth.py                       # register / login / MFA / declare-role / refresh
│   ├── contexts.py                   # multi-tenant context + memberships + invitations
│   ├── chat.py                       # chat models, send + STREAM (real tokens), audit chain
│   ├── solva_v2.py                   # Solva sessions, turn, handoff, PDF/DOCX export
│   ├── documents.py                  # upload, BM25 search, summary, journal-commentary, paragraph anchors
│   ├── briefings.py                  # aggregate briefings (signals → briefing → boardpack)
│   ├── cycle_manager.py              # Phase D — 6-step Executive cycle flow
│   ├── pulse.py                      # Phase F — same-context signal feed
│   ├── work_studio_export.py         # Export + Enhance + Continue-in-chat handoff
│   ├── studio_blocks.py              # Block editor lifecycle (briefing/deck/report)
│   └── … 40+ more
└── scripts/                          # seed scripts, migrations, one-shots

frontend/
├── public/
└── src/
    ├── App.js                        # all routes (public + /app + /admin)
    ├── contexts/AuthContext.jsx      # per-tab active context (sessionStorage), switch flow
    ├── lib/api.js                    # axios instance — single source of API_BASE
    ├── pages/                        # 60 pages (Chat, Workspace, SolvaSession, WorkStudio, Cycle, Pulse, …)
    ├── components/                   # 145 components (chat/, solva/, studio/, cycle/, home/, layout/, …)
    └── hooks/                        # useReviewQueue, useDepthStatus, useCycleConfig, …
```

**Key abstractions to internalise:**

- **`call_llm()`** in `backend/llm_service.py` — the only function in the codebase that talks to providers. Always shielded. Always returns `{response, mode, provider_used, fallback_triggered, shielding, …}`.
- **`stream_llm_direct()`** in `backend/services/llm_streaming.py` — async generator yielding `LlmStreamChunk` objects. Used by `routers/chat.py` for real per-token streaming.
- **`shield_payload_async()`** in `backend/services/synisense/pipeline.py` — outbound shield. Consumed by `call_llm`.
- **`project_for_pulse()`** / **`project_audit_row()`** in `services/privacy_wall.py` — field-projection guards on cross-context reads (called by `routers/governance.py`, `routers/shares.py`).
- **Hash chain** in `routers/chat.py` — `prev_hash` + `row_hash` over a canonical content payload, genesis string `"GENESIS-AKKI-CHAT-AUDIT-2026"`. Validated by `/api/chats/{id}/audit/export.zip`.

---

## 6. Critical concepts (must-read before your first PR)

### 6.1 Synisense Shield — every LLM call routes through it
`call_llm()` always:
1. Shields the outbound prompt (`surface="<module>"`, e.g. `"chat"`, `"briefing"`, `"solva_v2.synthesis"`).
2. Sends shielded text to the provider.
3. Rehydrates the response locally using the shield map.

**Discipline:** when adding a new LLM-using route, pick a `surface=` string that appears in `db.synisense_runs` and is namespaced to the feature. **Do NOT** call providers directly bypassing `call_llm` or `stream_llm_direct` — Synisense **must** see every payload.

### 6.2 Two-pass reasoning in chat (`services/two_pass.py`)
For every chat turn:
1. **Classifier pass** — categorises user input (`strategic_deliverable`, `factual_question`, `casual_chat`, etc.).
2. **Provider call** — actual answer.
3. **Four-check pass** — banned-word grep, refusal-template match, voice-violation match, evidence list.

Streaming changes nothing about ordering. The four-check runs on the **assembled final reply**, not on individual deltas. Adding a new turn class? Edit `two_pass.classify_turn_async` and the prompt registry, not `routers/chat.py`.

### 6.3 Solva "v3" branding ≠ `solva_v2` code paths
The **UX brand** says "Solva v3". The **code** says `solva_v2` everywhere — package, router, collection name, audit-row surface. This is **naming drift, not a bug**. Don't try to "fix" it by renaming files; it would invalidate every audit row. The only legitimate place "v3" appears is in user-facing copy.

### 6.4 Roles & context isolation
- `account.declared_role ∈ {executive, ned, dual, undeclared}` — what the user said they are.
- `membership.role ∈ {executive, ned}` — what the user actually IS in this context.
- The **live role** is derived from `membership.role`, not `declared_role`.
- Per-tab active context is stored in **`sessionStorage`** (NOT `localStorage`) — two tabs in different contexts must not trample each other. `frontend/src/lib/api.js` injects `X-Active-Context` from sessionStorage on every request.

### 6.5 Audit hash chain — DO NOT BREAK
`db.chat_audit_log` is mathematically chained. Each row's `row_hash = SHA256(prev_hash + canonical_content_payload)`. The genesis row uses `"GENESIS-AKKI-CHAT-AUDIT-2026"`. Adding new fields to a row is fine; **adding new fields to the canonical content payload** invalidates every downstream hash. The canonical payload shape lives in `routers/chat.py` near `_compute_row_hash`. Treat it as immutable; if you must extend it, write a forward-compatible migration that records the schema version on every row.

### 6.6 Privacy Wall (`services/privacy_wall.py`)
- `project_for_pulse(collection, doc)` — strips fields from a Mongo doc so cross-context aggregations don't leak.
- `project_audit_row(row, drop_metadata=True)` — same idea on audit rows.
- Pulse currently **same-context only**. Cross-context aggregation requires §2c (`redact_for_pulse_text` is a no-op stub today; `assemble_pulse_prompt` raises `NotImplementedError("Phase 2c")`). **Do not call those two functions until that work ships.**

---

## 7. Running tests + reproducing user reports

| What | How |
|---|---|
| OpenAPI / Swagger | `http://localhost:8001/api/docs` |
| Test credentials | `memory/test_credentials.md` (admin / viewer / Julius — all roles) |
| Backend pytest | `cd backend && pytest tests/ -x -q` |
| Targeted backend test | `pytest backend/tests/test_<phase>_<topic>.py -k <name> -v` |
| Frontend lint | `cd frontend && yarn run lint` |
| Frontend a11y | `yarn a11y:ci` |
| Frontend perf | `yarn perf:ci` (Lighthouse) |
| Reproduce user 502 / 404 | `tail /var/log/supervisor/backend.err.log`, then `curl` the exact URL from the report against localhost:8001 |
| Cron probe | `curl -X POST http://localhost:8001/api/cron/<job> -H "X-Cron-Secret: $AKKI_CRON_SECRET"` |
| Chat hash-chain validation | `curl http://localhost:8001/api/chats/{id}/audit/export.zip -H "Authorization: Bearer $TOKEN" -o audit.zip && unzip -p audit.zip` |

When a user reports a bug, the first step is **reproduce server-side** with `curl` before touching code. Server-side 200 + browser failure = frontend bug. Server-side 5xx = backend bug. We've shipped two regressions in the last fortnight where the difference mattered (the homepage upload `${API_BASE}/api/...` 404, and the briefings Claude-proxy 502).

---

## 8. Coding conventions

### Python (backend)
- Linter: `ruff`. Formatter: `black`. Run before push: `ruff check backend/ && black --check backend/`.
- **Async-first.** No sync I/O inside request handlers. No `requests.get` — use `httpx.AsyncClient`.
- Required env vars: `os.environ["NAME"]` (KeyError on missing). Optional: `os.environ.get("NAME", default)`. Never `os.getenv` for required reads — it returns `None` silently.
- Models: Pydantic v2 (`BaseModel`, `Field`, `model_validator`). NOT `dict[..., ...]` types in route signatures.
- IDs: **always UUIDv4 strings**. Never `ObjectId`. The whole DB layer assumes string `id` fields.
- Audit logs: write through `services.audit.write_audit(...)` — don't insert directly into `db.audit_log`.
- LLM calls: through `call_llm` (request/response) or `stream_llm_direct` (streaming). **Never** import `LlmChat` directly outside those two helpers.

### React / TypeScript (frontend)
- Functional components + hooks only. No class components.
- HTTP: **`api` instance from `lib/api.js` ONLY**. Never raw `fetch` against a hand-built URL.
- **Never** write `${API_BASE}/api/...` — `API_BASE` already ends in `/api`. The recent `/api/api/...` 404 incident on the homepage upload modal is the cautionary tale; we just spent half a day on a one-character bug.
- Markdown: `react-markdown` + `remark-gfm`. Never `dangerouslySetInnerHTML` on LLM output.
- Toasts: `sonner` (already imported globally).
- Tailwind: prefer the `akki-*` design tokens (`akki-w-narrow|medium|wide`, `akki-overline`, `akki-greeting`, `akki-meta`, `akki-serif`) over raw Tailwind classes for layout primitives.

### Env-var hygiene
- Local `.env` is in `.gitignore` — keep it that way.
- Never log a secret value. Never paste a secret into a PR description, an issue, or chat.
- Required-in-prod boot guards live in `server.py`. Add a guard when you add a new required secret.

---

## 9. Branching + PR process

- `main` is **protected** and **auto-deploys to production** via `.github/workflows/deploy.yml`. Merging to `main` ships to `https://akki.syni.ai`.
- Feature branches: `feat/<scope>` (new functionality) or `fix/<scope>` (bugfix). Avoid `wip/`, `tmp/`, `bram/` etc.
- Squash-merge default. Keep the squash commit message concise and Phase-numbered (e.g. `Phase B.3 — direct provider streaming + service-layer failover`).
- PR description template (TODO: add as `.github/pull_request_template.md` — flag for the user).
- Before merging:
  - [ ] Lint clean (`ruff check`, `eslint`)
  - [ ] Banned-word grep clean on touched UI copy
  - [ ] Audit-chain unaffected (or migration script attached)
  - [ ] No new secrets committed
  - [ ] `.env.example` updated if you added an env var
  - [ ] If you touched a route used by frontend: verify no `${API_BASE}/api/` double-prefix anywhere

---

## 10. Secrets management

- **Local:** `backend/.env` (gitignored). Use `openssl rand -hex 32` for any new secret you generate locally.
- **Production:** Azure Key Vault, sourced by `scripts/deploy/akki-load-secrets.sh` on every boot + every deploy. Names are kebab-cased on the vault side and translated to UPPER_SNAKE_CASE in the env file. Full procedure: `docs/DEPLOYMENT.md` §7.
- **Never paste real secrets** in PRs, issues, chat threads or screenshots. The recent `.env` you edited locally is yours alone.
- Secret rotation: most secrets are hot-swap (rotate in vault → next deploy picks them up). Two exceptions, both documented in `DEPLOYMENT.md` §11:
  - `JWT_SECRET` — accept BOTH old + new during one access-token TTL (8 h), then drop the old. Single-step rotation logs everyone out.
  - `SYNISENSE_MASTER_KEY` — **one-shot at first prod boot**. Rotating it invalidates `db.synisense_shield_maps`. There is no re-encryption migration today; if you need to rotate, write the migration first.

---

## 11. Deployment

> **Prod deploy = `git push origin main`.**
>
> Workflow + step-by-step procedure: `docs/DEPLOYMENT.md`.
>
> **Read it before your first commit to `main`.** Particularly §3 (deploy blockers), §11 (the "without breaking it" checklist) and §12 (rollback procedures).

The TL;DR is:
1. CI builds backend + frontend Docker images, pushes to ACR with the immutable git-SHA tag.
2. CI SSHs to the production VM and runs `akki-deploy.sh <sha>`.
3. `akki-deploy.sh` refreshes secrets from Key Vault, runs `docker compose pull && up -d`, polls `/api/health` for 60 s.
4. On healthcheck pass: tag is recorded in `/var/lib/akki/last-good-tag`.
5. On failure: automatic rollback to the previous good tag, CI exits non-zero.

Manual rollback: `sudo /usr/local/bin/akki-rollback.sh` (1 step) or `sudo akki-rollback.sh --steps N`.

---

## 12. Common pitfalls

Cite the recent incidents — these are not hypothetical:

- **`${API_BASE}/api/...` double-prefix** — the homepage upload modal and `DocumentBodyModal` both shipped with this. URLs resolved to `…/api/api/contexts/…` and 404'd. Fix is one character per call site. **`API_BASE` already ends in `/api`.**
- **Cosmos vCore needs `retrywrites=false`** in the connection string. PyMongo defaults to `true`; Cosmos does not support retryable writes. Boot will *appear* to work, but writes will silently retry-fail under load. See `docs/DEPLOYMENT.md` §3 #7 and §8.
- **APScheduler is in-process and not leader-elected.** Single backend replica only. Two replicas means every cron fires twice (duplicate audit rows, duplicate digest emails, duplicate retention sweeps). Distributed-lock work is a separate piece of engineering.
- **`REACT_APP_BACKEND_URL` is baked into the JS bundle at `craco build` time.** Changing it requires a frontend image rebuild. `docker compose restart frontend` does **not** reload the value.
- **LLM proxy 502s transiently.** The Emergent proxy occasionally returns 502 on Claude. Phase B.3 service-layer failover (`services/llm_streaming.py`) now retries via the direct Anthropic / Gemini SDKs first and falls back to the proxy. The previous `briefings.py`-local band-aid (`_is_proxy_502`) was removed in the same change. Audit rows still record `provider_used` + `fallback_triggered` for forensic visibility.
- **`STORAGE_BACKEND=local` is dev only.** Prod uses `s3` against MinIO via the same code path. If you write a new file-upload route, test with `STORAGE_BACKEND=s3` against a local MinIO container before merging.
- **`ALLOW_UNSAFE_UPLOADS=true` is dev only.** It bypasses ClamAV virus scanning. Production sets this to `false` and the compose `depends_on: clamav: condition: service_healthy` enforces ClamAV health before backend accepts traffic.
- **Manual `Content-Type: multipart/form-data` headers in axios calls** — axios 1.x is smart in browsers and lets the boundary be auto-set, so this is currently benign but a footgun. Don't introduce more of them; pass FormData directly without setting the header.
- **`emergentintegrations` does not stream tokens through the proxy.** `litellm.completion(stream=True)` accepts the param but the proxy buffers and emits one chunk. Phase B.3 routes streaming through the direct provider SDKs (`anthropic.AsyncAnthropic.messages.stream`, `google.genai aio.models.generate_content_stream`).
- **Hash chain is brittle to canonical-payload edits.** Adding a field to an audit row is fine. Adding a field to the canonical payload that feeds `_compute_row_hash` invalidates every prior chain. Don't.

---

## 13. Debugging locally

```bash
# Backend stderr (tracebacks, warnings)
tail -f /var/log/supervisor/backend.err.log

# Backend stdout (uvicorn access logs)
tail -f /var/log/supervisor/backend.out.log

# Restart one service
sudo supervisorctl restart backend
sudo supervisorctl restart frontend

# Health probe
curl localhost:8001/api/health

# Browser network tab — primary tool for any frontend bug.
# Filter by Fetch/XHR. Look at the URL: any `/api/api/...` is the
# double-prefix regression; anything ending `:80/api/...` should be 200.

# Mongo inspection
mongosh akki_dev
# > db.documents.findOne({}, {_id:0,id:1,name:1,status:1})
# > db.synisense_runs.find({}).sort({ts:-1}).limit(5)
# > db.chat_audit_log.find({chat_id:"<id>"}).sort({seq:1})

# Banned-word grep on a touched file
rg -inE '\b(leverage|empower|unlock|game-?changer|AI-?powered)\b' frontend/src/pages/<file>

# Boot log streaming banner (Phase B.3)
grep '\[chat\] streaming' /var/log/supervisor/backend.err.log | tail -1
# expected: [chat] streaming: claude=direct_stream gemini=direct_stream gpt=proxy_buffered
```

When you hit a 5xx in the browser, the loop is:
1. `curl` the exact URL with the same auth → reproduce server-side.
2. `tail backend.err.log` for the traceback at that timestamp.
3. Read the line; usually the fix is local to one handler.
4. Restart backend (or hot-reload picks it up).
5. Re-curl; verify 200.
6. Re-test in the browser.

---

## 14. Who to ask

> TODO (user fills in once team roles are confirmed):
>
> | Topic | Person |
> |---|---|
> | Architecture / overall direction | _<TBC>_ |
> | Security / auth / privacy | _<TBC>_ |
> | Design / UX / copy tone | _<TBC>_ |
> | Infra / deploys / Cloudflare / Azure | _<TBC>_ |
> | Solva reasoning engine | _<TBC>_ |
> | Synisense Shield | _<TBC>_ |

Until then: post in the engineering Slack channel and CC whoever last touched the file (`git log -1 --format='%an %ae' -- <path>`).

---

## Appendix — Phase B.3 Streaming cheatsheet (Mar 2026 cutover)

| Question | Answer |
|---|---|
| Where does the chat send/stream endpoint live? | `backend/routers/chat.py`, the `_event_gen` async generator inside the `POST /api/chats/{id}/messages/stream` handler |
| Where do direct provider calls live? | `backend/services/llm_streaming.py` — `_stream_anthropic`, `_stream_gemini`, `_stream_proxy_buffered`, all funnelled through `stream_llm_direct(...)` |
| Where does Synisense fire on streamed replies? | The **assembled final reply** is rehydrated in `_event_gen` after the delta loop, before the `message` event is emitted. Deltas themselves are NOT shielded — the four-check + voice-violation pass + final hash all run on the rehydrated text. |
| What does the audit row contain? | Same canonical payload as before, plus two new metadata fields: `provider_used ∈ {anthropic_direct, gemini_direct, proxy_buffered}` and `fallback_triggered: bool`. Hash chain shape unchanged. |
| Rollback path? | Set `CHAT_STREAMING_MODE=proxy_buffered` in `backend/.env` and restart backend. Direct paths are bypassed; chat reverts to the buffered single-chunk SSE behaviour. |
| Frontend handler? | `frontend/src/pages/Chat.jsx:400` — already handles `delta` events incrementally and swaps to canonical `assistant_text` on the `message` event. No frontend changes were needed for B.3 (the FE was streaming-ready since B.1; the BE was the bottleneck). |
| Boot log line | `[chat] streaming: claude=<direct_stream|proxy_buffered> gemini=<...> gpt=proxy_buffered` |
