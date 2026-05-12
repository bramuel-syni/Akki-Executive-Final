Subject: Save-to-GitHub stuck spinning on Akki-Executive repo (other repos work — not OAuth)

Body:

Hello Emergent support team,

The "Save to GitHub" button in the Emergent web IDE has been spinning indefinitely for my workspace whenever I try to save to the Akki-Executive repository. The button never resolves — there is no error toast, no success confirmation, and the spinner does not time out. The behaviour looks vaguely auth-related from the outside, but I want to flag upfront that it is unlikely to be a token or OAuth problem because other GitHub repositories save fine from the same account with the same connection. The issue is isolated to this one repository.

A pod-side diagnostic was run before opening this ticket (full report at /app/memory/sprints/GITHUB_SAVE_DIAGNOSIS.md inside the workspace). The relevant facts: working tree is clean and all local commits are present, the .git directory is 38 MB total (well under any reasonable sync ceiling), no files larger than 50 MB exist anywhere outside node_modules, there are no stale lock files (.git/index.lock, .git/HEAD.lock, .git/packed-refs.lock are all absent), the platform's auto-commit cadence is healthy (most recent five commits are all signed by emergent-agent-e1 and apply small text diffs), and the .emergent directory contains only image-name and job-id metadata with no per-repo binding marker. In short, the pod is healthy and ready to push; the local-commit half of the integration is working perfectly.

Based on the scope ("only this one repo, was working before"), the most likely cause is per-repo state on the platform control plane that the pod cannot introspect. Two candidates fit cleanly: either the GitHub-side main branch has diverged from the SHA the platform expects (a squash-merge PR, force-push, branch rename, or parallel pod session writing to the same repo would all produce this), or the platform's record of the repo binding has gone stale (repo renamed, recreated, default branch renamed, or branch-protection rules added on the GitHub side).

To rule out destructive actions from our side: we have performed no force-pushes, no .git/config writes, no lock-file deletions, no history rewrites, and no manual remote configuration. The pod is in a known-good resting state and nothing has been done that would corrupt the binding.

Could you please check on your end the last-known-good sync state for this repo in the control plane, whether the GitHub-side main has diverged from the platform's expected commit SHA, and whether any recent branch-rename, repo-rename, branch-protection, or recreate event has occurred against Akki-Executive? Whichever of those it turns out to be, the recommended unblock path on your end would be very helpful so we don't reach for the workaround (manual personal-access-token push from the terminal) unnecessarily.

Thank you for your help.

Workspace job ID: 7c1bc239-6d8f-4bd2-8a8a-40a6b737bf9a
Environment image: fastapi_react_mongo_shadcn_base_image_cloud_arm:release-17042026-1
Account email: (please fill in your Emergent account email here before sending)
Target repo: Akki-Executive
