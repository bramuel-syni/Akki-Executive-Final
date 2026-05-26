"""Phase C Chat Cleanup — wire-check invariants.

Static + DOM-shape assertions for Chat surface (2026-05-26).
Anchors acceptance criteria (a)-(h) from the brief.
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CHAT = REPO / "frontend" / "src" / "pages" / "Chat.jsx"


def _read(p: Path) -> str:
    assert p.exists(), f"missing source file: {p}"
    return p.read_text(encoding="utf-8")


# ── (a) + (b) — sticky composer + scroll containment ─────────────
def test_phase_c_composer_is_sticky_bottom():
    src = _read(CHAT)
    # The composer block is wrapped in a `sticky bottom-0` container.
    assert "sticky bottom-0" in src, (
        "Composer must use sticky bottom-0 pattern so it stays "
        "pinned to the chat-pane bottom on load."
    )


def test_phase_c_chat_page_overflow_hidden():
    """Page-level chat container has overflow-hidden — page scroll
    is impossible; scroll happens only inside .message-list +
    .thread-list children."""
    src = _read(CHAT)
    # Find the data-testid="chat-page" element and confirm overflow-hidden.
    idx = src.find('data-testid="chat-page"')
    assert idx != -1
    pre = src[max(0, idx - 300):idx]
    assert "overflow-hidden" in pre, (
        "chat-page container must carry overflow-hidden to disable "
        "page-level scrolling."
    )


def test_phase_c_chat_messages_scroll_container_present():
    """Messages list scroll container exists with overflow-y-auto."""
    src = _read(CHAT)
    # The messages list block carries data-testid="chat-messages".
    idx = src.find('data-testid="chat-messages"')
    assert idx != -1, "chat-messages testid missing"
    pre = src[max(0, idx - 600):idx]
    assert "overflow-y-auto" in pre, (
        "chat-messages container must scroll its own overflow."
    )


# ── (c) — three-dot menu on thread rows ──────────────────────────
def test_phase_c_thread_row_menu_testid_present():
    src = _read(CHAT)
    assert 'data-testid={`chat-thread-row-menu-${c.id}`}' in src, (
        "Each thread row must carry a chat-thread-row-menu-{id} testid"
    )


def test_phase_c_thread_row_menu_uses_dropdown_primitive():
    src = _read(CHAT)
    assert "DropdownMenu" in src, (
        "Thread row menu must use the existing DropdownMenu primitive"
    )
    assert "DropdownMenuItem" in src
    assert "MoreVertical" in src, (
        "Three-dot icon (MoreVertical) must be imported"
    )


def test_phase_c_thread_row_delete_action_wired():
    """Delete item inside the dropdown calls onArchive(c.id) —
    same soft-archive op used by the top-bar trash icon."""
    src = _read(CHAT)
    # The menu item that calls onArchive(c.id) carries a delete testid.
    idx = src.find('data-testid={`chat-thread-row-delete-${c.id}`}')
    assert idx != -1, "chat-thread-row-delete-{id} testid missing"
    pre = src[max(0, idx - 600):idx]
    assert "onArchive(c.id)" in pre, (
        "Delete menu item must wire to the existing onArchive(c.id) op"
    )


def test_phase_c_thread_row_uses_div_not_nested_button():
    """A <button> cannot contain another <button>. Thread row must
    be a div with role=button so the DropdownMenuTrigger nests
    cleanly."""
    src = _read(CHAT)
    # The thread row container must be a div with role="button".
    # Anchor on the testid + walk backward to find the opening tag.
    idx = src.find('data-testid={`chat-item-${c.id}`}')
    assert idx != -1
    # Search backwards up to ~1500 chars to find the <div ...> opener
    # (the row is multi-line with JSX so 600 chars wasn't enough).
    pre = src[max(0, idx - 1500):idx]
    assert 'role="button"' in pre, (
        "Thread row must be `<div role=\"button\">` so the nested "
        "DropdownMenuTrigger button is valid HTML"
    )


# ── (d) — outer gutters removed ──────────────────────────────────
def test_phase_c_outer_gutters_removed():
    src = _read(CHAT)
    idx = src.find('data-testid="chat-page"')
    assert idx != -1
    pre = src[max(0, idx - 300):idx]
    assert "akki-w-wide" in pre, (
        "Chat page container must use akki-w-wide (100% width) — "
        "the akki-w-medium 1200px max-width creates outer gutters."
    )
    assert "akki-w-medium" not in pre, (
        "akki-w-medium must be replaced by akki-w-wide"
    )


def test_phase_c_outer_gutter_change_scoped_to_chat():
    """Other consumers of akki-w-medium must NOT be touched by this
    pass — the swap is local to the chat-page container only."""
    # Grep all .jsx files for akki-w-medium; expect 4+ surfaces still
    # using it (Decks, InboundQueue, InfluenceMap, Workspace, etc.).
    other_consumers = []
    for p in (REPO / "frontend" / "src").rglob("*.jsx"):
        if "_archived_legacy" in str(p):
            continue
        if p.name == "Chat.jsx":
            continue
        text = p.read_text("utf-8", errors="ignore")
        if "akki-w-medium" in text:
            other_consumers.append(str(p.relative_to(REPO)))
    assert len(other_consumers) >= 3, (
        "Other consumers of akki-w-medium must remain untouched. "
        f"Found {len(other_consumers)}; expected ≥ 3 (Decks, "
        f"InboundQueue, InfluenceMap, etc.). Surfaces: {other_consumers}"
    )


# ── (e) — LAYERS WON removed from Audit modal ────────────────────
def test_phase_c_layers_won_block_removed():
    """User-visible 'Layers won' / 'LAYERS WON' string + the
    metric-layer-breakdown testid must be gone from the JSX.

    The string may appear inside `/* ... */` documentation comments
    that explain the removal; we only fail if it appears as a JSX
    text child (e.g., `>Layers won<` or `>LAYERS WON<`) or as a
    user-visible label inside a className-bearing element."""
    src = _read(CHAT)
    # Anchor 1: testid is gone (existing strong signal).
    assert "metric-layer-breakdown" not in src, (
        "metric-layer-breakdown testid must be gone"
    )
    # Anchor 2: JSX text child form is gone (the visible label).
    assert ">Layers won<" not in src, (
        "User-visible 'Layers won' label must be removed"
    )
    assert ">LAYERS WON<" not in src
    # Anchor 3: the 3-prong breakdown copy is gone (regex · Presidio · LLM-fallback).
    assert " regex · " not in src or "Presidio" not in src, (
        "Layer-breakdown 'regex · Presidio · LLM-fallback' copy must be gone"
    )


def test_phase_c_audit_modal_keeps_other_metrics():
    src = _read(CHAT)
    # Identifiers Redacted + Model Calls + their testids remain.
    assert "Identifiers redacted" in src
    assert "Model calls" in src
    assert 'data-testid="metric-modelcalls"' in src


def test_phase_c_audit_modal_keeps_hash_chain_and_export():
    """Brief acceptance (e): 'all hash-chain rows still render'.
    Hash-chain rows render via `rows.map(...)` inside the
    `data-testid="chat-audit-rows"` container. Row action names
    (CHAT.CREATED, MESSAGE.SENT, etc.) come from the backend
    response — they don't appear as literals in source. We anchor
    on the rendering scaffolding."""
    chat_src = _read(CHAT)
    assert "Export audit pack" in chat_src
    assert "hash-chained" in chat_src.lower(), (
        "'hash-chained' descriptive copy must remain in Chat.jsx"
    )
    assert 'data-testid="chat-audit-rows"' in chat_src, (
        "Hash-chain rows container testid must remain — rows render "
        "dynamically from the backend `rows` array."
    )
    assert "rows.map(" in chat_src, (
        "rows.map() rendering loop must remain to surface every "
        "hash-chain entry."
    )
