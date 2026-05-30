# Cohort pricing — HELD

Pricing not yet defined. Page holds in registration-only mode until product
packaging is decided.

**Status: HELD** · See `frontend/src/website/pages/Cohort.jsx` for the
holding-state copy (the line above the application form) and
`backend/routers/cohort_applications.py` for the applicant confirmation body.

The /cohort page remains visible and the application form remains live so
interest is captured during the holding window. Submissions are stored in
the `cohort_applications` Mongo collection and trigger founder
notifications to `FOUNDER_NOTIFY_EMAIL` (comma-separated, dispatch 10).

When pricing is finalised:
- Replace the holding line in `copy/index.js::COHORT.holding`
- Restore the pricing reference in the applicant confirmation body
- Restore PRICING-related copy on adjacent pages (Pricing page,
  COHORT_TEASER, etc.) that may currently link here
