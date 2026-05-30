# Solva · Overview

Solva is Akki's structured reasoning surface. Use it when you want a
diagnosis you can defend in a board pack.

## What it does

Solva takes the framing you provide, runs a structured reasoning
pipeline, and outputs a fully-cited diagnosis. Every claim has a
source. Every bias is named. Confidence is calibrated against
genuinely independent evidence; it doesn't get a confidence bump from
echoing itself.

## How to use it

1. Open Solva from the top nav.
2. Pick a mode — `Seek clarity`, `Develop strategy`, `Simulate
   hypothesis`, `Get perspectives`.
3. Enter the question. Solva will ask you a few framing questions to
   pin down what you actually want to know. Answer them in plain
   language; bullet points are fine.
4. Solva runs through the reasoning steps in the background. You can
   close the tab and come back; the work persists.
5. The diagnosis lands on the artefact surface — a structured set of
   slides you can read, export, or share.

**Worked example.** An NED is preparing for a board meeting and wants
to know whether the proposed acquisition's cross-sell math holds. She
opens Solva in `Get perspectives` mode, drops in the acquisition
thesis and the last quarter's actuals. After three framing questions
she lets Solva run. The diagnosis comes back surfacing two tensions
the thesis didn't address — channel concentration risk + the post-
renewal cohort assumption — and grades the overall confidence at 62%
because it couldn't triangulate the third claim. The NED takes that
into the board meeting without pretending it's certainty.

## Common questions

- **How long does a session take?** 60-240 seconds depending on the
  mode and the depth of evidence you attach.
- **What if the answer feels wrong?** Open the audit trail. Every
  step is shown with the evidence it weighed. You can argue back via
  Work Studio Chat and re-compile.
- **Does Solva tell me what to do?** No. Solva names the evidence
  and the tensions; the decision stays yours.

## Troubleshooting

- **The session stalls.** Check `/status` for active incidents. If
  none, mark the session "failed" and start fresh — the work isn't
  lost (the audit log persists).
- **The confidence is lower than expected.** That's the calibration
  doing its job — Solva caps confidence at 69% when it can't
  independently triangulate. Add evidence and re-run if you have it.
