# Track B Phase B5 G7 — Send Share "Field required" false positive

**Dispatch:** 2026-06-04T07:59:00Z
**Scope:** Schema swap on document-share endpoint + canonical FE/BE field alignment + multi-recipient storage + engagement-read array shape. Surgical fix; no Track A, B3, B4, or G6 touch.

---

## Problem (per QA spec G7 + tester report on prior dispatches)

`ShareDocumentModal` always toasted **"Field required"** on submit. Root cause was a contract drift, not a stale validator:

| FE sent (pre-G7) | BE required (pre-G7) |
|---|---|
| `recipients: [...]` (list, no required key called `recipients`) | `to_email: EmailStr` (singular, required) |

Pydantic v2 returned `[{loc: ['body','to_email'], msg: 'Field required'}]`; `apiErrorMessage()` toasted the message verbatim. Every share submit failed.

The FE pattern (multi-recipient list) was the canonical one — mirrors:
- `routers/questions.py:351` (B3 Q4Y share, just shipped) — `recipient_emails: List[str]`
- `routers/pulse.py:561` — `recipients: List[str]`
- `ShareDocumentModal.jsx:123` — engagement panel renders `s.recipient_emails || []` as array
- `email_service.send_email(to: List[str], …)` — multi-recipient infrastructure already wired

Only the `DocumentShareIn` schema was singular; everything else was already array-shaped.

---

## Fix — per approved Pre-Read + orchestrator's Option A correction

**Step 0 (FE rename — 1 LOC):**

`ShareDocumentModal.jsx:56` — request body key `recipients` → `recipient_emails`. Single-line alignment to the canonical Q4Y share contract. The FE component otherwise unchanged (multi-recipient list, message field, engagement panel rendering all preserved).

**Step 1 (BE schema swap):**

```python
class DocumentShareIn(BaseModel):
    recipient_emails: List[EmailStr] = Field(..., min_length=1, max_length=10)
    message: Optional[str] = Field(default=None, max_length=2000)
```

Mirror of `questions.py:351-356`. `Optional message` preserves the FE's `null` path.

**Step 2 (storage — dual-shape write):**

```python
recipient_emails = [str(e) for e in body.recipient_emails]
primary_email = recipient_emails[0]
record = {
    "id": str(uuid.uuid4()),
    ...
    "recipient_emails": recipient_emails,        # canonical (new)
    "shared_with_email": primary_email,          # BC for prior consumers
    "shared_with_name": primary_email.split("@")[0],
    "message": (body.message or "").strip()[:2000],
    ...
}
```

Both fields populated on every new write. Legacy rows missing `recipient_emails` are handled by the engagement-read fallback below.

**Step 3 (engagement-read — array shape):**

```python
legacy_singular = s.get("shared_with_email")
recipient_emails = (
    s.get("recipient_emails")
    or ([legacy_singular] if legacy_singular else [])
)
shares.append({
    ...
    "recipient_emails": recipient_emails,   # FE renders `s.recipient_emails || []`
    "shared_with_email": legacy_singular,    # BC field kept for prior consumers
    ...
})
```

Pre-G7 rows naturally fall through to the singular fallback wrapped in a one-element list. FE rendering is array-only and stable.

**Step 4 (send_email — multi-recipient call):**

```python
send_result = await send_email(
    to=recipient_emails,
    subject=f"{sender_label} shared: {doc.get('name')}",
    html=html,
    text=...,
)
```

`email_service.send_email(to: List[str], …)` already accepts a list. Single send call fans out provider-side (SendGrid / Resend both support multi-`to` natively).

**Step 5 (audit log):**

```python
await write_audit(
    context_id, account["id"], "document.shared", "document", doc_id,
    {"recipient_emails": recipient_emails, "doc_name": doc.get("name")},
)
```

---

## Live wire verification (in-browser cookie-authed fetch, real preview env)

`https://akki-executive.preview.emergentagent.com` — admin@akki.ai post-login, in-browser `fetch()` against the live BE through the same cookie+CSRF session the real FE uses:

```json
{
  "happy_status": 200,
  "happy_id_present": true,
  "happy_body_first_200_chars": "{\"id\":\"63961720-82de-43d2-b6f2-934b4e87d2b2\",\"doc_id\":\"doc-smoke-g7-516f2a\",\"context_id\":\"ctx-smoke-g7-29cbe6\",\"shared_by_account_id\":\"cf6e7587-…\",\"shared_by_name\":\"AKKI Admi",
  "legacy_status": 422,
  "legacy_points_at_recipient_emails": true,
  "engagement_share_count": 1,
  "engagement_first_share_recipients": ["alice@example.com", "bob@example.com"],
  "engagement_first_share_bc_field": "alice@example.com"
}
```

- ✅ Canonical `recipient_emails: [...]` payload → **HTTP 200**, share row written with a fresh UUID (was 422 "Field required" pre-G7).
- ✅ Legacy `recipients: [...]` payload → 422, error message points at the new required `recipient_emails` field (test 2 sub-path c contract).
- ✅ Engagement panel returns `recipient_emails` as a 2-element array → matches the FE's `s.recipient_emails || []` rendering.
- ✅ BC field `shared_with_email = "alice@example.com"` (first recipient) preserved for prior consumers.
- ✅ Zero FE overlays.

A side-trip during the smoke probe: Pydantic v2's `EmailStr` rejects the IANA-reserved `.test` TLD. My first run used `@*.test` and got 422 with `"value is not a valid email address"` — **not** the old "Field required" symptom. Different error class, validator working as intended. Re-ran with `@example.com` and got the verbatim PASS above.

**Screenshot:** `/tmp/g7_smoke.png` (FE state after happy-path POST landed).

---

## Lockdown tests — 2 tests, 4 sub-paths total

**File:** `backend/tests/test_track_b_phase_b5_g7_send_share_field_required.py`

| # | Test | Sub-paths |
|---|---|---|
| 1 | `test_share_document_accepts_recipient_emails_list` | (single happy path) — POST 200; DB row carries `recipient_emails` array AND BC `shared_with_email`; engagement read returns array shape. |
| 2 | `test_share_document_rejects_malformed_payloads` | (a) empty list → 422 `min_length` violation. (b) legacy singular `{to_email}` → 422, locator points at `recipient_emails`. (c) legacy plural `{recipients}` → 422, locator points at `recipient_emails` (pins post-G7 rename enforcement). |

**Pytest verbatim:** 2/2 PASS in 4.05s.

---

## Regression — 93/93 PASS in 13.43s

- `test_track_b_phase_b5_g7_send_share_field_required.py` (G7, new) → 2/2 ✓
- `test_track_b_phase_b5_g6_notes_autosave.py` (G6 shipped same week) → 3/3 ✓
- `test_track_b_phase_b4_g11_q4y_promotion.py` (G11) → 4/4 ✓
- `test_track_b_phase3_questions_completion.py` (B3 Q4Y — independent share codepath, zero overlap) → all green ✓
- `test_solva_v1_unchanged.py` (v1 byte-identical guard) → 4/4 ✓
- `test_track_a_phase3_prompt_fix.py` + `test_track_a_phase3_narration.py` → all green ✓
- `test_phase_p5_14_workbook_analyze.py` → 32/32 ✓
- `test_sprint_z1_qa_fixes.py` (G6 source-text test) → all green ✓

ESLint clean on `ShareDocumentModal.jsx`. Ruff clean on `document_engagement.py` + the new test file. Voice-lint clean.

`test_iter26_engagement.py` carries 9 SKIPPED tests (architectural rewrite parked pre-G7); the only one that referenced the legacy `to_email` schema is dormant and naturally superseded by the G7 lockdown. No churn there.

---

## Files touched

```
M frontend/src/components/documents/ShareDocumentModal.jsx       # 1 LOC: recipients → recipient_emails
M backend/routers/document_engagement.py                          # +25 LOC: schema swap + dual storage + engagement-read array + audit log
?? backend/tests/test_track_b_phase_b5_g7_send_share_field_required.py   # 2 lockdowns / 4 sub-paths
M memory/MASTER_STATE.md                                          # G7 row, Section 4 B5 counter, Sections 6+7
?? memory/sprints/TRACK_B_PHASE_B5_G7_SEND_SHARE_VALIDATION.md
```

No new dependencies. No new env vars. No new UI components. No copy changes beyond the audit-log key rename (internal).

---

## Risks honoured (per Pre-Read)

| # | Risk | Status |
|---|---|---|
| R1 | Ripples into B3 Q4Y share (just shipped) | Verified zero — `questions.py:351` uses its own `ShareIn` model + own endpoint + own collection (`question_shares` vs `document_shares`). |
| R2 | Ripples into G11 doc-question promotion | Verified zero — G11 promoter writes `cycle_questions`, untouched. |
| R3 | Ripples into G6 Notes autosave (just shipped) | Verified zero — G6 touches `documents.notes`, untouched. |
| R4 | Backwards-compat with legacy `document_shares` rows | Engagement-read falls back to `shared_with_email` wrapped in a one-element array. FE rendering is unconditional `s.recipient_emails \|\| []`. |
| R5 | Email send fails on multi-recipient | `send_email(to: List[str], …)` already array-shaped; provider-native fan-out. |
| R6 | `apiErrorMessage` regression for new validators | Confirmed by smoke probe — Pydantic v2's `value_error` carries the same `detail[].msg` shape; toast formatting unchanged. |
| R7 | Studio share / pulse share regressions | Separate routers + separate models; untouched. |
| R8 | iter26 test churn | All 9 in iter26 are SKIPPED (pre-existing architectural rewrite). No churn. |

---

## Hard nos honoured

- ✓ No Track A touch.
- ✓ No G6 or G10 touch.
- ✓ No LLM / prompt touch.
- ✓ No new env vars.
- ✓ No new dependencies.
- ✓ No new UI components.
- ✓ No customer-facing copy changes (FE rename is a request-body key, not user-visible; audit-log key rename is internal).
- ✓ No Operation-ID warning cleanup.
- ✓ No schema additions beyond `recipient_emails` (additive, Mongo schemaless, prior rows handled by engagement-read fallback).

---

## Resume contract

Pause for tester journey-completion run. Track B Phase B5 G7 stays **🟡 SHIPPED tester-pending** until the live browser journey confirms:

1. Log in, open a doc drawer, click Share
2. Fill recipients with two valid emails (e.g. `alice@example.com, bob@example.com`)
3. Fill message
4. Click "Send share"
5. Assert success toast (not "Field required" red toast)
6. Refresh engagement panel — new share row appears with both emails listed

Next dispatch (after G7 tester PASS): **G10 — Calendar SELECTED placeholder leak.** Final B5 item; small surgical FE fix on the calendar component.