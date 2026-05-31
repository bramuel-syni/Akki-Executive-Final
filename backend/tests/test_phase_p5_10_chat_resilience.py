"""P5.10 — chat resilience lockdown (2026-02 fork-resume).

The user's production bug had TWO independent failure modes that
manifested as the same symptom ("response cancelled at ~0.9s + audit
panel red"):

  A. The raw fetch() in /app/frontend/src/pages/Chat.jsx (used to
     consume the SSE stream from `POST /api/chats/{id}/messages/stream`)
     did NOT send the `X-CSRF-Token` header. The axios api wrapper
     in /app/frontend/src/lib/api.js auto-injects it on every
     POST/PUT/PATCH/DELETE, but raw fetch() doesn't go through that
     interceptor. CSRFMiddleware therefore rejected the call with a
     403 csrf_token_missing in ~0.3s, and the SPA threw `HTTP 403`
     which the user read as "instantly cancelled". The fix: import
     `ensureCsrfToken` from lib/api.js and inject the header into
     the fetch headers object alongside the bearer token.

  B. Pre-fix cancelled message rows had `shield_audit_id: null` and
     the chat's `synisense_audit_ids[]` was out-of-band, so the
     audit-panel endpoint returned 404 and the panel rendered the
     red "Audit data isn't available for this message yet" copy.
     The P5.10 fix (already on disk) makes `_persist_cancel` mint an
     audit row with `outcome="cancelled"`, push its id onto the
     chat's `synisense_audit_ids[]`, AND set the new direct
     `chat_messages.shield_audit_id` field on the cancel row.

These tests are source-strict — they read the relevant files and
assert the invariants. They run in isolation (no MongoDB / no
running server) so the lockdown fires immediately on every CI run.

The richer integration coverage lives in
`tests/test_phase_p5_10_audit_panel_direct_linkage.py` which seeds
Mongo + uses the AsyncClient transport against the real FastAPI
app.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))


# ─────────────────────────────────────────────────────────────────
# Bug A — Frontend MUST inject X-CSRF-Token on the raw-fetch SSE call.
# ─────────────────────────────────────────────────────────────────


def test_chat_jsx_imports_ensure_csrf_token():
    """The SSE raw-fetch path MUST import `ensureCsrfToken` from
    lib/api.js. Without it, the only available CSRF source is the
    document.cookie read which would still need the header injection
    below — but reading the cookie inline + adding the header is the
    documented pattern."""
    src = (REPO / "frontend" / "src" / "pages" / "Chat.jsx").read_text(encoding="utf-8")
    assert re.search(
        r"import\s*\{[^}]*\bensureCsrfToken\b[^}]*\}\s*from\s*[\"']@/lib/api[\"']",
        src,
    ), "Chat.jsx does not import ensureCsrfToken from @/lib/api"


def test_chat_jsx_awaits_csrf_token_in_send_path():
    """The raw-fetch SSE call MUST `await ensureCsrfToken()` before
    constructing the headers object. We assert the literal call site
    sits in the same function as the `fetch(...messages/stream...)`
    invocation."""
    src = (REPO / "frontend" / "src" / "pages" / "Chat.jsx").read_text(encoding="utf-8")
    # The call site MUST appear:
    assert "await ensureCsrfToken()" in src, (
        "Chat.jsx does not await ensureCsrfToken() before sending"
    )


def test_chat_jsx_sends_x_csrf_token_header_on_raw_fetch():
    """The raw fetch headers object MUST include `X-CSRF-Token`.
    We grep for the literal header assignment near the raw fetch."""
    src = (REPO / "frontend" / "src" / "pages" / "Chat.jsx").read_text(encoding="utf-8")
    # Header must be set (the value is a `csrf` var, gated by truthiness).
    assert re.search(
        r'headers\[["\']X-CSRF-Token["\']\]\s*=\s*csrf',
        src,
    ), "Chat.jsx does not assign X-CSRF-Token onto the headers object"


def test_chat_jsx_only_uses_one_resolve_backend_origin_import():
    """Regression guard for the duplicate-import compile error that
    surfaced the moment we added `ensureCsrfToken` to the lib/api
    import. Both names MUST live on the SAME import statement so the
    eslint `no-duplicate-imports` rule stays green."""
    src = (REPO / "frontend" / "src" / "pages" / "Chat.jsx").read_text(encoding="utf-8")
    # Count import-from `@/lib/api` statements.
    matches = re.findall(r"^import\s+.*from\s+[\"']@/lib/api[\"']", src, flags=re.MULTILINE)
    assert len(matches) == 1, (
        f"Chat.jsx must only have ONE `from @/lib/api` import; got {len(matches)}:\n"
        + "\n".join(matches)
    )
    # And that ONE import must include both names.
    line = matches[0]
    assert "ensureCsrfToken" in line, line
    assert "resolveBackendOrigin" in line, line


# ─────────────────────────────────────────────────────────────────
# Bug A — Backend MUST keep /messages/stream OUTSIDE the CSRF allowlist.
# ─────────────────────────────────────────────────────────────────


def test_csrf_allowlist_does_not_include_messages_stream():
    """`POST /api/chats/{cid}/messages/stream` MUST be CSRF-protected.
    If a future change moves it into the allowlist, this guard breaks
    so the security review catches the regression."""
    src = (REPO / "backend" / "services" / "csrf.py").read_text(encoding="utf-8")
    assert "/messages/stream" not in src, (
        "messages/stream MUST NOT be in the CSRF allowlist"
    )
    assert "/api/chats" not in src, (
        "the chats router MUST NOT be in the CSRF allowlist"
    )


def test_csrf_middleware_returns_403_on_missing_header():
    """Sanity: the middleware's 403 path is keyed on the explicit
    `csrf_token_missing` error code (the SPA's response interceptor
    keys retry behaviour off this exact string)."""
    src = (REPO / "backend" / "services" / "csrf.py").read_text(encoding="utf-8")
    assert "csrf_token_missing" in src
    assert "status_code=403" in src
    assert "X-CSRF-Token" in src


# ─────────────────────────────────────────────────────────────────
# Bug B — `_persist_cancel` partial-write semantics (source-strict).
# ─────────────────────────────────────────────────────────────────


def test_persist_cancel_calls_shield_finalize_with_outcome_cancelled():
    """The cancel path MUST call shield_finalize with
    `outcome="cancelled"`. Anything else (success / stream_error)
    would write a misleading row."""
    src = (REPO / "backend" / "routers" / "chat.py").read_text(encoding="utf-8")
    # Locate the `_persist_cancel` function body.
    m = re.search(
        r"async def _persist_cancel\(.*?\) -> None:\s*(?:\"\"\".*?\"\"\"\s*)?(.*?)(?=^\s{8}async def |\Z)",
        src,
        flags=re.DOTALL | re.MULTILINE,
    )
    assert m, "could not locate _persist_cancel in routers/chat.py"
    body = m.group(1)
    # The shield_finalize call site with cancelled outcome:
    assert "outcome=\"cancelled\"" in body, (
        "_persist_cancel does not invoke shield_finalize with outcome=cancelled"
    )
    # The audit_id MUST be pushed onto chats.synisense_audit_ids:
    assert "synisense_audit_ids" in body, (
        "_persist_cancel does not push the cancelled audit_id onto chats.synisense_audit_ids"
    )
    # The cancelled chat_messages row MUST carry the direct link:
    assert "\"shield_audit_id\":" in body, (
        "_persist_cancel does not stamp shield_audit_id onto the chat_messages row"
    )


def test_persist_cancel_uses_partial_response_text():
    """The shield_finalize call inside `_persist_cancel` MUST pass
    `response_text=partial_raw` (the truncated raw text), not the
    full LLM reply. Mismatched accounting would over-report the
    shielded content for cancelled turns."""
    src = (REPO / "backend" / "routers" / "chat.py").read_text(encoding="utf-8")
    m = re.search(
        r"async def _persist_cancel\(.*?\) -> None:\s*(?:\"\"\".*?\"\"\"\s*)?(.*?)(?=^\s{8}async def |\Z)",
        src,
        flags=re.DOTALL | re.MULTILINE,
    )
    body = m.group(1)
    assert "partial_raw = raw_text[:emitted_chars_at]" in body, (
        "_persist_cancel does not truncate raw_text to emitted_chars_at"
    )
    assert "response_text=partial_raw" in body, (
        "_persist_cancel does not pass the truncated partial to shield_finalize"
    )
    # And the cancelled chat_messages row stores `emitted_chars` for
    # post-hoc analytics.
    assert "\"emitted_chars\": emitted_chars_at" in body
    assert "\"full_chars\": len(raw_text)" in body


def test_persist_cancel_guards_against_unbound_shield_finalize():
    """If cancellation lands BEFORE `_shield_prepare_streaming`
    returned, `shield_finalize` is still unbound. The cancel-path
    MUST guard with NameError/UnboundLocalError/AttributeError so
    persistence still completes for the chat_messages row (with
    `shield_audit_id: None`). Direct-linkage degrades gracefully —
    the resolver tolerates a missing audit_id by surfacing the
    "audit pending" copy ONLY for that single turn rather than
    cascading off-by-one to every subsequent assistant message."""
    src = (REPO / "backend" / "routers" / "chat.py").read_text(encoding="utf-8")
    m = re.search(
        r"async def _persist_cancel\(.*?\) -> None:\s*(?:\"\"\".*?\"\"\"\s*)?(.*?)(?=^\s{8}async def |\Z)",
        src,
        flags=re.DOTALL | re.MULTILINE,
    )
    body = m.group(1)
    assert "NameError" in body and "UnboundLocalError" in body, (
        "_persist_cancel does not guard against unbound shield_finalize "
        "(NameError / UnboundLocalError)"
    )


# ─────────────────────────────────────────────────────────────────
# Bug B — Audit panel resolver MUST prefer direct shield_audit_id
# over the legacy positional index. (Mirrors the production fix —
# we keep a source-strict probe here as a cheap belt-and-braces
# alongside the integration tests in test_phase_p5_10_*.)
# ─────────────────────────────────────────────────────────────────


def test_audit_panel_resolver_prefers_direct_link():
    src = (REPO / "backend" / "routers" / "chat_audit_panel.py").read_text(encoding="utf-8")
    # The direct-linkage query lookup MUST exist:
    assert 'await db.chat_messages.find_one(' in src
    assert '"shield_audit_id"' in src
    # And the legacy positional fallback MUST be UNDER an `if audit_id is None` guard:
    assert "if audit_id is None:" in src
    # The fallback message:
    assert "audit_ids[pos] if pos < len(audit_ids) else None" in src


# ─────────────────────────────────────────────────────────────────
# Sprint Z1.1 — cascade ordering (kept in sync; cheap to re-assert)
# ─────────────────────────────────────────────────────────────────


def test_cascade_classifier_strips_failing_id():
    """The cascade helper MUST strip the failing model id so the
    retry loop does not re-attempt the same broken model."""
    import importlib
    chat_mod = importlib.import_module("routers.chat")
    chosen = "claude-opus-4-6"
    cascade = chat_mod._cascade_starting_from(chosen)
    assert chosen not in cascade, f"cascade still contains {chosen}: {cascade}"
    # The first retry MUST be Sonnet 4.5 (workhorse).
    assert cascade[0] == "claude-sonnet-4-5", cascade
    # Haiku is the safety net at the tail.
    assert cascade[-1] == "claude-haiku-4-5", cascade


def test_is_model_invalid_error_classifier_only_fires_on_model_errors():
    """The classifier MUST fire on BadRequest / model-not-found
    strings AND ONLY on those — transport errors fall through to
    the existing transport-layer retry."""
    import importlib
    chat_mod = importlib.import_module("routers.chat")
    # POSITIVE — these MUST cascade:
    for s in [
        "BadRequestError: Invalid model name",
        "anthropic model_not_found",
        "no such model: claude-opus-4-7-20260416",
        "not_found_error",
    ]:
        assert chat_mod._is_model_invalid_error(s), s
    # NEGATIVE — these MUST NOT cascade:
    for s in [
        "rate_limit_exceeded",
        "connection_timeout",
        "internal_server_error",
        None,
        "",
    ]:
        assert not chat_mod._is_model_invalid_error(s), repr(s)
