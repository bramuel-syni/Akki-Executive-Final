"""H4 — CLI wrapper for Shield v1.x back-fill.

Invoke::

    python -m scripts.backfill_shield_v1 --batch-size 50 --sleep-ms 200
    python -m scripts.backfill_shield_v1 --dry-run --limit 10

Or directly::

    python /app/backend/scripts/backfill_shield_v1.py --batch-size 50

The admin endpoint ``POST /api/admin/shield/backfill`` runs the same
function — use the CLI for ops staging, the admin endpoint for
self-serve.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import os

# Ensure /app/backend is importable when invoked as a plain script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from services.backfill_shield_v1 import (  # noqa: E402
    run_backfill, DEFAULT_BATCH_SIZE, DEFAULT_SLEEP_MS,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Back-fill pre-Shield-v1.x chats through the "
                    "current Shield deidentifier.",
    )
    parser.add_argument(
        "--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
        help=f"Chats per batch (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--sleep-ms", type=int, default=DEFAULT_SLEEP_MS,
        help=f"Sleep between batches in ms (default: {DEFAULT_SLEEP_MS})",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview without writing any audit rows.",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Process at most N candidate chats (safe staging).",
    )
    args = parser.parse_args()

    summary = asyncio.run(run_backfill(
        batch_size=args.batch_size,
        sleep_ms=args.sleep_ms,
        dry_run=args.dry_run,
        limit=args.limit,
    ))
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("errors_count", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
