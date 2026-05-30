# Trust · Audit trail

Every reasoning step in Akki writes to an audit trail. The trail is
the evidence you would need to defend a decision later.

## What it does

The audit trail records: who initiated each session, the framing as
submitted, every reasoning step the engine took, the citations
weighed, the position returned, and any subsequent edits or
sign-offs. It is append-only — entries cannot be retroactively
changed.

## How to use it

1. Open the Trust Center.
2. Pick a session from the list, or click any cited claim in a
   Solva diagnosis to jump to the underlying entry.
3. Each entry shows the step type, the inputs, the outputs, and the
   timestamp.
4. Export the trail when you need it for a board pack or governance
   review.

**Worked example.** Following a strategy session, an executive was
asked by the audit committee to defend the recommendation. The
executive opened the Trust Center, exported the session's audit
trail, and walked the committee through the seven reasoning steps,
the eleven citations weighed, the two counter-positions named, and
the moment confidence shifted. The committee approved the
recommendation that meeting.

## Common questions

- **Can I edit the audit trail?** No. The trail is append-only by
  design.
- **How long is it retained?** For the life of the workspace.
  Deleting the workspace deletes the trail.
- **Does it carry user-typed content?** Only what you submitted to
  Akki yourself. Akki does not surface user-typed content to other
  members of the workspace via the trail.

## Troubleshooting

- **A session is missing from the trail.** Sessions in progress are
  not yet committed. Complete or discard the session to surface it.
- **An export failed.** Retry. If it persists, check /status — the
  export worker may be queued.
