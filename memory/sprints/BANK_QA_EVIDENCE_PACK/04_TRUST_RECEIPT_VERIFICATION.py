#!/usr/bin/env python3
"""Standalone Synisense Trust Receipt verifier.

No Akki dependencies. Pure Python standard library.

USAGE
-----
    python 04_TRUST_RECEIPT_VERIFICATION.py receipt.json \\
        --tenant-key <hex-encoded HMAC key> \\
        [--audit-body audit_body.json]

receipt.json should look like:
    {
        "receipt_id": "rec-…",
        "audit_id":   "aud-…",
        "tenant_id":  "acc-…",
        "version":    "v1",
        "signature":  "<hex>",
        "payload_hash": "sha256:<hex>"
    }

The script:
    1. Canonicalises the audit body (or the receipt itself minus the
       `signature` field if --audit-body is omitted) per the same
       JSON-canonical-form Akki uses.
    2. Recomputes HMAC-SHA256 with the supplied tenant key.
    3. Prints PASS if the recomputed signature matches the receipt's
       `signature` field; FAIL otherwise.

The per-tenant key is derived in Akki via:
    HKDF-SHA256(master_secret=SYNISENSE_MASTER_SECRET, info=tenant_id)
This script does NOT do the HKDF derivation — you supply the
already-derived per-tenant HMAC key directly. (Bank admins can export
the derived per-tenant key from the Synisense admin console.)

EXIT CODES
----------
    0 — verification PASSED
    1 — verification FAILED (signature mismatch, tampered chain)
    2 — input error (bad JSON, missing key, etc.)
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
from pathlib import Path


def canonicalise(payload: dict) -> bytes:
    """JSON-canonical form: keys sorted lexicographically, no whitespace,
    no trailing newline. Matches Akki's `trust_receipt._canonicalise`."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def verify(receipt: dict, tenant_key_hex: str, audit_body: dict | None = None) -> tuple[bool, str]:
    """Return (passed, message). Side-effect-free."""
    sig_actual = receipt.get("signature")
    if not sig_actual or not isinstance(sig_actual, str):
        return False, "receipt is missing the `signature` field"
    if not tenant_key_hex:
        return False, "tenant_key is empty"
    try:
        tenant_key = bytes.fromhex(tenant_key_hex)
    except ValueError as e:
        return False, f"tenant_key is not valid hex: {e}"

    # Body the receipt was signed over. If --audit-body is supplied, use
    # it as the canonical body. Otherwise the receipt itself (with the
    # `signature` field stripped) is the body.
    if audit_body is not None:
        body = audit_body
    else:
        body = {k: v for k, v in receipt.items() if k != "signature"}

    canonical = canonicalise(body)
    sig_expected = hmac.new(tenant_key, canonical, hashlib.sha256).hexdigest()
    passed = hmac.compare_digest(sig_actual, sig_expected)
    return (
        passed,
        f"expected_sig={sig_expected}\n"
        f"actual_sig  ={sig_actual}\n"
        f"canonical_payload (first 200 bytes): {canonical[:200]!r}",
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Verify a Synisense Trust Receipt against a per-tenant HMAC key.",
    )
    p.add_argument("receipt", help="Path to receipt JSON")
    p.add_argument("--tenant-key", required=True,
                   help="Per-tenant HMAC key in hex (export from Synisense admin)")
    p.add_argument("--audit-body", default=None,
                   help="Optional: path to the canonical audit body JSON. "
                        "If omitted, the receipt itself (minus signature) is treated as the body.")
    args = p.parse_args(argv)

    try:
        receipt = json.loads(Path(args.receipt).read_text())
    except Exception as e:
        print(f"ERROR: failed to read receipt JSON: {e}", file=sys.stderr)
        return 2
    body = None
    if args.audit_body:
        try:
            body = json.loads(Path(args.audit_body).read_text())
        except Exception as e:
            print(f"ERROR: failed to read audit-body JSON: {e}", file=sys.stderr)
            return 2

    passed, msg = verify(receipt, args.tenant_key, audit_body=body)
    print(msg)
    print()
    if passed:
        print("✅ PASS — trust receipt signature matches; chain is intact.")
        return 0
    print("❌ FAIL — signature mismatch. The audit chain has been tampered with,")
    print("          the supplied tenant key is wrong, or the audit body has been")
    print("          modified after signing.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
