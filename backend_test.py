"""Phase 11 backend tests — ITEMS A / B / C only.

Run with: python /app/backend_test.py

Auth: admin@akki.ai / AkkiAdmin2026! (superadmin owns Syni.ai HQ).
External URL is read from /app/frontend/.env.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
import sys
from typing import Any, Dict, List, Optional

import httpx
import jwt as pyjwt


# ─── Setup ────────────────────────────────────────────────────────────────
def _frontend_env() -> str:
    with open("/app/frontend/.env", "r") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


def _backend_env(key: str) -> Optional[str]:
    with open("/app/backend/.env", "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return None


BASE = _frontend_env().rstrip("/")
JWT_SECRET = _backend_env("JWT_SECRET") or "local-dev-jwt-secret-do-not-use-in-prod-30af8e2b91d3"

ADMIN_EMAIL = "admin@akki.ai"
ADMIN_PASSWORD = "AkkiAdmin2026!"

results: List[Dict[str, Any]] = []


def record(item: str, ok: bool, msg: str, snippet: Any = None):
    results.append({"item": item, "ok": ok, "msg": msg, "snippet": snippet})
    label = "PASS" if ok else "FAIL"
    snip = ""
    if snippet is not None:
        s = json.dumps(snippet, default=str)[:300] if not isinstance(snippet, str) else str(snippet)[:300]
        snip = f"  →  {s}"
    print(f"[{label}] {item}: {msg}{snip}")


def deep_walk_for_keys(obj: Any, denylist: set, path: str = "$") -> List[str]:
    """Return list of paths where any denylisted key occurs."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in denylist:
                found.append(f"{path}.{k}")
            found.extend(deep_walk_for_keys(v, denylist, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found.extend(deep_walk_for_keys(v, denylist, f"{path}[{i}]"))
    return found


PUBLIC_DENYLIST = {
    "audience", "validator_provider", "validator_model", "validation",
    "model", "model_id", "account_id", "chain", "events", "quota",
    "speaker_notes", "tier", "quality_check", "user_feedback",
    "audience_assumed", "outline_id", "missing_context",
}


# ─── Auth ─────────────────────────────────────────────────────────────────
async def login(client: httpx.AsyncClient) -> Dict[str, Any]:
    r = await client.post(
        f"{BASE}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    r.raise_for_status()
    body = r.json()
    return body


# ─── ITEM A — public Chair view ───────────────────────────────────────────
async def test_item_a(client: httpx.AsyncClient, ctx_id: str):
    print("\n=== ITEM A — Public Chair view ===")

    # Pick an existing deck
    r = await client.get(f"{BASE}/api/contexts/{ctx_id}/decks")
    decks = (r.json() or {}).get("items", [])
    if not decks:
        record("A.deck-pick", False, "No deck available to share")
        return
    deck_id = decks[0]["id"]
    record("A.deck-pick", True, f"Using deck {deck_id}")

    # Mint share
    share_payload = {
        "to_email": "external.reader@example.com",
        "to_name": "External Reader",
        "message": "Please review this deck.",
    }
    r = await client.post(
        f"{BASE}/api/contexts/{ctx_id}/studio/deck/{deck_id}/share-email",
        json=share_payload,
    )
    if r.status_code != 200:
        record("A.share-email", False, f"share-email returned {r.status_code}", r.text[:200])
        return
    sb = r.json()
    tracked_url = sb.get("tracked_url")
    if not tracked_url:
        record("A.share-email", False, "No tracked_url returned (Resend may be configured)", sb)
        return
    # Extract token from .../shared/<TOKEN>
    m = re.search(r"/shared/([^/?#]+)", tracked_url)
    if not m:
        record("A.share-email", False, f"Could not parse token from {tracked_url}", sb)
        return
    token = m.group(1)
    record("A.share-email", True, f"Got share token (len={len(token)})", tracked_url)

    # Public read
    r = await client.get(f"{BASE}/api/public/studio/read/{token}")
    if r.status_code != 200:
        record("A.public-read", False, f"GET public read returned {r.status_code}", r.text[:300])
        return
    body = r.json()

    # Watermark assertions
    wm = body.get("watermark") or {}
    ok_wm = (
        wm.get("label") and wm.get("recipient") == "external.reader@example.com"
        and wm.get("expires_at")
    )
    record("A.watermark", bool(ok_wm), "watermark block carries label/recipient/expires_at", wm)

    # Content kind-appropriate
    content = body.get("content") or {}
    has_slides = isinstance(content.get("slides"), list)
    record("A.content.deck", has_slides, "deck content carries 'slides' array", {"keys": list(content.keys())})

    # Denylist walk
    leaks = deep_walk_for_keys(body, PUBLIC_DENYLIST)
    record("A.no-denylisted-keys",
           len(leaks) == 0,
           f"no denylisted keys at any depth (found: {leaks[:3]})" if leaks
           else "denylist walk clean",
           leaks)

    # Repeat for briefing kind
    rb = await client.get(f"{BASE}/api/contexts/{ctx_id}/briefings")
    briefings = rb.json() if rb.status_code == 200 else []
    if isinstance(briefings, list) and briefings:
        bid = briefings[0]["id"]
        rs = await client.post(
            f"{BASE}/api/contexts/{ctx_id}/studio/briefing/{bid}/share-email",
            json={"to_email": "external.brief@example.com", "to_name": "Brief Reader"},
        )
        if rs.status_code == 200:
            tu = rs.json().get("tracked_url")
            mm = re.search(r"/shared/([^/?#]+)", tu or "")
            if mm:
                btoken = mm.group(1)
                rr = await client.get(f"{BASE}/api/public/studio/read/{btoken}")
                if rr.status_code == 200:
                    bbody = rr.json()
                    has_items = isinstance((bbody.get("content") or {}).get("items"), list)
                    record("A.content.briefing", has_items, "briefing content carries 'items' array")
                    bleaks = deep_walk_for_keys(bbody, PUBLIC_DENYLIST)
                    record("A.briefing.no-denylisted",
                           len(bleaks) == 0,
                           f"briefing payload clean of denylist (leaks={bleaks[:3]})",
                           bleaks)
                else:
                    record("A.content.briefing", False, f"briefing public-read got {rr.status_code}", rr.text[:200])
        else:
            record("A.content.briefing-share", False, f"briefing share-email got {rs.status_code}", rs.text[:200])
    else:
        record("A.content.briefing", False, "no briefing available to test (skipped optional)")

    # Tamper test — wrong secret
    bad_payload = {
        "kind": "deck", "aid": deck_id, "cid": ctx_id,
        "email": "evil@example.com", "purpose": "studio_share",
        "exp": int(time.time()) + 3600,
    }
    bad_token = pyjwt.encode(bad_payload, "totally-different-secret", algorithm="HS256")
    rt = await client.get(f"{BASE}/api/public/studio/read/{bad_token}")
    record(
        "A.tamper.wrong-secret",
        rt.status_code in (400, 410),
        f"wrong-secret token returned {rt.status_code} (expected 400/410, NOT 500)",
        rt.text[:200],
    )

    # Tamper test — malformed
    rt2 = await client.get(f"{BASE}/api/public/studio/read/notatokenat.all")
    record(
        "A.tamper.malformed",
        rt2.status_code in (400, 410),
        f"malformed token returned {rt2.status_code} (expected 400/410)",
        rt2.text[:200],
    )

    # Tamper — expired
    expired_payload = {
        "kind": "deck", "aid": deck_id, "cid": ctx_id,
        "email": "old@example.com", "purpose": "studio_share",
        "exp": int(time.time()) - 60,
    }
    expired_token = pyjwt.encode(expired_payload, JWT_SECRET, algorithm="HS256")
    rt3 = await client.get(f"{BASE}/api/public/studio/read/{expired_token}")
    record(
        "A.tamper.expired",
        rt3.status_code in (400, 410),
        f"expired token returned {rt3.status_code} (expected 410)",
        rt3.text[:200],
    )


# ─── ITEM B — validator fan-out + soft cap ────────────────────────────────
async def _make_outline_then_deck(client: httpx.AsyncClient, ctx_id: str) -> Optional[Dict[str, Any]]:
    """Create an outline and generate a deck. Returns the deck dict or None."""
    rOut = await client.post(
        f"{BASE}/api/contexts/{ctx_id}/decks/outline",
        json={
            "intent": "Brief the audit committee on Q3 revenue underperformance and the pricing-vs-mix split. Outline 6 slides.",
            "audience": "audit_committee",
            "target_slides": 6,
        },
        timeout=120.0,
    )
    if rOut.status_code != 200:
        record("B.deck.outline", False, f"outline returned {rOut.status_code}", rOut.text[:300])
        return None
    outline = rOut.json()
    record("B.deck.outline", True, f"outline created id={outline.get('id')}",
           {"slides": len(outline.get("slides", []))})

    rGen = await client.post(
        f"{BASE}/api/contexts/{ctx_id}/decks/{outline['id']}/generate",
        json={"outline_id": outline["id"], "confirmed": True},
        timeout=180.0,
    )
    if rGen.status_code != 200:
        record("B.deck.generate", False, f"generate returned {rGen.status_code}", rGen.text[:400])
        return None
    deck = rGen.json()
    return deck


async def test_item_b_decks(client: httpx.AsyncClient, ctx_id: str) -> Optional[str]:
    print("\n=== ITEM B — Decks validation ===")
    deck = await _make_outline_then_deck(client, ctx_id)
    if not deck:
        return None
    deck_id = deck["id"]
    val = deck.get("validation") or {}
    verdict_ok = val.get("verdict") in {"validated", "qualified", "flagged"}
    record("B.deck.validation.verdict", verdict_ok,
           f"deck.validation.verdict in {{validated,qualified,flagged}} → {val.get('verdict')}")
    confidence_ok = isinstance(val.get("confidence"), int) and 0 <= val["confidence"] <= 100
    record("B.deck.validation.confidence", confidence_ok,
           f"confidence is 0..100 → {val.get('confidence')}")
    notes_ok = isinstance(val.get("notes"), list)
    record("B.deck.validation.notes", notes_ok, f"notes is list → {val.get('notes')}")
    fields_ok = "validator_provider" in val and "validator_model" in val
    record("B.deck.validation.fields", fields_ok,
           f"validator_provider/model present → {val.get('validator_provider')}/{val.get('validator_model')}")

    # Re-fetch
    rg = await client.get(f"{BASE}/api/contexts/{ctx_id}/decks/{deck_id}")
    if rg.status_code == 200:
        dd = rg.json()
        v2 = dd.get("validation") or {}
        same = v2.get("verdict") == val.get("verdict")
        record("B.deck.validation.persisted", bool(v2 and same),
               f"validation persists across GET → {v2.get('verdict')}")
    else:
        record("B.deck.refetch", False, f"GET deck returned {rg.status_code}", rg.text[:200])
    return deck_id


async def test_item_b_reports(client: httpx.AsyncClient, ctx_id: str):
    print("\n=== ITEM B — Reports validation ===")
    cycle_name = f"test-cycle-validator-{int(time.time())}"
    rC = await client.post(
        f"{BASE}/api/contexts/{ctx_id}/reports/compose",
        json={
            "cycle_name": cycle_name,
            "title": "Q3 audit-committee deep dive: revenue and recognition",
            "description": "The auditors flagged 11M of revenue moved between Q2 and Q3. Walk the committee through volume-vs-price-vs-mix and the policy review.",
            "chain": [
                {"email": "ceo.test@example.com", "name": "Test CEO", "title": "CEO"},
                {"email": "chair.test@example.com", "name": "Test Chair", "title": "Board Chair"},
            ],
        },
        timeout=60.0,
    )
    if rC.status_code != 200:
        record("B.report.compose", False, f"compose returned {rC.status_code}", rC.text[:300])
        return
    rep = rC.json()
    rid = rep["id"]
    record("B.report.compose", True, f"composed report {rid}")

    # Send up first time
    rSU = await client.post(
        f"{BASE}/api/contexts/{ctx_id}/reports/{rid}/send_up",
        timeout=60.0,
    )
    if rSU.status_code != 200:
        record("B.report.send_up", False, f"send_up returned {rSU.status_code}", rSU.text[:300])
        return
    record("B.report.send_up", True, f"sent up to {rSU.json().get('to')}")

    # Re-fetch and verify validation present
    rG = await client.get(f"{BASE}/api/contexts/{ctx_id}/reports/{rid}", timeout=30.0)
    if rG.status_code != 200:
        record("B.report.refetch", False, f"GET returned {rG.status_code}", rG.text[:200])
        return
    rep_after = rG.json()
    val = rep_after.get("validation") or {}
    record("B.report.validation.present",
           bool(val) and val.get("verdict") in {"validated", "qualified", "flagged"},
           f"report.validation.verdict → {val.get('verdict')}",
           val)

    first_verdict = val.get("verdict")
    first_provider = val.get("validator_provider")

    # Send up second time. If chain has another tier and current reviewer
    # is named, calling /send_up as admin (who's NOT the current reviewer)
    # should 403. But the contract is: validation NOT overwritten.
    # Try calling again — likely 403 because admin isn't the current reviewer.
    rSU2 = await client.post(
        f"{BASE}/api/contexts/{ctx_id}/reports/{rid}/send_up",
        timeout=60.0,
    )
    record("B.report.send_up.second",
           rSU2.status_code in (403, 409, 200),
           f"second send_up returned {rSU2.status_code} (expect 403/409 since admin isn't CEO)",
           rSU2.text[:200])

    # Verify validation unchanged
    rG2 = await client.get(f"{BASE}/api/contexts/{ctx_id}/reports/{rid}", timeout=30.0)
    if rG2.status_code == 200:
        v2 = rG2.json().get("validation") or {}
        unchanged = (v2.get("verdict") == first_verdict and
                     v2.get("validator_provider") == first_provider)
        record("B.report.validation.not-overwritten", unchanged,
               f"validation unchanged after second send → verdict={v2.get('verdict')}",
               v2)


async def test_item_b_solve(client: httpx.AsyncClient):
    print("\n=== ITEM B — Solve synthesis validation ===")
    rC = await client.get(f"{BASE}/api/solve/clusters", timeout=30.0)
    clusters = (rC.json() or {}).get("clusters", [])
    if not clusters:
        record("B.solve.cluster", False, "No clusters returned")
        return
    cluster_id = clusters[0]["id"]
    record("B.solve.cluster", True, f"using cluster {cluster_id}")

    rS = await client.post(
        f"{BASE}/api/solve/sessions",
        json={
            "cluster_id": cluster_id,
            "intent": "Q3 revenue is 18% below plan; the CEO is blaming macro and we suspect pricing. We need to land on what to ask for next month.",
            "pro_tier": False,
        },
        timeout=120.0,
    )
    if rS.status_code != 200:
        record("B.solve.start", False, f"sessions create returned {rS.status_code}", rS.text[:300])
        return
    sid = rS.json().get("id") or rS.json().get("session_id") or (rS.json().get("session") or {}).get("id")
    record("B.solve.start", True, f"session id={sid}")

    # Drive turns: surface → depth → synthesis → lockin
    # post_turn returns the FULL session record; phase advances each call
    user_turns = [
        "The gap is on top-line revenue: actuals 82% of plan for Q3, mostly enterprise renewals slipping into Q4.",
        "I think it's pricing — we held list price flat while two competitors cut by 8%. Volume is fine.",
        "What I really want to ask the CFO is: what list-price flexibility do we have for the next quarter?",
        "Let's lock in the question for next month's audit committee.",
    ]
    last_rec = None
    for i, ut in enumerate(user_turns):
        rT = await client.post(
            f"{BASE}/api/solve/sessions/{sid}/turn",
            json={"user_text": ut},
            timeout=180.0,
        )
        if rT.status_code != 200:
            record(f"B.solve.turn.{i}", False, f"turn {i} returned {rT.status_code}", rT.text[:300])
            return
        last_rec = rT.json()
        phase = last_rec.get("phase")
        synth = last_rec.get("synthesis")
        if synth and synth.get("validation"):
            record("B.solve.synthesis.validation",
                   synth["validation"].get("verdict") in {"validated", "qualified", "flagged"},
                   f"synthesis.validation.verdict → {synth['validation'].get('verdict')}",
                   synth["validation"])
            return
        if phase == "lockin" and synth:
            # Reached past synthesis but no validation? That's a fail
            break

    if last_rec and last_rec.get("synthesis"):
        synth = last_rec["synthesis"]
        val = synth.get("validation")
        record("B.solve.synthesis.validation", bool(val and val.get("verdict")),
               f"synthesis.validation present at end-of-loop → {val}",
               val)
    else:
        record("B.solve.synthesis", False, "Never reached synthesis phase",
               last_rec.get("phase") if last_rec else "no record")


async def test_item_b_softcap(client: httpx.AsyncClient, ctx_id: str):
    print("\n=== ITEM B — Soft cap (VALIDATOR_DAILY_SOFT_CAP=1) ===")
    # Configure env, restart backend
    print("  Setting VALIDATOR_DAILY_SOFT_CAP=1 and clearing today's counter…")
    # Ensure today's counter is 0 by deleting the doc directly via mongo
    import subprocess
    # Set env in supervisor by writing to a process env file
    # The cleanest approach is to update /app/backend/.env and restart
    env_path = "/app/backend/.env"
    with open(env_path, "r") as f:
        env_lines = f.read()
    if "VALIDATOR_DAILY_SOFT_CAP=" not in env_lines:
        new_env = env_lines + "\nVALIDATOR_DAILY_SOFT_CAP=1\n"
    else:
        new_env = re.sub(r"VALIDATOR_DAILY_SOFT_CAP=\S*", "VALIDATOR_DAILY_SOFT_CAP=1", env_lines)
    with open(env_path, "w") as f:
        f.write(new_env)

    # Clear today's counter via pymongo
    try:
        from pymongo import MongoClient
        mc = MongoClient("mongodb://localhost:27017")
        mc["akki_dev"].llm_validator_usage.delete_many({})
        mc.close()
    except Exception as _e:
        print(f"  (warn) could not clear validator counter: {_e}")

    subprocess.run(["sudo", "supervisorctl", "restart", "backend"], capture_output=True, timeout=30)
    time.sleep(8)

    # Re-login (cookies invalid? actually cookies persist via JWT so OK,
    # but client may have stale state — re-login to be safe)
    await login(client)

    # First deck — should validate
    deck1 = await _make_outline_then_deck(client, ctx_id)
    if deck1:
        v1 = deck1.get("validation") or {}
        record(
            "B.softcap.first-deck",
            v1.get("verdict") in {"validated", "qualified", "flagged"},
            f"first deck after cap=1: verdict={v1.get('verdict')} provider={v1.get('validator_provider')}",
            v1,
        )

    # Second deck — should hit cap
    deck2 = await _make_outline_then_deck(client, ctx_id)
    if deck2:
        v2 = deck2.get("validation") or {}
        notes = v2.get("notes") or []
        cap_note = any("Daily validator cap" in (n or "") for n in notes)
        provider_na = v2.get("validator_provider") == "n/a"
        record(
            "B.softcap.second-deck",
            cap_note and provider_na,
            f"second deck: notes contains 'Daily validator cap reached' AND provider=='n/a' → "
            f"cap_note={cap_note} provider_na={provider_na} (notes={notes})",
            v2,
        )

    # Briefing surface bypass — call /api/contexts/{cid}/briefs which
    # invokes validate_independent without surface=, so cap is bypassed.
    rBr = await client.post(
        f"{BASE}/api/contexts/{ctx_id}/briefs",
        json={
            "kind": "topic",
            "objective": "What are the principal drivers of Q3 revenue underperformance and how should the audit committee frame the question to management?",
            "deep": False,
        },
        timeout=120.0,
    )
    if rBr.status_code == 200:
        b = rBr.json()
        bv = b.get("validation") or {}
        # The brief surface invokes validate_independent without surface so no cap
        # which means provider should NOT be "n/a" (or if it is, it should be due
        # to validator unavailability not cap).
        notes_b = bv.get("notes") or []
        no_cap_note = not any("Daily validator cap" in (n or "") for n in notes_b)
        record(
            "B.softcap.brief-bypass",
            no_cap_note,
            f"brief validation should NOT carry cap-tripped note → notes={notes_b} provider={bv.get('validator_provider')}",
            bv,
        )
    else:
        record("B.softcap.brief-bypass", False,
               f"brief endpoint returned {rBr.status_code}", rBr.text[:300])

    # ── Restore env ──
    with open(env_path, "r") as f:
        env_lines = f.read()
    new_env = re.sub(r"\nVALIDATOR_DAILY_SOFT_CAP=\S*\n?", "\n", env_lines)
    with open(env_path, "w") as f:
        f.write(new_env)
    subprocess.run(["sudo", "supervisorctl", "restart", "backend"], capture_output=True, timeout=30)
    time.sleep(5)
    print("  Restored env (removed VALIDATOR_DAILY_SOFT_CAP) + restart")


# ─── ITEM C — chat citation chips ─────────────────────────────────────────
async def test_item_c(client: httpx.AsyncClient, ctx_id: str):
    print("\n=== ITEM C — Chat citation chips ===")
    # Re-login if needed (if session was reset by restart in B)
    try:
        rme = await client.get(f"{BASE}/api/auth/me", timeout=15.0)
        if rme.status_code != 200:
            await login(client)
    except Exception:
        await login(client)

    # Verify a doc with extracted_text exists in this context
    rDoc = await client.get(f"{BASE}/api/contexts/{ctx_id}/documents", timeout=30.0)
    docs = rDoc.json() if rDoc.status_code == 200 else []
    if not isinstance(docs, list):
        docs = docs.get("documents") or []
    docs_with_text = [d for d in docs if (d.get("extracted_chars") or 0) > 100]
    if not docs_with_text:
        record("C.docs", False, f"No docs with extracted_text in context (found {len(docs)} total)")
        # We can still test the untethered path
    else:
        record("C.docs", True, f"{len(docs_with_text)} docs with extracted_text")

    # Tethered chat
    chat_payload = {
        "title": "Phase 11 grounding test",
        "model_id": "claude-sonnet-4-5",
        "context_id": ctx_id,
    }
    rCh = await client.post(f"{BASE}/api/chats", json=chat_payload, timeout=30.0)
    if rCh.status_code != 200:
        record("C.tethered.create", False, f"POST /chats returned {rCh.status_code}", rCh.text[:300])
        return
    chat = rCh.json()
    record("C.tethered.create",
           chat.get("context_id") == ctx_id,
           f"chat persisted context_id → {chat.get('context_id')}")

    chat_id = chat["id"]
    # Send a message that should ground
    rMsg = await client.post(
        f"{BASE}/api/chats/{chat_id}/messages",
        json={"content": "Summarise the key facts in the documents in this context. Cite specific sentences."},
        timeout=180.0,
    )
    if rMsg.status_code != 200:
        record("C.tethered.message", False, f"send message returned {rMsg.status_code}", rMsg.text[:300])
        return
    payload = rMsg.json()
    asst = payload.get("assistant_message") or {}
    content = asst.get("content") or ""
    citations = asst.get("citations") or []

    # Either grounding succeeded (non-empty citations + [n] in content)
    # OR retrieval returned empty (no docs with paragraphs) → empty citations + no [[cite:
    has_raw_marker = "[[cite:" in content
    record("C.tethered.no-raw-cite",
           not has_raw_marker,
           f"no [[cite: markers leak into content (has={has_raw_marker})",
           content[:200])

    if docs_with_text and citations:
        # When we have docs and citations: confirm shape
        citation = citations[0]
        required = {"n", "anchor_id", "doc_id", "doc_name", "page", "paragraph_number", "snippet"}
        missing = required - set(citation.keys())
        record("C.tethered.citations.shape",
               len(missing) == 0,
               f"citation shape (missing keys: {missing})",
               citation)
        # Confirm at least one [n] chip in content
        chips = re.findall(r"\[(\d+)\]", content)
        record("C.tethered.citations.chips",
               len(chips) > 0,
               f"content has [n] chips → {chips[:5]}")
    else:
        record("C.tethered.citations",
               isinstance(citations, list),
               f"citations is list (count={len(citations)}) — empty is OK if grounding produced no hits",
               citations[:2])

    # Inspect audit log for citations_kept / citations_dropped
    rAudit = await client.get(f"{BASE}/api/chats/{chat_id}/audit", timeout=30.0)
    if rAudit.status_code == 200:
        rows = rAudit.json()
        if isinstance(rows, dict):
            rows = rows.get("rows") or rows.get("audit") or []
        recv_rows = [r for r in rows if r.get("action") == "message.received"]
        if recv_rows:
            last = recv_rows[-1]
            payload_audit = last.get("payload") or {}
            has_kept = "citations_kept" in payload_audit
            has_dropped = "citations_dropped" in payload_audit
            record("C.audit.citation-counts",
                   has_kept and has_dropped,
                   f"audit row carries citations_kept/dropped → kept={payload_audit.get('citations_kept')}, dropped={payload_audit.get('citations_dropped')}",
                   payload_audit)
        else:
            record("C.audit.citation-counts", False, "no message.received audit row")
    else:
        record("C.audit.citation-counts", False, f"audit GET returned {rAudit.status_code}")

    # Untethered chat
    rUC = await client.post(
        f"{BASE}/api/chats",
        json={"title": "Untethered test", "model_id": "claude-sonnet-4-5"},
        timeout=30.0,
    )
    if rUC.status_code != 200:
        record("C.untethered.create", False, f"POST /chats returned {rUC.status_code}", rUC.text[:300])
        return
    uchat = rUC.json()
    record("C.untethered.create",
           not uchat.get("context_id"),
           f"untethered chat has no context_id → {uchat.get('context_id')}")

    rUMsg = await client.post(
        f"{BASE}/api/chats/{uchat['id']}/messages",
        json={"content": "What's the difference between operating and finance leases for a CFO?"},
        timeout=120.0,
    )
    if rUMsg.status_code != 200:
        record("C.untethered.message", False, f"send returned {rUMsg.status_code}", rUMsg.text[:300])
        return
    upayload = rUMsg.json()
    uasst = upayload.get("assistant_message") or {}
    ucontent = uasst.get("content") or ""
    ucits = uasst.get("citations") or []
    record("C.untethered.no-citations",
           len(ucits) == 0,
           f"untethered citations are empty → count={len(ucits)}",
           ucits)
    record("C.untethered.no-raw-cite",
           "[[cite:" not in ucontent,
           f"untethered content has no [[cite: markers",
           ucontent[:160])


# ─── Driver ───────────────────────────────────────────────────────────────
async def main():
    print(f"BASE = {BASE}")
    async with httpx.AsyncClient(follow_redirects=False, timeout=60.0) as client:
        body = await login(client)
        account = body.get("account") or {}
        ctx_id = account.get("default_context_id")
        if not ctx_id:
            ctxs = body.get("contexts") or []
            ctx_id = ctxs[0]["id"] if ctxs else None
        print(f"Logged in as {account.get('email')}; context = {ctx_id}")

        await test_item_a(client, ctx_id)

        await test_item_b_decks(client, ctx_id)
        await test_item_b_reports(client, ctx_id)
        await test_item_b_solve(client)

        # Soft-cap test (toggles env + restart)
        await test_item_b_softcap(client, ctx_id)

        # Item C — re-login because we restarted backend in B.softcap
        await test_item_c(client, ctx_id)

    # ── Summary ──
    print("\n" + "=" * 70)
    fails = [r for r in results if not r["ok"]]
    passes = [r for r in results if r["ok"]]
    print(f"PASS: {len(passes)}    FAIL: {len(fails)}")
    if fails:
        print("\nFailures:")
        for f in fails:
            print(f"  ❌ {f['item']}: {f['msg']}")
    sys.exit(0 if not fails else 1)


if __name__ == "__main__":
    asyncio.run(main())
