"""Phase N — Third-party branding / analytics scrub CI guard (2026-05-27).

Locks in the runtime no-emergent-branding / no-posthog policy:

  T1.  Zero `emergent.sh` literals in `/app/frontend/src` or `/app/backend`
       (active source, excluding `_archived/` and `.lighthouseci/`).
  T2.  Zero `posthog` literals (case-insensitive) in active source.
  T3.  No "Made with / Built with / Powered by Emergent" anywhere.
  T4.  `/app/frontend/public/index.html` has no `<script>` tag for
       posthog or emergent CDN, and no inline posthog snippet.
  T5.  Front-end user-facing pages don't render the brand name "Emergent"
       in copy. (Allowed: backend env-var name `EMERGENT_LLM_KEY`, the
       `emergentintegrations` package import statements, the anti-branding
       regression test that asserts the old "Emergent | Fullstack App"
       placeholder is gone.)
  T6.  `frontend/package.json` does NOT depend on
       `@emergentbase/visual-edits` (Emergent visual-edits SDK).
  T7.  `SignUp.jsx` does NOT pull its background image from
       `static.prod-images.emergentagent.com` (now a local asset).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
FE   = REPO / "frontend" / "src"
FE_PUBLIC = REPO / "frontend" / "public"
PACKAGE_JSON = REPO / "frontend" / "package.json"
INDEX_HTML   = FE_PUBLIC / "index.html"
SIGNUP_PAGE  = FE / "pages" / "SignUp.jsx"
BACKEND      = REPO / "backend"


# Files we deliberately don't scan:
#   • `_archived/` — frozen historical code
#   • `.lighthouseci/` — generated audit artifacts
#   • `node_modules/` — third-party libs
#   • `.git/` — version control internals
#   • `__pycache__/` — compiled python
#   • This guard file itself (we WANT to write "emergent.sh", "posthog",
#     etc. as scan targets here — it's a defensive test, not a leak.)
_EXCLUDE_DIR_FRAGMENTS = (
    "/_archived/", "/.lighthouseci/", "/node_modules/",
    "/.git/", "/__pycache__/",
)
_SELF_FILENAME = "test_phase_n_third_party_scrub.py"

# File-name suffixes we scan.
_SCAN_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".json", ".md"}

# Operating-integration whitelist for the bare word "Emergent". These
# refs are technical / operational, not user-facing branding:
#   • The backend env-var name `EMERGENT_LLM_KEY`.
#   • The `emergentintegrations` Python package + its import statements.
#   • `emergent.cloudfront` — internal package distribution URL.
#   • `emergentagent.com` — the deploy preview host.
#   • The anti-branding regression test docstring.
_EMERGENT_WORD_ALLOW_PATTERNS = (
    r"\bEMERGENT_LLM_KEY\b",
    r"\bemergentintegrations\b",
    r"emergent\.cloudfront",
    r"emergentagent\.com",
    # Anti-branding regression test (asserts the old placeholder is gone).
    r"the default `<title>` tag must NOT be the old Emergent placeholder",
    r"# The default <title> tag must NOT be the old Emergent placeholder",
)


def _iter_scan_files(root: Path):
    """Yield every file we want to scan under `root`, honouring the
    exclude-directory list AND skipping this guard file itself."""
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        as_posix = path.as_posix()
        if any(frag in as_posix for frag in _EXCLUDE_DIR_FRAGMENTS):
            continue
        if path.name == _SELF_FILENAME:
            continue
        if path.suffix not in _SCAN_SUFFIXES:
            continue
        yield path


def _strip_allowed(text: str) -> str:
    """Strip whitelisted operating-integration references so the
    `\\bEmergent\\b` regex only catches *user-facing branding*."""
    for pat in _EMERGENT_WORD_ALLOW_PATTERNS:
        text = re.sub(pat, "", text)
    return text


# ─────────────────────────────────────────────────────────────────
# T1. No emergent.sh literals in active source.
# ─────────────────────────────────────────────────────────────────
def test_phase_n_no_emergent_sh_in_active_source():
    offenders = []
    for path in _iter_scan_files(FE):
        if "emergent.sh" in path.read_text(encoding="utf-8"):
            offenders.append(path.as_posix())
    for path in _iter_scan_files(FE_PUBLIC):
        if "emergent.sh" in path.read_text(encoding="utf-8"):
            offenders.append(path.as_posix())
    for path in _iter_scan_files(BACKEND):
        if "emergent.sh" in path.read_text(encoding="utf-8"):
            offenders.append(path.as_posix())
    assert not offenders, (
        f"`emergent.sh` literals found in active source: {offenders}. "
        "Phase N scrub regression — remove the branding reference."
    )


# ─────────────────────────────────────────────────────────────────
# T2. No posthog literals (any case) in active source.
# ─────────────────────────────────────────────────────────────────
def test_phase_n_no_posthog_in_active_source():
    offenders = []
    rgx = re.compile(r"posthog", re.IGNORECASE)
    for path in _iter_scan_files(FE):
        if rgx.search(path.read_text(encoding="utf-8")):
            offenders.append(path.as_posix())
    for path in _iter_scan_files(FE_PUBLIC):
        if rgx.search(path.read_text(encoding="utf-8")):
            offenders.append(path.as_posix())
    for path in _iter_scan_files(BACKEND):
        if rgx.search(path.read_text(encoding="utf-8")):
            offenders.append(path.as_posix())
    assert not offenders, (
        f"`posthog` literals found in active source: {offenders}. "
        "Phase N scrub regression — runtime must have zero PostHog."
    )


# ─────────────────────────────────────────────────────────────────
# T3. No "Made with / Built with / Powered by Emergent" anywhere.
# ─────────────────────────────────────────────────────────────────
def test_phase_n_no_made_built_powered_by_emergent():
    offenders = []
    rgx = re.compile(r"(made|built|powered)\s+(with|by)\s+emergent", re.IGNORECASE)
    for path in _iter_scan_files(FE):
        if rgx.search(path.read_text(encoding="utf-8")):
            offenders.append(path.as_posix())
    for path in _iter_scan_files(FE_PUBLIC):
        if rgx.search(path.read_text(encoding="utf-8")):
            offenders.append(path.as_posix())
    for path in _iter_scan_files(BACKEND):
        if rgx.search(path.read_text(encoding="utf-8")):
            offenders.append(path.as_posix())
    assert not offenders, (
        f"`Made/Built/Powered by Emergent` literal found in: {offenders}. "
        "Branding badge regression — Phase N scrub forbids these."
    )


# ─────────────────────────────────────────────────────────────────
# T4. index.html has no script tag for posthog or emergent CDN.
# ─────────────────────────────────────────────────────────────────
def test_phase_n_index_html_has_no_emergent_or_posthog_scripts():
    html = INDEX_HTML.read_text(encoding="utf-8")
    # No <script> src to emergent.sh / posthog
    assert "emergent.sh" not in html, (
        "index.html still references emergent.sh — strip the loader."
    )
    assert "posthog" not in html.lower(), (
        "index.html still contains a PostHog reference — strip it."
    )
    # No inline init function for posthog (`(function(p,o,s,t,h,o,g)`
    # was the upstream snippet's IIFE signature).
    assert "p,o,s,t,h,o,g" not in html, (
        "index.html still contains the PostHog inline init IIFE."
    )
    # Script tags allowed — but must NOT load from emergent.sh.
    script_srcs = re.findall(
        r'<script[^>]*\bsrc=["\']([^"\']+)["\']',
        html,
    )
    bad = [s for s in script_srcs if "emergent.sh" in s or "posthog" in s.lower()]
    assert not bad, f"index.html loads bad scripts: {bad}"


# ─────────────────────────────────────────────────────────────────
# T5. No bare-word "Emergent" branding in active source (allowlist
#     applied for env-var name + integrations package + preview host
#     + anti-branding regression test).
# ─────────────────────────────────────────────────────────────────
def test_phase_n_no_emergent_brand_word_in_user_facing_source():
    offenders = []
    rgx = re.compile(r"\bEmergent\b")
    for root in (FE, FE_PUBLIC, BACKEND):
        for path in _iter_scan_files(root):
            text = path.read_text(encoding="utf-8")
            stripped = _strip_allowed(text)
            if rgx.search(stripped):
                # Capture the first 3 matches for the message.
                hits = []
                for m in rgx.finditer(stripped):
                    start = max(0, m.start() - 30)
                    end   = min(len(stripped), m.end() + 30)
                    hits.append(stripped[start:end].replace("\n", " "))
                    if len(hits) >= 3:
                        break
                offenders.append((path.as_posix(), hits))
    assert not offenders, (
        f"Branding word `Emergent` found in active source. "
        f"Allowlist did not match these residues: {offenders}"
    )


# ─────────────────────────────────────────────────────────────────
# T6. package.json does NOT depend on @emergentbase/visual-edits.
# ─────────────────────────────────────────────────────────────────
def test_phase_n_package_json_no_emergentbase_visual_edits():
    data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    assert "@emergentbase/visual-edits" not in deps, (
        "`@emergentbase/visual-edits` dependency still in package.json — "
        "Phase N scrub regression."
    )


# ─────────────────────────────────────────────────────────────────
# T7. SignUp.jsx background asset is local, not an Emergent CDN URL.
# ─────────────────────────────────────────────────────────────────
def test_phase_n_signup_page_uses_local_background_asset():
    src = SIGNUP_PAGE.read_text(encoding="utf-8")
    assert "static.prod-images.emergentagent.com" not in src, (
        "SignUp.jsx still pulls its background from the platform CDN. "
        "Replace with a local asset under /public/assets/."
    )
    # The BG constant points at a local asset.
    m = re.search(r'const\s+BG\s*=\s*["\']([^"\']+)["\']', src)
    assert m, "SignUp.jsx BG constant not found."
    bg_url = m.group(1)
    assert bg_url.startswith("/") or bg_url.startswith("./"), (
        f"SignUp.jsx BG constant is not a local path: `{bg_url}`."
    )
