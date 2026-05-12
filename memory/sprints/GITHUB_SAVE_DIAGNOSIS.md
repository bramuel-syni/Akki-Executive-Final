# GitHub Save — Diagnostic Report

> Sprint Item 2 close-out · 2026-05-12
> Diagnostic-only investigation in response to user report: *"I also can't save on GitHub."*
> No fix applied. The agent cannot fix this autonomously — see §5.

---

## 1. What "save on GitHub" most likely refers to

The Emergent platform's web-IDE **"Save to GitHub"** action (a button in
the chat-input toolbar, also reachable via the Profile / repo-settings
panel). It is a platform capability — NOT an AKKI-app feature.

Functionally it:
1. Authenticates the user against GitHub via Emergent's OAuth client
2. Creates or connects a target repository
3. Configures `origin` in the pod's `/app/.git/config`
4. Pushes the working tree (and any new commits) to that repository

The system prompt's CRITICAL RULES section lists this explicitly:
*"For git write actions (push, commit, etc.), direct users to 'Save to
GitHub' feature in the chat input."* The agent has no way to authenticate
the user, install OAuth tokens, or configure the remote on the user's
behalf.

---

## 2. Per-mode probe results

### Mode (a) — Emergent platform GitHub sync
- **Status**: **FAILING / unconfigured**
- **Evidence**:
  - `git remote -v` returns empty (no `origin` configured).
  - `git config --get credential.helper` is unset.
  - `git config -l` shows only `user.name=emergent-agent-e1`,
    `user.email=github@emergent.sh` — the platform's auto-commit
    identity, not a real GitHub user.
  - `.emergent/emergent.yml` carries only image / job-id metadata —
    no GitHub config block.
  - No environment variables in the pod reference GitHub
    (no `GITHUB_TOKEN`, `EMERGENT_GITHUB_*`, `GH_*`, `GIT_*`).
  - The most recent commit (`3b72e23`) is `auto-commit for
    616b6c69-…` — the platform is auto-committing locally but
    never pushing, consistent with no remote.

### Mode (b) — direct `git push` from inside the pod
- **Status**: **N/A — no remote to push to**
- **Evidence**:
  - Even if the user had a token, there's no `origin` to push against
    until the platform configures one.
  - A benign local probe commit (`ci: github save probe`) was created
    successfully and reverted cleanly (`git reset --soft HEAD~1` +
    `git restore --staged` + `rm`). Local git plumbing is healthy.
    Working tree restored intact.

### Mode (c) — AKKI app integrating with GitHub
- **Status**: **not applicable**
- **Evidence**:
  - `grep -rln "github.com/api\|octokit\|github_api\|github_token"
    /app/backend /app/frontend/src` returns **zero** hits.
  - AKKI is an executive-intelligence product. It has no GitHub
    integration in scope — the docs surface (Workspace) reads
    user-uploaded files, not VCS repos.

### Mode (d) — Web-IDE commit / save UI
- **Status**: same as mode (a) — this is the user-facing surface of
  mode (a). The button in the Emergent IDE is the entry point; the
  pod-side state (no remote) is the result.

---

## 3. Root cause

The Emergent platform's GitHub integration has either:
* **Never been authorised** for this account / workspace, OR
* **OAuth token has expired or been revoked**, OR
* The "Save to GitHub" UI handshake **failed silently** for a
  platform-side reason.

Symptom signature in any of these cases is identical from the pod's
perspective: no `origin` remote, no credential helper, no platform
environment override.

---

## 4. Recommended fix path

This is a platform action by the user — the agent cannot complete it
autonomously.

1. In the **Emergent web IDE chat input**, click the **"Save to GitHub"**
   button. It opens the GitHub OAuth flow.
2. If the user is **already connected**:
   * Disconnect and reconnect once — this refreshes the token.
   * If the failure recurs, that's a platform-side bug and the user
     should reach out to Emergent support (`support_agent` route).
3. If the user has **never connected**:
   * Authorise the Emergent app against their GitHub account.
   * Pick a target repo (new or existing).
   * The platform will then configure `origin` inside the pod and push.

Once `origin` is wired, the pod's git plumbing is already proven
healthy (see §2 mode-b probe).

---

## 5. What the user must provide

* Nothing for the agent to apply directly — there is no code-side
  fix that would unblock GitHub save without the platform OAuth
  handshake completing first.
* If the platform UI is itself failing (button does nothing,
  modal closes without a token), that's beyond the agent's
  surface area and should be escalated via `support_agent`.

---

## 6. What the agent did NOT do (intentionally)

* Did NOT push anything to GitHub.
* Did NOT modify `.git/config` to inject a remote.
* Did NOT install or attempt to read any token.
* Did NOT `git reset --hard` or otherwise destroy local state.
* The benign probe commit (mode b) was created and reverted
  with `git reset --soft` only — every uncommitted change in
  the working tree (Sprint Item 1 deliverables) survived intact.

---

## 7. Pod state evidence dump (redacted)

```text
$ git status
On branch main
Changes not staged for commit:
  modified:   memory/SYSTEM_STATE.md
  modified:   memory/sprints/CI_HYGIENE.md
Untracked files:
  .github/workflows/requirements-guard.yml
  backend/tests/test_requirements_guard.py
  frontend/yarn.lock
  scripts/check_requirements_urls.py

$ git remote -v
(no output)

$ git config --get credential.helper
(no output)

$ git config -l
user.name=emergent-agent-e1
user.email=github@emergent.sh
core.repositoryformatversion=0
core.filemode=true
core.bare=false
core.logallrefupdates=true

$ git log -1 --oneline
3b72e23 auto-commit for 616b6c69-94bf-49d6-8ae9-28a4fe89e217

$ env | grep -iE "github|gh_|git_"
(no output)

$ ls .emergent/
emergent.yml   # image name + job_id only; no GitHub block
```

— end of diagnostic —
