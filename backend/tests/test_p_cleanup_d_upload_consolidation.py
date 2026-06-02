"""P-Cleanup D — Upload entry point consolidation lockdown.

Catalog of every upload entry point in the frontend, surfacing
which use the canonical shared `UploadModal` (mounted ONCE in
`AppShell.jsx` and triggered by the `akki:open-upload-modal` event)
and which are intentionally distinct local uploaders.

Per dispatch contract: "Replace the thin/legacy callers to open the
rich modal (reuse existing component — do NOT duplicate). Preserve
any contextual prefill."

CATALOG (verbatim ground-truth from `grep -rn` 2026-02):

  ── CANONICAL mounting (single source of truth) ──
  • frontend/src/components/layout/AppShell.jsx:1022
      <UploadModal open=…/>  + listener on `akki:open-upload-modal`
      + `?upload=1` query-param consumption (P0-B Card 2 wiring).

  ── CANONICAL receivers (route to AppShell's modal via the event) ──
  • frontend/src/components/work_studio/WorkStudioSidebar.jsx:151
  • frontend/src/components/home/AddDocumentCard.jsx:15
  • frontend/src/components/home/HeroDocActions.jsx:26
  • frontend/src/pages/CompanyHome.jsx:411
  • frontend/src/pages/DocumentsPage.jsx:313
  • frontend/src/pages/FirstSession.jsx
      (Card 2 upload door → /app/documents?upload=1 → AppShell)

  ── INTENTIONALLY DISTINCT LOCAL UPLOADERS ──
  Each of these requires a per-caller completion callback or runs
  in a different auth context — features the canonical
  UploadModal does not (and per "no new product features" must
  not) provide. Cataloged here so future agents can see they were
  reviewed and DELIBERATELY left alone:

  • frontend/src/components/work_studio/CompilationWizard.jsx:645
      Reason: the wizard adds the uploaded doc to the source-
      selection set via an `onUploadFile` callback in its own
      flow. The canonical modal has no callback API.

  • frontend/src/components/monitor/ObjectivesProjectsPanel.jsx:118
      Reason: T2.3 X5-step-3 "no relevant docs" branch must re-
      run the assessment immediately after upload (state
      transition only meaningful inside this drawer). Local
      uploader supports the re-trigger callback.

  • frontend/src/pages/ContributorPortal.jsx:207
      Reason: External contributors auth via magic-link token,
      NOT via AppShell session. The shared modal cannot mount
      outside the authenticated AppShell context.

  • frontend/src/components/studio/BlockComposer.jsx:540
      Reason: <input type="file" accept="image/*"> — IMAGE upload
      for inline block content. Document-journal upload modal is
      the wrong tool.

Tests below ASSERT this catalog. If a new thick-caller appears it
must wire to the canonical event (caught by the source-strict
match below). If a refactor accidentally creates a SECOND
<UploadModal> mount, the test fails.
"""
from __future__ import annotations

import pytest


# ── 1. Single canonical mount. ─────────────────────────────────


def test_app_shell_mounts_exactly_one_upload_modal():
    """Asserts AppShell — the ONLY place that imports
    `components/upload/UploadModal` — mounts it exactly once."""
    src = open(
        "/app/frontend/src/components/layout/AppShell.jsx",
        encoding="utf-8",
    ).read()
    # Import statement.
    assert "from \"@/components/upload/UploadModal\"" in src or \
           "from '@/components/upload/UploadModal'" in src, src.count("UploadModal")
    # Exactly one JSX mount of <UploadModal …/>.
    mount_count = src.count("<UploadModal")
    assert mount_count == 1, (
        f"AppShell must mount the UploadModal exactly once, "
        f"got {mount_count}. If you added a second mount, the SPA "
        f"will have two modals fighting for focus."
    )


def test_app_shell_consumes_upload_modal_open_event():
    """AppShell must listen for the canonical event and the query
    flag the FirstSession Upload door (P0-B Card 2) emits."""
    src = open(
        "/app/frontend/src/components/layout/AppShell.jsx",
        encoding="utf-8",
    ).read()
    assert "akki:open-upload-modal" in src
    # P0-B Card 2 marker.
    assert "?upload=1" in src or "'upload'" in src or "\"upload\"" in src


# ── 2. No SECOND import of UploadModal anywhere. ───────────────


def test_no_other_file_imports_uploadmodal():
    """If anyone else imports UploadModal we have a duplication
    risk. Honesty-Protocol-safe — surfaces real drift fast."""
    import pathlib
    matches = []
    for p in pathlib.Path("/app/frontend/src").rglob("*.jsx"):
        if "_archived" in str(p):
            continue
        if str(p).endswith("AppShell.jsx"):
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if "from \"@/components/upload/UploadModal\"" in text or \
           "from '@/components/upload/UploadModal'" in text or \
           "components/upload/UploadModal" in text:
            # Allow comment-only mentions.
            for ln in text.splitlines():
                if "UploadModal" in ln and not ln.lstrip().startswith(("//", "*", "/*")):
                    if "import" in ln or "<UploadModal" in ln:
                        matches.append(f"{p}:{ln.strip()}")
    assert matches == [], (
        f"UploadModal imported outside AppShell — duplication risk. "
        f"Move the mount/import back into AppShell. Matches:\n"
        + "\n".join(matches)
    )


# ── 3. Each canonical RECEIVER routes via the event. ──────────


CANONICAL_RECEIVERS = [
    "/app/frontend/src/components/work_studio/WorkStudioSidebar.jsx",
    "/app/frontend/src/components/home/AddDocumentCard.jsx",
    "/app/frontend/src/components/home/HeroDocActions.jsx",
    "/app/frontend/src/pages/CompanyHome.jsx",
    "/app/frontend/src/pages/DocumentsPage.jsx",
]


@pytest.mark.parametrize("path", CANONICAL_RECEIVERS)
def test_canonical_receiver_uses_the_event(path):
    text = open(path, encoding="utf-8").read()
    assert "akki:open-upload-modal" in text, (
        f"{path} no longer dispatches the canonical event. If you "
        f"changed how this caller opens uploads, update the catalog "
        f"in this test file's docstring."
    )


def test_firstsession_upload_door_uses_canonical_url_flag():
    """The P0-B Card 2 upload door must navigate to the canonical
    URL flag the AppShell effect consumes."""
    text = open(
        "/app/frontend/src/pages/FirstSession.jsx", encoding="utf-8"
    ).read()
    assert "/app/documents?upload=1" in text


# ── 4. INTENTIONALLY DISTINCT local uploaders are still distinct. ─


# Each entry: (path, reason-it-cannot-route-to-shared-modal)
INTENTIONAL_LOCAL_UPLOADERS = [
    ("/app/frontend/src/components/work_studio/CompilationWizard.jsx",
     "needs per-call onUploadFile completion callback"),
    ("/app/frontend/src/components/monitor/ObjectivesProjectsPanel.jsx",
     "must re-run assessment on upload completion"),
    ("/app/frontend/src/pages/ContributorPortal.jsx",
     "token-auth context, no AppShell — shared modal cannot mount"),
    ("/app/frontend/src/components/studio/BlockComposer.jsx",
     "image-only upload, not document-journal"),
]


@pytest.mark.parametrize("path,reason", INTENTIONAL_LOCAL_UPLOADERS)
def test_intentional_local_uploader_still_distinct(path, reason):
    """Documents that these surfaces were reviewed and deliberately
    left as local uploaders, not migrated to the shared modal.
    Asserts the file still exists + still has a local file input.
    If you migrate one of these to the shared UploadModal, remove
    its row from this list to mark the catalog up-to-date."""
    import pathlib
    p = pathlib.Path(path)
    assert p.exists(), f"{path} is gone — update the catalog."
    text = p.read_text(encoding="utf-8")
    has_local_upload = (
        "type=\"file\"" in text
        or "setUploadOpen" in text  # local upload state, not the shared event
    )
    assert has_local_upload, (
        f"{path} no longer has a local uploader — its reason was "
        f"\"{reason}\". If you migrated it to the shared modal, "
        f"REMOVE this row from INTENTIONAL_LOCAL_UPLOADERS."
    )
