"""Phase P2 D.2 (2026-02) — Hybrid status page composite probe.

GET /api/health/composite
  Returns aggregate up/down status for the dependencies the in-app
  /status page renders as coloured dots. Public (no auth) so the
  status page is reachable from a signed-out browser.

Probes:
  - mongo:           ping the cluster
  - llm_key:         is `EMERGENT_LLM_KEY` set (we don't burn quota)
  - sendgrid:        is `SENDGRID_API_KEY` set (we don't send mail)
  - oauth_google:    is `GOOGLE_OAUTH_CLIENT_ID` set
  - oauth_microsoft: is `MICROSOFT_OAUTH_CLIENT_ID` set
  - solva_engine:    can we instantiate the v2 deterministic engine

Each probe returns `{state: "ok" | "warn" | "fail", detail: "..."}`
where `warn` means "configured but not exercised this minute" and
`fail` is unrecoverable.

Cached 30s — re-running the Mongo ping on every page-load would
hammer the cluster.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Dict

from fastapi import APIRouter

from core import db


log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["health"])


_CACHE_TTL = 30.0  # seconds
_cache: Dict[str, Any] = {"at": 0.0, "data": None}
_lock = asyncio.Lock()


async def _probe_mongo() -> Dict[str, str]:
    try:
        await db.command("ping")
        return {"state": "ok", "detail": "Connected."}
    except Exception as e:  # noqa: BLE001
        return {"state": "fail", "detail": f"Ping failed: {str(e)[:120]}"}


def _probe_env(key: str, ok_msg: str, missing_msg: str) -> Dict[str, str]:
    val = (os.environ.get(key) or "").strip()
    if val:
        return {"state": "ok", "detail": ok_msg}
    return {"state": "warn", "detail": missing_msg}


def _probe_solva_engine() -> Dict[str, str]:
    try:
        # Light-touch import: confirms the module is loadable.
        import importlib
        importlib.import_module("services.solva_v2.feature_flag")
        return {"state": "ok", "detail": "Engine module loadable."}
    except Exception as e:  # noqa: BLE001
        return {"state": "fail", "detail": f"Engine import error: {str(e)[:120]}"}


def _overall(probes: Dict[str, Dict[str, str]]) -> str:
    states = {p["state"] for p in probes.values()}
    if "fail" in states:
        return "fail"
    if "warn" in states:
        return "warn"
    return "ok"


@router.get("/composite")
async def composite_health():
    """Public composite health probe. 30s cache."""
    now = time.time()
    async with _lock:
        if _cache["data"] and (now - _cache["at"]) < _CACHE_TTL:
            return _cache["data"]

        probes: Dict[str, Dict[str, str]] = {
            "mongo": await _probe_mongo(),
            "llm_key": _probe_env(
                "EMERGENT_LLM_KEY",
                "LLM key configured.",
                "LLM key not configured.",
            ),
            "sendgrid": _probe_env(
                "SENDGRID_API_KEY",
                "Email sending configured.",
                "Email sending not configured.",
            ),
            "oauth_google": _probe_env(
                "GOOGLE_OAUTH_CLIENT_ID",
                "Google sign-in configured.",
                "Google sign-in not configured.",
            ),
            "oauth_microsoft": _probe_env(
                "MICROSOFT_OAUTH_CLIENT_ID",
                "Microsoft sign-in configured.",
                "Microsoft sign-in not configured.",
            ),
            "solva_engine": _probe_solva_engine(),
        }

        data = {
            "overall": _overall(probes),
            "probes": probes,
            "checked_at": now,
            "cache_ttl_seconds": int(_CACHE_TTL),
        }
        _cache["at"] = now
        _cache["data"] = data
        return data
