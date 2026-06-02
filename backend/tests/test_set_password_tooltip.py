"""Item 3 (2026-02 fork-resume) — Tooltip on /auth/set-password
heading.

Tiny lockdown — source-strict only. Logical assertion of the
tooltip markup shape (trigger present, content present,
aria-described-by wired) is sufficient because the visual
behaviour is delegated to Radix Tooltip (already covered by the
shadcn dependency).

Coverage:
  1. Heading carries an `id` so aria-described-by can reference it.
  2. The TooltipTrigger has `aria-label`, `aria-describedby`, and
     `data-testid="set-password-tooltip-trigger"`.
  3. The TooltipContent carries `role="tooltip"`, the verbatim
     fallback copy, and `data-testid="set-password-tooltip-content"`.
  4. The page imports the Tooltip primitives from the existing
     shadcn module (no new dependency).
"""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
PAGE = REPO / "frontend" / "src" / "pages" / "SetPasswordRequired.jsx"


def _read() -> str:
    return PAGE.read_text(encoding="utf-8")


def test_tooltip_uses_existing_shadcn_module():
    src = _read()
    assert 'from "@/components/ui/tooltip"' in src
    # Sanity check — no other tooltip-ish library was sneaked in.
    assert "react-tippy" not in src
    assert "react-popper-tooltip" not in src


def test_heading_has_id_for_aria_describedby():
    src = _read()
    assert 'id="set-password-heading-text"' in src


def test_tooltip_trigger_is_a11y_wired():
    src = _read()
    assert 'data-testid="set-password-tooltip-trigger"' in src
    assert 'aria-label="Why am I being asked to set a password?"' in src
    assert 'aria-describedby="set-password-heading-text"' in src


def test_tooltip_content_carries_verbatim_copy_and_testid():
    src = _read()
    assert 'data-testid="set-password-tooltip-content"' in src
    assert 'role="tooltip"' in src
    assert (
        "Akki uses your password as a fallback if your Google or "
        "Microsoft account becomes unreachable."
    ) in src


def test_form_fields_button_copy_and_flow_unchanged():
    """Hard contract — heading-only enhancement. The form fields,
    button copy, and submit flow must NOT have changed."""
    src = _read()
    # Fields preserved.
    assert 'data-testid="set-password-input"' in src
    assert 'data-testid="set-password-confirm"' in src
    # Submit button copy preserved.
    assert "Set password and continue" in src
    # POST shape preserved.
    assert 'api.post("/auth/set-password"' in src
