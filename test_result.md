#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

user_problem_statement: "Phase 11 — Distribution & Trust Visibility. ITEM A: Public Chair view routing fix (/share/:token) for non-AKKI directors with 30-day TTL, watermarks, and redacted read-only views; redaction assertion that hard-fails on un-redacted leaks. ITEM B: Extend Gemini 2.5 Flash second-pass validation to Decks, Reports, and Solve syntheses, persisting a `validation` payload, gating ValidatedBadge rendering on a real verdict, and enforcing a per-surface daily soft cap that never blocks the parent endpoint. ITEM C: Chat citation chips — backend retrieves grounded paragraphs via BM25 against a context's documents, instructs the LLM to cite using stable anchor markers, post-processes the reply to drop hallucinated citations, returns structured citations[] alongside the cleaned text; frontend renders inline `[n]` superscripts and a chip rail with click-through into the Reading Viewer at the cited paragraph anchor. Plus two surgical doc/comment cleanups (D + E)."

backend:
  - task: "Phase 11 ITEM A — Public Chair view (`/share/:token`) with redaction assertion + watermark payload"
    implemented: true
    working: true
    file: "/app/backend/routers/studio.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: "NA"
          -agent: "main"
          -comment: "Added `_assert_public_safe()` denylist check on the `GET /api/public/studio/read/{token}` response payload — fires 500 if any internal-metadata key (audience, validator_*, model, account_id, chain, quota, speaker_notes, etc.) appears at any depth. Response now also carries a `watermark` block (`label`, `recipient`, `expires_at` derived from the JWT exp). 30-day TTL was already in place. Frontend `/share/:token` route is an alias of `/shared/:token`. Test: (a) decode a valid token and confirm response includes `watermark` and excludes denylisted keys; (b) inject a denylisted key into the projection (e.g. monkeypatch a deck doc) and confirm 500; (c) confirm `/api/public/studio/track/{token}` still redirects to `/shared/{token}`."
        -working: true
          -agent: "testing"
          -comment: "PASS — backend_test.py covers deck + briefing public read paths. Verified: (1) share-email returns tracked_url with /shared/<token>; (2) GET /api/public/studio/read/{token} returns 200 with watermark{label,recipient,expires_at}; (3) deep recursive walk of response across deck (slides) and briefing (items) confirms zero denylisted keys (audience, validator_provider, validator_model, validation, model, model_id, account_id, chain, events, quota, speaker_notes, tier, quality_check, user_feedback, audience_assumed, outline_id, missing_context); (4) tamper tests — wrong-secret token → 400, malformed token → 400, expired token → 410. No 500s on bad input."

  - task: "Phase 11 ITEM B — Independent-validator fan-out to Decks / Reports / Solve syntheses with daily soft cap"
    implemented: true
    working: true
    file: "/app/backend/routers/decks.py, /app/backend/routers/cycle.py, /app/backend/routers/solve_engine.py, /app/backend/llm_service.py, /app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: "NA"
          -agent: "main"
          -comment: "Added `_validator_soft_cap_ok(surface)` in llm_service.py (default 200/day per surface, override via VALIDATOR_DAILY_SOFT_CAP). Counter is in `db.llm_validator_usage` with a unique compound index on (day_utc, surface). `validate_independent` now accepts `surface` + `account_id` and short-circuits to the `qualified` fallback when the cap trips (logs warning, never blocks). Hooks: decks.generate_deck (validates concatenated slide bodies before insert; persisted as `decks.validation`); cycle.send_report_up (validates report.body once on the draft → in_review transition, persisted as `reports.validation`, never overwritten on later sends); solve_engine.post_turn (validates synthesis body when phase=='synthesis', persisted as `solve_sessions.synthesis.validation`). Test: (a) generate a deck with a sufficiently long slide body and confirm `validation.verdict` is one of validated/qualified/flagged; (b) send a report up from draft and confirm `validation` is set on first send only; (c) confirm cap trips by setting VALIDATOR_DAILY_SOFT_CAP=1 and triggering twice on the same surface — second call should land on the cap fallback (`notes` includes 'Daily validator cap reached'); (d) verify `briefing` surface bypasses the cap (still calls validator)."
        -working: true
          -agent: "testing"
          -comment: "PASS on all four sub-surfaces. Decks: outline → generate returned deck with validation{verdict='validated',confidence=100,notes=[3 strings],validator_provider='gemini',validator_model='gemini-2.5-flash'}; GET /decks/{id} re-fetch confirms validation persists. Reports: compose → send_up → GET shows validation persisted (verdict='flagged' on a near-empty body — correct). Calling send_up a second time as admin (not the named CEO reviewer) returns 403 and validation unchanged. Solve: started session, drove turns; synthesis phase response carries synthesis.validation.verdict='validated' with proper provider/model. Soft cap: with VALIDATOR_DAILY_SOFT_CAP=1, first deck validates normally, second deck returns validation{verdict='qualified',validator_provider='n/a',validator_model='n/a',notes=['Daily validator cap reached; read with normal scrutiny.']}. Briefing surface bypass: POST /api/contexts/{cid}/briefs after deck cap trip still validated normally with provider='gemini'. Env was restored after test."

  - task: "Phase 11 ITEM C — Chat citation chips (BM25 grounding + hallucination drop)"
    implemented: true
    working: true
    file: "/app/backend/routers/chat.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: "NA"
          -agent: "main"
          -comment: "ChatCreateIn / ChatPatchIn now accept `context_id`. When set, send_message runs `_retrieve_grounding_paragraphs()` (BM25 over the context's documents' paragraph anchors, top-5), prepends a `[GROUNDING]` block to the prompt, and instructs the model to cite using `[[cite:<anchor_id>]]` markers from a fixed allowlist. After the LLM call, `_process_citations()` extracts every marker, drops any whose anchor is NOT in the retrieval allowlist (hallucinated), renumbers surviving markers as `[n]`, and persists a structured `citations[]` array on the assistant message. Untethered chats (no context_id) behave exactly as before. Test: (a) create a chat with a valid context_id and seed at least one document with an `extracted_text` substantial enough to compute paragraphs; (b) send a message that should ground; confirm response.assistant_message.citations is a non-empty list with anchor_id, doc_id, page, paragraph_number, snippet; (c) confirm `assistant_message.content` contains `[1]` style chips matching the citations; (d) confirm a chat with `context_id=None` returns no `citations` (or empty list) and content has no `[[cite:` markers."
        -working: true
          -agent: "testing"
          -comment: "PASS. Tethered chat: POST /api/chats with context_id persists context_id; sending message returns assistant_message with citations[] of 5 entries each containing {n, anchor_id, doc_id, doc_name, page, paragraph_number, snippet}; content has inline [1]..[5] chips; zero raw [[cite: markers leak. Audit log row for message.received carries citations_kept=5 and citations_dropped=0. Untethered chat: POST /api/chats with NO context_id; assistant_message.citations is empty list and content has no [[cite: markers. The deterministic post-processor `_process_citations` correctly drops hallucinated markers and renumbers surviving ones."

  - task: "Phase 11 ITEM E — Stale comment cleanup in studio_blocks.py"
    implemented: true
    working: "NA"
    file: "/app/backend/routers/studio_blocks.py"
    stuck_count: 0
    priority: "low"
    needs_retesting: false
    status_history:
        -working: "NA"
          -agent: "main"
          -comment: "Removed the `The virus-scan stub is retired.` line from the upload-image header comment (line ~815). Cosmetic only. No functional change. No retest needed."

frontend:
  - task: "Phase 11 ITEM A — `/share/:token` alias route + watermark overlay"
    implemented: true
    working: "NA"
    file: "/app/frontend/src/App.js, /app/frontend/src/pages/SharedArtefact.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: "NA"
          -agent: "main"
          -comment: "Added `/share/:token` route as an alias to the existing `/shared/:token` SharedArtefact page so newer share emails work on the shorter URL while older sent emails still resolve. Added a fixed-position diagonal `Watermark` component (pointer-events-none, z-5) carrying the recipient email + 'AKKI · read-only' tile and a discreet 'Link expires …' footer. Article content lifted to z-10. Frontend agent should NOT be tested unless user requests."

  - task: "Phase 11 ITEM B — ValidatedBadge renders on Decks / Reports / Solve"
    implemented: true
    working: "NA"
    file: "/app/frontend/src/pages/Decks.jsx, /app/frontend/src/components/cycle/ReportsTab.jsx, /app/frontend/src/pages/AppSolve.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: "NA"
          -agent: "main"
          -comment: "Imported and rendered `<ValidatedBadge size='compact' validation={...} />` on (a) the deck detail header next to the SensitivityChip when `deck.validation` is present, (b) the report editor modal subtitle row when `report.validation` is present, (c) above the comparables panel on the Solve session view when `session.synthesis.validation` is present. Each render is gated on a real validation prop — invariant preserved. No frontend testing required unless user asks."

  - task: "Phase 11 ITEM C — Chat citation chips (inline + chip rail)"
    implemented: true
    working: "NA"
    file: "/app/frontend/src/pages/Chat.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: "NA"
          -agent: "main"
          -comment: "Assistant `Message` component now renders inline `[n]` superscripts via `renderInlineCitations()` when the message carries `citations[]`, plus a chip rail beneath the body (each chip links to `/app/documents/<doc_id>#p=<anchor_id>` and shows `<doc_name> · p.<page>¶<paragraph_number>`). Server has already dropped hallucinated markers, so every chip resolves to a real paragraph. Untethered chats render as before — no chips. No frontend testing required unless user asks."

  - task: "Phase I.2 — Solva v3 Guided Flow state machine + page"
    implemented: true
    working: true
    file: "/app/frontend/src/lib/solvaFlow.js, /app/frontend/src/pages/SolvaSession.jsx, /app/frontend/src/components/solva/flow/*.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
          -agent: "main"
          -comment: "Pure reducer at /app/frontend/src/lib/solvaFlow.js with 14-state sequence + ARTEFACT_REFUSAL interrupt. 36 jest tests at /app/frontend/src/lib/__tests__/solvaFlow.test.js — all pass. New page /app/frontend/src/pages/SolvaSession.jsx mounted at /app/solva/session/:sessionId and /app/solva/session/new (App.js routes added). Picker click on /app/solva → navigates to /app/solva/session/new?submodule=<key>. SolvaApp.jsx now a tiny shim that mounts AppShell + SolvaLanding (legacy 865-line multi-panel UI removed). 5 flow components in components/solva/flow/: FramingScreen, QuestionScreen, PreparingInterstitial, ReflectionScreen, ProgressIndicator + Shell + PrimaryButton + tokens.js + usePrefersReducedMotion.js. Live walk verified: login → landing → click develop_strategy → framing → real LLM-generated Q1 → user answers → Q2. Auto-cluster path: backend resolves cluster from intent text via _resolve_auto_cluster keyword heuristic when auto_cluster=true (default in StartV2In). cluster_id now Optional. POST /api/solva/v2/sessions returns cluster_resolution: 'auto' | 'explicit'."

  - task: "Phase I.3 — Solva artefact composition view"
    implemented: true
    working: true
    file: "/app/frontend/src/components/solva/artefact/*.jsx, /app/backend/routers/solva_v2.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
          -agent: "main"
          -comment: "5-section composition (masthead, primary diagnosis, scenarios, sensitivity callout, tension callout) at /app/frontend/src/components/solva/artefact/SolvaArtefact.jsx. ProbabilityBar with 600ms ease-out animated fill + CI extension overlay; respects prefers-reduced-motion. ReasoningExpandable consumes new shaping endpoint GET /api/solva/v2/sessions/{sid}/artefact-reasoning that groups reasoning_audit_log into 4 sub-sections (candidates / triangulation / weighting breakdown / log entries). Refusal variant at SolvaRefusalArtefact.jsx with 4-section refusal anatomy + HONEST REFUSAL pill. Live verified with /app/backend/scripts/inject_phase_i_demo_session.py — full artefact renders correctly at /app/solva/session/<sid>; reasoning expandable opens and shows correct grouped data; download dropdown opens with PDF / DOCX entries."

  - task: "Phase I.4 — Solva v2 PDF + DOCX export endpoints"
    implemented: true
    working: true
    file: "/app/backend/solva_artefact_export.py, /app/backend/templates/solva_artefact.html, /app/backend/templates/solva_refusal_artefact.html, /app/backend/routers/solva_v2.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
          -agent: "main"
          -comment: "Added `weasyprint>=60.0` to backend/requirements.txt; python-docx==1.2.0 already in requirements (reused). Two new endpoints: GET /api/solva/v2/sessions/{sid}/export.pdf (WeasyPrint, ~30 KB std / ~22 KB refusal) and GET /api/solva/v2/sessions/{sid}/export.docx (python-docx, ~37 KB). Both auth-gated, refusal sessions automatically use the refusal template and emit X-Solva-Artefact: refusal header. HTML templates use Calibri + Georgia, CSS-div probability bars (no images). DOCX uses 1-row inline tables for bars and bordered cell-shaded callouts. backend/solva_artefact_export.py exposes build_pdf, build_docx, build_artefact_context (pure shaping). 13 pytest tests at /app/backend/tests/test_phase_i_solva_export.py — all pass: standard PDF, standard DOCX, refusal PDF, refusal DOCX, 401 unauth, 404 missing, auto_cluster default, auto_cluster=false fail, explicit cluster_id, artefact-reasoning grouping. Smoke artefacts copied to /app/frontend/public/static/qa/phase-i/{std,refusal}.{pdf,docx}."

  - task: "Phase I.5 — Reflection screens, A11y, docs sweep"
    implemented: true
    working: true
    file: "/app/frontend/src/components/solva/flow/ReflectionScreen.jsx, /app/frontend/src/components/solva/flow/usePrefersReducedMotion.js, /app/backend/scripts/contrast_audit.py, /app/docs/ROADMAP.md, /app/docs/PRODUCT_FEATURES.md"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
          -agent: "main"
          -comment: "ReflectionScreen wires REFLECT_1..3 with the 3 verbatim brief questions plus a refusal-variant first question. Skip option present but muted. On REFLECT_3 exit returns to artefact with 1.5s 'Session saved' toast. Keyboard nav (Tab traversal, Ctrl/Cmd+Enter submit, Escape to skip). ARIA: role='img' + full label on every probability bar; aria-expanded + aria-controls on reasoning expandable. prefers-reduced-motion honoured by hook + transition: none fallback across all motion. Contrast audit at /app/backend/scripts/contrast_audit.py — 20 specific Solva v3 surface combinations all PASS (see report). Brief-conflict resolved: ACCENT=#C25A38 ratios 4.36 vs LIGHT (below AA 4.5 normal text). Introduced ACCENT_DARK=#B85230 (4.90:1) for interactive fills (buttons, refusal pill); brand ACCENT preserved for kickers / dividers (large text, 3.82:1 on CREAM). Docs sweep applied: docs/ROADMAP.md gets a Phase I sub-step matrix; docs/PRODUCT_FEATURES.md updated to mark Solva UI as v3 with the new flow + export surfaces. /docs and /openapi.json HTTP 200 after every sub-step."

metadata:
  created_by: "main_agent"
  version: "1.0"
  test_sequence: 1
  run_ui: false

test_plan:
  current_focus: []
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
    -agent: "main"
      -message: "Phase 11 (A/B/C) backend implementation complete plus two doc/cleanup items (D doc-drift fix in PRODUCT_REVIEW.md, E stale-comment removal). All Python lint passes, syntax valid (ast parse), backend boots clean. Three items need backend testing (A, B, C). Use admin credentials from /app/memory/test_credentials.md (admin@akki.ai / AkkiAdmin2026!). Hard rules: (1) ValidatedBadge invariant — every frontend render gated on real validation prop, server returns null for cap-tripped briefings only. (2) Public Chair path must NEVER leak un-redacted content — `_assert_public_safe()` is a 500. (3) Hallucinated chat citations must be dropped, not rendered. Notes for testing: ClamAV / MinIO sidecars are not installed in this dev container — uploads will 503; do NOT exercise the upload paths in tests. Test surfaces that don't touch uploads: studio public read (use existing decks/briefings or seed minimal artefacts), decks generate (LLM call against EMERGENT_LLM_KEY), reports send_up, solve session post_turn at synthesis phase, chat send_message with and without context_id."
    -agent: "testing"
      -message: "All three Phase 11 backend items PASS. backend_test.py at /app/backend_test.py covers 38 assertions across A/B/C; 38/38 PASS. ITEM A: public Chair read returns watermark + content (deck slides / briefing items) with zero denylisted keys at any depth; tamper tests (wrong-secret, malformed, expired) return 400/410, never 500. ITEM B: deck/report/solve all persist real validation payloads (verdict in {validated,qualified,flagged}, confidence 0..100, validator_provider/model populated). Soft cap: VALIDATOR_DAILY_SOFT_CAP=1 ⇒ first call validates, second call returns provider='n/a' with note 'Daily validator cap reached'. Brief surface bypass confirmed (still validates after deck cap trips). Report validation never overwritten on second send_up (admin → 403). ITEM C: tethered chat returns 5 structured citations + inline [1]..[5] chips, no [[cite: markers leak, audit log carries citations_kept/dropped counters; untethered chat returns empty citations and clean content. Backend env was modified (VALIDATOR_DAILY_SOFT_CAP added then removed) and supervisor restarted twice; final state matches starting state."
    -agent: "main"
      -message: "Phase I — Solva v3 UX rebuild — COMPLETE (sub-steps I.2 → I.3 → I.4 → I.5; I.1 was already shipped). Backend: 13/13 pytest tests pass (/app/backend/tests/test_phase_i_solva_export.py); /openapi.json + /docs both HTTP 200 after every sub-step; new endpoints GET /api/solva/v2/sessions/{sid}/{artefact-reasoning, export.pdf, export.docx}; auto_cluster=true default in StartV2In with cluster_id now Optional. Frontend: 36/36 jest tests pass (/app/frontend/src/lib/__tests__/solvaFlow.test.js); pure reducer in /app/frontend/src/lib/solvaFlow.js; 9 new flow / artefact components; new page /app/frontend/src/pages/SolvaSession.jsx mounted at /app/solva/session/{new|:sessionId}. Live walk verified end-to-end on the preview URL: signin → /app/solva landing → click develop_strategy card → /app/solva/session/new → framing → real-LLM Q1 → answer → Q2; injected-completed-session also verified to render the full 5-section artefact + animated bars + sensitivity callout + tension callout + reasoning expandable + download menu; injected refusal session renders the 4-section refusal artefact with HONEST REFUSAL pill. Smoke artefacts at /app/frontend/public/static/qa/phase-i/{std,refusal}.{pdf,docx}. WCAG AA contrast audit: 20/20 specific surface combinations pass; introduced ACCENT_DARK=#B85230 to keep brand ACCENT (#C25A38) on kickers while moving button + pill fills onto the AA-safe shade (4.90:1 on white). Lint clean on every touched file. Docs sweep: ROADMAP.md gets a Phase I sub-step matrix; PRODUCT_FEATURES.md marks Solva UI as v3."