# Archived Coverage-Loss Tests

These were skipped before the Hardening Step 4 (2026-05-25) re-enable
audit because their **E2E harness pattern** had bit-rotted:
- They used `requests.Session()` against an external `BASE_URL`.
- They hardcoded `bramuel@syni.ai / Bramuel2026!` + `admin@akki.ai /
  AkkiAdmin2026!` credentials.
- They hardcoded `TULI_CTX` and `MAWINGU_CTX` UUIDs that no longer match
  the current seed.

Per the Step 4 brief's classification system:

| Original file | Path | Decision | Reason |
| --- | --- | --- | --- |
| `test_iter40_goals_kpi.py` | strategic-goals + sandbox KPI | **(b) Harness rewrite** | `/api/contexts/{cid}/strategic-goals` + `/api/admin/sandbox/kpi` endpoints still exist. Live replacement at `tests/test_iter40_goals_kpi_in_process.py` (new file, in-process httpx ASGI pattern, same invariants). |
| `test_iter41_signal_actions.py` | signal actions (Pulse Resolved) | **(b) Harness rewrite** | `/api/contexts/{cid}/signals/{sid}/recommendations` + `/actions` endpoints still exist. Live replacement at `tests/test_iter41_signal_actions_in_process.py`. |
| `test_iter19_polish_committee_medium.py` | polish + committee scope + blog admin | **(b) Harness rewrite** | `/api/contexts/{cid}/reports/{rid}/polish` + `/api/contexts/{cid}/cycle/committees` + `/api/blog/admin/posts/{slug}` endpoints still exist. Live replacement at `tests/test_iter19_polish_committee_blog_in_process.py`. |
| `test_iter62_solve_wave2_wave3.py` | `/api/solve/*` namespace walkthrough | **(c) Obsolete** | The `/api/solve/*` namespace was renamed to `/api/solva/v2/*` (note the `a`). All 10 tests' endpoints (`/solve/sessions`, `/solve/clusters/{cid}`, `/solve/sessions/{sid}/turn`, `/solve/sessions/{sid}/handoff/*`) are gone. The current Solva surface is exercised end-to-end by `tests/test_j4_stage_6_*` (chat starter seeding chain), `tests/test_solva_v2_*` (active in-process pattern), and the Phase-D framing tests in the J-suite. No new file written — coverage replaced laterally by the J-sprint test family. |
| `test_iter22_billing_schedule.py` | §M4 Stripe billing + recurring cycle cron | **(d) Contract retired** | Superseded by `tests/test_chunk_c_billing_coming_soon.py` per chunk (c) Stripe → Coming Soon flip (2026-05-25). The archived test asserts `body["url"].startswith("https://checkout.stripe.com/")` (line 98) — the new test asserts the exact opposite (`coming_soon: true`, `/checkout` returns `coming_soon: true` and *"NEVER a Stripe URL"*). No new file required; the live contract is fully covered by `test_chunk_c_billing_coming_soon.py`. Archived 2026-05-26 (CLEANUP_B1_LOG.md). |

**Total: 5 originals archived. 3 new in-process replacements written. 20 obsolete tests retired with documented rationale.**

The archived files are preserved at this path for the historical record only — pytest does NOT discover them (the `_archived_coverage_loss/` directory's `.py.archived` extension is not collected). To inspect the original assertions, open the `.archived` file directly.
