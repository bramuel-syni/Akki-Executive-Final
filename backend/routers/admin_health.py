"""Admin diagnostics — `/api/admin/health/full`.

A one-shot concurrent ping of every external dependency the app
relies on. Returns a per-service PASS / FAIL / DEGRADED with a small
piece of corroborating evidence per check, so deploys and demos can
be greenlit (or held) on a single page.

Restricted to platform superadmins (`accounts.is_superadmin == true`).
The `admin@akki.ai` seed account carries that flag by default.

Checks (all run in parallel via asyncio.gather):
    mongo     · ping + a writable round-trip on a noop collection
    llm       · 1-token Emergent LLM call (cheapest model)
    resend    · API-key shape check (no email actually sent)
    stripe    · /v1/balance call (read-only, no charge)
    apsched   · scheduler is running + jobs registered
    cron_secret · presence + length sanity check
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request

from core import db, get_current_account, now as _now, iso as _iso

router = APIRouter(prefix="/api")


def _require_superadmin(current: Dict[str, Any] = Depends(get_current_account)) -> Dict[str, Any]:
    if not current.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin required")
    return current


# ─────────────────────────────────────────────────────────────────────
# Individual checks — each returns a dict with the canonical shape.
# ─────────────────────────────────────────────────────────────────────
def _result(status: str, **kw: Any) -> Dict[str, Any]:
    """status ∈ {'pass', 'warn', 'fail', 'skip'}."""
    return {"status": status, **kw}


async def _check_mongo() -> Dict[str, Any]:
    started = time.monotonic()
    try:
        await db.command("ping")
        col = db.health_check
        rid = f"hc-{int(time.time() * 1000)}"
        await col.insert_one({"id": rid, "at": _iso(_now())})
        await col.delete_one({"id": rid})
        return _result(
            "pass", latency_ms=int((time.monotonic() - started) * 1000),
            evidence="ping + insert/delete round-trip",
        )
    except Exception as e:
        return _result("fail", error=f"{type(e).__name__}: {e}")


async def _check_llm() -> Dict[str, Any]:
    """A 1-token Emergent LLM ping via Synisense Shield (Phase B —
    migrated 2026-05-13). Uses `purpose="health.ping"`; Shield routes
    to the balanced provider (Gemini flash by default) for cost."""
    started = time.monotonic()
    try:
        from services.synisense.shield.client import invoke as shield_invoke
        result = await asyncio.wait_for(
            shield_invoke(
                purpose="health.ping",
                content="ping",
                tenant_id="system.health.probe",
                consumer_id="admin_health",
                user_id="system.health.probe",
                model_preference="balanced",
                internal_caller=True,
            ),
            timeout=15,
        )
        text = (result.get("response") or "").strip()
        return _result(
            "pass" if text else "warn",
            latency_ms=int((time.monotonic() - started) * 1000),
            evidence=f"{text[:60]!r}",
            audit_id=result.get("audit_id"),
            model=result.get("trust_receipt", {}).get("llm_model"),
        )
    except asyncio.TimeoutError:
        return _result("fail", error="timed out after 15s")
    except Exception as e:
        return _result("fail", error=f"{type(e).__name__}: {str(e)[:200]}")


async def _check_resend() -> Dict[str, Any]:
    """Verify the API key shape + sender domain config; do NOT send."""
    key = os.environ.get("RESEND_API_KEY", "")
    sender = os.environ.get("RESEND_FROM") or os.environ.get("RESEND_FROM_EMAIL", "")
    if not key:
        return _result("fail", error="RESEND_API_KEY missing")
    if not key.startswith("re_"):
        return _result("warn", error="key shape unexpected (no 're_' prefix)")
    if not sender:
        return _result(
            "warn", error="No sender configured — set RESEND_FROM_EMAIL",
            sandbox=True,
        )
    if "onboarding@resend.dev" in sender or "resend.dev" in sender:
        return _result(
            "warn", evidence=sender,
            note="sandbox sender — can only deliver to verified address. "
                 "Verify a domain at resend.com/domains before launch.",
            sandbox=True,
        )
    return _result("pass", evidence=f"sender={sender}")


async def _check_stripe() -> Dict[str, Any]:
    """Read-only balance probe."""
    key = os.environ.get("STRIPE_API_KEY", "")
    if not key:
        return _result("skip", note="STRIPE_API_KEY not set")
    started = time.monotonic()
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as ac:
            r = await ac.get(
                "https://api.stripe.com/v1/balance",
                headers={"Authorization": f"Bearer {key}"},
            )
        if r.status_code != 200:
            return _result("fail", status_code=r.status_code,
                           error=(r.json().get("error", {}).get("message") if r.headers.get("content-type", "").startswith("application/") else r.text[:200]))
        live = not key.startswith("sk_test_")
        return _result(
            "pass" if live else "warn",
            latency_ms=int((time.monotonic() - started) * 1000),
            mode="live" if live else "test",
            note="test-mode key — swap for live before launch" if not live else None,
        )
    except Exception as e:
        return _result("fail", error=f"{type(e).__name__}: {str(e)[:200]}")


async def _check_scheduler(req: Request) -> Dict[str, Any]:
    """Pull the scheduler off app.state and confirm it's running with the
    jobs we expect."""
    sched = getattr(req.app.state, "scheduler", None)
    if sched is None:
        return _result("warn", note="scheduler not initialised")
    if not sched.running:
        return _result("fail", error="scheduler stopped")
    jobs = [{"id": j.id,
             "next_run_time": j.next_run_time.isoformat() if j.next_run_time else None}
            for j in sched.get_jobs()]
    if not jobs:
        return _result("warn", note="no jobs registered")
    return _result("pass", jobs=jobs)


def _check_cron_secret() -> Dict[str, Any]:
    sec = os.environ.get("AKKI_CRON_SECRET", "")
    if not sec:
        return _result("warn", note="AKKI_CRON_SECRET not set — cron endpoints inaccessible")
    if len(sec) < 16:
        return _result("warn", note="AKKI_CRON_SECRET shorter than 16 chars")
    return _result("pass", evidence=f"len={len(sec)}")


# ─────────────────────────────────────────────────────────────────────
# Endpoint
# ─────────────────────────────────────────────────────────────────────
@router.get("/admin/health/full")
async def admin_health_full(
    request: Request,
    _: Dict[str, Any] = Depends(_require_superadmin),
):
    started = time.monotonic()
    mongo, llm, resend_, stripe_ = await asyncio.gather(
        _check_mongo(), _check_llm(), _check_resend(), _check_stripe(),
        return_exceptions=False,
    )
    sched = await _check_scheduler(request)
    cron = _check_cron_secret()

    checks = {
        "mongo": mongo, "llm": llm, "resend": resend_, "stripe": stripe_,
        "scheduler": sched, "cron_secret": cron,
    }
    statuses: List[str] = [c["status"] for c in checks.values()]
    overall = (
        "fail" if "fail" in statuses
        else "warn" if "warn" in statuses
        else "pass"
    )
    return {
        "overall": overall,
        "checks": checks,
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "checked_at": _iso(_now()),
        "env": {
            "frontend_origin": os.environ.get("FRONTEND_ORIGIN") or None,
            "node": os.environ.get("HOSTNAME") or "unknown",
        },
    }
