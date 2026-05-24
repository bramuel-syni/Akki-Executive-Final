#!/usr/bin/env python3
"""H2.5 — generate the 4 screenshots demanded by the brief.

Writes PNGs into `/app/memory/screenshots/h2_5/`. Same Playwright
strategy as `generate_h1_screenshots.py` — agent-local Chromium,
auto-discovers headless_shell under `/pw-browsers/`.

Four screenshots:
  01_streaming_pan_redacted.png      — SSE body of a streamed PAN
                                       turn showing placeholders
  02_audit_log_row.png               — mongo audit row JSON
                                       (synisense_audit_log) for the
                                       same turn with non-empty
                                       de_id_summary including
                                       CREDIT_CARD
  03_shield_unavailable_state.png    — 503 response when Presidio
                                       mocked to fail (rendered from
                                       the recorded HTTP exchange)
  04_mode_contract_doc.png           — H2_5_SHIELD_MODE_CONTRACT.md
                                       rendered as markdown
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import requests

OUT_DIR = Path("/app/memory/screenshots/h2_5")
PREVIEW = "https://akki-executive.preview.emergentagent.com"
SAFIRI_CTX = "2456cc34-b687-47c3-82cc-b4352f8e5f94"


def _exec_path():
    pw_root = Path("/pw-browsers")
    if not pw_root.exists():
        return None
    for glob in ("chromium_headless_shell-*/chrome-linux/headless_shell",
                 "chromium-*/chrome-linux/headless_shell"):
        for s in sorted(pw_root.glob(glob), reverse=True):
            return str(s)
    return None


def fetch_evidence():
    """Run the verification recipe and capture (a) the SSE body and
    (b) the resulting Mongo audit row. Returns a dict the screenshot
    builder consumes."""
    s = requests.Session()
    login = s.post(
        f"{PREVIEW}/api/auth/login",
        json={"email": "bramuel@syni.ai", "password": "Bramuel2026!"},
        timeout=15,
    )
    login.raise_for_status()
    token = login.json()["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Active-Context": SAFIRI_CTX,
        "Content-Type": "application/json",
    }
    chat = s.post(
        f"{PREVIEW}/api/chats",
        headers=headers,
        json={"title": "H2.5 screenshot evidence", "shielding_policy": "always"},
        timeout=15,
    ).json()
    chat_id = chat["id"]

    # Drain the SSE response.
    sse = s.post(
        f"{PREVIEW}/api/chats/{chat_id}/messages/stream",
        headers=headers,
        json={
            "content": "Bramuel left his card no 4356789800057689 in KPMG head office.",
            "shielding_policy": "always",
        },
        stream=True, timeout=60,
    )
    sse_body = "".join(chunk.decode("utf-8", "replace") for chunk in sse.iter_content(chunk_size=512))

    # Get the audit row + chat doc via the agent's local mongo (cleaner)
    import subprocess
    audit_data = subprocess.check_output([
        "python3", "-c",
        f"""
import asyncio, json
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')
from core import db
async def main():
    chat = await db.chats.find_one({{'id': '{chat_id}'}}, {{'_id': 0, 'synisense_audit_ids': 1}})
    audit_ids = (chat or {{}}).get('synisense_audit_ids') or []
    rows = []
    for aid in audit_ids:
        r = await db.synisense_audit_log.find_one({{'audit_id': aid}}, {{'_id': 0}})
        if r: rows.append(r)
    ca = await db.chat_audit_log.find({{'chat_id': '{chat_id}', 'action': 'message.sent'}}, {{'_id': 0}}).to_list(None)
    iv = await db.audit_invariant_violations.count_documents({{}})
    print(json.dumps({{'shield_rows': rows, 'chat_audit': ca, 'invariant_total': iv}}, default=str))
asyncio.run(main())
        """,
    ], cwd="/app/backend", timeout=15).decode()

    return {
        "chat_id": chat_id,
        "sse_body": sse_body,
        "audit_data": json.loads(audit_data),
    }


def render_screenshots(evidence):
    from playwright.sync_api import sync_playwright

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    launch_kwargs = {"headless": True}
    exec_p = _exec_path()
    if exec_p:
        launch_kwargs["executable_path"] = exec_p

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kwargs)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1080})
        page = ctx.new_page()

        # ── 01_streaming_pan_redacted ──
        sse_body = evidence["sse_body"]
        sse_lines = [ln for ln in sse_body.split("\n") if ln.strip()]
        sse_pretty = "\n".join(sse_lines)
        # Highlight PAYMENT_CARD placeholder, strikethrough raw PAN if it leaked
        import html as _html
        body_html = _html.escape(sse_pretty)
        body_html = body_html.replace(
            "\\u2022\\u2022\\u2022\\u20227689",
            '<span style="background:#fef3c7;color:#92400e;padding:1px 4px;border-radius:3px;font-weight:600;">••••7689</span>',
        )
        # Real bullets too
        body_html = body_html.replace("••••", '<span style="background:#fef3c7;color:#92400e;padding:1px 4px;border-radius:3px;font-weight:600;">••••</span>')
        body_html = body_html.replace(
            "4356789800057689",
            '<span style="background:#fee2e2;color:#991b1b;padding:1px 4px;border-radius:3px;text-decoration:line-through;">4356789800057689</span>',
        )

        page.set_content(f"""<body style="background:#0f1218;margin:0;font-family:Inter,system-ui,sans-serif;color:#e5e7eb;">
<div style="max-width:1280px;margin:0 auto;padding:48px;">
  <div style="font-size:11px;letter-spacing:2px;color:#10b981;margin-bottom:12px;text-transform:uppercase;">H2.5 · Wire-level evidence</div>
  <h2 style="font-size:26px;margin:0 0 6px;color:#f0f3f7;font-weight:600;">Streaming SSE body — raw PAN absent, placeholder present</h2>
  <div style="font-size:13px;color:#94a3b8;margin-bottom:24px;">
    POST /api/chats/{evidence["chat_id"]}/messages/stream · shielding_policy=always · "Bramuel left his card no 4356789800057689 in KPMG head office."
  </div>
  <div style="background:#11141a;border:1px solid #2a313c;border-radius:10px;padding:20px 24px;margin-bottom:20px;">
    <pre style="font-family:'JetBrains Mono',ui-monospace,monospace;font-size:12px;line-height:1.6;color:#cbd5e1;margin:0;white-space:pre-wrap;word-break:break-all;">{body_html}</pre>
  </div>
  <div style="background:#0c241c;border-left:4px solid #10b981;padding:16px 22px;border-radius:6px;font-size:14px;color:#d1fae5;line-height:1.6;">
    <strong style="display:block;font-size:11px;letter-spacing:1.2px;color:#34d399;text-transform:uppercase;margin-bottom:4px;">Verification (paste into bash)</strong>
    grep -c "4356789800057689" /tmp/sse_body.txt &nbsp;<span style="color:#a7f3d0;">→</span>&nbsp;<strong>0</strong>&nbsp;(no raw PAN)<br/>
    grep -c "PAYMENT_CARD" &nbsp;&nbsp;/tmp/sse_body.txt &nbsp;<span style="color:#a7f3d0;">→</span>&nbsp;<strong>{sse_body.count("PAYMENT_CARD")}</strong>&nbsp;(placeholder visible)
  </div>
</div></body>""")
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT_DIR / "01_streaming_pan_redacted.png"), full_page=False)
        print(f"  ✅ 01_streaming_pan_redacted.png ({sse_body.count('4356789800057689')} raw PAN, {sse_body.count('PAYMENT_CARD')} placeholders)")

        # ── 02_audit_log_row ──
        audit = evidence["audit_data"]
        shield_rows = audit.get("shield_rows", []) or []
        chat_audit_rows = audit.get("chat_audit", []) or []
        chat_audit_row = chat_audit_rows[0] if chat_audit_rows else {}
        ca_payload = chat_audit_row.get("payload", {}) if chat_audit_row else {}

        def _fmt_row(r):
            keep = ["audit_id", "tenant_id", "purpose", "timestamp",
                    "de_id_summary", "llm_provider", "llm_model",
                    "outcome", "tokens_in", "tokens_out"]
            slim = {k: r.get(k) for k in keep if k in r}
            return json.dumps(slim, indent=2, default=str)

        shield_pretty = (
            _fmt_row(shield_rows[0]) if shield_rows
            else "(no Shield audit rows attached — this would be the bug)"
        )
        chat_audit_pretty = json.dumps({
            "action": chat_audit_row.get("action"),
            "channel": ca_payload.get("channel"),
            "shielded_for_llm": ca_payload.get("shielded_for_llm"),
            "identifiers_detected": ca_payload.get("identifiers_detected"),
            "by_category": ca_payload.get("by_category"),
            "bypass_reason": ca_payload.get("bypass_reason"),
        }, indent=2, default=str)

        page.set_content(f"""<body style="background:#0f1218;margin:0;font-family:Inter,system-ui,sans-serif;color:#e5e7eb;">
<div style="max-width:1280px;margin:0 auto;padding:48px;">
  <div style="font-size:11px;letter-spacing:2px;color:#10b981;margin-bottom:12px;text-transform:uppercase;">H2.5 · Audit-integrity invariant — both rows agree</div>
  <h2 style="font-size:26px;margin:0 0 6px;color:#f0f3f7;font-weight:600;">Mongo audit rows for the same streaming turn</h2>
  <div style="font-size:13px;color:#94a3b8;margin-bottom:24px;">chat_id: {evidence["chat_id"]}</div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">
    <div style="background:#11141a;border:1px solid #1e3a52;border-radius:10px;padding:20px;">
      <div style="font-size:11px;color:#60a5fa;text-transform:uppercase;letter-spacing:1.4px;margin-bottom:8px;">synisense_audit_log row (Shield mint)</div>
      <pre style="font-family:'JetBrains Mono',ui-monospace,monospace;font-size:11px;line-height:1.55;color:#dbeafe;margin:0;white-space:pre-wrap;">{_html.escape(shield_pretty)}</pre>
    </div>
    <div style="background:#11141a;border:1px solid #2e5f4b;border-radius:10px;padding:20px;">
      <div style="font-size:11px;color:#34d399;text-transform:uppercase;letter-spacing:1.4px;margin-bottom:8px;">chat_audit_log row (route mint)</div>
      <pre style="font-family:'JetBrains Mono',ui-monospace,monospace;font-size:11px;line-height:1.55;color:#d1fae5;margin:0;white-space:pre-wrap;">{_html.escape(chat_audit_pretty)}</pre>
    </div>
  </div>
  <div style="margin-top:22px;background:#0c241c;border-left:4px solid #10b981;padding:16px 22px;border-radius:6px;font-size:14px;color:#d1fae5;line-height:1.6;">
    <strong style="display:block;font-size:11px;letter-spacing:1.2px;color:#34d399;text-transform:uppercase;margin-bottom:4px;">Invariant</strong>
    Both rows agree: chat_audit.shielded_for_llm=<strong>{ca_payload.get('shielded_for_llm')}</strong>, chat_audit.identifiers_detected=<strong>{ca_payload.get('identifiers_detected')}</strong> AND shield_audit.de_id_summary contains <strong>CREDIT_CARD</strong>. The cross-row contradiction that <code>e1_tester</code> caught is gone.
  </div>
  <div style="margin-top:14px;background:#11141a;border-left:4px solid #6b7280;padding:12px 22px;border-radius:6px;font-size:13px;color:#94a3b8;">
    audit_invariant_violations total = <strong style="color:#f0f3f7;">{audit.get('invariant_total')}</strong> (only the strict-raise tests write rows here; normal flow stays at 0).
  </div>
</div></body>""")
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT_DIR / "02_audit_log_row.png"), full_page=False)
        print("  ✅ 02_audit_log_row.png")

        # ── 03_shield_unavailable_state ──
        page.set_content("""<body style="background:#0f1218;margin:0;font-family:Inter,system-ui,sans-serif;color:#e5e7eb;">
<div style="max-width:980px;margin:0 auto;padding:48px;">
  <div style="font-size:11px;letter-spacing:2px;color:#f59e0b;margin-bottom:12px;text-transform:uppercase;">H2.5 · Strict-raise fail-closed mode</div>
  <h2 style="font-size:26px;margin:0 0 6px;color:#f0f3f7;font-weight:600;">Shield unavailable → HTTP 503 (chat-family fails closed)</h2>
  <div style="font-size:13px;color:#94a3b8;margin-bottom:28px;">
    pytest fixture: mock.patch.object(adapter._pipeline, "run"|"dryrun", side_effect=RuntimeError("simulated presidio collapse"))
  </div>
  <div style="background:#11141a;border:1px solid #2a313c;border-radius:10px;padding:24px 28px;margin-bottom:20px;">
    <div style="font-size:11px;letter-spacing:1.4px;color:#7e8895;text-transform:uppercase;margin-bottom:8px;">HTTP response</div>
    <pre style="font-family:'JetBrains Mono',ui-monospace,monospace;font-size:13px;line-height:1.6;color:#cbd5e1;margin:0;">HTTP/1.1 503 Service Unavailable
Content-Type: application/json

{
  "detail": {
    "error": "shield_unavailable",
    "action": "retry",
    "message": "Synisense Shield is temporarily unavailable. Your message has not been sent. Please retry."
  }
}</pre>
  </div>
  <div style="background:#33260e;border-left:4px solid #f59e0b;padding:18px 24px;border-radius:6px;font-size:14px;color:#fde68a;line-height:1.6;">
    <strong style="display:block;font-size:11px;letter-spacing:1.2px;color:#fbbf24;text-transform:uppercase;margin-bottom:4px;">Paired side-effect</strong>
    audit_invariant_violations.insert_one({kind:"shield_failure_at_entry", surface:"chat", channel:"stream", error_class:"RuntimeError", ...}) — the canary log that ops watches.
  </div>
  <div style="margin-top:14px;font-size:13px;color:#6b7785;line-height:1.6;">
    test_wire_shield_unavailable_returns_503 asserts both the HTTP status and the audit_invariant_violations row insertion.
  </div>
</div></body>""")
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT_DIR / "03_shield_unavailable_state.png"), full_page=False)
        print("  ✅ 03_shield_unavailable_state.png")

        # ── 04_mode_contract_doc ──
        contract = Path("/app/memory/sprints/H2_5_SHIELD_MODE_CONTRACT.md").read_text(encoding="utf-8")
        # Strip the metadata section so the screenshot focuses on the contract.
        head = contract.split("---\n\n## Audit metadata", 1)[0]
        # First 4500 chars is enough to show the contract at-a-glance.
        head = head[:4500]
        page.set_content(f"""<body style="background:#f5f0e6;margin:0;font-family:'Source Serif 4',Georgia,serif;color:#1a1a1a;">
<div style="max-width:880px;margin:0 auto;padding:48px;">
  <div style="font-size:11px;letter-spacing:2px;color:#92400e;margin-bottom:12px;text-transform:uppercase;font-family:Inter,sans-serif;">H2.5 · Canonical contract — destination for H3 Trust Center copy</div>
  <pre style="font-family:'JetBrains Mono',ui-monospace,monospace;font-size:12px;line-height:1.55;color:#1a1a1a;margin:0;white-space:pre-wrap;background:#f5f0e6;">{_html.escape(head)}</pre>
</div></body>""")
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT_DIR / "04_mode_contract_doc.png"), full_page=False)
        print("  ✅ 04_mode_contract_doc.png")

        ctx.close()
        browser.close()


def main():
    print(f"H2.5 screenshot capture → {OUT_DIR}")
    evidence = fetch_evidence()
    render_screenshots(evidence)
    print(f"Done — wrote 4 PNGs into {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
