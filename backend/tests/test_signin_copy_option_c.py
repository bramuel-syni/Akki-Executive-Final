"""Sign-in copy swap → Option C — CI lockdown (2026-05-27).

Locks the editorial Option C copy on /sign-in per the autonomous-mode
locked queue (user-decision 2026-05-27). Future agents must not
silently rewrite the headline/body without dispatching a new copy
phase.

Verbatim spec:
  Headline: "The colleague who reads everything with you."
  Body:    "Boards. Ops. Monitoring. Briefings. Research. AKKI reads
           what you don't have time to read, remembers what you asked
           the last six meetings, and prepares you without ever taking
           the floor."
  Quote:   KEEP AS-IS (FTSE 250 audit-committee chair quote).
"""
from __future__ import annotations
from pathlib import Path


SIGNIN_JSX = Path(__file__).resolve().parent.parent.parent / "frontend" / "src" / "pages" / "SignIn.jsx"


def test_signin_copy_C_headline_locked():
    src = SIGNIN_JSX.read_text(encoding="utf-8")
    assert "The colleague who reads everything with you." in src, \
        "Option C headline must be present verbatim"
    # Defensive: prior headline must be GONE
    assert "The colleague who reads with you." not in src, \
        "Pre-Option-C headline ('The colleague who reads with you.') must be removed"


def test_signin_copy_C_body_locked():
    src = SIGNIN_JSX.read_text(encoding="utf-8")
    # Strip JSX whitespace + escape entities; check the *significant*
    # phrases survive verbatim.
    for phrase in [
        "Boards. Ops. Monitoring. Briefings. Research.",
        "AKKI reads what",
        "have time to read",
        "remembers what you asked the",
        "last six meetings",
        "prepares you without ever taking the",
        "floor",
    ]:
        assert phrase in src, f"Option C body phrase missing: {phrase!r}"
    # Pre-Option-C body must be gone
    forbidden = [
        "the third party in the conversation",
        "sharp, sober",
        "reads every pack",
    ]
    for f in forbidden:
        assert f not in src, f"Pre-Option-C body fragment {f!r} must be removed"


def test_signin_copy_C_quote_unchanged():
    """User explicitly locked the FTSE 250 quote as KEEP AS-IS."""
    src = SIGNIN_JSX.read_text(encoding="utf-8")
    for phrase in [
        "It's not that we don't read the pack",
        "the pack",
        "doesn't read us back",
        "remembers what we asked",
        "the last six meetings",
        "Audit-committee chair, FTSE 250",
    ]:
        assert phrase in src, f"FTSE 250 quote fragment missing: {phrase!r}"
