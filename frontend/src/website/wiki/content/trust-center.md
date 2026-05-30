# Trust Center

The Trust Center is Akki's behind-the-scenes surface. Use it when you
want to know how the answer was made, not just what the answer is.

## What it does

The Trust Center shows the audit log of any session you have access
to. Every reasoning step, every cited source, every bias the
validator flagged. It also shows the trust pillars at a principle
level — what Akki commits to, what it refuses to do.

## How to use it

1. From any session, click "Trust" in the top nav account menu.
2. The page opens with the four trust pillars at the top. Below
   them, you'll see the session you're currently in (if any) with
   its audit trail expanded.
3. Click any reasoning step to see the inputs, outputs, and the
   evidence the step weighed.
4. The "Back" button (top left) takes you to the page you came
   from.

**Worked example.** A CFO has just compiled a Solva diagnosis and
wants to defend a specific claim ("15% capex acceleration") in a
board meeting. She opens Trust Center on the session, finds the
claim in the audit trail, and sees that the source was the company's
own Q3 board pack + the comparable from a 2024 industry peer. She
takes the source link to the meeting along with the diagnosis.

## Common questions

- **Why does Akki name biases?** Because every framing carries some.
  Naming them lets you read past them. Trust pillar 1.
- **Can I export the audit trail?** Yes — every session's audit log
  can be exported as JSON from the Trust Center.
- **Does anyone else see my sessions?** Only superadmins for support
  purposes, and only when you explicitly grant access via the
  support request flow.

## Troubleshooting

- **The Trust Center is empty.** You haven't run a session yet.
  Start one in Solva or Work Studio.
- **A reasoning step shows no evidence.** That means the step's
  output didn't reach the confidence threshold for triangulation,
  so it surfaces honestly as "low confidence" with no citations. By
  design.
