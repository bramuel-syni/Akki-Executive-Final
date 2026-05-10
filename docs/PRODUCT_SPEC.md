# AKKI — Product Specification

> Single source of truth. Supersedes `docs/PRODUCT_FEATURES.md` (deprecated).
>
> **Audience:** mixed. §1 is for the board / investor. §§4–9 are for engineering. §6 is the UX walkthrough. §§9–10 are the compliance read.
>
> **Last updated:** post-Phase-B.3 streaming cutover and Work-Studio Option-A failover hardening.

**Status legend used throughout:**
- `[SHIPPED]` — live, exercised in production-shape preview, audit-grade.
- `[PARTIAL]` — live but with explicit known gaps documented in-section.
- `[DEFERRED]` — design done, not built; deliberate de-scope.
- `[PLANNED]` — on the roadmap, no code yet.

---

## 1. Executive Summary

AKKI is an AI-powered intelligence layer for high-level corporate governance, purpose-built for Non-Executive Directors and C-suite executives at listed and pre-IPO companies. It is not a chatbot, not a summariser and not a generic copilot — it is an opinionated workspace that turns board materials and operational signals into financial-analyst-grade briefings, decks and reports, with hard guarantees about what an LLM is allowed to say and what it must decline.

The trust-first proposition runs through every surface. Every outbound LLM call is routed through Synisense Shield (regex → spaCy/Presidio → LLM-fallback ladder) so PII never leaves the boundary unredacted (`backend/llm_service.py:163`, `backend/services/synisense/pipeline.py`). The chat audit log is mathematically hash-chained — `prev_hash + row_hash` over a canonical content payload, genesis string `GENESIS-AKKI-CHAT-AUDIT-2026` (`backend/routers/chat.py:150`), exportable as a verifiable archive at `GET /api/chats/{id}/audit/export.zip` (`:2545`). The Work Studio export pipeline is **deterministic** — same input bytes produce the same output bytes, every render returns a SHA-256 (`backend/services/work_studio_export.py:1-21`). And the system's refusals are **server-authored** — a system that will not generate a board-facing claim it cannot trace to a citation, with the refusal copy living in Python, not in the LLM.

The build today: chat (5 models, two-pass + four-check + real direct-token streaming, hash-chained), Work Studio (aggregate listing + 5-button bar + DOCX/PPTX/PDF + Enhance + Continue-in-Chat), Cycle Manager (Executive flow live, NED design-only), Document Journal (Phase E rewire — homepage entry, BM25 search, single-drawer pattern), Solva v2 reasoning engine (4 sub-modules, state machine, PDF/DOCX export), Synisense Shield (live across 13 surfaces), Pulse same-context signal feed (cross-context aggregation deferred behind Privacy Wall §2c), and a complete deployment scaffolding for Azure VM + Cosmos DB vCore + MinIO + ClamAV via GitHub Actions → ACR → SSH (`docs/DEPLOYMENT.md`).

Stack: React 19 + CRACO + TailwindCSS + Radix UI on the frontend; FastAPI + Motor (async MongoDB) + APScheduler + WeasyPrint + spaCy/Presidio on the backend. Direct Anthropic + Gemini SDK streaming with Emergent proxy fallback (Phase B.3). Python 3.11, Node 20.

Production readiness: scaffolding complete, runbook written (`docs/DEPLOYMENT.md`), GitHub Actions wired for `git push origin main` → ACR → VM. Cutover blocked on three named items: secret rotation across the full Group-A list, finalising the Postmark inbound-webhook secret in Key Vault, and configuring the Cosmos vCore connection string with `retrywrites=false`. None require code change.

---

## 2. Product Vision & Value Proposition

AKKI is an **analyst-grade workspace for the board agenda**. The metaphor that drives the product is the financial-analyst desk: a working surface where unstructured documents (board packs, minutes, committee submissions, MI returns), structured operational signals (risks, hypotheses, follow-ups), and the executive's working memory (chat threads, Solva sessions, draft compositions) are continuously synthesised into briefings, decks and reports a CFO would put their name on.

**Three explicit non-goals:**

1. **Not a chatbot.** Chat is one surface among many; it is a deep-reasoning surface, not a conversational one. It refuses to speculate, it cites, and it terminates conversations that drift into territory the system cannot ground in evidence.
2. **Not a doc summariser.** Document Journal indexes, anchors and offers commentary on documents (`backend/document_commentary_service.py`, `backend/paragraph_anchors.py`) — but the analytic value comes from the synthesis surfaces (Work Studio, Solva, Cycle Manager) drawing on the journal as substrate.
3. **Not a generic copilot.** AKKI does not type code, does not draft emails, does not organise calendars. It owns one job: producing board-facing artefacts the board can defend.

**Three explicit must-be's:**

1. **Privacy-first.** Every LLM call is shielded. PII is regex-stripped, then NER-stripped, then LLM-judge-stripped before it crosses the boundary; rehydrated locally on response. Original PII is encrypted at rest (AES-GCM) with a TTL.
2. **Audit-by-design.** Every chat reply contributes to a hash-chained audit log. Every Synisense run logs the input SHA-256 (never the raw text). Every Work Studio export persists a SHA-256, a sensitivity band, and (post-Phase-B.3) the LLM provider used per pass.
3. **FT-tone output.** Dry, specific, confident. No "leverage", no "empower", no "unlock", no "game-changer", no "AI-powered" — banned by `services/two_pass.py` regex on every generated string and on every UI copy commit. Refusal copy is server-authored to ensure humans signed off on what the system declines and why.

---

## 3. Target Users & Personas

### Persona A — Operating Executive (CEO / CFO)

**Profile.** Sole or primary executive at a listed or late-stage private. Authors the board narrative each cycle. Has direct write access to operational data and can declare anything sensitive. Time-poor in the prep window (T-7 → T-1 days before a board meeting), exhaustion-prone in the post-board window.

**Goals.** Cut board-prep time by half without cutting prep quality. Surface assumption gaps before the NEDs do. Standardise the cycle artefacts (briefing, board pack, minutes) so quality does not degrade when delegated.

**Frustrations.**
- Board materials live in inboxes, drives and Slack threads with no canonical store.
- Drafting committee briefings consumes a full evening per cycle.
- Speculative copy from generic AI tools cannot be cited and does not survive a NED reading.

**Decision-making style.** Hypothesis-first; expects to be challenged. Wants AKKI to challenge before the NEDs do. Tolerant of refusal — preferring "I cannot ground this claim" to a hallucinated answer.

**AKKI value.**
- **Cycle Manager (executive flow)** drafts the agenda, scores contributions and compiles the follow-up email pack (`backend/routers/cycle_manager.py`, `frontend/src/pages/Cycle.jsx`).
- **Work Studio** turns selected aggregates (board pack + minutes + committee pack) into briefing / deck / report exports in <60 s, deterministically, with one-click `Enhance` and `Continue-in-chat` (`backend/routers/work_studio_export.py`).
- **Chat (deep reasoning)** answers structured-deliverable prompts via two-pass orchestration with token streaming, citation-tethered, four-check'd (`backend/routers/chat.py`).
- **Solva** lets them simulate hypotheses with the four-engine pipeline before risking exec-team time on the same scenario.

**Day in the life — executive prep cycle.**
1. **08:30 — open `/app/cycle`.** Last cycle's compilation banner is still visible. Click *Start new cycle*. Cycle Manager pre-fills agenda from prior history + recent active signals (`backend/routers/cycle_manager.py:agenda`).
2. **08:50 — Team tab.** Confirm reportee assignments. AKKI flags one reportee whose contribution-score has trended down two cycles running.
3. **09:30 — Document Journal.** Drop in this month's MI pack. ClamAV scan in <2 s; extracted text indexed; commentary generated on first read (`backend/services/clamav_service.py`, `backend/document_commentary_service.py`).
4. **11:00 — Chat.** Draft prompt: *"Three risks in the receivables ageing trend that the audit committee should debate."* Tokens stream in via direct Anthropic SDK; four-check passes; one risk gets refused for lack of grounding citation (refusal template surfaces verbatim from the server).
5. **14:00 — Work Studio.** Open `Board Pack — Cycle 7` aggregate in the side drawer. Click *Export brief* (DOCX). Two-pass LLM (Pass 1 silent reasoning, Pass 2 strict JSON). Render in 8 s. SHA-256 returned. Open *Continue in chat* on the artefact to refine one section.
6. **17:30 — Cycle Manager *Follow-ups*.** Approve drafted follow-up emails to reportees. Click *Send*. Resend delivers; outbound from `akki+lemasy@syni.ai`. Audit row persisted.

### Persona B — Non-Executive Director (NED)

**Profile.** Sits on 3–6 boards. Read-only access to materials in most contexts; in some, has explicit advisory mandates with limited write. Lives on the inbound side of the cycle — receives the executive's compilation T-3 days before the meeting; reads, marks up, and arrives prepared.

**Goals.** Catch up on multiple boards in ≤ 2 hours per board per cycle. Distinguish what the executive is asserting from what the data supports. Cite any AI-assisted insight with provenance — never claim originality the audit chain disagrees with.

**Frustrations.**
- Six contexts in six tabs, six different vocabularies, six different cycle phases.
- Read-only surfaces in most boards mean copy/paste workflows that strip context.
- Most generic AI tools cheerfully invent citations; a NED who cites an invented source loses credibility for years.

**Context-switching pain.** Per-tab role isolation matters. The active context lives in `sessionStorage` (NOT `localStorage`, see `frontend/src/lib/api.js`), and the `X-Active-Context` header is injected on every request. Two boards open in two tabs do not trample each other.

**AKKI value.**
- **Document Journal** is the catch-up surface — homepage `<AllDocumentsButton/>` button, BM25 search, on-demand commentary, single-drawer pattern (`frontend/src/pages/Workspace.jsx`, Phase E).
- **Reading View** with paragraph anchors — the NED can hover a paragraph and ask "What does the briefing say about this?", chasing the lineage from MI line item → board pack page → minutes line.
- **Chat (NED mode)** asks the same chat surface but with a NED flavour in the prompt registry, encouraging skeptical framing.
- **Solva (NED flavour)** simulates "what if this assumption is wrong?" without committing to the hypothesis; an explicit refusal-of-speculation guardrail.
- **Pulse (same-context today)** shows recent signals in the active board with social actions (save, comment, take-to-Solva). Cross-context aggregation deferred until Privacy Wall §2c lifts.

**Day in the life — NED catches up before the audit committee.**
1. **20:00 — login.** Lands on `/app` (HomeNed variant, `frontend/src/pages/home/HomeNed.jsx`). Top-bar shows the next cycle phase indicator.
2. **20:05 — `<AllDocumentsButton/>`.** Open Document Journal at `/app/workspace`. BM25 search "receivables ageing".
3. **20:08 — open MI return.** Single-drawer detail; commentary stream on the right. Click *Open in body modal* for full reading.
4. **20:25 — Reading View.** Paragraph-anchor on Note 14 of the MI return. Click *Ask AKKI* — chat opens pre-tethered to the paragraph.
5. **20:40 — chat refuses one prompt.** "Why has the executive understated the receivables risk?" — server-authored refusal: AKKI declines to attribute intent without explicit evidence; suggests reframing as a structural question.
6. **21:30 — Solva get_perspective.** Draft a perspective for the audit committee. Solva runs framing → grounding → synthesis → reflection (`backend/services/solva_v2/state_machine.py`). Final artefact exports to PDF (`backend/routers/solva_v2.py:export.pdf`).
7. **22:00 — `/app/pulse`.** Three new signals in the active context. Save the receivables one for the meeting; comment on the audit-committee one. *Take to Solva* spawns a fresh session pre-populated with the signal text.

---

## 4. Core Design Principles

**Privacy-first.** Synisense Shield is non-optional on every LLM boundary. The single chokepoint is `services.llm_streaming.collect_llm_text` (request/response) and `stream_llm_direct` (streaming) (`backend/services/llm_streaming.py`); both call into `backend/llm_service.call_llm` which invokes `shield_payload_async` before any provider call (`backend/llm_service.py:163`). The shield ladder is regex → Presidio (spaCy `en_core_web_lg`) → small-model LLM judge fallback. Identifiers found are masked outbound and rehydrated on response. The `synisense_runs` collection logs only the input SHA-256, never raw text.

**Audit-by-design.** The chat audit log is hash-chained: each row's `row_hash = SHA256(prev_hash + canonical_content_payload)`, genesis row `prev_hash = "GENESIS-AKKI-CHAT-AUDIT-2026"` (`backend/routers/chat.py:150, 2652`). Export at `GET /api/chats/{id}/audit/export.zip` (`:2545`) returns the chain plus a verifier. Work Studio exports persist `sha256`, `sensitivity_band`, `sensitivity_score`, `sensitivity_reasons`, `pass_1_ms`, `pass_2_ms`, and (post-B.3) `llm_pass1` + `llm_pass2` provider/fallback metadata on every successful row (`backend/routers/work_studio_export.py`). Synisense runs are tagged by surface (one of `chat`, `chat_classifier`, `chat_four_check`, `chat_evidence_list`, `ingest`, `briefing`, `deck`, `report`, `brief`, `minutes`, `journal_commentary`, `enhance`, `blog`).

**Server-authored refusals.** Refusal copy lives in the backend (`backend/services/two_pass.py`), so humans review what the system declines. The four-check pass runs `find_banned_word`, refusal-template match, voice-violation match and evidence-list assertion against the model's reply; refusals are not generated by the LLM, they are emitted by the router.

**Two-pass reasoning.** Every chat turn runs: (1) classifier pass (categorises input — `strategic_deliverable`, `factual_question`, `casual_chat`, `thin_input`, etc.), (2) provider call (the actual answer; for `strategic_deliverable` this is a Pass-1 silent reasoning + Pass-2 strict-JSON two-pass), (3) four-check pass on the assembled final reply. Streaming changes nothing about this ordering: deltas stream raw to the client during step 2; rehydration + four-check + audit run on the assembled text after the last delta.

**Per-tab role isolation.** `frontend/src/lib/api.js` injects `X-Active-Context` from `sessionStorage` (NOT `localStorage`). Multiple boards open in multiple tabs cannot trample each other. The backend `core.require_context_membership` dependency rejects with `403 MEMBERSHIP_REVOKED` when the active context's membership has been revoked, triggering a forced re-pick on the frontend (`frontend/src/contexts/AuthContext.jsx`).

**FT-tone output.** Banned-word regex enforces this on every UI copy commit and every generated string (`services/two_pass.find_banned_word`). The four-check pass surfaces a voice violation when the model uses banned terms; refusal templates use verbatim server copy.

**Deterministic exports.** `backend/services/work_studio_export.py:1-21` is explicit: same input bytes → same output bytes for DOCX and PPTX. Every renderer returns `(bytes, sha256, filename)`. PDFs are deterministic for the canonical-template renderers; `render_deck_pdf` is intentionally `NotImplementedError` (PPTX is the deck output of record).

**Direct-provider primary, proxy fallback.** Phase B.3 cutover: Anthropic + Gemini direct SDKs are the primary streaming + request paths when keys are present (`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`). The Emergent universal-key proxy is the **automatic per-call fallback** — same prompt retried via proxy if direct path 5xx's or network-fails. Boot log shows the active mode per provider: `[chat] streaming: claude=direct_stream gemini=direct_stream gpt=proxy_buffered`. GPT-5.2 stays on proxy until direct OpenAI keys are provisioned. Audit rows record `provider_used` and `fallback_triggered` so ops can spot post-facto when direct paths flapped.

---

## 5. Feature Catalog

### 5.1 Solva — decision-support reasoning engine `[SHIPPED]` (with `[PARTIAL]` naming drift)

**Purpose.** Lets an executive or NED reason through a decision under structure: surface candidate framings, triangulate against evidence, weight probabilistically, reflect on what would falsify the conclusion.

**User-visible behaviour.**
- Four sub-module cards on the landing surface (`frontend/src/components/solva/SolvaLanding.jsx`): `seek_clarity`, `develop_strategy`, `simulate_hypothesis`, `get_perspective`. Brand says "Solva v3"; backend code says `solva_v2` (naming drift documented under §14).
- Per session: state machine runs `framing → grounding → synthesis → reflection`; `simulate_hypothesis` inserts an additional `hypothesis` layer.
- Each turn writes one row to `solva_v2_sessions.reasoning_audit_log[]` with engine name+version, input/output hashes, shielding flag, latency, provider tier, Synisense run id.
- PDF and DOCX exports of the final artefact: `GET /api/solva/v2/sessions/{sid}/export.{pdf,docx}`.
- Refusal of speculation: when the grounding contract cannot be satisfied (`backend/services/solva_v2/grounding_contract.py`), the engine emits a refusal artefact rather than fabricated synthesis.

**Backend touchpoints.**
- Routes: `backend/routers/solva_v2.py` (14 endpoints under `/api/solva/v2/*`).
- Engine package: `backend/services/solva_v2/` (state_machine, llm_adapter, grounding_contract, guardrails, opinion_filter, submodules + 6 engines under `engines/`).

**Frontend touchpoints.**
- `frontend/src/pages/SolvaApp.jsx`, `SolvaLanding.jsx`, `SolvaSession.jsx`.
- Components: `frontend/src/components/solva/{flow/*, artefact/*}`.
- Reducer: `frontend/src/lib/solvaFlow.js`.

**Integrations / dependencies.** Anthropic Claude Sonnet 4.5 (default standard tier) via direct SDK (Phase B.3). Synisense Shield on every LLM call (`surface="solva_v2.*"` per engine).

**Audit posture.** Per-engine reasoning row in `solva_v2_sessions.reasoning_audit_log[]`. Per-call Synisense run with input SHA-256.

**Known gaps.**
- "Solva v3" branding does not exist in code; it is UX-only. Engineering should not "fix" the rename — it would invalidate every `solva_v2_sessions` audit row.
- Cluster picker code paths (`routers/solva_v2.py:753`) remain post the v3 UX brief retiring clusters; deprecated but not deleted.

---

### 5.2 Synisense Shield — PII de-identification `[SHIPPED]`

**Purpose.** Ensure no LLM call leaves the boundary with raw PII. Every outbound payload is shielded; every response is rehydrated locally.

**User-visible behaviour.**
- No user-facing surface; runs in-process before every LLM call.
- The `/api/synisense/status` endpoint surfaces capacity and last-warmup status (`backend/routers/synisense.py`).
- Sensitivity bands assigned to every Studio block compute deterministically from the shielding report (`backend/studio_sensitivity.py`).

**Backend touchpoints.**
- Service package: `backend/services/synisense/{pipeline,encryption,llm_fallback,pool,presidio_engine,regex_recognisers,adapter}.py`.
- Single chokepoint invocation: `shield_payload_async` imported at `backend/llm_service.py:163`.
- Routers: `backend/routers/synisense.py` (`/synisense/status`, `/synisense/dryrun`, `/admin/synisense/perf`).

**Surface taxonomy (verbatim distinct values found in code).** `chat`, `chat_classifier`, `chat_four_check`, `chat_evidence_list`, `ingest`, `briefing`, `deck`, `report`, `brief`, `minutes`, `journal_commentary`, `enhance`, `blog`, `solva_v2.framing`, `solva_v2.synthesis`, `solva_v2.reflection`, `solva_v2.hypothesis`. The surface tag is the join key for compliance audits — every row in `db.synisense_runs` carries it.

**Integrations / dependencies.**
- spaCy `en_core_web_lg` for NER. Baked into the prod Docker image at build time (`Dockerfile.backend`) so cold starts don't pull on first request.
- Presidio analyzer + anonymizer.
- LLM fallback: Gemini 2.5 Flash via the proxy (small-model judge layer 3).

**Audit posture.**
- `db.synisense_runs` — one row per call, contains `input_sha256` (NEVER raw text), surface tag, identifiers-masked count, latency, layer that won.
- `db.synisense_shield_maps` — per-call shield map, AES-GCM envelope-encrypted with `SYNISENSE_MASTER_KEY`, TTL via `expireAfterSeconds`.

**Known gaps.**
- Pulse signals are **not** routed through Synisense at read time (no `surface="pulse"` runs are written). Pulse renders DB rows directly. Same-context boundary holds today; cross-context aggregation will require lifting this gap (§5.10).
- Inbound email payload Synisense fire — unverified that `surface="ingest"` runs cover Postmark-delivered raw bodies; worth confirming during the Postmark hardening pass.

---

### 5.3 Chat — multi-model, two-pass, real streaming, hash-chained audit `[SHIPPED]`

**Purpose.** A deep-reasoning surface for executives and NEDs. Five model choices. Every reply is shielded, four-check'd and audited.

**User-visible behaviour.**
- Five chat models surfaced at `GET /api/chat/models`: Claude Sonnet 4.5, Claude Haiku 4.5, GPT-5.2, Gemini 2.5 Pro, Gemini 2.5 Flash (`backend/routers/chat.py`).
- **Real per-token streaming** via SSE (`POST /api/chats/{cid}/messages/stream`). Tokens trickle in within ~1 s of first byte for direct-stream providers (Phase B.3).
- Streaming indicator on the in-progress assistant bubble; on `message` event the canonical shielded text replaces the in-progress content.
- Hash-chained audit chain export at `GET /api/chats/{cid}/audit/export.zip` returns the rows and a verifier (`backend/routers/chat.py:2545`).
- Banned-word voice-violation suppression: if the model emits a banned term, the reply is rewritten or refused per refusal templates (`services/two_pass.py`).

**Backend touchpoints.**
- Router: `backend/routers/chat.py` (~2700 lines, 13 routes).
- Streaming SSE generator at `_event_gen` (around `:2000` after Phase B.3 edit).
- Two-pass orchestration: `backend/services/two_pass.py` — `classify_turn_async`, `CHAT_ADAPTED_FOUR_CHECK_PROMPT`, `find_banned_word`, `split_two_pass`.
- Hash chain: `prev_hash` + `row_hash` over canonical payload (`:148-183`); genesis `"GENESIS-AKKI-CHAT-AUDIT-2026"` (`:150, :2652`).
- Direct streaming wrapper: `backend/services/llm_streaming.py`.

**Frontend touchpoints.**
- `frontend/src/pages/Chat.jsx` — handles `delta`, `message`, `error` events; streaming-ready since Phase B.1, real tokens since Phase B.3.
- Model picker: `frontend/src/components/chat/ModelAvatar.jsx`.

**Integrations / dependencies.**
- Anthropic + Gemini direct SDKs (Phase B.3), Emergent proxy fallback.
- Synisense Shield on every prompt + reply (`surface="chat"`, `chat_classifier`, `chat_four_check`, `chat_evidence_list`).

**Audit posture.**
- `db.chat_audit_log` rows carry `prev_hash`, `row_hash`, canonical payload (immutable shape — see §6.5 of `docs/ENGINEERING_ONBOARDING.md`).
- Phase B.3 added `provider_used ∈ {anthropic_direct, gemini_direct, proxy_buffered}` and `fallback_triggered: bool` to the persisted row + the SSE `message` event (does NOT change the canonical hash payload — additive metadata only).
- Daily 03:30 UTC cron sweeps soft-deleted chats older than 30 days, hard-removing them; one `chat.hard_deleted` row preserves chain integrity.

**Known gaps.**
- The strategic-deliverable two-pass branch in chat (Pass 2) still uses proxy-buffered (already 2× LLM calls; deferred until traffic justifies streaming the second pass too — Phase B.3 follow-up).
- GPT-5.2 stays on proxy until direct OpenAI keys are provisioned. Boot log makes this explicit.

---

### 5.4 Work Studio — aggregate listing + drawer + 5-button bar `[SHIPPED]`

**Purpose.** The single surface where an executive turns aggregates (Board Pack, Minutes, Committee Pack) into board-facing deliverables.

**User-visible behaviour.**
- Three tabs by aggregate kind on `/app/work-studio`.
- Single-drawer detail (~50% width side drawer; same UX shape as Document Journal's drawer).
- 5-button action bar: `Export brief` (DOCX), `Export summary deck` (PPTX), `Export report` (DOCX), `Enhance my deck`, `Enhance my report`.
- Async pattern: route returns 200 + `export_id` + `status="running"`; frontend polls `/api/contexts/{cid}/work-studio/exports/{eid}` for completion. Background task does Pass 1 (silent reasoning) + Pass 2 (strict JSON) + render + sensitivity scoring.
- On completion: download URL + sensitivity band + `Continue in chat` mints a follow-on chat tethered to the artefact + a deep-link doc.
- "Thin enhance" guard: if the user's enhance instruction is below the substance threshold, the system emits a verbatim refusal artefact (`backend/routers/work_studio_export.py:_is_thin_enhance_shape`).

**Backend touchpoints.**
- Router: `backend/routers/work_studio_export.py` (`POST /work-studio/export/{kind}`, `POST /work-studio/enhance/{kind}`, `GET /work-studio/exports/{eid}[/download]`).
- Renderers: `backend/services/work_studio_export.py` (deterministic; banned-word filter; content schema validator).
- LLM transport: `services.llm_streaming.collect_llm_text` per-pass (post Phase B.3 Option-A; see §5.15).
- Aggregate read: `GET /api/contexts/{cid}/briefings/aggregates[/{aid}]` (`backend/routers/briefings.py`).

**Frontend touchpoints.**
- `frontend/src/pages/WorkStudio.jsx` — 5-button bar at `:297-310`, BriefDrawer at `:174`.
- `frontend/src/components/studio/{BlockComposer,EnhanceModal,ExportModal,ShareArtefactModal}.jsx`.

**Integrations / dependencies.**
- python-docx (DOCX), python-pptx (PPTX), WeasyPrint + Jinja2 (PDF).
- Banned-word grep imported from `services/two_pass.py`.

**Audit posture.**
- `db.work_studio_exports` row per attempt: `kind`, `output_format`, `status`, `sha256`, `byte_len`, `sensitivity_band/score/reasons`, `pass_1_ms`, `pass_2_ms`, `voice_violation`, `continue_chat_id`, `continue_doc_id`, `llm_pass1`/`llm_pass2` (Phase B.3).
- Audit log rows: `work_studio.export.completed`, `work_studio.enhance.completed`.

**Known gaps.**
- `render_deck_pdf` raises `NotImplementedError`; PPTX is the deck output of record.
- A pre-existing post-LLM citation-index validator occasionally flags briefings with `error: validation:Section X references citation [N] but only Y citations are declared` — content-quality issue (LLM emits cite index beyond manifest length), not infrastructure. Tracked in §14.
- `llm_pass1`/`llm_pass2` only persist on success rows; failure rows do not record provider metadata. 4-line additive change available but not yet shipped.

---

### 5.5 Document Journal — Phase E rewire `[SHIPPED]`

**Purpose.** The substrate surface for Persona B (NED catch-up). Indexes, anchors, comments-on documents; serves as citation-tether source for every other surface.

**User-visible behaviour.**
- Top-nav slot **removed** in Phase E; entry point is the homepage `<AllDocumentsButton/>` button (`frontend/src/components/home/AllDocumentsButton.jsx`).
- Title-bar Upload + Camera buttons on `/app/workspace` for new ingestion.
- Single-drawer detail pattern (mirrors Work Studio).
- BM25 search across notes, extracted text and metadata: `GET /api/contexts/{cid}/document-journal/search?q={query}`.
- On-demand journal commentary: `POST /api/contexts/{cid}/documents/{did}/journal-commentary`.
- Reading View at `/app/documents/:id` with paragraph anchors; click any paragraph → "Ask AKKI" pre-tethers the chat.
- Document evolution diff between versions: `POST /api/contexts/{cid}/documents/{did}/evolution-diff`.

**Backend touchpoints.**
- Router: `backend/routers/documents.py` (16 endpoints).
- Service: `backend/document_commentary_service.py`, `backend/paragraph_anchors.py`, `backend/bm25.py`.
- Backfill: `POST /api/admin/journal/backfill` (`routers/admin_journal.py`).

**Frontend touchpoints.**
- `frontend/src/pages/Workspace.jsx` (Phase E rewrite).
- `frontend/src/pages/ReadingView.jsx`.
- `frontend/src/components/{documents/*, reading/*, home/AllDocumentsButton.jsx}`.

**Integrations / dependencies.**
- ClamAV virus scan (`backend/services/clamav_service.py`); bypassed in dev via `ALLOW_UNSAFE_UPLOADS=true`, mandatory in prod.
- S3 / local-disk storage (`backend/services/storage_service.py`).
- pypdf, python-docx for extraction.
- Synisense pipeline runs `surface="ingest"` on every uploaded document.

**Audit posture.**
- `db.documents` row with extracted_chars, status, sensitivity metadata.
- `db.document_views` and `db.document_engagement` for telemetry.
- Daily 03:00 UTC cron paragraph-anchors sweep.

**Known gaps.**
- Pre-2026-05-05 journal-commentary rows are mis-bucketed under `surface="briefing"` in `synisense_runs` (forensic only).
- Recent regression: homepage upload modal shipped with `${API_BASE}/api/...` double-prefix (fixed; see Risks §14).

---

### 5.6 Cycle Manager — Executive flow live, NED design-only `[PARTIAL]`

**Purpose.** Drives the board cycle from "Start cycle" to "Compilation sent". Owns agenda drafting, reportee assignment, contribution scoring, follow-up email generation.

**User-visible behaviour.**
- Six-step stepper at `/app/cycle`: **Agenda → Team → Contributions → Scoreboard → Follow-ups → Compilation** (`frontend/src/pages/Cycle.jsx`, `akki-w-medium` framed).
- Each step has its own backend endpoint (14 total under `cycle_manager.py`).
- Follow-ups send via Resend with `From: akki+<context_slug>@syni.ai`.
- Draft Compilation produces a citation-cited summary — currently with a placeholder citation row (see Known gaps).

**Backend touchpoints.**
- Router: `backend/routers/cycle_manager.py` (14 endpoints).
- Phase D additive collections: `db.cycle_agendas`, `db.cycle_team`, `db.cycle_contributions`, `db.cycle_followups`.
- Coexists with the legacy 30-endpoint `backend/routers/cycle.py` (questions/checklists/reports/committees/schedule). Same `/api` prefix; different verbs; no URL collision.

**Frontend touchpoints.** `frontend/src/pages/Cycle.jsx`.

**Integrations / dependencies.** Resend (outbound emails). Synisense on every LLM call within the flow.

**Audit posture.** Per-step audit_log rows; follow-ups recorded with sender + payload SHA-256.

**Known gaps.**
- **NED side has zero code today.** Design lives at `/app/docs/NED_CYCLE_MANAGER_DESIGN.md` (177 lines). The router is verbatim: *"D-003 — NED-side flow ships as design only … no NED endpoints here"* (`routers/cycle_manager.py:25-26`).
- Compilation step injects a placeholder citation row `{"doc_id": "stub", "doc_name": "Cycle compilation", …}` when no real citation is resolved (`routers/cycle_manager.py:726`).
- Two cycle routers coexist intentionally; cognitive collision risk for new contributors. Document the legacy/Phase-D split before any refactor.

---

### 5.7 Roles & Navigation — Executive/NED context binding `[SHIPPED]`

**Purpose.** Per-tab, per-context isolation so a NED on six boards does not leak data across them.

**User-visible behaviour.**
- Active context picker visible top-right.
- Switching contexts via the modal calls `POST /api/me/active-context`; the modal copy comes verbatim from server-authored memo strings (`backend/routers/active_context.py:44`) — frontend never invents these.
- `403 MEMBERSHIP_REVOKED` triggers a forced re-pick on the frontend, with the original-page restored after the new context is selected.
- Two tabs in different contexts do not trample each other.
- Sandbox accounts always route to `HomeExecutive` regardless of `declared_role` (`frontend/src/pages/AppHome.jsx:33-36`).

**Backend touchpoints.**
- `backend/routers/active_context.py` — `/api/me/{contexts,active-context,role-probe,role-probe/executive,role-probe/ned}`.
- `backend/core.require_context_membership` dependency on every authenticated route.
- Role derivation: `account.declared_role` is what the user said; `membership.role` is what they actually are; **live role uses `membership.role`** in this context.

**Frontend touchpoints.**
- `frontend/src/lib/api.js` — `ACTIVE_CONTEXT_STORAGE_KEY` in `sessionStorage` (NOT `localStorage`).
- `frontend/src/contexts/AuthContext.jsx` — switch-flow event handlers; listens for `akki:active-context-changed`.
- Switch modal: `frontend/src/components/layout/ContextSwitchModal.jsx`.

**Integrations / dependencies.** None external.

**Audit posture.** `db.audit_log` rows for context switch / role probe / membership revocation.

**Known gaps.** None that are actionable today. The `localStorage` vs `sessionStorage` choice is intentional and tested.

---

### 5.8 Export Pipeline — deterministic .docx / .pptx / .pdf `[SHIPPED]`

**Purpose.** Same input bytes → same output bytes. Auditable. SHA-256 returned per render.

**User-visible behaviour.**
- Five renderers: `render_brief_docx`, `render_deck_pptx`, `render_report_docx`, `render_brief_pdf`, `render_report_pdf`.
- Banned-word scanner runs on every generated string (`scan_for_banned_words`).
- Schema validator runs on the LLM-emitted content_dict (`validate_content`).

**Backend touchpoints.**
- Service: `backend/services/work_studio_export.py:1-21` — explicit determinism docstring.
- All renderers return `(bytes, sha256, filename)`.
- Cycle Manager, Solva v2, Briefings export endpoints all use the same render contract.

**Frontend touchpoints.** Download anchors honour `Content-Disposition: attachment` from the backend; SHA-256 surfaced in the export row metadata.

**Integrations / dependencies.** python-docx, python-pptx, WeasyPrint + Jinja2, ReportLab.

**Audit posture.** Every export row carries `sha256`, `byte_len`. Sensitivity metadata follows the renderer.

**Known gaps.**
- `render_deck_pdf` raises `NotImplementedError` — PPTX is the deck output of record.
- Determinism is documented but **not enforced by a CI test** in this repo. `test_render_determinism.py` does not exist; trust is in the code shape, not in a regression check. Quick-win for Phase 2.

---

### 5.9 Enhance & Continue-in-Chat `[SHIPPED]`

**Purpose.** Iterate on a generated artefact via free-text instructions; mint a follow-on chat tethered to the artefact for further refinement.

**User-visible behaviour.**
- `Enhance my deck` and `Enhance my report` buttons in Work Studio's 5-button bar.
- User supplies an instruction string; system runs the same Pass-1+Pass-2 pipeline with the prior artefact + instructions in scope, then re-renders.
- After both export AND enhance, a chat is minted tethered to the artefact (`continue_chat_id` + `continue_doc_id` on the export row).
- "Thin enhance" guard: if the instruction lacks substance, system emits the verbatim refusal artefact rather than a degraded enhancement (`_is_thin_enhance_shape` at `routers/work_studio_export.py:91`).

**Backend touchpoints.** `backend/routers/work_studio_export.py:_run_enhance` calls into `_run_two_pass_for_export` (shared with `_run_export`).

**Frontend touchpoints.** `frontend/src/components/studio/EnhanceModal.jsx`.

**Integrations / dependencies.** Synisense `surface="enhance"`. Resend not used.

**Audit posture.** Same row + audit shape as exports; `source: "enhance"` differentiates from `source: "export"`.

**Known gaps.** None on the happy path. Thin-enhance refusal copy could drift if the LLM is invoked indirectly; the verbatim memo refusal text is hard-coded for safety.

---

### 5.10 Akki Pulse — same-context aggregator `[PARTIAL]`

**Purpose.** A within-context signal feed surfacing recent risks/hypotheses/follow-ups with social actions (save, comment, resolve, take-to-Solva).

**User-visible behaviour.**
- Feed at `/app/pulse`. Type and freshness filters.
- Social actions per signal: `save`, `comment`, `share`, `resolve`, `take-to-solva`.
- "Take to Solva" mints a Solva v2 session pre-populated with the signal text; returns `session_id` (`backend/routers/pulse.py:take-to-solva`).
- Filters scope by active context only.

**Backend touchpoints.**
- Router: `backend/routers/pulse.py` (6 endpoints — feed + 5 actions).
- Verbatim docstring: *"same-context only. Cross-context aggregation requires Privacy Wall completion; that is a separate big lift and is deliberately deferred."*

**Frontend touchpoints.** `frontend/src/pages/Pulse.jsx` (489 lines).

**Integrations / dependencies.** Reuses `db.signals` and `db.signal_actions`. Solva v2 minting via shared session creator.

**Audit posture.** Per-action audit_log row. No Synisense run today (renders DB rows directly).

**Known gaps.**
- **Cross-context aggregation deferred.** Today's Pulse is single-context. Roadmap (§15) tracks the lift behind Privacy Wall §2c.
- Cluster resolution still labelled `"deferred"` (`routers/pulse.py:426`).
- An orphan file `frontend/src/pages/PulsePlaceholder.jsx` exists from the pre-F.1 era; not imported anywhere except itself (quick-win cleanup).
- Existing `db.signals` rows do not carry the `PULSE_CLASSIFIER_ENUM` (`services/privacy_wall.py`) topic field; would need a one-time backfill once the cross-context lift ships.

---

### 5.11 Privacy Wall — projection guards (Phase 2b live, 2c deferred) `[PARTIAL]`

**Purpose.** Prevent cross-context leakage on read paths. Allowlist/denylist field projection on Mongo docs that surface in cross-context aggregations.

**User-visible behaviour.** Invisible — runs behind cross-context aggregation routes (`/me/governance/audit`, `/me/home/stream`, `/me/shares/{inbox,outbox}`).

**Backend touchpoints.**
- Module: `backend/services/privacy_wall.py`.
- Live call sites: `routers/governance.py:24, 66`, `routers/shares.py:27, 490-544`.
- Strict mode: `STRICT_PRIVACY_WALL` (default true) logs drift at WARN; `STRICT_PRIVACY_WALL_RAISE` (default false) escalates to a `PrivacyWallDriftError` 500.

**Frontend touchpoints.** None — backend-only.

**Integrations / dependencies.** None.

**Audit posture.** Drift events surfaced via WARN logs; `STRICT_PRIVACY_WALL_RAISE` gives hard-fail in Production should ops want it.

**Known gaps.**
- **Phase 2c placeholders explicit:** `redact_for_pulse_text(text)` is a no-op pass-through (`:27`, `:392-400`); `assemble_pulse_prompt(per_context_outputs)` raises `NotImplementedError("Phase 2c")` (`:30-32`, `:403`).
- Pulse same-context feed is **not** routed through `project_for_pulse` (no import in `routers/pulse.py`). Same-context boundary holds today by accident-of-architecture; cross-context lift will require both Phase 2c AND wiring Pulse through the projection guard.

---

### 5.12 Authentication & Sandbox `[SHIPPED]`

**Purpose.** Identity and tenancy. JWT + bcrypt; per-tab session; multi-context membership; sandbox accounts for trial.

**User-visible behaviour.**
- `/signin`, `/signup`, `/invite/:token`, MFA setup at `/app/security`.
- Login returns access + refresh cookies (HttpOnly, `SameSite=none; Secure`); Bearer header also accepted.
- Sandbox flow at `/sandbox` — pre-auth demo across 5 industry contexts; conversion endpoint (`POST /api/sandbox/convert`) creates a real account from sandbox state.

**Backend touchpoints.**
- `backend/routers/auth.py` (9 endpoints).
- `backend/core.py` JWT/bcrypt helpers; HS256 8h access / 7d refresh.
- `backend/routers/sandbox.py` (25 endpoints, v1+v2).

**Frontend touchpoints.** `frontend/src/pages/{SignIn,SignUp,InviteAccept,AccountSecurity,SandboxV2}.jsx`. `frontend/src/contexts/AuthContext.jsx`.

**Integrations / dependencies.** `bcrypt` 4.1.3, `PyJWT` 2.12, `pyotp` (TOTP MFA), `qrcode`.

**Audit posture.** Sampled (1%) success + 100% failure into `db.auth_events`. `db.login_attempts` per attempt.

**Known gaps.**
- Invitation email is a **stub log** today (`routers/contexts.py:404`: `[invite-email-stub] to=… link=…`). `email_service.send_email` is wired; the call site just logs instead. 5-line fix listed under Roadmap.

---

### 5.13 Email Integrations — Resend (out) + Postmark (in) `[PARTIAL]`

**Purpose.** Outbound notifications (cycle follow-ups, share confirmations) via Resend. Inbound triage (forwarded board materials) via Postmark.

**User-visible behaviour.**
- Cycle Manager *Send* button delivers via Resend.
- Inbound Postmark webhook ingests forwarded mails; routes by per-account/context inbound token.

**Backend touchpoints.**
- `backend/email_service.py` — Resend wrapper; returns `{ok, id, mode}` envelope.
- `backend/routers/inbound_email.py` — Postmark webhook handler.
- `_verify_secret` constant-time compares the URL `?secret=` query param.

**Frontend touchpoints.** Only the Resend status surfaces (success toast). Postmark is webhook-only.

**Integrations / dependencies.** `RESEND_API_KEY`, `POSTMARK_SERVER_TOKEN`, `POSTMARK_WEBHOOK_SECRET` (Phase B.3 boot guard added).

**Audit posture.** Per-send `db.email_events` row (Resend); per-inbound `db.inbound_queue_raw` + parsed `db.inbound_queue` rows.

**Known gaps.**
- **Resend in test mode** today: only the registered test recipient delivers; everyone else gets `mode: test_mode_restricted` (`email_service.py:19, 57, 72`). Production must verify a sending domain.
- Inbound webhook authentication is URL-shared-secret, not HMAC-signature. Production boot guard added in Phase B.3 ensures `AKKI_ENV=production` refuses without `POSTMARK_WEBHOOK_SECRET` (or `POSTMARK_SERVER_TOKEN`) set.

---

### 5.14 Storage Pipeline — S3-compatible (MinIO in pod, Azure-deployable) `[SHIPPED]`

**Purpose.** Single backend abstraction for file storage that works against MinIO (dev/prod-on-VM), AWS S3, or any S3-compatible target.

**User-visible behaviour.** Invisible — runs behind Document Journal upload + Work Studio export download.

**Backend touchpoints.**
- `backend/services/storage_service.py` — `LocalDiskStorage` and `S3Storage` backends, switched by `STORAGE_BACKEND` env.
- AES256 SSE on every PUT (`.put_object(..., ServerSideEncryption="AES256")`); MinIO accepts the header silently if KMS is off.
- Migration helper: `scripts/migrate_local_to_s3.py`.

**Frontend touchpoints.** Download URLs surfaced via `/api/contexts/{cid}/work-studio/exports/{eid}/download` and `/api/contexts/{cid}/documents/{did}/download`.

**Integrations / dependencies.** `boto3` (`s3` backend); ClamAV scan upstream of every PUT in production.

**Audit posture.** Storage key recorded on the document/export row; bytes never logged.

**Known gaps.**
- **Dev pod uses `STORAGE_BACKEND=local`.** Production runbook reverses this (`STORAGE_BACKEND=s3` against MinIO container).
- ClamAV bypass via `ALLOW_UNSAFE_UPLOADS=true` is **dev-only**; production must set `false` and run the daemon (`docs/DEPLOYMENT.md` §3 deploy blocker #3).

---

### 5.15 Direct LLM Streaming + Strategic Failover (Phase B.3) `[SHIPPED]`

**Purpose.** Real per-token streaming for chat; strategic per-call failover (direct provider → proxy) for every LLM-using surface.

**User-visible behaviour.**
- Chat tokens render progressively; first byte ~1 s; smooth typing-indicator until `message` event swaps in canonical text.
- Behind the scenes, every LLM call across the app (chat, briefings, signals, decks, solva v2 engines, work studio export+enhance, cycle compilation) tries the direct Anthropic SDK or direct Gemini SDK first; on any 5xx/network/parse error, falls back to the Emergent proxy automatically — no user-visible failure.
- Boot log line: `[chat] streaming: claude=<direct_stream|proxy_buffered> gemini=<...> gpt=proxy_buffered` (`backend/server.py` `on_startup`).

**Backend touchpoints.**
- `backend/services/llm_streaming.py` — `LlmStreamChunk` dataclass; `stream_llm_direct` async generator; `collect_llm_text` non-streaming companion; `streaming_mode_per_provider` boot probe; `provider_for_model` mapper.
- `backend/llm_service.py` `call_llm` — single-call surface re-routed through `collect_llm_text` so all callers (briefings, signals, decks, solva v2, learn, …) benefit. Returns the same envelope shape as before plus two additive keys: `provider_used`, `fallback_triggered`.
- `backend/routers/chat.py` `_event_gen` — emits `data: {"type":"delta","text":...}` per chunk, then the existing `message` event with shielded `assistant_text` + `provider_used` + `fallback_triggered`, then `done`.
- `backend/routers/work_studio_export.py` — Pass 1 + Pass 2 of `_run_two_pass_for_export` swapped to `collect_llm_text` (Phase B.3 Option-A hardening, post-cutover).

**Frontend touchpoints.** `frontend/src/pages/Chat.jsx:400` — already streaming-ready; no changes required (frontend was the lead, backend was the bottleneck).

**Integrations / dependencies.** `anthropic>=0.39.0` (resolved to 0.100), `google-genai==1.71.0`, `emergentintegrations==0.1.0`.

**Audit posture.**
- Chat `message` event payload + persisted audit row include `provider_used` and `fallback_triggered` (additive, does not change the canonical hash payload).
- Work Studio rows include `llm_pass1` + `llm_pass2` provider/fallback metadata on success.
- Briefings rows include `llm_fallback` in the row + audit metadata when fallback fires.

**Known gaps.**
- Strategic-deliverable two-pass branch in chat (Pass 2 of strategic deliverables) still uses proxy-buffered (already 2× LLM calls; deferred until traffic justifies streaming the second pass too).
- GPT-5.2 stays on proxy until direct OpenAI keys are provisioned.
- Mid-stream failure handling: if direct path emits some deltas then errors, fallback is **NOT** attempted (would double-emit content). User sees `{"type":"error","code":"stream_interrupted"}`. Pre-emit failure does fall back.

---

## 6. User Journeys

### Journey A — Executive prepares a board cycle

**Frame.** It is Wednesday evening; the board meets next Tuesday at 10:00. The CFO needs to draft the agenda, score reportee contributions from the prior cycle, draft follow-ups, generate this cycle's brief and deck.

1. **Login at `/signin`.** JWT issued; HttpOnly cookies set. AuthContext writes the active context to `sessionStorage`. Lands on `/app` → `HomeExecutive` (role-aware dispatcher at `frontend/src/pages/AppHome.jsx`).
2. **Navigate to `/app/cycle`.** Cycle Manager loads `GET /api/contexts/{cid}/cycle/agenda` and presents the six-step stepper. Step 1: Agenda. The handler pre-populates from the prior cycle's compilation + recent active signals. **Audit:** one `cycle.agenda.viewed` row in `db.audit_log`.
3. **Confirm or edit the agenda.** Click *Save & continue*. `POST /api/contexts/{cid}/cycle/agenda` writes to `db.cycle_agendas`. Step 2: Team.
4. **Step 2 — Team.** Reportees auto-populated from `db.reportees` + last cycle's contributions. The CFO drops one reportee (cycle-end swap). `POST /cycle/team` updates `db.cycle_team`. **Audit:** `cycle.team.updated`.
5. **Step 3 — Contributions.** AKKI pulls each reportee's last-cycle submission. The CFO grades them via the Scoreboard. `POST /cycle/contributions/{ccid}/score` writes to `db.cycle_contributions`. **Audit:** one `cycle.contribution.scored` row per reportee.
6. **Step 4 — Scoreboard / Readiness.** `GET /cycle/readiness` shows the cycle's distance-to-ready (% of contributions scored, % of agenda items resolved). The CFO opens **Document Journal in a new tab** (`/app/workspace`) to drop in this month's MI pack — ClamAV scans, extraction completes, Synisense `surface="ingest"` run logged.
7. **Back to `/app/cycle` Step 5 — Follow-ups.** Click *Draft follow-ups*. `POST /cycle/follow-ups/draft` runs an LLM call (now via the Phase B.3 direct path; provider_used recorded). Drafts land in `db.cycle_followups` with `status=draft`.
8. **Review + edit each follow-up.** Click *Approve*. `POST /cycle/follow-ups/{fid}/approve`. Click *Send*. `POST /cycle/follow-ups/{fid}/send` calls Resend with `From: akki+<context_slug>@syni.ai`. **Audit:** `cycle.followup.sent` per email.
9. **Step 6 — Compilation.** Click *Compile cycle*. `POST /cycle/draft-compilation` runs the LLM with the full cycle state in scope. Output: a citation-cited summary written to `db.boardpacks` as a special-source briefing.
10. **Open `/app/work-studio`.** The compilation appears in the *Board Pack* tab. Open it in the side drawer. Click *Export brief* (DOCX). Async pattern: route returns 200 + `export_id` + `status=running`; frontend polls `/api/contexts/{cid}/work-studio/exports/{eid}` until `complete`.
11. **Background task runs Pass 1 + Pass 2 + render + sensitivity.** Phase B.3 Option-A: direct Anthropic SDK serves both passes. WeasyPrint deterministic render; SHA-256 returned. **Audit:** `db.work_studio_exports` row with `llm_pass1.provider="anthropic_direct"`, `llm_pass2.provider="anthropic_direct"`.
12. **Click `Export summary deck` (PPTX).** Same pipeline; different renderer (`render_deck_pptx`).
13. **Click `Continue in chat`** on the brief. Mints a follow-on chat tethered to the export (`continue_chat_id`). The CFO refines the *Risk* section conversationally; replies stream in via direct Anthropic SDK. **Audit:** chat hash chain extends.
14. **Click *Share with NEDs*.** A share token is minted (`db.studio_shares`); link `https://akki.syni.ai/share/{token}` is generated. NEDs receive the link via Resend.

**Refusal branch (step 7).** When drafting a follow-up that asks the LLM to *"explain why the FD missed the cash forecast"*, the four-check pass detects an unsourced attribution claim (no document in scope supports the *why*). The system emits a verbatim refusal: *"I can summarise the variance against forecast and the named factors in the FD's submission. I cannot infer intent without explicit evidence."* The CFO accepts the refusal, reframes the prompt, the second pass succeeds.

### Journey B — NED catches up before the audit committee

**Frame.** The NED has 2 hours before tomorrow's audit committee. Three boards are due in the same week; this is the most material one.

1. **Login at `/signin` as NED.** Lands on `/app` → `HomeNed`. Top-bar shows next cycle phase indicator.
2. **Click `<AllDocumentsButton/>` on Home.** Navigate to `/app/workspace`. Document Journal lists this cycle's documents reverse-chronologically.
3. **BM25 search "receivables ageing"** — `GET /api/contexts/{cid}/document-journal/search?q=receivables+ageing` returns top 10 paragraph hits across the MI pack and the audit-committee submission.
4. **Open the MI pack in the side drawer.** Commentary stream loads on the right (cached if previously generated; on-demand if first read — `POST /journal-commentary`). **Audit:** Synisense `surface="journal_commentary"` run.
5. **Click *Open in body modal*.** Reading View at `/app/documents/{did}` renders the full doc with paragraph anchors. The NED hovers Note 14 (receivables ageing breakdown).
6. **Click *Ask AKKI* on Note 14.** Chat opens at `/app/chat` pre-tethered to the paragraph (deep-link param). Prompt: *"Summarise what this paragraph says about >90-day receivables and contrast with the prior cycle."*
7. **Tokens stream in.** Direct Anthropic SDK serves; first byte ~1 s. The reply quotes the paragraph anchor, adds a comparison against the prior cycle's MI pack from the same context, and surfaces one open question for the audit committee.
8. **NED prompts again: "Why has the executive understated this risk?"** — the four-check detects an unsourced intent attribution. Refusal artefact emitted verbatim: *"AKKI does not attribute intent to the executive without explicit evidence. The variance pattern is real; the cause is not in scope. Reframe as: what structural factors would explain this trend?"*
9. **NED reframes.** Direct Anthropic SDK serves; the answer triangulates two structural framings, weighted by probability, with citations to the MI pack and the prior cycle's compilation.
10. **NED goes to Solva — `/app/solva` → `simulate_hypothesis` card.** Frame: *"What if the receivables-ageing trend continues for two more cycles?"* Solva runs `framing → grounding → hypothesis → synthesis → reflection`. Refusal-of-speculation guardrail does not fire because the hypothesis is named and grounded.
11. **PDF export of the Solva session.** `GET /api/solva/v2/sessions/{sid}/export.pdf`. The NED prints it for the meeting.
12. **`/app/pulse` for the same context.** Three new signals from the executive's last sweep. The NED saves the receivables one (`POST /api/contexts/{cid}/pulse/signals/{sid}/save`), comments on the audit-committee one. *Take to Solva* would spawn a new session; the NED skips that for now.
13. **End of evening — audit chain check.** The NED clicks *Export audit* on the Solva session. `GET /api/chats/{cid}/audit/export.zip` (for any chat referenced) returns the verifier. The NED archives the .zip in their personal records.

**Refusal branch (step 8).** Documented above — the unsourced-intent refusal. The NED accepts, reframes, system answers cleanly. The audit row records the refusal fired (`refusal_template="unsourced_intent_attribution"`).

### Journey C — Executive asks Solva for a hypothesis simulation

**Frame.** The CFO is considering a one-off restructuring charge for the half-year. Wants to test the hypothesis before committing executive time.

1. **`/app/solva`.** Solva landing surface (`frontend/src/components/solva/SolvaLanding.jsx`) shows the four cards.
2. **Click *Simulate hypothesis*.** `POST /api/solva/v2/sessions` with `submodule="simulate_hypothesis"`. New session id; redirects to `/app/solva/session/{sid}`.
3. **Frame the hypothesis.** "What is the financial-statement impact of a £4M restructuring charge in H2, including share-price reaction and analyst reception?"
4. **Solva runs the layered state machine** (`backend/services/solva_v2/state_machine.py`):
   - **Framing:** generates 3 candidate framings (cost-curve flat versus step, perception versus economics, signalling versus accounting).
   - **Grounding:** Synisense-shielded LLM call with the active context object + 5-tier grounding (`docs/PRODUCT_FEATURES_legacy_2026-05-04.md` describes the tiers). Per-engine reasoning_audit_log row written.
   - **Hypothesis layer (only for simulate_hypothesis):** runs the named hypothesis through each candidate framing.
   - **Synthesis:** Pass-2-style strict output with citations, confidence intervals, three reflection questions.
   - **Reflection:** "What would change my mind?" / "What's the explanation in six months if I got this wrong?" / "What am I disappointed by?"
5. **Each engine writes one row to `solva_v2_sessions.reasoning_audit_log[]`.** Engine name+version, input/output hashes, shielding flag, latency, provider tier, Synisense run id.
6. **Solva returns the artefact.** Frontend renders structured output with grounding citations and reflection questions inline.
7. **CFO clicks *Export*.** `GET /api/solva/v2/sessions/{sid}/export.pdf`. Deterministic PDF render via WeasyPrint. SHA-256 returned.
8. **CFO clicks *Continue in chat*.** A follow-on chat is minted tethered to the Solva session. Streaming Q&A about the simulation. Hash chain extends.

**Refusal branch (step 4).** When the user hypothesises *"What if the regulator pre-approves this charge?"* — the grounding contract fails (no document in scope speaks to regulator pre-approval; no precedent in the cycle history). Solva emits a refusal artefact rather than fabricated synthesis. The user can either (a) provide grounding documents and retry, or (b) accept the refusal and reframe.

---

## 7. Architecture Overview

```
                       Browser (TLS 1.3)
                              │
                              ▼
                    Cloudflare proxy (akki.syni.ai)        Full (strict)
                              │  origin TLS via Cloudflare Origin Certificate
                              ▼
   Azure VM  Ubuntu 22.04 LTS   Standard_B2ms (8 GB / 2 vCPU minimum)
   ┌─ systemd: akki.service
   │    ▪ akki-load-secrets.sh  ── Azure Key Vault → /etc/akki/akki.env (0600)
   │    ▪ docker compose -f /opt/akki/docker-compose.prod.yml up -d
   │
   │  docker network: akki_internal (bridge)
   │  ┌─────────────────────────────────────────┐
   │  │ frontend  nginx 1.27   :80 :443 (host)  │ ◀ only ports exposed off-host
   │  │   /etc/akki/origin.{crt,key} :ro        │
   │  │        │                                │
   │  │        ▼ /api/* → proxy_pass            │
   │  │ backend   uvicorn      :8001            │
   │  │   FastAPI + APScheduler (single replica)│
   │  │        │              │                 │
   │  │        ▼              ▼                 │
   │  │ clamav  :3310    minio  :9000  :9001    │
   │  └─────────────────────────────────────────┘
   │
   ▼ (mongodb+srv over TLS, retrywrites=false)
   Azure Cosmos DB for MongoDB (vCore)
   cluster:  <prefix>.mongocluster.cosmos.azure.com
   database: akki_prod
```

**Bidirectional flows.**
- **Chat (SSE):** browser → nginx (proxy_buffering off) → backend `/api/chats/{cid}/messages/stream`. Tokens stream back via `data: {...}` events. 300 s `proxy_read_timeout` allows for two-pass orchestration on long prompts.
- **Synisense (in-process):** before every LLM call inside the backend container; never crosses the network boundary; results written to `db.synisense_runs` (input SHA-256 only) and `db.synisense_shield_maps` (AES-GCM payloads with TTL).
- **Audit (write-only):** every authenticated request that mutates state writes to `db.audit_log` (single mutation collection). Chat additionally hash-chains into `db.chat_audit_log`.

**Process model.**
- Single backend replica (APScheduler crons run in-process; no leader election yet — see §12).
- nginx-served frontend (CRA build artefact, hashed assets immutable, `index.html` no-store).
- Separate ClamAV + MinIO containers on the same docker network.

For the deployment runbook, see `docs/DEPLOYMENT.md` — this section deliberately stops at the architectural level.

---

## 8. Data Model

| Collection | Purpose | Key fields | Audit / compliance role |
|---|---|---|---|
| `accounts` | User identity | `id` (UUID), `email` (unique), `password_hash` (bcrypt), `declared_role`, `mfa_enabled`, `is_superadmin`, `first_session.status` | Holds password hash + MFA secret. NOT hash-chained. Sampled login events into `db.auth_events`. |
| `memberships` | Per-context tenancy | `(account_id, context_id)`, `role ∈ {executive, ned}`, `sub_role`, `status`, `provisioning` | Live-role join key. Revocation triggers `403 MEMBERSHIP_REVOKED`. |
| `contexts` | Tenant boundary | `id`, `name`, `type`, `industry`, `jurisdiction`, `owner_account_id`, `status`, `progress_state` | Privacy boundary unit. All cross-context aggregation guarded via `project_for_pulse`. |
| `documents` | Document Journal substrate | `id`, `context_id`, `name`, `storage_key`, `extracted_text` (or pointer), `extracted_chars`, `status`, `sensitivity_band`, `synisense_run_id` | Synisense `surface="ingest"` run on every upload. Storage AES256 SSE. |
| `chat_messages` | Chat content | `chat_id`, `seq`, `role`, `content`, `provider_used` (Phase B.3), `fallback_triggered` (Phase B.3), `voice_violation`, `refusal_template` | Hash-chain row written alongside; raw content TTL'd 30d on soft-delete. |
| `chat_audit_log` | Hash-chained audit | `chat_id`, `seq`, `prev_hash`, `row_hash`, canonical content payload | **Hash-chain immutable.** Genesis `GENESIS-AKKI-CHAT-AUDIT-2026`. Daily 03:30 UTC retention sweep with chain-preserving hard-delete row. |
| `boardpacks` | Briefings (M.3 migration target — name retained) | `id`, `context_id`, `version`, `title`, `items[]`, `signal_ids[]`, `mode`, `shielding`, `llm_fallback` (option-b legacy field), `status` | Per-briefing audit row in `db.audit_log`. Synisense `surface="briefing"`. |
| `signals` | Pulse + signal feed substrate | `id`, `context_id`, `kind`, `topic`, `summary`, `created_at`, `status` | No PII at rest assumed (signals are derivative from already-shielded LLM calls). `signal_actions` records every interaction. |
| `solva_v2_sessions` | Solva reasoning sessions | `id`, `context_id`, `submodule`, `status ∈ {active, completed, abandoned, blocked_hard}`, `reasoning_audit_log[]`, `final_artefact`, `pdf_sha256`, `docx_sha256` | Per-engine audit rows in the embedded array. Synisense surfaces per engine. |
| `synisense_runs` | PII redaction audit | `id`, `surface`, `input_sha256`, `identifiers_masked`, `layer_won ∈ {regex, presidio, llm_fallback}`, `latency_ms`, `account_id`, `context_id`, `created_at` | **Never holds raw text.** Surface is the join key for compliance audits. |
| `synisense_shield_maps` | Per-call shield map | `run_id`, `payload_aesgcm_envelope`, `expires_at` | AES-GCM with `SYNISENSE_MASTER_KEY`. TTL via `expireAfterSeconds`. **Master key non-rotatable today** — see §14. |
| `work_studio_exports` | Export + enhance audit row | `id`, `context_id`, `kind`, `output_format`, `status`, `sha256`, `byte_len`, `sensitivity_*`, `pass_1_ms`, `pass_2_ms`, `llm_pass1`, `llm_pass2` (Phase B.3), `continue_chat_id`, `continue_doc_id` | SHA-256 per render. Provider provenance (Phase B.3) on success rows. |
| `cycle_agendas` | Cycle Manager Phase D | `context_id`, `cycle_id`, `agenda_items[]`, `status` | Per-step audit row. |
| `cycle_team` | Cycle reportee assignments | `context_id`, `cycle_id`, `members[]` | Per-step audit row. |
| `cycle_contributions` | Reportee submissions | `context_id`, `cycle_id`, `reportee_id`, `submission`, `score`, `status` | Per-score audit row. |
| `cycle_followups` | Drafted/sent follow-ups | `context_id`, `cycle_id`, `recipient`, `body_draft`, `body_sent`, `status`, `sent_at`, `resend_message_id` | Per-send audit row. Resend ID retained for forensic cross-reference. |
| `audit_log` | Generic audit trail | `id`, `account_id`, `context_id`, `action`, `resource_type`, `resource_id`, `metadata`, `created_at` | Append-only. Surfaced via `GET /api/me/governance/audit`. |
| `health_check` | `/api/health` write-test | `ts` (ISODate) | **TTL index recommended** (`expireAfterSeconds=86400`) to prevent row bloat on docker-compose 30s pings. Listed as a deploy blocker. |

For the full collection inventory (~85 collections), see the audit at `docs/CODE_INVENTORY_2026-05-05.md` and `docs/INVENTORY_2026-05-{02,04}.md`.

---

## 9. Security & Privacy Stance

**Synisense Shield as the boundary.** Every LLM call routes through `shield_payload_async` at the single chokepoint in `backend/llm_service.py:163`. The ladder is regex → Presidio (spaCy) → small-model LLM judge fallback. The surface taxonomy (`chat`, `chat_classifier`, `chat_four_check`, `chat_evidence_list`, `ingest`, `briefing`, `deck`, `report`, `brief`, `minutes`, `journal_commentary`, `enhance`, `blog`, plus `solva_v2.*`) is the join key on every audit query. `db.synisense_runs` rows hold input SHA-256 only, never raw text. `db.synisense_shield_maps` rows hold AES-GCM-encrypted originals with a TTL.

**Hash-chained audit log.** Chat audit rows compute `row_hash = SHA256(prev_hash + canonical_content_payload)`. Genesis `prev_hash = "GENESIS-AKKI-CHAT-AUDIT-2026"` (`backend/routers/chat.py:150, :2652`). Export at `GET /api/chats/{cid}/audit/export.zip` returns the chain plus a verifier script; tampering at any row breaks the chain mathematically and the verifier flags the offending row.

**Privacy Wall.** Cross-context read paths are guarded by `project_for_pulse` (collection allow/denylist field projection) and `project_audit_row` (drops audit metadata that could leak across boundaries). Strict mode (`STRICT_PRIVACY_WALL=true`, default) logs drift at WARN; `STRICT_PRIVACY_WALL_RAISE=true` (default false) escalates to a `PrivacyWallDriftError` 500 — production-grade hardening when ops is ready.

**Server-authored refusals.** The deterministic refusal templates today are `thin_input` (UI tells user the prompt is below the substance threshold and what would push it above), `unsourced_claim` (four-check found a model claim with no citation), `unsourced_intent_attribution` (four-check found an attribution of intent to a person without explicit evidence), `voice_violation` (banned-word grep), and the Phase D *placeholder citation* surfacing in Cycle Manager. **Less deterministic surfaces** still rely on LLM discretion: `named_assumption` framing in Solva's reflection layer, and the suite of Solva refusal-ladder steps (`backend/services/solva_v2/refusal.py`).

**Secret management.** Production: Azure Key Vault + VM managed identity; secrets fetched into `/etc/akki/akki.env` (0600) on every boot + every deploy by `scripts/deploy/akki-load-secrets.sh`. Never-commit policy enforced by `.gitignore` (`.env` and `.env.*`). Rotation procedures documented in `docs/DEPLOYMENT.md` §11. Two exceptions: `JWT_SECRET` rotation requires a dual-accept window; `SYNISENSE_MASTER_KEY` rotation is not yet supported (needs a re-encryption migration that doesn't exist).

---

## 10. Compliance Posture

**What an auditor would find today.**
- **Hash-chained chat audit.** Every chat reply contributes one row with `prev_hash` + `row_hash` over an immutable canonical payload. Tamper-evident; verifier script ships alongside the export.
- **Surface-tagged PII redaction with input-only SHA-256 storage.** `db.synisense_runs` records the surface, the layer that won, latency and identifiers-masked count — but never the raw text. Original PII held in `db.synisense_shield_maps` under AES-GCM with TTL.
- **Deterministic export hashing.** Every Work Studio export row carries the file's SHA-256 plus byte length. Re-rendering the same input produces the same hash; auditors can re-run and compare.
- **Scheduled retention sweeps.**
  - Daily 03:00 UTC paragraph-anchors sweep (`POST /cron/paragraph-anchors-sweep`).
  - Daily 03:30 UTC chat-retention sweep (`POST /api/admin/chat-retention/sweep`) — soft-deleted chats older than 30 days are hard-removed; one `chat.hard_deleted` row per chat preserves chain integrity.
  - Daily 04:00 UTC Solva v2 stale-session sweep (`POST /api/solva/v2/cron/stale-session-sweep`).
  - Mon 08:00 UTC Influence Digest cron.
  - Tue 10:00 UTC blog weekly cron.
- **Audit log export.** `GET /api/me/governance/audit/export` (POST per the route signature) returns a context-bounded extract for the ops team.

**What is NOT audit-grade today.**
- **Same-context Pulse signal feed** is not routed through Privacy Wall projection guards. Same-context boundary holds, but the projection guard would be the belt-and-braces. Quick-win listed in §15.
- **GPT-5.2 streaming** is proxy-buffered, not direct. Token streaming for OpenAI models is therefore not real per-token. Boot log makes this explicit; no-token-streaming claim is documented.
- **`db.signals` topic field** does not yet enforce `PULSE_CLASSIFIER_ENUM` (privacy-wall constant defined but unused). One-time backfill listed for the cross-context lift.
- **Postmark inbound webhook** authenticates via URL `?secret=` shared-secret, not HMAC signature. Boot guard added in Phase B.3 prevents production starting without a secret. Hardening to HMAC is a roadmap item.
- **Determinism of exports** is documented in code (`backend/services/work_studio_export.py:1-21`) but not enforced by a CI regression test. Quick-win Phase 2.

**Proposed roadmap to full audit-grade.**
1. Add a deterministic-render CI test (~30 lines).
2. Wire Pulse same-context reads through `project_for_pulse`.
3. Backfill `db.signals.topic` against `PULSE_CLASSIFIER_ENUM`.
4. Implement Postmark HMAC signature verification (replace shared-secret).
5. Provision direct OpenAI keys; bring GPT-5.2 onto the direct streaming path.
6. Build the SYNISENSE master-key rotation migration (greenfield work — not needed for first prod boot, but blocks any subsequent rotation event).

---

## 11. Integrations

| Provider | Purpose | Status | Fallback behaviour | Where the key lives |
|---|---|---|---|---|
| Anthropic (Claude Sonnet 4.5 / Haiku 4.5) | Primary LLM (chat, briefings, Solva, Work Studio) | `[SHIPPED]` direct SDK + proxy fallback | Per-call fallback to Emergent proxy on 5xx/network/parse | `ANTHROPIC_API_KEY` (Key Vault → `backend/.env`) |
| Google Gemini (2.5 Flash / 2.5 Pro) | Validator tier, Synisense LLM-fallback layer, secondary chat model | `[SHIPPED]` direct SDK + proxy fallback | Per-call fallback to Emergent proxy on 5xx/network/parse | `GEMINI_API_KEY` (Key Vault → `backend/.env`) |
| OpenAI (GPT-5.2) | One of the five chat models | `[SHIPPED]` proxy-buffered only | None — proxy is the only path today | `EMERGENT_LLM_KEY` (Key Vault → `backend/.env`) |
| Emergent universal LLM key | Multi-provider proxy (back-stop for direct paths) | `[SHIPPED]` | N/A (it is the fallback) | `EMERGENT_LLM_KEY` |
| Resend | Outbound email | `[PARTIAL]` test mode in dev pod; production must verify sending domain | None — failure logged + `mode: error` returned by `email_service.send_email` | `RESEND_API_KEY` |
| Postmark | Inbound email webhook | `[PARTIAL]` URL shared-secret today; HMAC roadmap | Boot refuses to start in production without secret | `POSTMARK_SERVER_TOKEN`, `POSTMARK_WEBHOOK_SECRET` |
| MinIO (S3-compatible) | Object storage on the production VM | `[SHIPPED]` | None — boto3 retries on 5xx; AES256 SSE on every PUT | `S3_ACCESS_KEY`, `S3_SECRET_KEY` |
| AWS S3 | Same code path as MinIO if pointed at AWS | `[SHIPPED]` (untested but supported) | Same as MinIO | Same env vars |
| ClamAV | Virus scanning on every upload | `[SHIPPED]` | Production `ALLOW_UNSAFE_UPLOADS=false`; dev bypass is intentional | None (TCP daemon on internal docker network) |
| Stripe | Billing | `[DEFERRED]` — `BILLING_ENABLED=false`; secrets unset | Boot guard refuses if flag flipped without keys | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` |
| Microsoft Presidio | PII NER (Synisense layer 2) | `[SHIPPED]` — spaCy `en_core_web_lg` baked into image | None — Synisense LLM fallback (layer 3) takes over on Presidio failure | None |
| WeasyPrint / python-docx / python-pptx | Document rendering | `[SHIPPED]` | Deterministic; failure surfaces in export row error field | None |
| APScheduler | In-process cron | `[SHIPPED]` (single-replica only) | Disarmed if `AKKI_CRON_SECRET` unset | `AKKI_CRON_SECRET` |
| Azure Key Vault | Production secret store | `[SHIPPED]` (scaffolded) | VM managed identity → `Key Vault Secrets User` role; missing-secret → boot refusal | `KEY_VAULT_NAME` env var |
| Azure Container Registry | Production image registry | `[SHIPPED]` (scaffolded) | VM `AcrPull` role; GitHub `acr-token` push | `ACR_LOGIN_SERVER`, `ACR_USERNAME`, `ACR_PASSWORD` (GitHub secrets) |
| Cloudflare | Edge TLS, WAF, DNS | `[SHIPPED]` (scaffolded) | Origin Certificate (15-year ECC) — fallback is Let's Encrypt if Cloudflare is bypassed | None at runtime |
| Azure Cosmos DB for MongoDB (vCore) | Production database | `[SHIPPED]` (scaffolded) | Standard connection-string failover via `mongodb+srv://`; **`retrywrites=false` mandatory** | `MONGO_URL` |

---

## 12. Operational Posture

**Cron jobs (in-process APScheduler — single replica only).**

The crons in `backend/server.py` (around `:540+`) only arm if `AKKI_CRON_SECRET` is set. They make HTTP self-calls so the cron logic lives in the regular request-response path, not in a special scheduler path:

| Schedule (UTC) | Job | Endpoint hit |
|---|---|---|
| Tue 10:00 | Blog weekly compose | `POST /api/blog/cron/weekly` |
| Mon 08:00 | Influence Digest | `POST /api/cron/weekly-digest` |
| Daily 03:00 | Paragraph-anchors sweep | `POST /api/cron/paragraph-anchors-sweep` |
| Daily 03:30 | Chat retention sweep | `POST /api/admin/chat-retention/sweep` |
| Daily 04:00 | Solva v2 stale-session sweep | `POST /api/solva/v2/cron/stale-session-sweep` |

**Single-replica constraint.** Running two backend replicas duplicates every cron fire — duplicate audit rows, duplicate digest emails, duplicate retention sweeps. Distributed-lock work (Mongo-leader-election or external scheduler) is required before any horizontal scale. Documented loudly in `docs/DEPLOYMENT.md` §11 and the Dockerfile and the compose file's `replicas: 1` comment.

**Health endpoints.**
- `GET /api/health` returns `{"status":"ok","db":"up"}` after a real Mongo write/read. Sufficient as combined liveness + readiness for docker compose `healthcheck`. Recommendation: add a `ts: 1` TTL index on `db.health_check` (24 h) to prevent row bloat at the docker-compose default 30 s ping interval.
- `GET /api/admin/health/full` (auth-required) — deeper probe of ClamAV, MinIO, LLM proxy. For ops dashboards.

**Logging.**
- Structured warn lines for `[brief-fallback] claude_502 → retrying with tier=fast` (legacy briefings option-b — removed Phase B.3); `[llm-fallback] direct_<provider>_failed → proxy_buffered` (Phase B.3 generic); `[postmark] signature verification disabled (no secret in env)` (dev only); `[chat] streaming: claude=... gemini=... gpt=...` (boot banner).
- `logs.json-file` driver in compose — 50 MB max-size × 5 max-file rotation per service.
- Forensic queries cross-reference `db.audit_log`, `db.synisense_runs`, `db.work_studio_exports.llm_pass{1,2}`, `db.chat_audit_log` to build a complete picture.

---

## 13. Status Snapshot

The one-page table.

| # | Feature | Status | Pending Work | Owner | Strategic blocker |
|---|---|---|---|---|---|
| 5.1 | Solva — decision-support | `[SHIPPED]` | Cluster-picker code paths post v3 UX brief retiring clusters; v2/v3 naming alignment | TBD | N |
| 5.2 | Synisense Shield | `[SHIPPED]` | Pulse-surface coverage; inbound-email surface confirmation | TBD | N |
| 5.3 | Chat (multi-model + B.3 streaming) | `[SHIPPED]` | Pass 2 strategic-deliverable streaming; OpenAI direct path | TBD | N |
| 5.4 | Work Studio (5-button bar) | `[SHIPPED]` | `llm_pass1/2` on failure rows; deck-PDF renderer | TBD | N |
| 5.5 | Document Journal | `[SHIPPED]` | Backfill mis-bucketed pre-2026-05-05 commentary surfaces | TBD | N |
| 5.6 | Cycle Manager (Executive flow) | `[SHIPPED]` | Compilation placeholder citation row | TBD | N |
| 5.6 | Cycle Manager (NED flow) | `[DEFERRED]` | Zero code today; design at `docs/NED_CYCLE_MANAGER_DESIGN.md` | TBD | Y |
| 5.7 | Roles & Navigation | `[SHIPPED]` | None | TBD | N |
| 5.8 | Export Pipeline (deterministic) | `[SHIPPED]` | CI determinism test; deck-PDF renderer | TBD | N |
| 5.9 | Enhance & Continue-in-Chat | `[SHIPPED]` | None | TBD | N |
| 5.10 | Akki Pulse (same-context) | `[PARTIAL]` | Cross-context aggregation requires Privacy Wall §2c | TBD | Y |
| 5.11 | Privacy Wall (2b live) | `[PARTIAL]` | Phase 2c — `redact_for_pulse_text`, `assemble_pulse_prompt`; signal classifier enforcement | TBD | Y |
| 5.12 | Authentication & Sandbox | `[SHIPPED]` | Invitation email stub → real send | TBD | N |
| 5.13 | Email — Resend | `[PARTIAL]` | Verified sending domain; out of test mode | TBD | N |
| 5.13 | Email — Postmark | `[PARTIAL]` | HMAC signature verification (replace URL shared-secret) | TBD | N |
| 5.14 | Storage (MinIO/S3 + ClamAV) | `[SHIPPED]` | Production cutover (`STORAGE_BACKEND=s3`, `ALLOW_UNSAFE_UPLOADS=false`) | TBD | N |
| 5.15 | Direct LLM Streaming + Failover (B.3) | `[SHIPPED]` | Pass 2 strategic-deliverable streaming; OpenAI direct | TBD | N |
| Infra | Production deployment scaffolding | `[SHIPPED]` | Secret rotation; Cosmos `retrywrites=false`; Postmark secret | TBD | Y (deploy blockers) |

---

## 14. Risks & Open Issues

The honest list. Each item has an owner placeholder (TBD) and a strategic-blocker flag.

1. **Solva v2/v3 naming drift.** UX brand says "Solva v3"; backend says `solva_v2` everywhere — package name, router prefix `/api/solva/v2`, collection `solva_v2_sessions`, audit-row surface `solva_v2.*`. Cosmetic but engineering-confusing. Deliberate non-rename: changing the strings would invalidate every audit row. **Mitigation:** call out in onboarding and in this doc; leave the code alone. Strategic blocker: N.
2. **NED-side Cycle Manager (zero code today).** Design lives at `docs/NED_CYCLE_MANAGER_DESIGN.md`. Roadmap line item. Strategic blocker: Y for the NED user persona.
3. **Cross-context Pulse + Privacy Wall §2c.** `redact_for_pulse_text(text)` is a no-op pass-through; `assemble_pulse_prompt(per_context_outputs)` raises `NotImplementedError("Phase 2c")`. Pulse today is same-context only. Strategic blocker: Y for the cross-board catch-up promise.
4. **Two-pass Pass 2 still proxy-buffered for strategic-deliverable chat turns.** Already 2× LLM calls; deferred until traffic justifies streaming the second pass too. Phase B.3 partial. Strategic blocker: N.
5. **Lemasy brief citation-index validator.** A pre-existing post-LLM content validator occasionally flags briefings with `error: validation:Section X references citation [N] but only Y citations are declared`. LLM emits cite indices beyond manifest length. Content-quality issue, not infrastructure. Fix: tighter prompt or relaxed validator (allow LLM to drop a cite from a section without failing the whole render). Strategic blocker: N.
6. **Invitation email stub.** `routers/contexts.py:404` logs `[invite-email-stub] to=… link=…` instead of calling `email_service.send_email`. Five-line fix; `email_service` already wired. Strategic blocker: N.
7. **Secret rotation pending before any prod deploy.** Every secret in Group A of `.env.example` (Key Vault names) must be rotated before first cutover. Current dev `.env` contains real-looking values that should be assumed compromised. Strategic blocker: Y.
8. **`SYNISENSE_MASTER_KEY` rotation is not supported.** Rotating it invalidates every row in `db.synisense_shield_maps` (forensic retrieval breaks). One-time issuance at first prod boot; never rotated until a re-encryption migration exists. Strategic blocker: Y if we ever need to rotate.
9. **ClamAV bypass + local storage are dev-only.** Production runbook reverses both (`ALLOW_UNSAFE_UPLOADS=false`, `STORAGE_BACKEND=s3`). Documented in `docs/DEPLOYMENT.md` §3. Strategic blocker: Y until first prod cutover.
10. **`db.health_check` row bloat.** `/api/health` writes a row per call. Without TTL, the docker-compose 30 s ping accumulates ~86 k rows per month. Listed as a deploy blocker in the runbook (`docs/DEPLOYMENT.md` §3 #7). Strategic blocker: N (operationally trivial).
11. **APScheduler single-replica constraint.** No leader election; running >1 backend instance duplicates every cron fire. Distributed-lock work is a separate piece of engineering. Strategic blocker: Y if we need to scale beyond 1 replica.
12. **Postmark webhook URL shared-secret.** Production boot now refuses without a secret (Phase B.3). Hardening to HMAC signature verification is a roadmap item. Strategic blocker: N (URL secret + IP allowlist is acceptable for MVP).
13. **Upstream Emergent proxy 502 flakiness.** Mitigated post-Phase-B.3 via direct provider failover in `services.llm_streaming`. Pre-B.3 surface coverage: `briefings.py` (option-b band-aid removed in B.3), `work_studio_export.py` (Option-A hardening landed post-B.3), and chat (B.3 native). All other LLM-using surfaces inherit the failover via `llm_service.call_llm`.
14. **`/api/api/...` double-prefix regression risk.** Fixed in `UploadModal.jsx` and `DocumentBodyModal.jsx`. Cautionary tale documented in `ENGINEERING_ONBOARDING.md` §12. Easy to re-introduce; PR review checklist line.
15. **Determinism not enforced by CI test.** `test_render_determinism.py` does not exist. Trust is in the code shape, not in a regression check. Quick-win.

---

## 15. Roadmap

| Next 30 days | Next 90 days |
|---|---|
| Production launch (Azure VM + Cosmos vCore + MinIO + ClamAV per `docs/DEPLOYMENT.md`) | Solva 2×2 restructure (v3 brand → v3 code path consolidation OR finalise the v2 stay-decision; rename to `solva_v3` if greenfield is justified) |
| Secret rotation across the full Group A list | Full NED Cycle Manager (Phase D NED-side endpoints + UI) |
| Invitation email stub → real `email_service.send_email` call | Cross-context Pulse — Privacy Wall §2c implementation (`redact_for_pulse_text`, `assemble_pulse_prompt`) + Pulse routed through `project_for_pulse` |
| Solva v2 ↔ v3 naming decision (rename the code OR document the brand-only stance permanently) | GPT-5.2 direct streaming once direct OpenAI keys are provisioned |
| NED Cycle Manager skeleton (router stubs + read-only view) | Distributed lock for APScheduler if scaling beyond 1 replica (Mongo-based leader election) |
| Postmark HMAC signature verification (replace URL shared-secret) | Determinism CI test for `services/work_studio_export.py` |
| `db.health_check` TTL index (deploy blocker) | `db.signals.topic` backfill against `PULSE_CLASSIFIER_ENUM` |
| `llm_pass1/2` on Work Studio failure rows (4-line additive change) | Synisense master-key rotation migration (greenfield work) |
| `frontend/src/pages/PulsePlaceholder.jsx` orphan deletion | Pulse signals via `project_for_pulse` (defensive guard before cross-context lift) |

---

## 16. Glossary

- **Synisense.** AKKI's PII de-identification engine. Three-layer ladder: regex → Presidio (spaCy) → LLM-fallback small-model judge. Per-call `surface=` tag identifies which feature triggered the run. AES-GCM shield maps hold the originals with a TTL.
- **Solva.** AKKI's decision-support reasoning engine. Four sub-modules: `seek_clarity`, `develop_strategy`, `simulate_hypothesis`, `get_perspective`. Layered state machine `framing → grounding → synthesis → reflection` (+`hypothesis` for `simulate_hypothesis`). UX brand "Solva v3"; code `solva_v2`.
- **Pulse.** AKKI's signal feed surface. Today same-context only; cross-context aggregator deferred behind Privacy Wall §2c.
- **Two-pass.** The chat orchestration: classifier pass → provider call → four-check pass. For `strategic_deliverable` turns, the provider call is itself a Pass-1 (silent reasoning) + Pass-2 (strict JSON output) pair.
- **Four-check.** Post-reply check: banned-word grep, refusal-template match, voice-violation match, evidence-list assertion. Lives in `services/two_pass.py`.
- **Privacy Wall.** Read-path projection guards (`project_for_pulse`, `project_audit_row`) that enforce allow/denylist field stripping when one tenant's data could surface in another tenant's view.
- **Surface.** A Synisense audit join key. One of `chat`, `chat_classifier`, `chat_four_check`, `chat_evidence_list`, `ingest`, `briefing`, `deck`, `report`, `brief`, `minutes`, `journal_commentary`, `enhance`, `blog`, `solva_v2.*`. Every Synisense run carries a surface.
- **Shield map.** A per-call AES-GCM-encrypted record of the original PII tokens redacted by Synisense, stored in `db.synisense_shield_maps` with a TTL. Used for forensic retrieval if an auditor needs to reconstruct an exchange.
- **Aggregate.** A Work Studio entity grouping a board-cycle's documents into one of three kinds: Board Pack, Minutes, Committee Pack. Read at `GET /api/contexts/{cid}/briefings/aggregates`.
- **Continue-in-chat.** The handoff from a Work Studio export or Solva session to a follow-on chat tethered to that artefact. Mints a `db.chats` row with `continue_source` set; the audit chain extends from the session into the chat.
- **Hash chain.** The chat audit log's `prev_hash` + `row_hash` mathematical lineage. Tamper-evident; verifier ships with the audit export.
- **Refusal template.** A server-authored block of copy that the system emits in place of an LLM-generated reply when the four-check fires. Today: `thin_input`, `unsourced_claim`, `unsourced_intent_attribution`, `voice_violation`, plus the Solva refusal ladder.
- **Active context.** The per-tab session-scoped tenant the user is currently operating in. Stored in `sessionStorage` (NOT `localStorage`); injected as `X-Active-Context` header on every authenticated request.
- **Cycle.** One iteration of the board-meeting drumbeat: agenda → submissions → committee briefings → board pack → meeting → minutes → follow-ups. Cycle Manager (Phase D) is the surface that drives the executive side; the NED side is design-only.

---

## 17. Appendix

**Env var reference.** See `.env.example` for the full list grouped into:
- Group A — Secrets to rotate
- Group B — Service config
- Group C — Feature flags / env class
- Group D — Frontend build-arg (`REACT_APP_BACKEND_URL`)
- Group E — Compose env-file references (`IMAGE_TAG`, `ACR_NAME`)
- Group F — Optional

**Key collections.** See §8 of this document. The full ~85-collection inventory lives in `docs/CODE_INVENTORY_2026-05-05.md`.

**Test credentials.** `memory/test_credentials.md`. Three sandbox accounts (admin / viewer / Julius) covering all three role classes.

**Related docs.**
- `docs/DEPLOYMENT.md` — production runbook (Azure VM + Cosmos vCore + Cloudflare; secrets, deploy, rollback, cutover).
- `docs/ENGINEERING_ONBOARDING.md` — engineer's first day; codebase tour; coding conventions; debugging recipes.
- `docs/NED_CYCLE_MANAGER_DESIGN.md` — the NED catch-up + cycle-monitoring + trust/data-isolation design that ships as code in a future phase.
- `docs/SYNISENSE_SCOPE.md` — Synisense surface taxonomy and operational scope.
- `docs/PRIVACY_WALL_DESIGN.md`, `docs/PRIVACY_WALL_LEAKAGE_AUDIT.md` — Privacy Wall design notes and the leakage audit that informed Phase 2b.
- `docs/MEMO.md`, `docs/MEMO_DECISIONS.md`, `docs/ROADMAP.md`, `docs/BUILD_PHASES.md` — historical product memos (read for the "why" behind a decision; this doc is the "what").
- `docs/PRODUCT_FEATURES.md` — **deprecated**; superseded by this document.

---

*End of document.*
