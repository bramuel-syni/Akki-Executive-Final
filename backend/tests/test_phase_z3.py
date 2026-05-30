"""Phase Z3 (2026-02 fork-resume v2) — Claude-style chat actions.

  • User bubbles: Edit · Copy
  • Assistant bubbles: Regenerate · Copy
  • Hover-revealed via `group-hover:opacity-100` parent contract
  • Keyboard accessible (each action is a `<button>` with aria-label)
  • Clipboard write with textarea-execCommand fallback
"""
from __future__ import annotations
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
FRONTEND = REPO / "frontend" / "src"
ACTIONS = FRONTEND / "components" / "chat" / "MessageActions.jsx"
CHAT = FRONTEND / "pages" / "Chat.jsx"


def test_z3_message_actions_component_exists():
    src = ACTIONS.read_text(encoding="utf-8")
    assert "export default function MessageActions" in src
    # Hover-reveal via the parent `group` contract
    assert "group-hover:opacity-100" in src
    # Both user and assistant action sets present
    assert "Edit" in src and "Copy" in src and "Regenerate" in src
    # Clipboard writer + textarea fallback
    assert "navigator.clipboard.writeText" in src
    assert "document.execCommand" in src
    # ARIA on every button (no naked icons)
    assert 'aria-label={label}' in src


def test_z3_chat_jsx_wires_actions_and_handlers():
    src = CHAT.read_text(encoding="utf-8")
    assert 'import MessageActions from "@/components/chat/MessageActions"' in src
    # The `group` class is required on the bubble row for hover-reveal.
    assert 'className={`group flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}' in src
    # Handlers plumbed from parent to Message
    assert "onEdit={(text) => {" in src
    assert "onRegenerate={() => {" in src
    # Edit handler populates composer + focuses input (no in-place mutation)
    assert 'setInput(text || "")' in src
    assert 'data-testid="chat-input"' in src
    # Regenerate handler re-submits the most-recent prior user turn
    assert "for (let i = idx - 1; i >= 0; i--)" in src
    assert 'arr[i].role === "user"' in src


def test_z3_actions_skip_streaming_and_optimistic_bubbles():
    """Don't render Copy/Edit/Regenerate on a streaming-placeholder
    bubble (no content yet) or on an optimistic `tmp-` user bubble
    (no real message id to anchor)."""
    src = CHAT.read_text(encoding="utf-8")
    assert '!m.streaming && m.id && !String(m.id).startsWith("tmp-")' in src


def test_z3_action_testids_locked():
    src = ACTIONS.read_text(encoding="utf-8")
    for k in ["chat-action-edit-", "chat-action-copy-", "chat-action-regenerate-"]:
        assert k in src, f"Missing testid prefix {k!r}"
    # Bubble-level testid container
    assert "chat-message-actions-${role}" in src


def test_z3_voice_lint_on_button_labels():
    """The only user-visible strings in MessageActions are `Edit`,
    `Copy`, `Regenerate`, `Copied` — all voice-clean."""
    banned = ["leverage", "empower", "AI-powered", "seamless",
              "revolutionary", "synergy", "frictionless", "unlock",
              "supercharge", "disrupt"]
    src = ACTIONS.read_text(encoding="utf-8")
    for w in banned:
        # Check inside the JSX `>...<` and `label="..."` only
        assert w not in src.lower() or w == "synergy" and False, \
            f"Banned word {w!r} appeared in MessageActions"
