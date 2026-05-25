#!/usr/bin/env python3
"""Hardening Step 2 — Phase A audit (one-shot script).

Scans the frontend for the three known false-green patterns from the
closeout doc lessons (§5.6, §5.7, §5.8).

  P1 (T2.3): `{cond && <Component data-testid="...">...` — short-circuit
            JSX immediately preceding a component that carries a stable
            data-testid (likely spec-anchored, likely victim of the
            "found by source-string but DOM never renders" pattern).

  P2 (B3): Symbol used inside `{cond && <SymbolName ...>}` or
           `{cond ? <SymbolName ...> ...}` where `SymbolName` is NOT
           in the file's named-imports OR default-import (jsx-no-undef
           regression, hidden behind the conditional gate at unit-test
           time).

  P3 (J2.3): Auth-context writer — a `useAuth()` consumer that calls a
            mutation endpoint but does NOT call any of the auth-state
            refresh helpers (`bootstrap`, `refreshAuth`, `refresh`,
            `setUser`). Cross-checks with `useAuth()` consumer list.

Output: `/app/memory/sprints/FALSE_GREEN_AUDIT_LEDGER.md`. Read-only
on the source tree — this script NEVER edits source.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FRONTEND = REPO / "frontend/src"
OUT = REPO / "memory/sprints/FALSE_GREEN_AUDIT_LEDGER.md"


def iter_jsx_files():
    for p in FRONTEND.rglob("*.jsx"):
        if "node_modules" in str(p):
            continue
        if "/ui/" in str(p):
            # shadcn primitives — out of audit scope (vendor surface)
            continue
        yield p


# ── Pattern 1 — `&&` short-circuit immediately preceding testid ──
TESTID_AFTER_AMP = re.compile(
    r"\{[^{}\n]+&&\s*\(?\s*\n?\s*<[A-Za-z][^>]*?data-testid=\"([^\"]+)\"",
    re.MULTILINE,
)


def scan_pattern_1(src: str):
    """Return list of (line_no, testid, code_excerpt)."""
    hits = []
    for m in TESTID_AFTER_AMP.finditer(src):
        line_no = src[: m.start()].count("\n") + 1
        excerpt = m.group(0).replace("\n", " ").strip()[:120]
        hits.append((line_no, m.group(1), excerpt))
    return hits


# ── Pattern 2 — undefined JSX symbol inside conditional branch ──
NAMED_IMPORT_RE = re.compile(
    r"^import\s*(?:type\s+)?\{([^}]+)\}\s*from\s*['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)
DEFAULT_IMPORT_RE = re.compile(
    r"^import\s+(?!\{)\s*(\w+)(?:\s*,\s*\{[^}]+\})?\s+from\s*['\"][^'\"]+['\"]",
    re.MULTILINE,
)
SIDE_EFFECT_IMPORT_RE = re.compile(
    r"^import\s+['\"][^'\"]+['\"];?$", re.MULTILINE,
)


def collect_imports(src: str) -> set:
    """Best-effort set of in-scope JSX symbols (named + default)."""
    syms = set()
    for m in NAMED_IMPORT_RE.finditer(src):
        for raw in m.group(1).split(","):
            raw = raw.strip()
            if not raw:
                continue
            # Strip `as alias` if present.
            if " as " in raw:
                raw = raw.split(" as ", 1)[1].strip()
            # Strip `type ` prefix if present.
            raw = re.sub(r"^type\s+", "", raw)
            if raw:
                syms.add(raw)
    for m in DEFAULT_IMPORT_RE.finditer(src):
        syms.add(m.group(1))
    # Symbols defined locally — functions, consts.
    for m in re.finditer(
        r"^(?:export\s+)?(?:async\s+)?function\s+([A-Z]\w+)", src, re.MULTILINE,
    ):
        syms.add(m.group(1))
    for m in re.finditer(
        r"^(?:export\s+)?const\s+([A-Z]\w+)\s*=", src, re.MULTILINE,
    ):
        syms.add(m.group(1))
    # React component is implicit via JSX runtime.
    syms.update({"React", "Fragment"})
    return syms


# JSX symbols used inside conditional branches (`&&` or ternary).
CONDITIONAL_JSX_SYMBOL = re.compile(
    r"\{[^{}\n]+(?:&&|\?)\s*\(?\s*\n?\s*<([A-Z][\w.]*)",
    re.MULTILINE,
)


# Built-in / globally-available JSX symbols that don't need import.
BUILTIN_JSX = {"React", "Fragment", "Suspense", "StrictMode"}


def scan_pattern_2(src: str, imports: set):
    """Return list of (line_no, undefined_symbol, code_excerpt)."""
    hits = []
    for m in CONDITIONAL_JSX_SYMBOL.finditer(src):
        sym = m.group(1).split(".")[0]
        if sym in BUILTIN_JSX:
            continue
        if sym in imports:
            continue
        line_no = src[: m.start()].count("\n") + 1
        excerpt = m.group(0).replace("\n", " ").strip()[:120]
        hits.append((line_no, sym, excerpt))
    return hits


# ── Pattern 3 — Auth-writer without refresh ────────────────────────
USE_AUTH_RE = re.compile(r"\buseAuth\s*\(\s*\)")
AUTH_REFRESH_RE = re.compile(
    r"\b(bootstrap|refreshAuth|refresh|setUser|setAccount)\s*\(",
)
AUTH_MUTATING_API_RE = re.compile(
    r'api\.post\(\s*[`"\']'
    r"(/me/first-session/(?:choose-door|intake|skip)"
    r"|/users/me/profile"
    r"|/contexts/[^/`\"\']+/(?:switch|activate)"
    r"|/auth/(?:register|login|signin))",
    re.MULTILINE,
)


def scan_pattern_3(src: str):
    """Files that import useAuth + invoke an auth-mutating endpoint
    but don't appear to call any refresh helper."""
    if not USE_AUTH_RE.search(src):
        return []
    hits = []
    for m in AUTH_MUTATING_API_RE.finditer(src):
        line_no = src[: m.start()].count("\n") + 1
        # Look in a window around the mutation call for a refresh call.
        window_start = max(0, m.start() - 200)
        window_end = min(len(src), m.end() + 800)
        window = src[window_start:window_end]
        if AUTH_REFRESH_RE.search(window):
            continue
        # Or if the file as a whole calls a refresh helper near any
        # post — surface it for review.
        excerpt = m.group(0).replace("\n", " ").strip()[:120]
        hits.append((line_no, m.group(1), excerpt))
    return hits


# ── Priority classifier ─────────────────────────────────────────────
ONBOARDING_HOT_PATH = (
    "FirstSession.jsx",
    "AppShell.jsx",
    "AuthContext.jsx",
    "TrustCenterTour.jsx",
    "SolvaPhaseDSession.jsx",
    "BillingTab.jsx",
    "UpgradeModal.jsx",
    "SignIn",
    "Register",
)


def classify_priority(rel: str, sym_or_testid: str) -> str:
    """P0 = breaks onboarding path. P1 = silently darks a spec section.
    P2 = anywhere else."""
    for marker in ONBOARDING_HOT_PATH:
        if marker in rel:
            return "P0"
    # P1 if the testid is referenced by a J-suite or chunk-c test.
    if sym_or_testid and any(
        prefix in (sym_or_testid or "")
        for prefix in (
            "billing-coming-soon",
            "billing-notify",
            "billing-deferred",
            "upgrade-modal",
            "trust-center-",
            "help-tooltip",
            "first-doc",
            "onboarding-",
            "intake-",
            "door-",
            "akki-banner",
            "demo-",
        )
    ):
        return "P1"
    return "P2"


# ── Main ───────────────────────────────────────────────────────────
def main():
    p1_rows = []
    p2_rows = []
    p3_rows = []

    for path in iter_jsx_files():
        src = path.read_text(encoding="utf-8", errors="replace")
        rel = str(path.relative_to(REPO))
        imports = collect_imports(src)
        for line_no, testid, excerpt in scan_pattern_1(src):
            p1_rows.append((rel, line_no, testid, excerpt,
                            classify_priority(rel, testid)))
        for line_no, sym, excerpt in scan_pattern_2(src, imports):
            p2_rows.append((rel, line_no, sym, excerpt,
                            classify_priority(rel, sym)))
        for line_no, endpoint, excerpt in scan_pattern_3(src):
            p3_rows.append((rel, line_no, endpoint, excerpt,
                            classify_priority(rel, endpoint)))

    def by_pri(rows):
        return {pri: [r for r in rows if r[-1] == pri]
                for pri in ("P0", "P1", "P2")}

    p1_by = by_pri(p1_rows)
    p2_by = by_pri(p2_rows)
    p3_by = by_pri(p3_rows)

    lines = []
    lines.append("# False-Green Audit Ledger — Hardening Step 2 Phase A")
    lines.append("")
    lines.append("**Generated:** 2026-05-25 (post-Step-1 close).")
    lines.append(
        "**Scope:** all `frontend/src/**/*.jsx` excluding the shadcn `ui/` "
        "primitives. Read-only static analysis."
    )
    lines.append("")
    lines.append("**Pattern legend:**")
    lines.append(
        "- **P1**: T2.3 — `{cond && <Section data-testid=\"...\">}` JSX "
        "short-circuit immediately preceding a testid'd element. Likely "
        "violates the DOM-unconditional rule (§5.7) IF the testid is "
        "spec-referenced. Many will be legitimate (truly optional UI)."
    )
    lines.append(
        "- **P2**: B3 — JSX symbol used inside a conditional branch "
        "that doesn't appear in the file's imports. Likely ReferenceError "
        "at runtime, invisible to CI until the branch fires."
    )
    lines.append(
        "- **P3**: J2.3 — `useAuth()` consumer that POSTs an "
        "auth-mutating endpoint without a nearby refresh call. The "
        "AuthContext may render stale on the very next route guard."
    )
    lines.append("")
    lines.append("**Priority legend:**")
    lines.append(
        "- **P0**: site lives in the onboarding hot-path "
        "(FirstSession, AppShell, AuthContext, TrustCenterTour, "
        "SolvaPhaseDSession, BillingTab, UpgradeModal, signin/register)."
    )
    lines.append(
        "- **P1**: testid matches a known J-suite or chunk-c anchor "
        "(billing-*, trust-center-*, help-tooltip, intake-*, door-*, "
        "demo-*, akki-banner, onboarding-*, first-doc-*, upgrade-modal-*)."
    )
    lines.append("- **P2**: anywhere else.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        f"## Summary counts — "
        f"P1(T2.3)={len(p1_rows)} · "
        f"P2(B3)={len(p2_rows)} · "
        f"P3(J2.3)={len(p3_rows)}"
    )
    lines.append("")
    lines.append("| Pattern | P0 | P1 | P2 | Total |")
    lines.append("| --- | --- | --- | --- | --- |")
    for label, rows_by, total in (
        ("P1 — T2.3 conditional-render-hiding", p1_by, len(p1_rows)),
        ("P2 — B3 undefined-symbol-in-conditional", p2_by, len(p2_rows)),
        ("P3 — J2.3 auth-writer-without-refresh", p3_by, len(p3_rows)),
    ):
        lines.append(
            f"| {label} | {len(rows_by['P0'])} | "
            f"{len(rows_by['P1'])} | "
            f"{len(rows_by['P2'])} | {total} |"
        )
    lines.append("")

    for label, rows_by in (
        ("Pattern 1 — T2.3 conditional-render-hiding spec-anchored sections", p1_by),
        ("Pattern 2 — B3 undefined-symbol-in-conditional branch", p2_by),
        ("Pattern 3 — J2.3 auth-writer-without-refresh", p3_by),
    ):
        lines.append(f"## {label}")
        lines.append("")
        for pri in ("P0", "P1", "P2"):
            rows = rows_by[pri]
            if not rows:
                continue
            lines.append(f"### {pri} ({len(rows)} site"
                         f"{'s' if len(rows) != 1 else ''})")
            lines.append("")
            lines.append("| File | Line | Symbol / Testid | Excerpt |")
            lines.append("| --- | --- | --- | --- |")
            for rel, line_no, sym, excerpt, _ in sorted(rows):
                cleaned = excerpt.replace("|", "\\|")
                lines.append(
                    f"| `{rel}` | {line_no} | `{sym}` | `{cleaned}` |"
                )
            lines.append("")
        lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote ledger: {OUT}")
    print(
        f"Counts — P1(T2.3): {len(p1_rows)} "
        f"({len(p1_by['P0'])}P0/{len(p1_by['P1'])}P1/{len(p1_by['P2'])}P2)"
    )
    print(
        f"Counts — P2(B3):   {len(p2_rows)} "
        f"({len(p2_by['P0'])}P0/{len(p2_by['P1'])}P1/{len(p2_by['P2'])}P2)"
    )
    print(
        f"Counts — P3(J2.3): {len(p3_rows)} "
        f"({len(p3_by['P0'])}P0/{len(p3_by['P1'])}P1/{len(p3_by['P2'])}P2)"
    )


if __name__ == "__main__":
    sys.exit(main())
