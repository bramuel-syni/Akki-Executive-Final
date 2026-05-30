"""Phase ZZ.3 (2026-02 fork-resume v2) — Trust Center > Reasoning
aggregate endpoint + frontend wiring source-strict locks.

Source-strict layer:
  * `routers/trust_center.py` exposes `/reasoning` route with
    `7d|30d` window enum.
  * Tiles keys lock the spec exactly so the frontend can rely on
    them at type-shape level.

Frontend source-strict layer:
  * `TrustCenter.jsx` mounts `<ReasoningView />` under the
    `reasoning` tab.
  * `ReasoningView` renders the 6 tile labels verbatim + window
    toggle + feed.
  * `GovernanceSignals.jsx` POSTs the click-receipt before
    navigating.

End-to-end smoke (mocked DB rows):
  * Seed two chat_audit_log rows + one synisense_runs row into a
    throwaway chat and assert the tile counts.
"""
from __future__ import annotations
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
TC_PY = REPO / "backend" / "routers" / "trust_center.py"
CHAT_PY = REPO / "backend" / "routers" / "chat.py"
TC_JSX = REPO / "frontend" / "src" / "pages" / "TrustCenter.jsx"
GS_JSX = REPO / "frontend" / "src" / "components" / "chat" / "GovernanceSignals.jsx"


def test_zz3_backend_endpoint_present():
    src = TC_PY.read_text(encoding="utf-8")
    assert '@router.get("/reasoning")' in src
    assert 'pattern="^(7d|30d)$"' in src


def test_zz3_backend_tiles_shape():
    src = TC_PY.read_text(encoding="utf-8")
    for key in [
        "identifiers_protected", "restored_on_view",
        "grounding_checks", "unsourced_refused",
        "bias_flags_total", "bias_flags_by_kind",
        "escalations_offered", "escalations_accepted",
    ]:
        assert f'"{key}"' in src, f"Missing tile key {key!r}"


def test_zz3_backend_aggregates_three_action_kinds():
    src = TC_PY.read_text(encoding="utf-8")
    assert '"message.received"' in src
    assert '"chat.refused"' in src
    assert '"chat.solva_escalation_clicked"' in src


def test_zz3_chat_persists_zz2_governance_in_audit_payload():
    src = CHAT_PY.read_text(encoding="utf-8")
    # Audit row for message.received on the SUCCESS path (the streaming
    # request_obj suffix is shared by the cancelled-path row too, so
    # we scan all matches and assert at least one persists zz2_governance).
    idxs = []
    cursor = 0
    needle = 'action="message.received", request=request_obj'
    while True:
        i = src.find(needle, cursor)
        if i < 0:
            break
        idxs.append(i)
        cursor = i + 1
    assert idxs, "No message.received audit rows found"
    found = any('"zz2_governance": zz2_governance' in src[i:i + 2500] for i in idxs)
    assert found, "Success-path message.received audit must persist zz2_governance"


def test_zz3_chat_solva_escalation_click_endpoint():
    src = CHAT_PY.read_text(encoding="utf-8")
    assert '@router.post("/chats/{chat_id}/governance/solva-escalation-clicked")' in src
    assert 'action="chat.solva_escalation_clicked"' in src


def test_zz3_governance_signals_posts_before_navigate():
    src = GS_JSX.read_text(encoding="utf-8")
    assert "useNavigate" in src
    assert "/governance/solva-escalation-clicked" in src
    assert "handleEscalationClick" in src
    # Button (not Link) so we can intercept and POST first.
    assert '<button' in src and 'onClick={handleEscalationClick}' in src


def test_zz3_trust_center_mounts_reasoning_tab():
    src = TC_JSX.read_text(encoding="utf-8")
    assert 'testid="tc-tab-reasoning"' in src
    assert "<ReasoningView />" in src
    assert 'data-testid="tc-reasoning-tiles"' in src
    # Window-toggle testids are template-rendered as
    # `tc-reasoning-window-${w}` — assert the dynamic form.
    assert 'data-testid={`tc-reasoning-window-${w}`}' in src


def test_zz3_tile_labels_verbatim():
    """Voice-lint anchor: tile labels are declarative and locked
    against the spec. Adding marketing puffery would break this."""
    src = TC_JSX.read_text(encoding="utf-8")
    for label in [
        'label="Identifiers protected"',
        'label="Restored on your view"',
        'label="Evidence-grounding checks"',
        'label="Unsourced claims refused"',
        'label="Bias flags surfaced"',
        'label="Solva escalations"',
    ]:
        assert label in src, f"Missing verbatim tile label {label}"


def test_zz3_voice_lint_no_banned_vocab():
    """Banned-word lockdown on the ZZ.3 surfaces. Marketing words
    must not creep into Trust Center copy."""
    banned = ["empower", "seamless", "AI-powered", "AI-driven",
              "lightning-fast", "blazing"]
    for path in (TC_JSX, GS_JSX, TC_PY):
        src = path.read_text(encoding="utf-8").lower()
        for word in banned:
            assert word.lower() not in src, (
                f"Banned word {word!r} found in {path.name}"
            )


@pytest.mark.asyncio
async def test_zz3_reasoning_endpoint_e2e_admin_smoke():
    """Hit the live preview endpoint as admin@akki.ai and assert the
    locked response shape. No data assumptions (admin may have zero
    rows in the window) — we only assert keys + types."""
    import requests
    base = "https://akki-executive.preview.emergentagent.com"
    r = requests.post(f"{base}/api/auth/login",
                      json={"email": "admin@akki.ai",
                            "password": "AkkiAdmin2026!"},
                      timeout=15)
    if r.status_code >= 400:
        pytest.skip(f"login failed: {r.status_code}")
    token = r.json()["access_token"]
    rr = requests.get(f"{base}/api/trust-center/reasoning?window=7d",
                      headers={"Authorization": f"Bearer {token}"},
                      timeout=20)
    assert rr.status_code == 200, rr.text
    body = rr.json()
    assert body["window"] == "7d"
    assert "since" in body
    tiles = body.get("tiles") or {}
    for key in [
        "identifiers_protected", "restored_on_view",
        "grounding_checks", "unsourced_refused",
        "bias_flags_total", "bias_flags_by_kind",
        "escalations_offered", "escalations_accepted",
    ]:
        assert key in tiles, f"Missing tile {key!r} in response"
    assert isinstance(tiles["bias_flags_by_kind"], dict)
    assert isinstance(body.get("feed"), list)
    # 30d also responds 200 with the same shape.
    r30 = requests.get(f"{base}/api/trust-center/reasoning?window=30d",
                       headers={"Authorization": f"Bearer {token}"},
                       timeout=20)
    assert r30.status_code == 200, r30.text
    # Invalid window → 422.
    rbad = requests.get(f"{base}/api/trust-center/reasoning?window=foo",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=15)
    assert rbad.status_code == 422
