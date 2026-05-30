# Account & sign-in

How to sign in, manage your account, and recover access.

## What it does

Akki supports three sign-in methods: email + password, magic link to
your inbox, and OAuth with Google or Microsoft. All routes land you
at the same account.

## How to use it

### Sign in (existing account)

1. Visit `/signin`.
2. Pick the route that fits your access:
   - Type your email + password and click "Sign in"
   - Click "Continue with Google" and complete the Google flow
   - Click "Continue with Microsoft" and complete the Microsoft flow
   - Or type your email and click "Send me a magic link" — we'll
     email a one-tap sign-in link
3. You land at the app home.

### Reset a forgotten password

1. From `/signin`, click "Forgot password?"
2. Type your email; we'll send a reset link if an account exists.
3. The reset link is valid for 1 hour.

### Change your name or notification preferences

1. From any signed-in page, open the account menu (top right) →
   "Settings".
2. Edit the field, click "Save".

**Worked example.** A NED forgets her password an hour before a
meeting. She visits `/forgot-password`, types her email, gets the
reset link in under 30 seconds, picks a new password, and is signed
in. Her existing sessions on her phone are signed out automatically
by the password reset — only her browser session stays.

## Common questions

- **Can I use multiple sign-in methods on the same account?** Yes.
  All routes that land on the same email address link to the same
  account.
- **Do you require MFA?** Not yet at account level. MFA is on the
  P1 roadmap.
- **How do I delete my account?** Settings → Security → "Delete
  account". The deletion is permanent and runs within 24 hours.

## Troubleshooting

- **"Too many failed attempts. Try again shortly."** Wait 15 minutes
  and re-try, or use the magic-link path instead.
- **The magic link didn't arrive.** Check spam. If still missing,
  try again or use a different sign-in route.
- **Microsoft sign-in errors out.** See the runbook on the OAuth
  callback failure path — most causes are recoverable in 5 minutes.
