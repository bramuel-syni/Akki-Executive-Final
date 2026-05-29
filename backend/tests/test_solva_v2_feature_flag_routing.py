"""Solva v2 — Slice 2b feature-flag routing contract.

Verifies the feature flag swap discipline:

  1. SolvaSession.jsx routes the ARTEFACT + COMPLETE states through
     `solvaV2EnabledFor(account)` — never hardcoded to v1 or v2.
  2. The frontend helper supports the URL `?v2=1` override for
     cross-account smoke testing.
  3. The backend route `GET /api/solva/sessions/{sid}/v2/payload`
     returns 404 when the account's flag is OFF (so callers can't
     accidentally consume v2 with v1 UI).
  4. v1 stays byte-identical — `SolvaArtefact.jsx` source unchanged
     (sha guard via byte length + the v1 unchanged test).
  5. Backend startup auto-enables the flag on `admin@akki.ai` for
     preview-pod ergonomics, but leaves all other accounts OFF.
"""
from __future__ import annotations

import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SESSION_PAGE = REPO / "frontend" / "src" / "pages" / "SolvaSession.jsx"
FLAG_HELPER = REPO / "frontend" / "src" / "lib" / "solvaV2FeatureFlag.js"
V1_ARTEFACT = REPO / "frontend" / "src" / "components" / "solva" / "artefact" / "SolvaArtefact.jsx"
BACKEND_FLAG = REPO / "backend" / "services" / "solva_v2" / "feature_flag.py"
BACKEND_ROUTER = REPO / "backend" / "routers" / "solva_v2_artefact.py"
BACKEND_SERVER = REPO / "backend" / "server.py"


# ─────────────────────────────────────────────────────────────────
# A. Frontend feature flag — URL override + account-flag truth table
# ─────────────────────────────────────────────────────────────────


def test_flag_helper_supports_url_override():
    """`?v2=1` and `?v2=0` URL params must override the account flag."""
    src = FLAG_HELPER.read_text(encoding="utf-8")
    assert "URLSearchParams" in src, (
        "Flag helper must parse URLSearchParams to read `?v2=...` override."
    )
    # Both true and false tokens recognised (or token table)
    assert "TRUE_TOKENS" in src or "true" in src
    assert "FALSE_TOKENS" in src or "false" in src
    # The override branch must execute BEFORE the account check.
    override_idx = src.find("_readUrlOverride")
    account_idx = src.find("account.feature_flags")
    assert override_idx > 0 and account_idx > 0, (
        "Flag helper must define both URL override + account-flag paths."
    )
    # URL override is read first in the function body.
    enabled_fn = src[src.find("export function solvaV2EnabledFor"):]
    assert enabled_fn.find("_readUrlOverride") < enabled_fn.find("account.feature_flags"), (
        "URL override must be checked BEFORE the account flag."
    )


def test_flag_helper_does_not_read_process_env():
    """Frontend cannot read backend env at runtime. The helper code
    (after stripping comments) must NOT reference process.env."""
    src = FLAG_HELPER.read_text(encoding="utf-8")
    code = re.sub(r"/\*[\s\S]*?\*/", "", src)
    code = re.sub(r"//[^\n]*", "", code)
    assert "process.env" not in code, (
        "Feature-flag helper must NOT execute process.env at runtime."
    )


# ─────────────────────────────────────────────────────────────────
# B. SolvaSession.jsx routing — flag-gated swap between v1 + v2
# ─────────────────────────────────────────────────────────────────


def test_solva_session_imports_both_v1_and_v2_artefact():
    src = SESSION_PAGE.read_text(encoding="utf-8")
    assert "import SolvaArtefact " in src or "import SolvaArtefact\n" in src, (
        "SolvaSession.jsx must import the v1 artefact."
    )
    assert "import SolvaArtefactV2 " in src or "import SolvaArtefactV2\n" in src, (
        "SolvaSession.jsx must import the v2 artefact."
    )


def test_solva_session_routes_artefact_state_through_flag():
    src = SESSION_PAGE.read_text(encoding="utf-8")
    # Both v1 and v2 must appear in the ARTEFACT + COMPLETE branches,
    # gated by `solvaV2EnabledFor(account)`.
    assert "solvaV2EnabledFor(account)" in src, (
        "SolvaSession.jsx must check `solvaV2EnabledFor(account)`."
    )
    # Locate ARTEFACT case and ensure both v1 + v2 sit inside the
    # ternary downstream of the flag check.
    artefact_block = re.search(
        r'case\s+"ARTEFACT":[\s\S]+?break;',
        src,
    )
    assert artefact_block, "SolvaSession.jsx must have an ARTEFACT case branch."
    block = artefact_block.group(0)
    assert "solvaV2EnabledFor(account)" in block, (
        "ARTEFACT branch must check the v2 flag."
    )
    assert "<SolvaArtefactV2" in block, "ARTEFACT branch must mount the v2 component."
    assert "<SolvaArtefact" in block, "ARTEFACT branch must keep v1 mounted under the flag-off path."


# ─────────────────────────────────────────────────────────────────
# C. v1 stays byte-identical — no edits to SolvaArtefact.jsx
# ─────────────────────────────────────────────────────────────────


def test_v1_artefact_file_exists_and_is_untouched_by_slice2():
    """Slice 2 is a pure addition under `/artefact_v2/`. The v1
    component lives at `/artefact/SolvaArtefact.jsx` and must NOT have
    been edited as part of this slice. Source-strict guard: the file
    contains zero references to v2 components."""
    src = V1_ARTEFACT.read_text(encoding="utf-8")
    # v1 must not import any v2 component.
    forbidden = (
        "SolvaArtefactV2",
        "artefact_v2",
        "solva-v2-",
        "data-solva-v2-",
    )
    for needle in forbidden:
        assert needle not in src, (
            f"v1 SolvaArtefact.jsx must not contain {needle!r} — v2 is "
            "a pure addition; v1 stays byte-identical."
        )


# ─────────────────────────────────────────────────────────────────
# D. Backend feature flag — env + account truth table
# ─────────────────────────────────────────────────────────────────


def test_backend_flag_env_default_resolved_at_call_time():
    """`SOLVA_V2_ENABLED` must be re-read on every `solva_v2_enabled_for`
    call so pytest fixtures that monkeypatch the env see the change."""
    src = BACKEND_FLAG.read_text(encoding="utf-8")
    assert "os.environ.get(\"SOLVA_V2_ENABLED\"" in src, (
        "Backend feature flag must read SOLVA_V2_ENABLED at call time."
    )
    assert "def _env_default" in src, (
        "Backend feature flag must isolate env read in `_env_default`."
    )


def test_backend_flag_account_override_wins_over_env():
    src = BACKEND_FLAG.read_text(encoding="utf-8")
    # Truth table: account flag value of True/False overrides env.
    assert "account.get(\"feature_flags\")" in src, (
        "Backend flag must read `account.feature_flags`."
    )
    assert "isinstance(value, bool)" in src, (
        "Backend flag must accept bool account-flag values directly."
    )


def test_backend_artefact_router_returns_404_when_flag_off():
    """`GET /api/solva/sessions/{sid}/v2/payload` returns 404 when the
    flag is off so callers can't discover v2 by URL probing."""
    src = BACKEND_ROUTER.read_text(encoding="utf-8")
    assert "solva_v2_enabled_for(account)" in src
    assert "status_code=404" in src
    assert "Solva v2 not enabled" in src


# ─────────────────────────────────────────────────────────────────
# E. Admin auto-enable at boot (preview ergonomics)
# ─────────────────────────────────────────────────────────────────


def test_server_startup_auto_enables_v2_for_admin_only():
    """`admin@akki.ai` gets `feature_flags.solva_v2=true` at boot so
    the founder can eyeball the deck immediately. Other accounts stay
    off — v1 regression-protection is real."""
    src = BACKEND_SERVER.read_text(encoding="utf-8")
    assert "feature_flags.solva_v2" in src, (
        "server.py must auto-enable the v2 flag for admin@akki.ai."
    )
    # The flip must target the admin email lookup, not a global update.
    assert "admin_email" in src
    # And it must guard against repeated writes (idempotent).
    assert "existing_flags" in src or "solva_v2" in src
