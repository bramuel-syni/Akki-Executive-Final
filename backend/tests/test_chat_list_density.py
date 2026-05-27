"""Phase H.3 side-fix CI guard — Chat list density (2026-05-27).

Locks the Claude-style tightening on the `/app/chat` left sidebar
so the density doesn't drift back to the loose/serif/with-subtitle
posture.

Source asserts only (JSX + Tailwind class strings). Live computed-
style verification has been captured separately by the agent via
Playwright on the preview environment — that evidence is recorded
in CHANGELOG/PRD.

Locks in:
  T1.  Row title uses font-sans + text-[13.5px] + font-medium +
       leading-[1.35] + truncate.
  T2.  Row root carries py-2 px-3 (8px vertical / 12px horizontal).
  T3.  No subtitle / preview <p> element rendered inside the
       non-search default chat row. (Search hits and archive rows
       keep their snippet/secondary line — those are deliberate.)
  T4.  Active state preserves the 2px oxblood left accent bar.
  T5.  Header sub-line "Synisense-shielded · multi-model · audited"
       uses text-[10px] (single-line muted, not 14px serif).
  T6.  Search input is the tightened 32px (h-8 + text-[13px]).
  T7.  Sidebar background is var(--paper) (warm parchment kept).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
CHAT_PAGE = REPO / "frontend" / "src" / "pages" / "Chat.jsx"


def _read() -> str:
    return CHAT_PAGE.read_text(encoding="utf-8")


def _extract_default_row_block(src: str) -> str:
    """Slice out the default chat-row render block (the one with
    `data-testid={`chat-item-${c.id}`}`). Returns the substring
    from the role="button" wrapper through the closing </div>."""
    # The default row begins with the chats.map((c) => { ... return ( <div role="button" ...
    m = re.search(
        r"chats\.map\(\(c\)\s*=>\s*\{(.*?)\}\s*\)\s*\}\s*\n\s*</div>",
        src, flags=re.DOTALL,
    )
    assert m, "Default chat-row .map(c => ...) block not found in Chat.jsx"
    return m.group(1)


# ── T1. Title typography ──────────────────────────────────────────
def test_chat_row_title_uses_sans_13_5_weight_500_leading_135():
    src = _read()
    # Title <p> tag carries the exact Tailwind classes.
    title_cls = 'font-sans text-[13.5px] font-medium leading-[1.35] truncate text-[var(--ink)]'
    assert title_cls in src, (
        f"Chat row title must carry exactly: `{title_cls}`. "
        "The Claude-style tightening lock is broken — restore the "
        "13.5px / weight-500 / sans / leading-1.35 contract."
    )
    # Title testid present on the default row.
    assert "chat-item-title-${c.id}" in src


# ── T2. Row root spacing ──────────────────────────────────────────
def test_chat_row_root_has_8px_vertical_12px_horizontal_padding():
    block = _extract_default_row_block(_read())
    # Tailwind: px-3 = 12px / py-2 = 8px. We assert both as literal
    # class tokens on the row wrapper.
    assert "px-3" in block, "Chat row root missing px-3 (12px horizontal padding)"
    assert "py-2" in block, "Chat row root missing py-2 (8px vertical padding)"
    # The row wrapper has the `chat-item-${c.id}` testid.
    assert "chat-item-${c.id}" in block


# ── T3. NO subtitle / preview line inside default row ─────────────
def test_chat_row_drops_subtitle_preview_line():
    """The default chat row renders the title only — no secondary
    text node (preview / last-message-snippet / timestamp line) is
    permitted. Search hits keep a snippet (deliberate, see T6 of
    the search-hit block); this guard targets only the default row.
    """
    block = _extract_default_row_block(_read())
    # Count <p> tags inside the row block.
    p_count = len(re.findall(r"<p\b", block))
    assert p_count == 1, (
        f"Default chat row contains {p_count} <p> elements; the "
        "Claude-style tightening allows exactly 1 (the title). "
        "If a preview / subtitle / timestamp line crept back in, "
        "drop it — search hits and archive rows have their own "
        "render path and are not affected."
    )
    # Forbidden tokens that would indicate a subtitle leak.
    for forbidden in (
        "last_message_preview",   # field name → message snippet
        "no messages yet",        # legacy fallback label
        "last_message_at",        # timestamp line
    ):
        # We allow the field/label to live in OTHER parts of the file
        # (chat header, top-bar etc) but not inside the default row.
        assert forbidden not in block, (
            f"`{forbidden}` re-appeared inside the chat-list row body. "
            "Tightening regression — keep the row to title-only."
        )


# ── T4. Active state preserves the 2px oxblood left accent bar ────
def test_chat_row_active_state_keeps_2px_oxblood_accent_bar():
    block = _extract_default_row_block(_read())
    assert "border-l-2 border-l-[var(--accent)]" in block, (
        "Active chat-row must keep the 2px oxblood left accent bar. "
        "Removing it eliminates the only strong visual anchor for "
        "the active conversation."
    )
    # The active branch also tints the background subtly.
    assert "bg-[var(--cream)]" in block


# ── T5. Header sub-line is tightened ──────────────────────────────
def test_chat_sidebar_header_subline_tight_10px():
    src = _read()
    # The Synisense sub-line is rendered with text-[10px] muted in
    # a single line. We assert the literal classes AND the verbatim
    # spec text.
    assert "Synisense-shielded · multi-model · audited" in src
    # text-[10px] + text-[var(--muted)] + truncate are the tightening
    # markers on the sub-line.
    subline_classes = 'text-[10px] text-[var(--muted)] truncate'
    assert subline_classes in src, (
        f"Sub-line must carry exactly: `{subline_classes}`. "
        "If a larger size or serif sneaks back in, the header "
        "loses density."
    )


# ── T6. Search input is tightened (32px tall, 13px text) ──────────
def test_chat_sidebar_search_input_is_h8_text_13():
    src = _read()
    # The search <input> carries h-8 + text-[13px].
    assert 'data-testid="chat-search-input"' in src
    # h-8 = 32px, matches spec.
    assert "h-8 text-[13px]" in src, (
        "Search input must be h-8 (32px) + text-[13px] per the "
        "tightening spec."
    )


# ── T7. Sidebar background stays warm parchment ───────────────────
def test_chat_sidebar_keeps_warm_parchment_background():
    """Spec: do NOT switch to white or dark — keep existing pale
    cream. We assert via the bg-[var(--paper)] class on the aside."""
    src = _read()
    aside_re = re.search(
        r'<aside[^>]*data-testid="chat-sidebar"[^>]*>',
        src,
    )
    assert aside_re, "chat-sidebar aside element not found"
    aside_open = aside_re.group(0)
    assert "bg-[var(--paper)]" in aside_open, (
        "chat-sidebar must keep bg-[var(--paper)] (warm parchment). "
        "If this flipped to bg-white or bg-slate-* the chat surface "
        "loses its editorial palette."
    )


# ── T8. Title testid present on every row, no extra wrapping ──────
def test_chat_row_title_testid_attached_directly_to_title_paragraph():
    """The data-testid `chat-item-title-${c.id}` must be on the
    title <p> so Playwright can read its computed style directly
    (without crawling DOM children)."""
    src = _read()
    # The literal pattern: `<p\n   className="..."\n   data-testid={`chat-item-title-${c.id}`}>`
    # We match across newlines.
    pattern = re.compile(
        r"<p[^>]*data-testid=\{`chat-item-title-\$\{c\.id\}`\}",
        flags=re.DOTALL,
    )
    assert pattern.search(src), (
        "`chat-item-title-${c.id}` testid must be on the title <p> "
        "element itself, not on a wrapper. Playwright reads "
        "computed style from this exact node in the runtime guard."
    )
