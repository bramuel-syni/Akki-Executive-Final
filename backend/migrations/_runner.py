"""Migration runner. Imports and runs each migration module in order,
each gated by its own marker in `db._migrations`."""
from __future__ import annotations

import logging

from . import _0001_multi_cycle as _m0001

logger = logging.getLogger("akki.migrations.runner")


async def run_all() -> None:
    try:
        res = await _m0001.run()
        if res.get("applied"):
            logger.info("migration 0001_multi_cycle: %s", res.get("stats"))
    except Exception as exc:  # noqa: BLE001
        logger.exception("migration 0001_multi_cycle FAILED: %s", exc)
