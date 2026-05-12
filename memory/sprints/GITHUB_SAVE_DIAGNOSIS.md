# GitHub Save — Diagnostic Report (v2, refined)

> Sprint Item 2 close-out · 2026-05-12 (refined after user clarification)
> Diagnostic-only investigation. **No fix applied. No push performed. No `.git/config` write. No lock files deleted.**

---

## 0. User-supplied context (post-v1)

| Field | Value |
|---|---|
| Action | Emergent UI **"Save to GitHub"** button (not terminal `git push`, not IDE commit, not in-app feature) |
| Symptom | Spinning forever / nothing happens / possibly auth-related |
| Scope | **Only the `Akki-Executive` repo fails. Other repos save fine** for the same user / same OAuth token. |
| Last known good | User does not recall — could be days or weeks |

Scope = "just this repo" **rules out broad OAuth / token expiry / global
platform outage**. Whatever this is, it's specific to the Akki-Executive
repo's per-repo state.

---

## 1. Refined probe — outputs

### 1.1 `git status`
```
On branch main
Untracked files:
  frontend/yarn.lock
nothing added to commit but untracked files present
```
**Interpretation**: working tree is clean — every code change has been
auto-committed by the platform's local-commit half. The pod-side
plumbing for **commit** is working perfectly.

### 1.2 `git log --oneline -5`
```
d1a9c5d auto-commit for 88154271-05ed-49e7-a3e1-0bb283f09f6c
3b72e23 auto-commit for 616b6c69-94bf-49d6-8ae9-28a4fe89e217
5269830 auto-commit for 799c8e66-7146-4fe5-9225-3b3150e6bb86
a09f8da auto-commit for b4ea6f29-fd3a-4a3f-8282-e25d5e0766bc
bb02e38 auto-commit for dfb6857c-5aeb-4fd3-be6a-7ffcab3ff576
```
All 5 most-recent commits are **platform auto-commits** signed by
`emergent-agent-e1 <github@emergent.sh>`. Cadence is healthy — every
agent action results in a snapshot. **Pod-side local history is intact.**

### 1.3 `git fetch origin`
```
fatal: 'origin' does not appear to be a git repository
fatal: Could not read from remote repository.
```
**Interpretation**: there is no `origin` configured in `.git/config`.
Every subsequent probe that depends on `origin/*` (ahead/behind counts,
`ls-remote`) fails for the same reason — see 1.4 / 1.5 / 1.9.

### 1.4 `git log origin/main..HEAD --oneline` (ahead)
```
fatal: ambiguous argument 'origin/main..HEAD': unknown revision …
```
N/A — no `origin/main` ref exists locally.

### 1.5 `git log HEAD..origin/main --oneline` (behind)
```
fatal: ambiguous argument 'HEAD..origin/main': unknown revision …
```
Same — N/A.

### 1.6 `du -sh .git`
```
38M    .git
```
**Interpretation**: repo size is small. **38 MB is well below any
platform push limit.** Rules out "repo too large" as a cause.

### 1.7 `find . -size +50M -not -path "./.git/*" -not -path "*/node_modules/*"`
```
(no output)
```
**Interpretation**: no files >50 MB anywhere in the working tree. Rules
out "single large blob blocking push" as a cause.

### 1.8 `git config --get-all remote.origin.url`
```
(no output — none set)
```
**Interpretation**: no remote URL anywhere in `.git/config`. The
platform sync evidently keeps its target out-of-band (not in `.git/config`)
and writes it transiently when push is invoked. This is normal for
Emergent — the absence of `origin` at rest does NOT by itself indicate
a misconfiguration.

### 1.9 `git ls-remote origin HEAD`
```
fatal: 'origin' does not appear to be a git repository
```
Same as 1.3 — N/A without origin. Cannot test remote-side reachability
from the pod directly.

### 1.10 Lock files
```
ls: cannot access '.git/index.lock': No such file or directory
ls: cannot access '.git/HEAD.lock': No such file or directory
ls: cannot access '.git/packed-refs.lock': No such file or directory
```
**Interpretation**: **no stale lock files**. Rules out "interrupted
prior push left a lock that's blocking subsequent attempts" as a cause.

### 1.11 `.emergent/` contents
```
/app/.emergent/emergent.yml
{
  "env_image_name": "fastapi_react_mongo_shadcn_base_image_cloud_arm:release-17042026-1",
  "job_id": "7c1bc239-6d8f-4bd2-8a8a-40a6b737bf9a",
  "created_at": "2026-05-03T14:18:14.989893+00:00Z"
}
```
**Interpretation**: only image name + job_id. No `.emergent/github.yml`,
no `.emergent/sync.yml`, no per-repo marker. The GitHub binding lives
**in the platform's control plane**, not in the pod filesystem.

### 1.12 `git show --stat HEAD`
```
commit d1a9c5d776a4e99295384c5cdf37ffb00b373477
    auto-commit for 88154271-05ed-49e7-a3e1-0bb283f09f6c
 .github/workflows/requirements-guard.yml |  46 ++++++++
 backend/tests/test_requirements_guard.py | 126 ++++++++++++++++++++
 memory/SYSTEM_STATE.md                   |  10 ++
 memory/sprints/CI_HYGIENE.md             |  64 +++++++++++
 memory/sprints/GITHUB_SAVE_DIAGNOSIS.md  | 169 +++++++++++++++++++++++++++
 scripts/check_requirements_urls.py       | 191 +++++++++++++++++++++++++++++++
 6 files changed, 606 insertions(+)
```
**Interpretation**: most recent commit is small (6 text files,
606 insertions). Not a "huge diff scaring the platform" case.

### 1.13 Object-store size signals
```
loose objects: 3374
pack files:    1 (1.8 MB pack, 70 KB idx)
```
**Interpretation**: 3374 loose objects on a 38 MB repo is **mildly
elevated** but not pathological. A platform `git gc` would compact
this. It would NOT by itself cause "spin forever". Noting for
completeness.

---

## 2. Most likely root cause

Given:
- **Only `Akki-Executive` fails** (other repos save fine → not OAuth)
- **No stale locks** (rules out interrupted prior save)
- **No oversized files / no oversized repo** (rules out push-size limits)
- **No `.emergent/github.yml`** marker (binding is in platform control plane, which the pod can't introspect)
- Local commits accumulate fine (commit half works)
- Platform's push half cannot be tested from the pod (no `origin` at rest, by design)

**Most likely cause** is one of two per-repo states on the **platform
control-plane side** — invisible from the pod:

1. **History divergence on `main`** — the GitHub-side `main` has been
   advanced by an out-of-band action (a PR merged with squash, a force-push,
   another pod session writing to the same repo) such that the pod's
   local `main` no longer fast-forwards into the remote. The platform's
   "Save to GitHub" almost certainly enforces fast-forward-only pushes
   (force-push is destructive and platforms gate it). When it can't
   fast-forward, it stalls.
2. **Repo binding stale** — the platform's record of which GitHub
   repo this pod targets has gone stale (renamed repo, deleted-and-
   recreated repo, the target branch was renamed from `main` to
   something else, or branch-protection rules now reject the push
   identity). The platform UI silently retries / spins because the
   push call returns a non-actionable error from GitHub and the UI
   doesn't surface it.

**Both are "platform control-plane" issues.** Neither can be observed
from inside the pod, and neither can be fixed by changing files in
`/app`. Both fit the symptom signature ("just this repo, spinning
forever") cleanly.

A third possibility — that this is a transient backend error on the
Emergent side — is also plausible. Retrying in 30 min often unblocks
this class. Has the user already retried?

---

## 3. Recommended action — pod side

**There is nothing to fix in the pod for this issue.**

- No lock files to clear.
- No oversized blobs to remove.
- No history to rewrite (would be destructive without explicit
  user OK and a clear understanding of what the platform expects).
- The pod's local git is healthy — `git status`, `git log`, `git commit`
  all work. The platform's sync layer is the only thing broken.

If we want to **prove** the issue is platform-side vs pod-side, the
agent can — only with explicit user OK and a GitHub PAT — configure
a manual `origin` and attempt `git push` from the terminal. The
server-side error message it returns would conclusively tell us
whether it's divergence (`non-fast-forward`), branch protection
(`refusing to update protected ref`), or something else. **The agent
will not do this without explicit approval — it requires handling a
user-owned credential.**

---

## 4. Recommended action — user side

### 4.1 Safe path (lowest risk)
1. **Retry once after 5–10 min** — eliminate the transient-platform-error case.
2. If it still spins: open Emergent **support ticket** with this exact
   wording (copy-paste):

   > *"Save to GitHub spins indefinitely for repo `Akki-Executive`.
   > Other repos save fine for the same account, ruling out OAuth/token
   > issues. Pod-side state is clean: no lock files, no oversized blobs,
   > no `origin` configured at rest. Most likely the platform's record
   > of the GitHub repo binding is stale, or the GitHub-side `main`
   > has diverged from what the platform expects. Pod diagnosis doc:
   > `/app/memory/sprints/GITHUB_SAVE_DIAGNOSIS.md`."*

   This is the path I recommend if the user is risk-averse.

### 4.2 Fallback path (faster, requires user action)
If the user wants to unblock immediately, the workaround that bypasses
the Emergent UI altogether:

1. User generates a **GitHub Personal Access Token** with `repo` scope
   (https://github.com/settings/tokens). Keep the token confidential.
2. User shares the **HTTPS repo URL** (e.g.
   `https://github.com/<owner>/Akki-Executive.git`) AND grants
   explicit OK to configure the remote temporarily inside the pod.
3. Agent (with explicit user OK) runs:
   ```sh
   git remote add origin https://<token>@github.com/<owner>/Akki-Executive.git
   git fetch origin
   git status         # see divergence picture
   ```
4. Based on what `git fetch` reveals:
   - **If diverged**: agent reports the divergence (commits ahead / behind),
     user decides between (i) `git pull --rebase origin main` then push,
     (ii) accepting the remote and replaying pod commits on top, or
     (iii) force-push (destructive — only if user is the sole writer).
   - **If clean fast-forward**: agent runs `git push origin main`.
   - **If push fails with "protected branch"**: agent reports the error
     and the user adjusts branch-protection rules on GitHub.
5. Whichever path resolves it, agent **removes the temporary remote**
   afterwards (`git remote remove origin`) so the platform's own sync
   layer is not confused.

**Risks of 4.2**: handling a personal access token in chat is not ideal
— would prefer the token be set as an env var in the pod via the
platform's secret store rather than pasted. Force-push, if chosen,
permanently rewrites history on GitHub for that branch. Both require
explicit user OK before the agent acts.

### 4.3 Nuclear option (last resort)
If both 4.1 and 4.2 fail or the user wants to start fresh:
- User creates a **new GitHub repo** with a different name
- User connects the new repo via "Save to GitHub" UI (likely succeeds
  because there's no stale binding yet)
- Pod's working tree pushes cleanly to the new repo
- User archives the old `Akki-Executive` repo on GitHub for reference

This loses the existing repo's PR history / Issues / stars but is the
guaranteed path to a working save flow.

---

## 5. What the agent did NOT do (this round)

- Did NOT `git push` anything.
- Did NOT write `.git/config`. The remote was not added.
- Did NOT delete `.git/index.lock` (there is none — nothing to delete).
- Did NOT touch a single user-owned credential, token, or OAuth scope.
- Did NOT modify the `.emergent/` directory.
- The previous benign probe-commit (from v1 of this report) was
  already reverted with `git reset --soft` + `git restore --staged` +
  `rm`. No probe state survives in the working tree.

— end of v2 diagnostic —
