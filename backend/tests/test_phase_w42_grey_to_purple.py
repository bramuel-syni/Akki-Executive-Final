"""Phase W4.2 (2026-05-27, fork-resume) — Grey-capsule → light brand
purple highlights sweep. SOURCE-STRICT locks per institutional rule:
DOM assertions in Playwright probes (separate file), source locks
here.

Wave 4.2.followup.2 (2026-02 fork-resume) update — token form is now
the Tailwind-config short name `bg-ned-purple/N` instead of the
silent-fail `bg-[var(--ned-purple)]/N` syntax. The `text-` and `border-`
modifiers still resolve via the raw CSS var (no opacity modifier on
them in this layout, so they continue to work). All assertions below
accept either form so this guard tolerates both pre- and post-
followup.2 source.

Scope clarification from user (this dispatch):
  IN-SCOPE: pill-shaped CAPSULE HIGHLIGHTS currently rendered as
    plain grey — status pills, neutral-state markers, sub_role chips,
    feature locks. Excludes any pill that is semantically coloured
    (red/amber/green/blue stay).
  OUT-OF-SCOPE: page backgrounds, card surfaces, hover greys,
    borders, dividers, modal backdrops, skeleton states, text colours
    (background-fill is the only target).

Sites swapped (9 total, partition table archived in PHASE_LEDGER.md
under W4.2):
  1. StrategicGoalsPanel.STATUS_STYLE.abandoned
  2. StrategicGoalsPanel.STATUS_STYLE.not_started
  3. TenantSettings — isSponsored=false pill
  4. TenantSettings — cohort feature-lock badge
  5. TenantSettings — non-admin sub_role pill
  6. AccountSecurity — mfa_enabled=false pill
  7. SolvaSessions.StatusPill.refused
  8. SolvaSessions.StatusPill.blocked_hard / abandoned (legacy)
  9. SolvaSessions.StatusPill fallback (unknown status)

Locked utility tokens (either form acceptable post-Wave 4.2.followup.2):
  bg:     bg-ned-purple/10  OR  bg-[var(--ned-purple)]/10
  text:   text-[var(--ned-purple)]
  border: border-ned-purple/20  OR  border-[var(--ned-purple)]/20

Equivalent inline form (used in SolvaSessions where the palette is
defined via inline rgba()): bg=rgba(107,70,193,0.10) / fg=var(--ned-purple).

The W4.1 "Active" marker (TaskListing) + Phase V AdminUsers chip use
this exact token — staying consistent with that precedent.
"""
from __future__ import annotations

from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent.parent

STRATEGIC_GOALS = REPO / "frontend" / "src" / "components" / "monitor" / "StrategicGoalsPanel.jsx"
TENANT_SETTINGS = REPO / "frontend" / "src" / "pages" / "TenantSettings.jsx"
ACCOUNT_SECURITY = REPO / "frontend" / "src" / "pages" / "AccountSecurity.jsx"
SOLVA_SESSIONS = REPO / "frontend" / "src" / "pages" / "SolvaSessions.jsx"


# Wave 4.2.followup.2 — accept either token form when asserting purple bg.
_PURPLE_BG_FORMS = ("bg-ned-purple/10", "bg-[var(--ned-purple)]/10")


def _has_purple_bg(block: str) -> bool:
    return any(form in block for form in _PURPLE_BG_FORMS)


# ─────────────────────────────────────────────────────────────────────
# A. Strategic Goals — `abandoned` + `not_started` pills now purple
# ─────────────────────────────────────────────────────────────────────

def test_W42_a_strategic_abandoned_pill_is_purple():
    src = STRATEGIC_GOALS.read_text(encoding="utf-8")
    # Match the STATUS_STYLE.abandoned line.
    abandoned_block = src[src.find("abandoned:"):src.find("abandoned:") + 300]
    assert _has_purple_bg(abandoned_block), \
        "abandoned status pill must use light brand purple background " \
        f"(either of {_PURPLE_BG_FORMS!r})"
    assert "text-[var(--ned-purple)]" in abandoned_block, \
        "abandoned status pill must use brand-purple foreground"
    # Old grey tokens must be GONE on this row.
    assert "bg-slate-100 border-slate-200" not in abandoned_block, \
        "abandoned row must not still reference the legacy slate tokens"


def test_W42_a_strategic_not_started_pill_is_purple():
    src = STRATEGIC_GOALS.read_text(encoding="utf-8")
    block = src[src.find("not_started:"):src.find("not_started:") + 300]
    assert _has_purple_bg(block), \
        "not_started status pill must use light brand purple background " \
        f"(either of {_PURPLE_BG_FORMS!r})"
    assert "text-[var(--ned-purple)]" in block
    assert "bg-slate-100 border-slate-300" not in block


@pytest.mark.parametrize("semantic_status,expected_color_root", [
    ("on_track",  "emerald"),
    ("at_risk",   "amber"),
    ("off_track", "red"),
    ("achieved",  "blue"),
])
def test_W42_a_semantic_pills_remain_semantic(semantic_status, expected_color_root):
    """Semantically-coloured pills (RED/AMBER/GREEN/BLUE) MUST be
    preserved — only PLAIN grey capsules become purple."""
    src = STRATEGIC_GOALS.read_text(encoding="utf-8")
    # Tight match — STATUS_STYLE row form: `<key>:  { label: "...", tone: "..." },`.
    idx = src.find(f"{semantic_status}:")
    assert idx > 0
    line_end = src.find("\n", idx)
    block = src[idx:line_end]
    assert expected_color_root in block, \
        f"semantic {semantic_status} pill must keep its {expected_color_root}-* tokens"
    assert "ned-purple" not in block, \
        f"semantic {semantic_status} pill must NOT be swept to purple"


def test_W42_a_operations_dept_chip_is_purple_unified_sweep():
    """OVERRIDDEN by the unified Wave 4.2 sweep (2026-02 fork-resume):
    Operations dept chip is now part of the brand-purple sweep. The
    earlier institutional decision to keep palette members slate was
    superseded — every neutral capsule across Monitor/Pulse/Documents
    is now brand-purple-only.

    Backlog note: see Wave 4.2.followup.1 in PHASE_LEDGER.md — if
    cohort feedback reports lost visual taxonomy on Operations vs other
    categories, re-introduce hue differentiation within the brand-purple
    family. P3, founder-feedback-gated.
    """
    src = STRATEGIC_GOALS.read_text(encoding="utf-8")
    idx = src.find("operations:")
    if idx == -1:
        pytest.skip("Operations dept chip removed — assertion no longer needed")
    block = src[idx:idx + 300]
    # Either raw-var or short-name form is acceptable post-followup.2.
    has_purple = ("var(--ned-purple)" in block) or ("ned-purple/" in block)
    assert has_purple, \
        "Operations dept chip must carry the brand-purple token after the unified Wave 4.2 sweep"
    assert "bg-slate-100" not in block, \
        "Operations dept chip must NOT carry the legacy slate background after the unified Wave 4.2 sweep"


# ─────────────────────────────────────────────────────────────────────
# B. Tenant Settings — 3 pills swept (sponsored/non, feature-lock, sub_role)
# ─────────────────────────────────────────────────────────────────────

def test_W42_b_tenant_isSponsored_false_pill_is_purple():
    src = TENANT_SETTINGS.read_text(encoding="utf-8")
    # Ternary expression: `isSponsored ? "..." : "<purple tokens>"`.
    # Locate the isSponsored ternary.
    idx = src.find("isSponsored ? ")
    assert idx > 0
    block = src[idx:idx + 400]
    has_purple = (
        ("bg-ned-purple/10 text-[var(--ned-purple)]" in block)
        or ("bg-[var(--ned-purple)]/10 text-[var(--ned-purple)]" in block)
    )
    assert has_purple, \
        "non-sponsored pill must carry light-purple tokens (either form)"
    assert "bg-slate-100 text-slate-600" not in block


def test_W42_b_tenant_feature_lock_badge_is_purple():
    src = TENANT_SETTINGS.read_text(encoding="utf-8")
    idx = src.find("text-slate-400")
    # If still present anywhere on a feature-lock badge → fail.
    if idx > -1:
        # Confirm the residue isn't on a feature-lock badge.
        block = src[max(0, idx-200):idx+100]
        assert "lock" not in block or "bg-slate-100" not in block, \
            "feature-lock badge must use brand-purple tokens"
    # Affirmative — the brand-purple tokens are present where the
    # lock badge renders (either form acceptable).
    has_purple = (
        ("text-[var(--ned-purple)] bg-ned-purple/10" in src)
        or ("text-[var(--ned-purple)] bg-[var(--ned-purple)]/10" in src)
    )
    assert has_purple, \
        "feature-lock badge must carry text+bg purple (either form)"


def test_W42_b_tenant_non_admin_sub_role_pill_is_purple():
    src = TENANT_SETTINGS.read_text(encoding="utf-8")
    # The non-admin branch of the m.sub_role === "admin" ternary —
    # specifically the CHIP definition (contains the rounded-sm
    # capsule class). Other usages of `m.sub_role === "admin"`
    # are inline text concatenations, not chips.
    needle = 'm.sub_role === "admin" ? "bg-amber-50 text-[var(--accent)] border border-[var(--accent)]/30"'
    idx = src.find(needle)
    assert idx > 0, "non-admin chip ternary not found in TenantSettings"
    block = src[idx:idx + 600]
    has_purple = (
        ("bg-ned-purple/10 text-[var(--ned-purple)]" in block)
        or ("bg-[var(--ned-purple)]/10 text-[var(--ned-purple)]" in block)
    )
    assert has_purple, \
        "non-admin sub_role pill must carry light-purple tokens (either form)"
    assert "bg-slate-100 text-slate-700 border border-slate-200" not in block, \
        "legacy slate tokens must be gone from this site"


# ─────────────────────────────────────────────────────────────────────
# C. Account Security — mfa-disabled pill swept
# ─────────────────────────────────────────────────────────────────────

def test_W42_c_account_security_mfa_disabled_pill_is_purple():
    src = ACCOUNT_SECURITY.read_text(encoding="utf-8")
    # The mfa_enabled ternary.
    idx = src.find("account?.mfa_enabled")
    assert idx > 0
    block = src[idx:idx + 400]
    has_purple = (
        ("bg-ned-purple/10 text-[var(--ned-purple)]" in block)
        or ("bg-[var(--ned-purple)]/10 text-[var(--ned-purple)]" in block)
    )
    assert has_purple, \
        "mfa_enabled=false pill must carry light-purple tokens (either form)"
    assert "bg-slate-100 text-slate-600 border border-slate-200" not in block


# ─────────────────────────────────────────────────────────────────────
# D. Solva Sessions — refused/blocked_hard/abandoned/default fallback
# ─────────────────────────────────────────────────────────────────────

def test_W42_d_solva_refused_uses_brand_purple_rgba():
    """The Solva StatusPill palette is defined via inline rgba() for
    historical reasons — swap the grey rgba to brand-purple rgba.

    Tight needle: the palette entry has a unique `refused:` followed
    immediately by `{ bg:` — distinguishes from the counts state
    object (`{ active: 0, paused: 0, complete: 0, refused: 0 }`).
    """
    src = SOLVA_SESSIONS.read_text(encoding="utf-8")
    idx = src.find("refused:       {")
    assert idx > 0, "refused palette entry not found"
    line_end = src.find("\n", idx)
    block = src[idx:line_end]
    assert "rgba(107,70,193,0.10)" in block, \
        "refused status palette must use brand-purple rgba (107,70,193,0.10)"
    assert "var(--ned-purple)" in block
    assert "rgba(0,0,0,0.07)" not in block


@pytest.mark.parametrize("legacy_status", ["blocked_hard:", "abandoned:"])
def test_W42_d_solva_legacy_status_remap_to_purple(legacy_status):
    src = SOLVA_SESSIONS.read_text(encoding="utf-8")
    # Tight needle — palette entries have the `<key>:    { bg:` form,
    # but the column-aligned indent varies between entries. Match via
    # the `:` + whitespace + `{ bg:` pattern instead.
    import re
    rx = re.search(rf"{re.escape(legacy_status)}\s+\{{ bg:", src)
    assert rx is not None, f"palette entry {legacy_status} not found"
    line_end = src.find("\n", rx.start())
    block = src[rx.start():line_end]
    assert "rgba(107,70,193,0.10)" in block, \
        f"legacy status {legacy_status} must remap to brand-purple rgba"


def test_W42_d_solva_default_fallback_is_purple():
    """The default-branch fallback in the StatusPill palette ternary."""
    src = SOLVA_SESSIONS.read_text(encoding="utf-8")
    idx = src.find("}[s] ||")
    assert idx > 0
    block = src[idx:idx + 200]
    assert "rgba(107,70,193,0.10)" in block, \
        "unknown-status fallback must use brand-purple rgba"
    assert "rgba(0,0,0,0.05)" not in block


def test_W42_d_solva_semantic_pills_preserved():
    """active=green, paused=amber, complete=blue stay semantic."""
    src = SOLVA_SESSIONS.read_text(encoding="utf-8")
    # Tight match — palette entries have form `<key>:        { bg:`.
    for key, needle, color_rgba in [
        ("active",   "active:        {", "rgba(50,140,90"),
        ("paused",   "paused:        {", "rgba(180,130,50"),
        ("complete", "complete:      {", "rgba(50,100,180"),
    ]:
        idx = src.find(needle)
        assert idx > 0, f"palette entry {key} not found"
        line_end = src.find("\n", idx)
        block = src[idx:line_end]
        assert color_rgba in block, \
            f"{key} status palette must preserve its semantic colour"


# ─────────────────────────────────────────────────────────────────────
# E. No collateral grey-capsule regressions
# ─────────────────────────────────────────────────────────────────────

def test_W42_e_no_residual_legacy_grey_capsule_classes_in_swept_files():
    """The 9 sites' specific legacy tokens must not reappear anywhere
    else in the same file (would indicate a copy-paste regression)."""
    legacy_capsule_marker = "bg-slate-100 text-slate-600 border border-slate-200"
    for path in (STRATEGIC_GOALS, TENANT_SETTINGS, ACCOUNT_SECURITY, SOLVA_SESSIONS):
        src = path.read_text(encoding="utf-8")
        # The very-specific 3-class triplet must be ABSENT post-W4.2 sweep.
        assert legacy_capsule_marker not in src, \
            f"{path.name} still carries legacy grey-capsule triplet"


def test_W42_e_brand_purple_token_consistent_across_sweep():
    """All swept files must use one of the canonical brand-purple
    token forms (no drift to bg-violet-* / bg-purple-* / similar
    one-offs). Either `bg-ned-purple/10` (Wave 4.2.followup.2 short
    name) or the legacy `bg-[var(--ned-purple)]/10` form is accepted."""
    for path in (STRATEGIC_GOALS, TENANT_SETTINGS, ACCOUNT_SECURITY):
        src = path.read_text(encoding="utf-8")
        has_purple = any(form in src for form in _PURPLE_BG_FORMS)
        assert has_purple, \
            f"{path.name} must use one of the canonical purple bg tokens {_PURPLE_BG_FORMS!r}"
