"""C19-001 (Chunk 19, 2026-05-21) — Sample Trust Receipt HMAC verifier.

Bank-QA reviewer companion script. Takes a saved trust-receipt JSON +
the platform's public verification key and confirms the HMAC-SHA256
chain matches. Stays standalone so reviewers can run it without
installing the rest of the AKKI stack — only stdlib + a single env
var or argument for the secret.

Why this exists
===============
Trust receipts are AKKI's primary export-of-trust artefact for
governance reviews. A bank-QA assessor needs a 30-second way to
verify the receipt JSON they were sent really came from AKKI and
wasn't tampered with downstream. This is that script.

Usage
=====
    # Verify a receipt file:
    python verify_trust_receipt.py /path/to/receipt.json \
        --secret-file /path/to/synisense_master_secret.txt

    # Or via env var (no shell history leak of the secret):
    SYNISENSE_MASTER_SECRET=... python verify_trust_receipt.py receipt.json

    # Verify the included sample (always passes — round-trips against
    # a documented test secret):
    python verify_trust_receipt.py --self-test

Exit codes
==========
    0 — receipt valid (HMAC chain matches, no tampering detected).
    1 — receipt invalid (HMAC mismatch or structural failure).
    2 — usage error (missing receipt file, missing secret, etc).

This script has NO third-party dependencies. Stdlib only. Should run
on any Python 3.8+.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from typing import Any, Dict, Tuple


# Canonical-JSON serialisation rules for the request_hash + response_hash
# fields. MUST match what `services/synisense/shield/trust_receipt.py`
# does on the server.
def _hash_payload(payload: Any) -> str:
    if isinstance(payload, str):
        body = payload
    else:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _expected_signature(receipt: Dict[str, Any], secret: str) -> str:
    """Recompute the HMAC the server would have written into the
    `signature` field. The signed-payload shape is locked — adding
    new fields without touching this function is a CONTRACT change.
    """
    signed_fields = (
        "audit_id",
        "tenant_id",
        "consumer_id",
        "purpose",
        "timestamp",
        "request_hash",
        "response_hash",
        "outcome",
        "llm_provider",
        "llm_model",
    )
    canonical = "|".join(
        f"{k}={receipt.get(k, '')}" for k in signed_fields
    )
    return "hmac-sha256:" + hmac.new(
        secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify(receipt: Dict[str, Any], secret: str) -> Tuple[bool, str]:
    """Return (ok, reason)."""
    missing = [k for k in ("audit_id", "tenant_id", "signature") if not receipt.get(k)]
    if missing:
        return (False, f"receipt missing required fields: {missing}")
    expected = _expected_signature(receipt, secret)
    actual = receipt.get("signature", "")
    if not hmac.compare_digest(expected, actual):
        return (False, "HMAC signature mismatch — receipt has been tampered with or the secret is wrong")
    return (True, "OK — signature verified against the supplied secret")


# ─── Self-test fixture ──────────────────────────────────────────────
# A canned receipt + its matching secret so reviewers can run the
# script end-to-end before they trust it with a real receipt. The
# secret here is intentionally meaningless; the real platform's
# `SYNISENSE_MASTER_SECRET` lives in `backend/.env` on production.
SAMPLE_RECEIPT = {
    "audit_id": "aud-c19-sample-deadbeef",
    "tenant_id": "tnt-c19-sample",
    "consumer_id": "test",
    "purpose": "test.echo",
    "timestamp": "2026-05-21T19:30:00+00:00",
    "request_hash": "sha256:" + hashlib.sha256(b"hello").hexdigest(),
    "response_hash": "sha256:" + hashlib.sha256(b"world").hexdigest(),
    "outcome": "success",
    "llm_provider": "anthropic",
    "llm_model": "claude-sonnet-4-5-20250929",
    # signature filled in at runtime so the constant doesn't go stale
    # if the canonical shape changes.
}
SAMPLE_SECRET = "DOCS_ONLY_NOT_A_REAL_SECRET_REVIEWER_SAMPLE"


def _self_test() -> int:
    receipt = dict(SAMPLE_RECEIPT)
    receipt["signature"] = _expected_signature(receipt, SAMPLE_SECRET)
    ok, reason = verify(receipt, SAMPLE_SECRET)
    print(json.dumps({"ok": ok, "reason": reason}, indent=2))
    # Negative-case sanity check.
    bad_secret = SAMPLE_SECRET + "_TAMPERED"
    ok2, reason2 = verify(receipt, bad_secret)
    if (not ok) or ok2:
        print("SELF-TEST FAILED — verifier didn't pass the matching secret or accepted a bad one.")
        return 1
    print("self-test PASS — verifier accepts matching secret + rejects mismatched secret.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt_file", nargs="?",
                        help="path to a saved trust-receipt JSON")
    parser.add_argument("--secret-file",
                        help="path to a file containing the master secret (preferred over env)")
    parser.add_argument("--self-test", action="store_true",
                        help="run the bundled self-test fixture; no receipt file needed")
    args = parser.parse_args()

    if args.self_test:
        return _self_test()

    if not args.receipt_file:
        parser.error("receipt_file is required (or pass --self-test)")
        return 2

    if args.secret_file:
        with open(args.secret_file, "r", encoding="utf-8") as f:
            secret = f.read().strip()
    else:
        secret = os.environ.get("SYNISENSE_MASTER_SECRET", "").strip()
    if not secret:
        print(json.dumps({
            "ok": False,
            "reason": "no secret supplied — use --secret-file or set SYNISENSE_MASTER_SECRET",
        }, indent=2))
        return 2

    try:
        with open(args.receipt_file, "r", encoding="utf-8") as f:
            receipt = json.load(f)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "reason": f"could not read receipt: {exc}"}, indent=2))
        return 2

    ok, reason = verify(receipt, secret)
    print(json.dumps({"ok": ok, "reason": reason}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
