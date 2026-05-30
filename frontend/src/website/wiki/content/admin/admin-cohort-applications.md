# Admin · Cohort applications

The cohort inbox is where early-access requests land. Admin reviews
them and decides whether to send an invite.

## What it does

Every form submitted at /cohort lands in this inbox. The row carries
the applicant's name, email, organisation, declared role, use case,
and referral source. Status moves from `received` → `reviewed` →
`invited` (or `declined`). Each transition is audited.

## How to use it

1. Open Admin → Cohort applications.
2. Read the use-case field first — that is the only field that
   tells you whether Akki fits.
3. Filter by status to triage. New applications default to
   `received`.
4. To invite, hit "Issue magic link" — the applicant receives an
   email with a single-use sign-in link valid for 14 days.
5. To decline, mark the row `declined` with a one-line reason. The
   reason is internal-only; no email is sent.

**Worked example.** A submission arrives from a private-equity NED
asking whether Akki can handle portfolio-company board packs across
four jurisdictions. Admin reads the use case, confirms the fit, and
issues the magic link. The NED clicks the link the following
morning, lands on the wizard, and is in the workspace within ten
minutes.

## Common questions

- **Does the applicant know we are reviewing them?** Yes. They
  receive an applicant-confirmation email at submission.
- **Can I bulk-invite?** Not yet. Each invite carries a per-row
  magic link.
- **How do I see who invited an applicant?** The audit trail on the
  row records the inviting admin.

## Troubleshooting

- **An invite did not deliver.** Check /status — if SendGrid is
  failing the invite will be queued and retried. If SendGrid is
  green, the receiving inbox may have filtered it; reach out
  directly with the link from the row.
- **An applicant says the link doesn't work.** Confirm it is within
  the 14-day window. If yes, issue a fresh link from the row.
