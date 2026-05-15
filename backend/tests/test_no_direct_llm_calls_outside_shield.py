"""Phase B passive CI guard — no direct LLM provider calls survive
outside `services/synisense/shield/`.

Background
==========
The Phase B brief established a structural-privacy invariant: every
LLM provider SDK call goes through `services.synisense.shield.client`
(consumer-facing) → `services.synisense.shield.llm_router` (the
single chokepoint that actually holds provider credentials). Anything
else is a regression that leaks raw consumer content past the de-id
pipeline.

This test enforces the invariant by greppping the backend tree for
patterns that indicate a direct LLM call. It deliberately runs at
test-collection time so a PR that smuggles a direct call back in
fails CI loudly, naming the violating file:line.

Exempt regions
==============
- `services/synisense/shield/`  — the chokepoint itself.
- `tests/`                       — tests legitimately need to
                                   monkeypatch / mock providers.
- `routers/billing.py`          — uses `emergentintegrations.payments`
                                   (Stripe SDK), not LLM.
- `scripts/`                    — bootstrap utilities; LLM key is
                                   listed in required-env-vars only.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Tuple

BACKEND = Path(__file__).resolve().parents[1]

# Files / directories the guard intentionally ignores.
ALLOWED_PREFIXES = (
    str(BACKEND / "services" / "synisense" / "shield") + os.sep,
    str(BACKEND / "tests") + os.sep,
    str(BACKEND / "scripts") + os.sep,
)
ALLOWED_FILES = {
    str(BACKEND / "routers" / "billing.py"),
}

# Forbidden patterns.
#
# We use ASCII anchors that match the syntactic shape, not bare
# substrings, so a comment that says "we used to call LlmChat
# directly" does not trip the guard. The CONFIG patterns target the
# specific provider SDK constructors / module attributes.
FORBIDDEN_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("emergentintegrations.llm import",
     re.compile(r"(?:^|\W)(?:from|import)\s+emergentintegrations\.llm\b")),
    ("LlmChat(",
     re.compile(r"(?:^|\W)LlmChat\s*\(")),
    ("UserMessage(",
     re.compile(r"(?:^|\W)UserMessage\s*\(")),
    ("openai.ChatCompletion / .chat / .completions",
     re.compile(r"(?:^|\W)openai\.(?:ChatCompletion|chat|completions)\b")),
    ("anthropic.Anthropic( / .messages",
     re.compile(r"(?:^|\W)anthropic\.(?:Anthropic\s*\(|messages\b)")),
    ("genai.GenerativeModel",
     re.compile(r"(?:^|\W)genai\.GenerativeModel\b")),
    ("google.generativeai import",
     re.compile(r"(?:^|\W)(?:from|import)\s+google\.generativeai\b")),
    ("litellm.completion",
     re.compile(r"(?:^|\W)litellm\.(?:completion|acompletion)\b")),
    ("EMERGENT_LLM_KEY env read",
     re.compile(r"""(?:^|\W)os\.environ(?:\.get)?\(['"]EMERGENT_LLM_KEY['"]""")),
    ("EMERGENT_LLM_KEY subscript read",
     re.compile(r"""(?:^|\W)os\.environ\[['"]EMERGENT_LLM_KEY['"]\]""")),
]


def _iter_python_files() -> List[Path]:
    out: List[Path] = []
    for p in BACKEND.rglob("*.py"):
        sp = str(p)
        if any(sp.startswith(pfx) for pfx in ALLOWED_PREFIXES):
            continue
        if sp in ALLOWED_FILES:
            continue
        out.append(p)
    return out


def test_no_direct_llm_calls_outside_shield():
    """Fails with a per-violation report so PRs know exactly what to fix."""
    violations: List[str] = []
    for path in _iter_python_files():
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            # Skip docstring/comment lines — they are not executable.
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            for label, pat in FORBIDDEN_PATTERNS:
                if pat.search(line):
                    # Final defence: lines INSIDE a docstring also slip
                    # the comment check above. We use a cheap heuristic
                    # by stripping triple-quoted regions per file.
                    if _line_in_docstring(text, line_no):
                        continue
                    rel = path.relative_to(BACKEND)
                    violations.append(
                        f"{rel}:{line_no}  [{label}]  {line.strip()[:140]}"
                    )

    assert not violations, (
        "Phase B invariant breach — direct LLM provider call outside "
        "services/synisense/shield/. All LLM calls MUST route through "
        "`services.synisense.shield.client.invoke(...)`. "
        f"\n\n{len(violations)} violation(s):\n  " + "\n  ".join(violations)
    )


_TRIPLE = re.compile(r'("""|\'\'\')')


def _line_in_docstring(text: str, line_no: int) -> bool:
    """True iff `line_no` (1-indexed) falls inside a triple-quoted
    string region. Lightweight — counts triple-quote openings up to
    the line and returns parity."""
    lines = text.splitlines()
    upto = "\n".join(lines[: line_no - 1])
    return (len(_TRIPLE.findall(upto)) % 2) == 1
