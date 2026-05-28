"""Wave 5 (2026-05-27) — Chat no-context default CI lockdown.

Locks the user-asked behavior change:
  • General RAG (no-context) is the DEFAULT chat mode.
  • `onNewChat` no longer blocks when activeContext is unset; sends
    `context_id: activeContext?.id || null` so the backend mints a
    general chat when no context is selected.
  • The chat-list fetch effect no longer early-bails when there's no
    activeContext — the list surfaces both general + context-scoped
    chats.
  • Context picker remains optional (the existing company switcher
    in AppShell is unchanged).
  • The pre-W5 toast `"Pick a company first to start a chat."` is GONE
    from `onNewChat`.
  • Phase Q (general chat / no-context) is now absorbed into the
    default Chat surface state — closes Phase Q.

Backend invariants verified upstream:
  • backend/routers/chat.py line 143: `context_id: Optional[str] = Field(default=None, max_length=120)`
  • backend/routers/chat.py line 158: `context_id: Optional[str] = None`
"""
from __future__ import annotations

from pathlib import Path
import re


REPO = Path(__file__).resolve().parent.parent.parent
CHAT = REPO / "frontend" / "src" / "pages" / "Chat.jsx"
CHAT_BACKEND = REPO / "backend" / "routers" / "chat.py"


def _on_new_chat_block(src):
    """Return the `onNewChat = async () => {...}` function body."""
    m = re.search(
        r'const onNewChat = async \(\) => \{[\s\S]*?^\s\s\};',
        src,
        re.MULTILINE,
    )
    assert m, "onNewChat function must exist in Chat.jsx"
    return m.group(0)


def test_W5_a_on_new_chat_no_longer_blocks_without_context():
    src = CHAT.read_text(encoding="utf-8")
    block = _on_new_chat_block(src)
    # The pre-W5 toast is GONE from onNewChat.
    assert "Pick a company first to start a chat" not in block, \
        "Legacy 'Pick a company first to start a chat' block must be removed from onNewChat"


def test_W5_b_on_new_chat_sends_optional_context_id():
    src = CHAT.read_text(encoding="utf-8")
    block = _on_new_chat_block(src)
    # Posts `context_id: activeContext?.id || null` (Wave 5 default).
    assert "activeContext?.id || null" in block, \
        "onNewChat must POST `context_id: activeContext?.id || null` so the backend " \
        "can mint a general chat when no context is selected"


def test_W5_c_chat_list_effect_no_longer_early_bails_on_no_context():
    """The chat-list `useEffect` that runs on activeContext change
    must no longer early-bail with `if (!activeContext?.id) return;`."""
    src = CHAT.read_text(encoding="utf-8")
    # Find the comment marker for the Phase B.1 effect.
    pb1_idx = src.find("Phase B.1 — wipe the visible chats list")
    assert pb1_idx > 0
    # Slice just the executable code after the last comment line
    # (`*/` closes the lineage comment that quotes the removed bail).
    snippet = src[pb1_idx:pb1_idx + 1200]
    # Locate the `useEffect(() => {` opener after the comment block.
    code_start = snippet.find("useEffect(() =>")
    assert code_start > 0, "useEffect opener must be present after the Phase B.1 comment"
    code_only = snippet[code_start:]
    assert "if (!activeContext?.id) return;" not in code_only, \
        "Phase B.1 effect body must no longer early-bail when activeContext is unset (Wave 5)"
    # And the Wave 5 marker is present in the surrounding comment.
    assert "Wave 5" in snippet, \
        "Phase B.1 effect must carry the Wave 5 lineage comment"


def test_W5_d_chat_splash_copy_unchanged():
    """The pre-existing splash copy ('Your private AI workspace.' +
    'Ask anything you'd ask ChatGPT, Claude, or Gemini') already
    handles the no-context default. Verify it's still in place + the
    splash CTA points to onNewChat."""
    src = CHAT.read_text(encoding="utf-8")
    assert "Your private AI workspace." in src
    assert "Ask anything you'd ask ChatGPT, Claude, or Gemini" in src
    assert 'data-testid="chat-splash-new-btn"' in src


def test_W5_e_backend_accepts_optional_context_id():
    """The backend `/api/chats` POST endpoint must already accept
    `context_id: Optional[str] = None` — Wave 5 frontend depends on
    this contract."""
    src = CHAT_BACKEND.read_text(encoding="utf-8")
    assert "context_id: Optional[str] = Field(default=None" in src, \
        "Backend ChatCreateIn must declare `context_id: Optional[str] = Field(default=None, ...)`"


def test_W5_f_backend_create_no_longer_requires_context():
    """Wave 5 — the chat POST endpoint must NOT raise
    ACTIVE_CONTEXT_REQUIRED when neither header nor body has a
    context. The pre-W5 guard at line ~532 is GONE."""
    src = CHAT_BACKEND.read_text(encoding="utf-8")
    # Find the chat-create endpoint body. The pre-W5 guard was an
    # explicit raise of ACTIVE_CONTEXT_REQUIRED with the message
    # "Chat creation requires an active company context."
    assert "Chat creation requires an active company context" not in src, \
        "Backend chat-create endpoint must no longer raise ACTIVE_CONTEXT_REQUIRED"
    # Wave 5 lineage comment present.
    assert "Wave 5 (2026-05-27) — General RAG (no-context) is now the" in src, \
        "Backend chat-create endpoint must carry the Wave 5 lineage comment"


def test_W5_g_backend_list_returns_general_when_no_header():
    """Wave 5 — the chat LIST endpoint must surface general chats
    (context_id None) when no X-Active-Context header is sent. The
    pre-W5 helper guard `_require_active_context(request)` is GONE
    from the chat-list function body."""
    src = CHAT_BACKEND.read_text(encoding="utf-8")
    # The list function carries the Wave 5 lineage + the no-header
    # general-only $or filter.
    assert "General mode — only general chats" in src, \
        "Backend chat LIST endpoint must carry the Wave 5 general-mode comment"
    # The general-mode $or filter.
    assert '"$or": [{"context_id": None}, {"context_id": {"$exists": False}}]' in src or \
        "context_id\": None}, {\"context_id\": {\"$exists\": False}" in src, \
        "Backend chat LIST must filter general chats when no header is sent"


def test_W5_h_send_message_supports_general_chats():
    """Wave 5 — send_message + stream_message endpoints must lookup
    the chat without enforcing a context header when the chat is
    general."""
    src = CHAT_BACKEND.read_text(encoding="utf-8")
    # Five Wave 5 lineage markers — one per relaxed endpoint.
    assert src.count("Wave 5 (2026-05-27) — General RAG default") >= 5, \
        "Backend chat.py must carry the Wave 5 lineage marker on each of the 5 relaxed endpoints (list/search/create/send_message/stream_message/delete)"
    # stream_message specifically points back to send_message.
    assert "matched general-chat-aware lookup pattern" in src, \
        "stream_message must point back to send_message for the matched pattern"
