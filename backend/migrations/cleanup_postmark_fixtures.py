"""P-Cleanup A — Cohort A.5 Postmark fixture cleanup.

The Postmark wire is retired (cohort_email.py:228-230 stub, plus the
410 Gone returns on `/api/inbound/postmark` and the back-compat
`/api/webhooks/postmark/inbound` route — see
`backend/services/sprints/P5_8_4_postmark_winddown.md`). This one-shot
migration removes the 453 leftover pytest fixture rows in
`admin_inbox_messages` that still carry `provider="postmark"`.

DISCLAIMER (Honesty Protocol):

Only the legacy `provider="postmark"` rows are deleted. The internal
inbound pipeline (`routers/inbound_email.py:212+`) still references
"Postmark-shape dict" in its comments — that's the historical name of
the canonical internal payload format. The runtime code is alive
and is the BACKBONE of the SendGrid adapter, which normalises its
multipart form to the same shape. This script does NOT touch the
runtime code.

Run idempotently:

    python3 /app/backend/migrations/cleanup_postmark_fixtures.py

Re-running shows `deleted=0`.
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

from core import db  # noqa: E402


async def main() -> int:
    before = await db.admin_inbox_messages.count_documents({"provider": "postmark"})
    total_before = await db.admin_inbox_messages.count_documents({})
    print(f"BEFORE: provider=postmark={before} total={total_before}")

    res = await db.admin_inbox_messages.delete_many({"provider": "postmark"})
    deleted = res.deleted_count

    after = await db.admin_inbox_messages.count_documents({"provider": "postmark"})
    total_after = await db.admin_inbox_messages.count_documents({})
    print(f"AFTER:  provider=postmark={after} total={total_after}  deleted={deleted}")

    if after != 0:
        print("FAIL: rows remaining after delete — non-idempotent.")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
