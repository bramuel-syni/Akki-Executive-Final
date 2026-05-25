"""Chunk (c.1) closeout — zero-Stripe-SDK invariant test.

e1_tester (c.1)(c) FAIL diagnosis:
    `backend/services/stripe_webhook.py::verify_and_parse_event`
    contained a lazy `import stripe`. No runtime caller (the
    Coming-Soon webhook stub in `routers/billing.py` dead-letters
    directly), but the source line tripped the strict zero-Stripe-
    SDK invariant grep audit.

Fix: deleted `verify_and_parse_event` + its `SignatureInvalid`
companion exception. The Mongo-side plumbing (`is_replay`,
`record_event`, `ensure_indexes`, `dead_letter`, `configured`)
remains because none of it loads the Stripe SDK.

This test pins the invariant: any future "lazy import stripe"
smuggled back into `backend/routers/` or `backend/services/`
breaks the test. Matches the exact grep used by the e1_tester at
the (c.1)(c) audit.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCOPE_DIRS = [
    REPO / "backend/routers",
    REPO / "backend/services",
]
# Exclude __pycache__ + this test file itself + the chunk-c
# regression test family (they contain the forbidden literals as
# documentary strings, not as live imports).
EXCLUDE_FILE_PATTERNS = (
    "__pycache__",
    "test_chunk_c_no_stripe_sdk_import.py",
)


def test_chunk_c_no_stripe_sdk_import_in_backend_routers_or_services():
    """Zero-Stripe-SDK invariant. ``import stripe`` / ``from stripe
    import …`` / ``emergentintegrations.payments.stripe`` MUST NOT
    appear anywhere under ``backend/routers/`` or
    ``backend/services/``. Documentary strings inside docstrings
    are filtered by ignoring this test file's own path."""
    # Use grep directly — mirrors the exact pattern the e1_tester
    # ran at the (c.1)(c) audit. -rn returns 1 (no match) → empty
    # stdout. We pin to the same scope they audited.
    cmd = [
        "grep", "-rn",
        "--include=*.py",
        "-E", r"import stripe|from stripe|emergentintegrations\.payments\.stripe",
        str(SCOPE_DIRS[0]),
        str(SCOPE_DIRS[1]),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    # grep exit code 1 = no matches (good), 0 = matches found (bad).
    hits = [
        line for line in proc.stdout.splitlines()
        if not any(p in line for p in EXCLUDE_FILE_PATTERNS)
    ]
    assert not hits, (
        f"Zero-Stripe-SDK invariant violated. Found {len(hits)} hit(s):\n"
        + "\n".join(hits)
        + "\n\nChunk (c) Coming-Soon contract requires zero Stripe "
          "SDK references anywhere under backend/routers/ or "
          "backend/services/. If a hit appears here in the future, "
          "delete the offending import — the webhook stub in "
          "routers/billing.py dead-letters directly without "
          "needing the Stripe SDK."
    )


def test_chunk_c_stripe_webhook_helpers_have_no_stripe_sdk_load():
    """Targeted check on `services/stripe_webhook.py` — the file
    that held the dead `verify_and_parse_event` function. The
    helpers that remain (`is_replay`, `record_event`,
    `ensure_indexes`, `dead_letter`, `configured`) MUST not load
    the Stripe SDK."""
    src = (REPO / "backend/services/stripe_webhook.py").read_text(encoding="utf-8")
    # Strip docstrings so documentary references don't trip us.
    no_docstrings = re.sub(r'"""[\s\S]*?"""', "", src)
    forbidden = [
        r"\bimport\s+stripe\b",
        r"\bfrom\s+stripe\s+import\b",
        r"emergentintegrations\.payments\.stripe",
    ]
    for pat in forbidden:
        m = re.search(pat, no_docstrings)
        assert m is None, (
            f"Forbidden Stripe SDK load matched in "
            f"`services/stripe_webhook.py` (pattern {pat!r}): "
            f"line context {m.group(0)!r}."
        )
    # Anti-regression — deleted symbols must stay deleted.
    assert "def verify_and_parse_event(" not in src, (
        "`verify_and_parse_event` re-appeared. Chunk (c.1)(c) "
        "audit will FAIL again."
    )
    assert "class SignatureInvalid" not in src, (
        "`SignatureInvalid` exception re-appeared. Chunk (c.1)(c) "
        "audit will FAIL again."
    )
