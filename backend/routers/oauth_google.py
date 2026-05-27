"""Phase I.4.c (2026-05-27) — Google Calendar OAuth + sync.

Flow:
  1. `GET /api/oauth/google/connect?context_id={cid}` — returns
     `{authorize_url}`. Frontend redirects user there.
  2. User grants consent on Google's screen.
  3. Google redirects back to `GET /api/oauth/google/callback?code&state`.
     We exchange the code for tokens, encrypt + persist them in
     `db.user_calendar_credentials`, then HTTP-302 the user back to
     `/app/events?context_id={cid}&calendar_connected=google`.
  4. Frontend detects the `calendar_connected=google` query param and
     fires `POST /api/contexts/{cid}/events/sync-calendar?provider=google`
     once, then strips the param from the URL.
  5. Subsequent syncs go through `POST .../sync-calendar`.
  6. Disconnect via `POST /api/contexts/{cid}/oauth/google/disconnect` —
     revokes Google's token and soft-deletes the credentials row.

Scopes (this phase, read-only):
  • `https://www.googleapis.com/auth/calendar.events.readonly`
  • `https://www.googleapis.com/auth/calendar.readonly`
  • `openid`, `email`, `profile` (added automatically by Google).

Future (write-back) — bumps scope to `.events` (read+write). Out-of-scope.

Microsoft Graph (Outlook) lands as a sibling `routers/oauth_microsoft.py`
when credentials arrive — same `user_calendar_credentials.provider` enum.
"""
from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from core import db, get_current_account, JWT_SECRET
from services.crypto import token_vault


log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["oauth_google"])

# OAuth config
_GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"

_GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
    "openid",
    "email",
    "profile",
]

_STATE_TTL_SECONDS = 10 * 60  # 10 minutes


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _client_id() -> str:
    cid = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    if not cid:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth not configured (GOOGLE_OAUTH_CLIENT_ID missing).",
        )
    return cid


def _client_secret() -> str:
    cs = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    if not cs:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth not configured (GOOGLE_OAUTH_CLIENT_SECRET missing).",
        )
    return cs


def _redirect_uri() -> str:
    ru = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI", "").strip()
    if not ru:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth not configured (GOOGLE_OAUTH_REDIRECT_URI missing).",
        )
    return ru


def _sign_state(payload: Dict[str, Any]) -> str:
    """JWT-sign the OAuth state token. Reuses the app-wide JWT_SECRET so we
    don't introduce a new key story."""
    body = {**payload, "exp": int(_now().timestamp()) + _STATE_TTL_SECONDS}
    return jwt.encode(body, JWT_SECRET, algorithm="HS256")


def _verify_state(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid state token: {e}") from e


async def _assert_member(account_id: str, context_id: str) -> None:
    m = await db.memberships.find_one(
        {"account_id": account_id, "context_id": context_id, "status": "active"},
        {"_id": 0, "role": 1},
    )
    if not m:
        raise HTTPException(status_code=403, detail="Not a member of this context")


# -----------------------------------------------------------------------------
# OAuth flow endpoints
# -----------------------------------------------------------------------------

class ConnectOut(BaseModel):
    authorize_url: str


@router.get("/oauth/google/connect", response_model=ConnectOut)
async def oauth_google_connect(
    context_id: str = Query(...),
    me: Dict[str, Any] = Depends(get_current_account),
) -> ConnectOut:
    """Stage-1 of the OAuth dance — returns the Google consent URL. The
    frontend redirects the user there; Google bounces back to the
    callback endpoint below."""
    await _assert_member(me["id"], context_id)
    state = _sign_state({
        "account_id": me["id"], "context_id": context_id,
        "nonce": uuid.uuid4().hex,
    })
    # google-auth-oauthlib's Flow could build this; but the URL is simple
    # enough that hand-building keeps the dep surface tiny.
    from urllib.parse import urlencode
    qs = urlencode({
        "response_type": "code",
        "client_id": _client_id(),
        "redirect_uri": _redirect_uri(),
        "scope": " ".join(_GOOGLE_SCOPES),
        "access_type": "offline",        # request refresh_token
        "prompt": "consent",             # force consent screen so refresh_token is always returned
        "state": state,
        "include_granted_scopes": "true",
    })
    return ConnectOut(authorize_url=f"{_GOOGLE_AUTHORIZE_URL}?{qs}")


@router.get("/oauth/google/callback")
async def oauth_google_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
) -> RedirectResponse:
    """Stage-2 of the OAuth dance — Google redirected back. We exchange
    the auth code for tokens, persist them encrypted, then HTTP-302 the
    user to the Events page with a success flag."""
    if error:
        log.info("[oauth.google] callback got error=%s", error)
        # Bounce user to events surface with the error flag so the UI
        # can render a clear "connection failed" toast.
        return RedirectResponse(
            url=f"/app/events?calendar_error={error}",
            status_code=302,
        )
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code/state")
    payload = _verify_state(state)
    account_id = payload.get("account_id")
    context_id = payload.get("context_id")
    if not account_id or not context_id:
        raise HTTPException(status_code=400, detail="State token missing identity")

    # Code → tokens exchange.
    import httpx
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(_GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "redirect_uri": _redirect_uri(),
            "grant_type": "authorization_code",
        })
    if r.status_code != 200:
        log.warning("[oauth.google] token exchange failed: %s %s", r.status_code, r.text[:200])
        return RedirectResponse(
            url=f"/app/events?context_id={context_id}&calendar_error=token_exchange_failed",
            status_code=302,
        )
    tokens = r.json()
    access_token = tokens.get("access_token") or ""
    refresh_token = tokens.get("refresh_token") or ""
    expires_in = int(tokens.get("expires_in") or 3600)
    scope = tokens.get("scope") or " ".join(_GOOGLE_SCOPES)

    if not access_token:
        return RedirectResponse(
            url=f"/app/events?context_id={context_id}&calendar_error=no_access_token",
            status_code=302,
        )

    now = _now()
    expires_at = _iso(now + timedelta(seconds=expires_in - 60))   # 1-min safety margin

    rec = {
        "id": str(uuid.uuid4()),
        "user_id": account_id,
        "context_id": context_id,
        "provider": "google",
        "access_token_encrypted": token_vault.encrypt(access_token),
        "refresh_token_encrypted": token_vault.encrypt(refresh_token) if refresh_token else None,
        "expires_at": expires_at,
        "scope": scope,
        "calendar_id": "primary",
        "connected_at": _iso(now),
        "last_sync_at": None,
        "last_sync_status": "ok",
        "last_sync_error": None,
        "deleted_at": None,
    }
    # Upsert on (user_id, context_id, provider).
    await db.user_calendar_credentials.update_one(
        {"user_id": account_id, "context_id": context_id, "provider": "google"},
        {"$set": rec},
        upsert=True,
    )

    return RedirectResponse(
        url=f"/app/events?context_id={context_id}&calendar_connected=google",
        status_code=302,
    )


@router.post("/contexts/{cid}/oauth/google/disconnect")
async def oauth_google_disconnect(
    cid: str,
    me: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    """Soft-delete the credentials row + revoke the token at Google."""
    await _assert_member(me["id"], cid)
    cred = await db.user_calendar_credentials.find_one({
        "user_id": me["id"], "context_id": cid, "provider": "google",
        "deleted_at": None,
    }, {"_id": 0})
    if not cred:
        # Idempotent: nothing to do.
        return {"ok": True, "revoked": False, "note": "Not connected"}

    # Best-effort token revocation; don't fail the disconnect if Google is down.
    try:
        import httpx
        access_token = token_vault.decrypt(cred["access_token_encrypted"])
        async with httpx.AsyncClient(timeout=10) as c:
            await c.post(_GOOGLE_REVOKE_URL, params={"token": access_token})
    except Exception as e:
        log.info("[oauth.google] revoke best-effort failed: %s", e)

    await db.user_calendar_credentials.update_one(
        {"user_id": me["id"], "context_id": cid, "provider": "google"},
        {"$set": {"deleted_at": _iso(_now())}},
    )
    return {"ok": True, "revoked": True}


# -----------------------------------------------------------------------------
# Status (used by the frontend to render the connection banner)
# -----------------------------------------------------------------------------

class StatusOut(BaseModel):
    connected:      bool
    provider:       Optional[str]
    connected_at:   Optional[str]
    last_sync_at:   Optional[str]
    last_sync_status: Optional[str]
    last_sync_error: Optional[str]
    synced_count:   int


@router.get("/contexts/{cid}/oauth/calendar/status", response_model=StatusOut)
async def calendar_status(
    cid: str,
    me: Dict[str, Any] = Depends(get_current_account),
) -> StatusOut:
    """Aggregated status for the Events surface's connection banner.
    Currently only Google but the shape is provider-agnostic so a future
    Microsoft Graph leg lands without surface changes."""
    await _assert_member(me["id"], cid)
    cred = await db.user_calendar_credentials.find_one({
        "user_id": me["id"], "context_id": cid, "deleted_at": None,
    }, {"_id": 0})
    if not cred:
        return StatusOut(
            connected=False, provider=None, connected_at=None,
            last_sync_at=None, last_sync_status=None, last_sync_error=None,
            synced_count=0,
        )
    synced_count = await db.events.count_documents({
        "context_id": cid,
        "source": "calendar_sync",
        "source_ref": {"$ne": None},
        "deleted_at": None,
    })
    return StatusOut(
        connected=True,
        provider=cred.get("provider"),
        connected_at=cred.get("connected_at"),
        last_sync_at=cred.get("last_sync_at"),
        last_sync_status=cred.get("last_sync_status"),
        last_sync_error=cred.get("last_sync_error"),
        synced_count=synced_count,
    )


# -----------------------------------------------------------------------------
# Sync — pull Google Calendar events into db.events
# -----------------------------------------------------------------------------

class SyncOut(BaseModel):
    imported: int
    skipped:  int
    errors:   int


_TYPE_INFERENCE_RULES = [
    # ordered priority: first match wins. More-specific / more-actionable
    # keywords come FIRST so multi-keyword titles resolve to the
    # actionable type (e.g. "Pre-read deadline" → deadline, NOT briefing;
    # "Pre-board briefing" → briefing, NOT board_meeting).
    (re.compile(r"\b(deadline|due|submission|cut-?off)\b", re.IGNORECASE), "deadline"),
    (re.compile(r"\b(audit|audit committee)\b",            re.IGNORECASE), "audit_review"),
    (re.compile(r"\b(briefing|brief|pre-?read)\b",         re.IGNORECASE), "briefing"),
    (re.compile(r"\b(board|agm|annual general meeting)\b", re.IGNORECASE), "board_meeting"),
]


def _infer_type(title: str) -> str:
    """Title-keyword type inference. Default 'other'."""
    if not isinstance(title, str):
        return "other"
    for rx, t in _TYPE_INFERENCE_RULES:
        if rx.search(title):
            return t
    return "other"


def _map_google_event(ev: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map a Google Calendar event resource → events-schema row.
    Returns None for events we can't safely map (no start time, no id)."""
    eid = ev.get("id")
    if not eid:
        return None
    summary = (ev.get("summary") or "").strip()
    if not summary:
        summary = "(No title)"
    summary = summary[:200]

    start = ev.get("start") or {}
    end = ev.get("end") or {}

    def _coerce(d: Dict[str, Any]) -> Optional[str]:
        if d.get("dateTime"):
            try:
                dt = datetime.fromisoformat(str(d["dateTime"]).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.isoformat()
            except Exception:
                return None
        if d.get("date"):
            # All-day event: bracket to UTC midnight.
            try:
                ymd = d["date"]
                dt = datetime.fromisoformat(f"{ymd}T00:00:00+00:00")
                return dt.isoformat()
            except Exception:
                return None
        return None

    start_iso = _coerce(start)
    if not start_iso:
        return None
    end_iso = _coerce(end)

    location = (ev.get("location") or "")[:200].strip() or None
    notes = (ev.get("description") or "")[:2000].strip() or None

    return {
        "title":      summary,
        "type":       _infer_type(summary),
        "start_at":   start_iso,
        "end_at":     end_iso,
        "location":   location,
        "notes":      notes,
        "source_ref": eid,
    }


async def _refresh_access_token(cred: Dict[str, Any]) -> Optional[str]:
    """Use the refresh token to mint a new access token. Returns the new
    plaintext access token, or None if refresh fails. On failure, updates
    the credentials row with `last_sync_status='auth_expired'`."""
    if not cred.get("refresh_token_encrypted"):
        log.info("[oauth.google] no refresh token stored — re-consent required")
        await db.user_calendar_credentials.update_one(
            {"id": cred["id"]},
            {"$set": {"last_sync_status": "auth_expired",
                      "last_sync_error": "No refresh token; re-connect required"}},
        )
        return None
    refresh_token = token_vault.decrypt(cred["refresh_token_encrypted"])
    import httpx
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(_GOOGLE_TOKEN_URL, data={
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })
    if r.status_code != 200:
        log.warning("[oauth.google] refresh failed: %s %s", r.status_code, r.text[:200])
        await db.user_calendar_credentials.update_one(
            {"id": cred["id"]},
            {"$set": {"last_sync_status": "auth_expired",
                      "last_sync_error": f"Refresh failed: HTTP {r.status_code}"}},
        )
        return None
    tokens = r.json()
    new_access = tokens.get("access_token") or ""
    if not new_access:
        return None
    new_expires_in = int(tokens.get("expires_in") or 3600)
    await db.user_calendar_credentials.update_one(
        {"id": cred["id"]},
        {"$set": {
            "access_token_encrypted": token_vault.encrypt(new_access),
            "expires_at": _iso(_now() + timedelta(seconds=new_expires_in - 60)),
        }},
    )
    return new_access


async def _get_live_access_token(cred: Dict[str, Any]) -> Optional[str]:
    """Returns a usable access token, refreshing if expired. Returns None
    if refresh fails (caller should surface auth_expired)."""
    try:
        expires_at_str = cred.get("expires_at") or ""
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
            if expires_at > _now():
                return token_vault.decrypt(cred["access_token_encrypted"])
    except Exception:
        pass
    # Expired or unparseable → refresh.
    return await _refresh_access_token(cred)


@router.post(
    "/contexts/{cid}/events/sync-calendar",
    response_model=SyncOut,
)
async def sync_calendar(
    cid: str,
    provider: str = Query("google"),
    me: Dict[str, Any] = Depends(get_current_account),
) -> SyncOut:
    """Pull events from the connected calendar (Google this phase) and
    persist them in `db.events` as `source="calendar_sync"`. Idempotent:
    re-syncing replaces prior `calendar_sync` rows for matching
    `source_ref`. Manual + doc_extraction events are NEVER touched.

    Window: now → now+90d (wider than Card 5's 14d so the Events page
    Past/All tabs also see history)."""
    await _assert_member(me["id"], cid)
    if provider != "google":
        # Microsoft Graph leg lands here once creds arrive — sibling
        # `routers/oauth_microsoft.py` exposes the same shape and this
        # router will dispatch by provider string.
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    cred = await db.user_calendar_credentials.find_one({
        "user_id": me["id"], "context_id": cid, "provider": "google",
        "deleted_at": None,
    }, {"_id": 0})
    if not cred:
        raise HTTPException(
            status_code=400,
            detail="Google Calendar not connected for this context.",
        )

    access_token = await _get_live_access_token(cred)
    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="Google Calendar access expired. Reconnect required.",
        )

    # Pull window: now → now+90d.
    now = _now()
    horizon = now + timedelta(days=90)
    try:
        from google.oauth2.credentials import Credentials as GoogleCreds
        from googleapiclient.discovery import build as gb
        gcreds = GoogleCreds(token=access_token)
        service = gb("calendar", "v3", credentials=gcreds, cache_discovery=False)
        items: List[Dict[str, Any]] = []
        page_token = None
        while True:
            resp = service.events().list(
                calendarId=cred.get("calendar_id") or "primary",
                timeMin=_iso(now), timeMax=_iso(horizon),
                singleEvents=True, orderBy="startTime",
                maxResults=250, pageToken=page_token,
            ).execute()
            items.extend(resp.get("items") or [])
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
    except Exception as e:
        log.warning("[oauth.google] events.list failed: %s", e)
        await db.user_calendar_credentials.update_one(
            {"id": cred["id"]},
            {"$set": {
                "last_sync_status": "error",
                "last_sync_error": f"Calendar API: {str(e)[:200]}",
                "last_sync_at": _iso(now),
            }},
        )
        raise HTTPException(status_code=502, detail=f"Google Calendar API failure: {e}") from e

    # Idempotency (E4-style): wipe all prior `calendar_sync` rows for this
    # `(context_id, user_id)` before inserting. Manual + doc_extraction
    # events are untouched. We delete-and-reinsert (rather than upsert)
    # so cancelled-on-Google events naturally drop off too.
    await db.events.delete_many({
        "context_id": cid,
        "source": "calendar_sync",
        "created_by_account_id": me["id"],
        "deleted_at": None,
    })

    now_iso = _iso(now)
    imported = 0
    skipped = 0
    for ev in items:
        mapped = _map_google_event(ev)
        if not mapped:
            skipped += 1
            continue
        await db.events.insert_one({
            "id":         str(uuid.uuid4()),
            "context_id": cid,
            "title":      mapped["title"],
            "type":       mapped["type"],
            "start_at":   mapped["start_at"],
            "end_at":     mapped["end_at"],
            "location":   mapped["location"],
            "notes":      mapped["notes"],
            "source":     "calendar_sync",
            "source_ref": mapped["source_ref"],
            "status":     "confirmed",
            "confidence": None,
            "extracted_at": None,
            "extracted_by": None,
            "created_by_account_id": me["id"],
            "created_at": now_iso,
            "updated_at": now_iso,
            "deleted_at": None,
        })
        imported += 1

    await db.user_calendar_credentials.update_one(
        {"id": cred["id"]},
        {"$set": {
            "last_sync_at":    now_iso,
            "last_sync_status": "ok",
            "last_sync_error": None,
        }},
    )

    # Phase R.5.a (2026-05-27) — wire `calendar.sync.linked` event
    # (constant defined in R.3 as a placeholder). Best-effort.
    try:
        from services.cohort.feature_events import (
            emit_feature_event, CALENDAR_SYNC_LINKED,
        )
        acct = await db.accounts.find_one(
            {"id": me["id"]}, {"_id": 0, "cohort_tag": 1},
        ) or {}
        await emit_feature_event(
            event_type=CALENDAR_SYNC_LINKED,
            account_id=me["id"],
            cohort_tag=acct.get("cohort_tag"),
            payload={"context_id": cid, "provider": provider,
                     "imported": imported, "skipped": skipped},
        )
    except Exception:
        pass

    return SyncOut(imported=imported, skipped=skipped, errors=0)
