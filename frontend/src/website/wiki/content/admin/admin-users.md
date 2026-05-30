# Admin · Users

**Visibility:** superadmin only.

The Admin · Users surface manages every account on the platform.

## What it does

Admin · Users exposes the full account directory with status,
verification state, role, and an audit timeline. Superadmins can
create, suspend, restore, and re-role accounts.

## How to use it

1. Open the account menu (top right) → "Admin · Users". (Visible
   only to superadmins.)
2. The directory loads — paginated, searchable by name or email,
   filterable by status (`active` / `suspended` / `all`).
3. To create an account: click "New user", fill in email + name +
   role, submit.
4. To suspend: click the row, then "Suspend" — a modal asks for the
   reason, which lands on the user's timeline.
5. To restore: from the suspended list, click "Restore".
6. To change role: click the row, edit the role select, save.
7. CSV export: top-right "Export CSV" — downloads the current
   filter set.

**Worked example.** A cohort applicant signs up but doesn't complete
onboarding for 30 days. A superadmin opens Admin · Users, filters by
`onboarding_stage = profile_complete`, sorts by last sign-in,
identifies stale accounts, and either nudges them via the
confirmation-email path or suspends with a "stale onboarding" reason.

## Common questions

- **What's the difference between suspend and delete?** Suspend
  preserves the account record + audit trail. Delete is permanent
  and irreversible. Only the user themselves can delete their
  account.
- **Can a regular admin see this surface?** No. Only `is_superadmin`
  accounts. Even admins can't see other accounts' data.
- **Does suspending a user invalidate their sessions?** Yes,
  immediately. Their next API call returns 401.

## Troubleshooting

- **The page says "Access denied".** You're not a superadmin. The
  audit log will record the attempt.
- **Suspend fails silently.** Check the network tab — the backend
  will surface the failure reason (e.g. trying to suspend yourself,
  which is blocked).
- **CSV export is missing recent users.** The export uses the
  current filter — broaden it and re-export.
