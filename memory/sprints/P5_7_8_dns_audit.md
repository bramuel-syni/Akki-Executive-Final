# P5.7.8 — DNS audit: `syni.ai` + `akki.syni.ai` (2026-02)

## Captured records

DNS lookups performed via `dnspython` against Google Public DNS (`8.8.8.8`, `1.1.1.1`) at the time of writing.

### `syni.ai` (apex)

| Record | Value |
|---|---|
| `A` | (not queried — apex is not used to serve the SPA; subdomain handles that) |
| `TXT` | `"v=spf1 include:spf.protection.outlook.com -all"` |
| `MX` | `0 syni-ai.mail.protection.outlook.com.` |
| `_dmarc.syni.ai TXT` | `"v=DMARC1; p=none;"` |
| `s1._domainkey.syni.ai CNAME` | `s1.domainkey.u54234824.wl036.sendgrid.net.` (SendGrid DKIM selector 1) |
| `s2._domainkey.syni.ai CNAME` | `s2.domainkey.u54234824.wl036.sendgrid.net.` (SendGrid DKIM selector 2) |

### `akki.syni.ai` (subdomain that serves the production SPA)

| Record | Value |
|---|---|
| `A` | Cloudflare anycast IPs (172.66.0.96, 162.159.140.98) — the marketing SPA is fronted by Cloudflare. |
| `TXT` | — none — |
| `MX` | — none — |
| `_dmarc.akki.syni.ai TXT` | — none — |
| `s1._domainkey.akki.syni.ai CNAME` | — none — |
| `s2._domainkey.akki.syni.ai CNAME` | — none — |
| `em.akki.syni.ai CNAME` | — none — |
| `inbound.akki.syni.ai MX` | `10 mx.sendgrid.net.` (SendGrid Inbound Parse) |

## Authentication summary

Production sends `From: akki@syni.ai` via SendGrid. That means SPF + DKIM checks must pass on `syni.ai` (the From-domain), not on `akki.syni.ai`.

| Check | Required for | Current state on `syni.ai` | Verdict |
|---|---|---|---|
| **SPF** alignment | The `Return-Path` (envelope sender, which SendGrid sets) and/or From-domain must permit the sending IP | SPF on `syni.ai` includes **only Microsoft Outlook** (`spf.protection.outlook.com`). SendGrid IPs are NOT in this SPF record. | **MISCONFIGURED.** When SendGrid sends `From: akki@syni.ai`, the receiving server queries the SPF record on `syni.ai`, sees "only Outlook is allowed to send from here", and SPF returns `fail`. |
| **DKIM** alignment | A valid DKIM signature signed with a key whose selector is published in the From-domain's DNS | SendGrid DKIM selectors `s1._domainkey.syni.ai` and `s2._domainkey.syni.ai` both point at SendGrid's signing keys. SendGrid will sign with the matching key. | **ALIGNED.** DKIM validates. |
| **DMARC** policy | If both SPF and DKIM fail, the DMARC policy decides whether to deliver, quarantine, or reject | `_dmarc.syni.ai` is `p=none` (monitor only, no enforcement) | **PERMISSIVE.** With `p=none`, even an SPF fail + missing DKIM gets delivered. Recipients running their own anti-spam may still flag the message based on heuristics, but DMARC itself won't reject. |

**Bottom line:** outbound deliverability today depends on DKIM passing (it does) AND DMARC being permissive (it is). The SPF failure is real but masked. If `_dmarc.syni.ai` is ever moved to `p=quarantine` or `p=reject` WITHOUT first fixing SPF, ALL SendGrid sends from `akki@syni.ai` start landing in spam folders or bouncing.

## Requirements gap table

| Requirement (for clean SendGrid sending from `akki@syni.ai`) | Current | Status | Action needed |
|---|---|---|---|
| `syni.ai` SPF includes SendGrid | only includes Outlook | **MISSING** | Add SendGrid include — see fix below |
| `syni.ai` DKIM selectors (s1, s2) point at SendGrid | s1 ✓, s2 ✓ | **OK** | none |
| `_dmarc.syni.ai` published | `v=DMARC1; p=none;` | **OK (lax)** | optional — move to `p=quarantine` once SPF is fixed for stricter spoofing protection |
| Branded link tracking on `akki.syni.ai` | not configured | **MISSING (optional)** | Only needed if SendGrid Branded Link Tracking is enabled in the account |
| SendGrid Inbound Parse on `inbound.akki.syni.ai` | MX → mx.sendgrid.net | **OK** | none |
| Inbox on `*@akki.syni.ai` (e.g. hello@, contact@) | no MX | **MISSING** | See P5.7.7 — decide Option A/B/C |

## Concrete DNS changes (copy-paste into registrar)

The user owns `syni.ai` and `akki.syni.ai`; based on the apex MX they are using **Microsoft 365 for the apex** and **Cloudflare for the subdomain**, so likely the registrar's DNS plan is editable directly (Cloudflare or another registrar).

### 1. Fix SPF on `syni.ai` apex (REQUIRED for clean deliverability)

Replace the existing TXT record:

| Type | Host | Value |
|---|---|---|
| TXT | `@` (or `syni.ai`) | `v=spf1 include:spf.protection.outlook.com include:sendgrid.net -all` |

**What this does:** keeps Outlook authorised AND adds SendGrid. The `-all` mechanism stays hard-fail for anyone else.

**Verification after change** (allow 5–30 minutes to propagate):
```
nslookup -type=TXT syni.ai
# Expected: "v=spf1 include:spf.protection.outlook.com include:sendgrid.net -all"
```

### 2. Optionally tighten DMARC (recommended once §1 is verified)

Add a rua (reporting) destination and move policy to quarantine:

| Type | Host | Value |
|---|---|---|
| TXT | `_dmarc` | `v=DMARC1; p=quarantine; pct=25; rua=mailto:dmarc-reports@syni.ai; aspf=r; adkim=r;` |

**What this does:** asks receivers to send aggregate reports to the rua mailbox so the user can observe what's actually being sent on their behalf before going to `p=reject`. The `pct=25` means quarantine is applied to 25% of failing mail initially — a safe rollout. Move to `pct=100` then `p=reject` over weeks once the reports are clean.

**Prerequisite:** the rua mailbox must exist on the apex (`dmarc-reports@syni.ai` — currently routes to the Outlook tenant). Replace with whatever inbox the user actually wants to receive these reports in.

### 3. Optional: branded SendGrid link tracking on `akki.syni.ai`

Only relevant if SendGrid's "Link Branding" is enabled in the SendGrid dashboard for the `syni.ai` domain group. If it is, SendGrid will require two additional CNAMEs on `akki.syni.ai`:
- `url123.akki.syni.ai CNAME → sendgrid.net.` (exact selector varies; SendGrid's UI gives the precise value)
- `url456.akki.syni.ai CNAME → sendgrid.net.`

Currently NEITHER is configured. If the user wants click-tracking to show `https://url123.akki.syni.ai/...` instead of `https://u54234824.ct.sendgrid.net/...` in mail clients, add per SendGrid UI instructions. Otherwise leave as is.

### 4. Optional: real inbox on `akki.syni.ai` (Option C from P5.7.7)

If the user wants `hello@akki.syni.ai`, `contact@akki.syni.ai` etc. to work:

| Type | Host | Priority | Value |
|---|---|---|---|
| MX | `@` (within akki.syni.ai zone) | 10 | `mx1.improvmx.com.` |
| MX | `@` | 20 | `mx2.improvmx.com.` |
| TXT | `@` (within akki.syni.ai zone) | — | `v=spf1 include:spf.improvmx.com -all` (only if outbound from akki.syni.ai is ever needed; for receive-only ImprovMX, skip) |

Then claim the domain in ImprovMX and add aliases.

## Summary table (for the dispatch's "requirement / current / status" format)

| Requirement | Current | Status |
|---|---|---|
| SPF on `syni.ai` authorises SendGrid | Only authorises Outlook | **missing** |
| DKIM on `syni.ai` for SendGrid (s1, s2 selectors) | Present, pointing at SendGrid | **aligned** |
| DMARC on `syni.ai` published | `v=DMARC1; p=none;` | **aligned (permissive)** |
| Mail to `akki@syni.ai` is received | Yes — Outlook tenant via apex MX | **aligned** |
| Mail to `*@akki.syni.ai` is received | No MX on `akki.syni.ai` | **missing (intentional — see P5.7.7)** |
| SendGrid Inbound Parse subdomain configured | `inbound.akki.syni.ai MX → mx.sendgrid.net` | **aligned** |
| Branded link tracking on `akki.syni.ai` | No CNAMEs | **missing (optional)** |

## Priority recommendation

**P0:** Fix SPF on `syni.ai` (step §1 above). Single TXT-record edit. Improves deliverability of every SendGrid send from `akki@syni.ai` (currently `pass` only because of DKIM + permissive DMARC; with SPF aligned, the message will pass strict checks at gateways that pre-DMARC-evaluate SPF for reputation).

**P1:** Tighten DMARC to `p=quarantine; pct=25; rua=...` (step §2). After SPF fix is verified.

**P2:** Decide inbox strategy per P5.7.7 (Option A / B / C).

**P3:** Branded link tracking — cosmetic; defer.
