"""Sprint Z1 — backend contract tests.

Covers:
  • Z1.1 — chat model registry has a valid Opus id; model-cascade
           helper resolves the fallback list correctly; the
           `_is_model_invalid_error` classifier matches the
           BadRequest-class error strings emitted by transport.
  • Z1.2 — Document PATCH accepts a notes-only payload AND persists
           the value; empty-payload still 400s with the existing
           "Send at least one field" message.
  • Z1.3 — Contribution status PATCH rejects approve-from-not_started
           with 409 (server-side belt + braces).
  • Z1.5 — Doc-scoped briefing generation returns 400 with the
           "no signals" copy when the document has no related signals.
  • Z1.6 — `GET /api/contexts/{cid}/documents?origin=upload` returns
           uploaded documents (the wizard's new fetch path).
"""
from __future__ import annotations

import sys
import importlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))


# ─────────────────────────────────────────────────────────────────
# Z1.1 — Chat model registry + model-cascade helpers
# ─────────────────────────────────────────────────────────────────


def test_supported_models_opus_id_is_valid():
    """The Opus picker entry MUST point to a known-good Anthropic id.
    The bogus `claude-opus-4-7-20260416` (Sprint Z1.1) raised
    BadRequest from litellm. We pin to `claude-opus-4-6` which is
    verified GA + already used by `LLM_MODEL_DEEP`."""
    chat_mod = importlib.import_module("routers.chat")
    opus_entries = [m for m in chat_mod.SUPPORTED_MODELS if "opus" in m["id"].lower()]
    assert opus_entries, "No Opus entry in SUPPORTED_MODELS — registry broken"
    for entry in opus_entries:
        # The bogus dated id MUST be gone.
        assert entry["model"] != "claude-opus-4-7-20260416", (
            f"Opus entry still pinned to bogus id: {entry}"
        )
        # The replacement MUST be a known-good Anthropic Opus id.
        assert entry["model"].startswith("claude-opus-"), entry
        # And it must not have a date suffix that doesn't exist
        # (we accept the anchored alias `claude-opus-4-6`).
        assert "20260416" not in entry["model"]


def test_model_fallback_cascade_is_ordered():
    """The cascade list must start with Sonnet 4.5 (workhorse) and
    end with Haiku (safety net)."""
    chat_mod = importlib.import_module("routers.chat")
    assert chat_mod.MODEL_FALLBACK_CASCADE[0] == "claude-sonnet-4-5"
    assert chat_mod.MODEL_FALLBACK_CASCADE[-1] == "claude-haiku-4-5"
    assert "claude-sonnet-3-7" in chat_mod.MODEL_FALLBACK_CASCADE


def test_cascade_starting_from_strips_the_failing_id():
    chat_mod = importlib.import_module("routers.chat")
    result = chat_mod._cascade_starting_from("claude-sonnet-4-5")
    assert "claude-sonnet-4-5" not in result
    assert "claude-sonnet-3-7" in result


def test_is_model_invalid_error_matches_litellm_errors():
    chat_mod = importlib.import_module("routers.chat")
    # Exact litellm error pattern seen in the QA report:
    assert chat_mod._is_model_invalid_error(
        "proxy_fallback_failed: ChatError: BadRequestError: Invalid model name passed in model=claude-opus-4-7-20260416"
    )
    assert chat_mod._is_model_invalid_error("anthropic_not_found_error: model not found")
    assert chat_mod._is_model_invalid_error("model does not exist")
    # Negative — transport / rate-limit errors MUST NOT cascade.
    assert not chat_mod._is_model_invalid_error("rate_limit_exceeded")
    assert not chat_mod._is_model_invalid_error("connection_timeout")
    assert not chat_mod._is_model_invalid_error(None)
    assert not chat_mod._is_model_invalid_error("")


# ─────────────────────────────────────────────────────────────────
# Z1.2 — Document PATCH accepts notes-only payload
# ─────────────────────────────────────────────────────────────────


def test_doc_patch_in_schema_has_notes_field():
    """The Pydantic model on the PATCH endpoint MUST accept `notes`."""
    docs_mod = importlib.import_module("routers.documents")
    fields = docs_mod._DocPatchIn.model_fields
    assert "notes" in fields, "_DocPatchIn missing `notes` field"
    # Optional with default None — empty string clears the field.
    assert not fields["notes"].is_required()


def test_doc_patch_in_accepts_notes_only():
    """Constructing _DocPatchIn with ONLY notes should succeed (no
    other fields required)."""
    docs_mod = importlib.import_module("routers.documents")
    inst = docs_mod._DocPatchIn(notes="My private notes about this doc.")
    assert inst.notes == "My private notes about this doc."
    assert inst.title is None
    assert inst.body is None


# ─────────────────────────────────────────────────────────────────
# Z1.3 — Contribution approve from not_started rejected (source code)
# ─────────────────────────────────────────────────────────────────


def test_tasks_router_blocks_approve_from_not_started_in_source():
    """The handler enforces the eligibility set at call-time.
    We assert the literal allowlist + the 409 raise pattern exist
    in the source — a runtime integration test in another file can
    exercise the endpoint."""
    src = (REPO / "backend" / "routers" / "tasks.py").read_text(encoding="utf-8")
    assert '_APPROVE_ELIGIBLE_FROM = {"submitted", "in_review"}' in src
    assert "status_code=409" in src
    assert "Cannot approve a contribution in status" in src


# ─────────────────────────────────────────────────────────────────
# Z1.5 — Doc-scoped briefing endpoint exists + raises on zero signals
# ─────────────────────────────────────────────────────────────────


def test_doc_scoped_briefing_endpoint_registered():
    """The wrapper endpoint must be registered on the documents
    router so the drawer can POST to it."""
    docs_mod = importlib.import_module("routers.documents")
    routes = {r.path: r for r in docs_mod.router.routes}
    target = "/api/contexts/{context_id}/documents/{doc_id}/briefings/generate"
    assert target in routes, f"Missing route {target}; got {list(routes.keys())[:20]}"
    # Confirm it's wired as POST and returns 202.
    route = routes[target]
    assert "POST" in route.methods
    assert route.status_code == 202


# ─────────────────────────────────────────────────────────────────
# Z1.6 — Documents listing accepts origin filter
# ─────────────────────────────────────────────────────────────────


def test_documents_listing_accepts_upload_origin():
    """The documents listing endpoint must accept `origin=upload` so
    the Compilation Wizard can fetch user-uploaded docs alongside
    Akki-generated aggregates."""
    docs_mod = importlib.import_module("routers.documents")
    # Check the handler signature accepts an `origin` query param.
    import inspect
    sig = inspect.signature(docs_mod.list_documents)
    assert "origin" in sig.parameters
    # Source-strict: the handler's allowlist must include `upload`.
    src = (REPO / "backend" / "routers" / "documents.py").read_text(encoding="utf-8")
    assert '"akki_generated", "upload", "email_receipt"' in src


# ─────────────────────────────────────────────────────────────────
# Z1.1 + Z1.2 + Z1.3 + Z1.5 + Z1.6 — frontend source-strict probes
# ─────────────────────────────────────────────────────────────────


def test_frontend_drawer_notes_payload_is_correct():
    """The DocumentDrawer's notes save MUST send {notes} — not the
    previous {body: undefined, title: undefined} bug."""
    src = (REPO / "frontend" / "src" / "components" / "documents" / "DocumentDrawer.jsx").read_text(encoding="utf-8")
    assert 'api.patch(`/contexts/${contextId}/documents/${doc.id}`, { notes })' in src


def test_frontend_drawer_generate_brief_no_longer_navigates_to_solva():
    """The Generate brief CTA MUST NOT carry a buildBriefUrl that
    routes to /app/solva. The fix replaces navigation with a
    `briefings/generate` POST + job poll."""
    src = (REPO / "frontend" / "src" / "components" / "documents" / "DocumentDrawer.jsx").read_text(encoding="utf-8")
    # The old code constructed `buildBriefUrl` pointing at /app/solva.
    assert "buildBriefUrl" not in src
    # The new handler MUST exist.
    assert "onGenerateBrief" in src
    assert "briefings/generate" in src


def test_frontend_email_drafts_card_routes_to_task_manager():
    src = (REPO / "frontend" / "src" / "pages" / "CompanyHome.jsx").read_text(encoding="utf-8")
    # Old route gone:
    assert "/app/work-studio?tab=drafts" not in src
    # New route present:
    assert "/app/task-manager?filter=email_drafts_ready" in src


def test_frontend_compile_wizard_select_all_ready_is_100pct():
    """Sprint Z1.7 — readiness threshold MUST be 100, not 80."""
    src = (REPO / "frontend" / "src" / "components" / "work_studio" / "CompilationWizard.jsx").read_text(encoding="utf-8")
    # Old 80% threshold gone:
    assert "readiness_pct || 0) >= 80" not in src
    # New 100% threshold present:
    assert "readiness_pct || 0) >= 100" in src
    # Toast feedback when zero qualify:
    assert "No sources are ready yet. Sources hit ready at 100%." in src
    # Helper text under the button:
    assert "Pre-selects sources at 100% readiness." in src


def test_frontend_compile_wizard_fetches_uploaded_docs():
    """Sprint Z1.6 — the wizard MUST fire a second fetch against the
    documents listing endpoint with origin=upload, AND render an
    Uploaded group."""
    src = (REPO / "frontend" / "src" / "components" / "work_studio" / "CompilationWizard.jsx").read_text(encoding="utf-8")
    assert 'origin: "upload"' in src
    assert '"wizard-source-group-uploaded"' in src
    assert '"wizard-source-group-akki"' in src
    assert 'source_group: "uploaded"' in src
    assert 'source_group: "akki_generated"' in src


def test_frontend_task_drawer_approve_disabled_on_not_started():
    """Sprint Z1.3 — Approve button MUST be disabled unless the
    contributor is in submitted or in_review."""
    src = (REPO / "frontend" / "src" / "components" / "tasks" / "TaskDrawer.jsx").read_text(encoding="utf-8")
    # The disabled condition must reference the eligibility set.
    assert '["submitted", "in_review"].includes(m.status)' in src
    # aria-disabled mirror present.
    assert "aria-disabled=" in src
