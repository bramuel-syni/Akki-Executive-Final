"""P5.11.3 — Live MX inbound round-trip probe.

End-to-end check of the SendGrid Inbound Parse chain:

  1. Mint a unique recipient address `mx-probe-{uuid}@inbound.akki.syni.ai`.
  2. Send an email FROM the verified `akki@syni.ai` sender TO the
     unique address via the SendGrid HTTP API.
  3. Sign in as admin@akki.ai against the live preview backend.
  4. Poll `GET /api/admin/inbox/messages?q=<probe-id>` for up to 90s.
  5. On hit: print `MX_INBOUND_OK <message_id>` + a short summary.
  6. On miss: print `MX_INBOUND_FAIL <diagnostic>` covering:
       - DNS MX lookup for inbound.akki.syni.ai
       - SendGrid send status code
       - Last admin-inbox poll response body excerpt

Usage:
  python3 scripts/probe_inbound_mx.py
  python3 scripts/probe_inbound_mx.py --backend https://akki-executive.preview.emergentagent.com
  python3 scripts/probe_inbound_mx.py --backend https://akki.syni.ai
  python3 scripts/probe_inbound_mx.py --timeout 120
"""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

from dotenv import dotenv_values  # noqa: E402
ENV = dotenv_values(REPO / "backend" / ".env")

import requests  # noqa: E402


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dig_mx(domain: str) -> str:
    """Best-effort MX lookup. Returns a short string for the diagnostic."""
    try:
        out = subprocess.check_output(
            ["dig", "+short", "MX", domain],
            stderr=subprocess.DEVNULL, timeout=8,
        ).decode().strip()
        if out:
            return out.replace("\n", " | ")
        return "no MX records returned"
    except FileNotFoundError:
        # `dig` not available — fall back to dnspython if present, then
        # to a socket A-record probe as a last resort. `dnspython` is
        # pulled in transitively by `requests`/`urllib3` in many
        # envs but is not guaranteed; we degrade gracefully.
        try:
            import dns.resolver  # type: ignore
            answers = dns.resolver.resolve(domain, "MX")
            return " | ".join(f"{a.preference} {a.exchange}" for a in answers)
        except Exception as e:  # noqa: BLE001
            try:
                socket.getaddrinfo(domain, None)
                return f"(no dig/dnspython; domain has A record but MX unprobed: {e})"
            except Exception as e2:  # noqa: BLE001
                return f"(no dig/dnspython; domain unresolvable: {e2})"
    except subprocess.TimeoutExpired:
        return "(dig timeout)"
    except subprocess.CalledProcessError as e:
        return f"(dig exit={e.returncode})"


def _sendgrid_send(*, api_key: str, from_email: str, to_email: str,
                   subject: str, body: str) -> dict:
    """Send via the SendGrid v3 HTTP API. Returns
    `{status_code, headers, body}` regardless of outcome (no raise)."""
    url = "https://api.sendgrid.com/v3/mail/send"
    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": from_email},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}],
    }
    try:
        r = requests.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=20,
        )
        return {
            "status_code": r.status_code,
            "x_message_id": r.headers.get("X-Message-Id", ""),
            "body": r.text[:400],
        }
    except Exception as e:  # noqa: BLE001
        return {"status_code": -1, "x_message_id": "", "body": f"send_exception: {e}"[:400]}


def _admin_login(*, backend: str, email: str, password: str) -> requests.Session:
    """Return a requests.Session authenticated as admin via the
    same CSRF dance the live preview already accepts (we just ran
    this in the P5.10 verification — see /app/memory/sprints/
    P5_10_chat_resilience.md)."""
    s = requests.Session()
    # 1) Mint CSRF.
    r1 = s.get(f"{backend}/api/csrf", timeout=15)
    r1.raise_for_status()
    csrf = r1.json()["csrf_token"]
    # 2) Login.
    r2 = s.post(
        f"{backend}/api/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf, "Content-Type": "application/json"},
        timeout=15,
    )
    r2.raise_for_status()
    # 3) Refresh CSRF (cookie may have rotated).
    r3 = s.get(f"{backend}/api/csrf", timeout=15)
    r3.raise_for_status()
    s.headers.update({"X-CSRF-Token": r3.json()["csrf_token"]})
    return s


def _poll_admin_inbox(s: requests.Session, *, backend: str, q: str,
                      deadline: float) -> dict | None:
    """Poll GET /api/admin/inbox/messages?q=<q> until a match shows
    up or the deadline is hit. Returns the matching row or None."""
    while time.time() < deadline:
        try:
            r = s.get(
                f"{backend}/api/admin/inbox/messages",
                params={"q": q, "limit": 10},
                timeout=15,
            )
            r.raise_for_status()
            body = r.json()
            items = body.get("items") or []
            for it in items:
                hay = " ".join([
                    str(it.get("subject") or ""),
                    str(it.get("from_email") or ""),
                    str(it.get("body_snippet") or ""),
                ])
                if q in hay:
                    return it
        except Exception as e:  # noqa: BLE001
            print(f"[probe] poll exception: {e}")
        time.sleep(3.0)
    return None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--backend",
        default="https://akki-executive.preview.emergentagent.com",
        help="Backend base URL (preview by default).",
    )
    p.add_argument("--timeout", type=int, default=90,
                   help="Inbox polling timeout in seconds.")
    p.add_argument("--admin-email", default="admin@akki.ai")
    p.add_argument("--admin-password", default="AkkiAdmin2026!")
    args = p.parse_args()

    api_key = (ENV.get("SENDGRID_API_KEY") or "").strip()
    from_email = (ENV.get("SENDGRID_FROM_EMAIL") or "").strip()
    inbound_domain = (ENV.get("SENDGRID_INBOUND_DOMAIN") or "").strip()
    if not api_key or not from_email or not inbound_domain:
        print(
            f"MX_INBOUND_FAIL config_missing api_key={bool(api_key)} "
            f"from_email={bool(from_email)} inbound_domain={bool(inbound_domain)}"
        )
        return 1

    probe_id = "mx-probe-" + uuid.uuid4().hex[:12]
    to_email = f"{probe_id}@{inbound_domain}"
    subject = f"{probe_id} round-trip test {_now_iso()}"
    body = (
        f"This is a one-shot inbound-parse round-trip probe.\n\n"
        f"probe_id: {probe_id}\n"
        f"sent_at:  {_now_iso()}\n"
    )

    print(f"[probe] probe_id   : {probe_id}")
    print(f"[probe] to_email   : {to_email}")
    print(f"[probe] from_email : {from_email}")
    print(f"[probe] backend    : {args.backend}")

    # 1) Send via SendGrid HTTP API.
    send = _sendgrid_send(
        api_key=api_key, from_email=from_email, to_email=to_email,
        subject=subject, body=body,
    )
    print(f"[probe] sendgrid   : status={send['status_code']} x_message_id={send['x_message_id']!r}")
    if send["status_code"] not in (200, 201, 202):
        mx = _dig_mx(inbound_domain)
        print(
            f"MX_INBOUND_FAIL sendgrid_send_rejected "
            f"status={send['status_code']} "
            f"body={send['body']!r} "
            f"mx={mx!r}"
        )
        return 1

    # 2) Sign in as admin.
    try:
        sess = _admin_login(
            backend=args.backend,
            email=args.admin_email,
            password=args.admin_password,
        )
    except Exception as e:  # noqa: BLE001
        print(f"MX_INBOUND_FAIL admin_login_failed err={e}")
        return 1

    # 3) Poll the inbox.
    deadline = time.time() + args.timeout
    print(f"[probe] polling /api/admin/inbox/messages?q={probe_id} for up to {args.timeout}s")
    hit = _poll_admin_inbox(
        sess, backend=args.backend, q=probe_id, deadline=deadline,
    )
    if hit:
        print(
            f"MX_INBOUND_OK message_id={hit.get('id','?')} "
            f"received_at={hit.get('received_at','?')} "
            f"from={hit.get('from_email','?')} "
            f"subject={(hit.get('subject') or '')[:80]!r}"
        )
        return 0

    # 4) Diagnose.
    mx = _dig_mx(inbound_domain)
    try:
        last = sess.get(
            f"{args.backend}/api/admin/inbox/messages",
            params={"q": probe_id, "limit": 5}, timeout=15,
        )
        last_body = last.text[:400]
        last_status = last.status_code
    except Exception as e:  # noqa: BLE001
        last_status = -1
        last_body = f"poll_exception: {e}"
    print(
        f"MX_INBOUND_FAIL no_inbound_received_within_{args.timeout}s "
        f"sendgrid_status={send['status_code']} "
        f"sendgrid_x_message_id={send['x_message_id']!r} "
        f"inbound_domain_mx={mx!r} "
        f"last_admin_inbox_status={last_status} "
        f"last_admin_inbox_body={last_body!r}"
    )
    print()
    print("Diagnostic interpretation:")
    if "sendgrid.net" in mx.lower():
        print("  ✓ MX points at SendGrid (DNS chain is correct).")
        print("  ✓ Send accepted (status 202) — message is in SendGrid's outbound queue.")
        print(f"  ✗ But no webhook POST hit /api/inbound/sendgrid for {probe_id} in {args.timeout}s.")
        print()
        print("  Most likely cause: SendGrid Inbound Parse webhook is NOT registered")
        print(f"  for host `{inbound_domain}` in the SendGrid console.")
        print()
        print("  Fix (user-side, ~3 minutes in SendGrid UI):")
        print("    1. Sign in to https://app.sendgrid.com")
        print("    2. Settings → Inbound Parse → 'Add Host & URL'")
        print(f"    3. Domain:  {inbound_domain}")
        print( "    4. Subdomain: (leave blank — the MX is on the apex of this host)")
        print(f"    5. Destination URL: https://akki.syni.ai/api/inbound/sendgrid")
        print(f"       (preview: https://akki-executive.preview.emergentagent.com/api/inbound/sendgrid)")
        print( "    6. Check 'POST the raw, full MIME message'")
        print( "    7. Save. Webhook fires within 5 s of the next inbound email.")
        print()
        print("  Verify after fix: re-run `python3 scripts/probe_inbound_mx.py`.")
    elif "no MX records" in mx:
        print("  ✗ Inbound domain has NO MX records — Cloudflare DNS not pointed at SendGrid.")
    else:
        print(f"  ? MX value unclear: {mx!r}")
    print("  → Cross-check: SendGrid Activity (https://app.sendgrid.com/email_activity).")
    print("  → If SendGrid says 'delivered to inbound parse' but the inbox has no row, check backend logs for `/api/inbound/sendgrid` 5xx.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
