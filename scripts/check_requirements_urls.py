#!/usr/bin/env python3
"""CI guard — block deploy-fragile requirements syntax.

Why this exists
---------------
The deployer's pip-compile / pip-freeze pass rewrites ``package @ url``
lines (PEP 508 direct references) into ``package==version`` form before
the Docker build runs. That's fine for PyPI-published packages but fatal
for anything that lives only on GitHub releases, a private wheelhouse,
or a VCS — there's no PyPI index entry to resolve against, so pip dies
with "Could not find a version that satisfies the requirement …".

This guard surfaces the same class of failure at PR time, BEFORE the
production build ever runs.

Patterns we flag
----------------
* PEP 508 direct references:        ``package @ https://…``
* Plain GitHub release URLs:        ``https://github.com/owner/repo/…``
* Pip find-links pointing offsite:  ``--find-links https://…`` / ``-f …``
* VCS pins:                         ``git+https://…``, ``hg+…``, ``svn+…``

Files scanned
-------------
* ``requirements.txt`` and any ``requirements-*.txt`` under the repo
* ``pyproject.toml`` (optional — only when present, the ``[tool.poetry.dependencies]``
  and ``[project]``-style ``dependencies = […]`` blocks are inspected)

Allow-list
----------
Append ``# ci-requirements-guard: allow <reason>`` to a line to opt it
out. Use sparingly — every allow-listed line must have a runtime
fallback installer in code (see
``backend/services/synisense/presidio_engine.py::_ensure_spacy_model``
for the canonical pattern).

Exit codes
----------
* 0 — clean
* 1 — at least one offending line; details printed to stderr
* 2 — script error (file missing, unreadable, etc.)

Usage
-----
::

    python3 scripts/check_requirements_urls.py [--root <path>]

Default root is the current working directory.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

# Tolerate either spaces or a tab around the `@` in PEP 508 direct refs.
PATTERNS: List[Tuple[str, "re.Pattern[str]"]] = [
    ("pep508-direct-ref", re.compile(r"^\s*[A-Za-z0-9_.\-]+\s+@\s+\S+")),
    ("github-url",        re.compile(r"https?://github\.com/")),
    ("find-links",        re.compile(r"^\s*(?:--find-links|-f)\s+\S+")),
    ("vcs-pin",           re.compile(r"^\s*[A-Za-z0-9_.\-]+\s*@?\s*(?:git|hg|svn|bzr)\+")),
]

ALLOW_MARKER = "ci-requirements-guard: allow"

ERROR_HINT = (
    "Direct-URL or VCS requirement detected. These break the deployer's "
    "pip-compile rewrite (it converts `package @ url` into `package==version`, "
    "which then fails to resolve against PyPI for packages that don't live there). "
    "Either pin a PyPI-available version, or add a runtime fallback installer "
    "(see backend/services/synisense/presidio_engine.py::_ensure_spacy_model for the "
    "spaCy pattern) and annotate the line with "
    "`# ci-requirements-guard: allow [reason]`."
)


def _strip_inline_comment(line: str) -> str:
    """Strip a trailing ``# …`` comment but preserve ``#sha256=…`` hashes
    (those are part of a PEP 508 URL fragment, not a comment).
    """
    out = []
    in_url = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "#":
            # Treat ``#sha256=`` as part of the URL fragment, not a comment.
            if line[i:i + 8] == "#sha256=":
                in_url = True
                out.append(ch)
                i += 1
                continue
            if not in_url:
                break
        if ch.isspace():
            in_url = False
        out.append(ch)
        i += 1
    return "".join(out)


def _line_has_allow_marker(raw: str) -> bool:
    return ALLOW_MARKER in raw


def scan_file(path: Path) -> List[Tuple[int, str, str]]:
    """Return ``[(line_no, pattern_label, line_text), …]`` for each
    offending line in ``path``. Allow-listed lines are skipped.
    Empty / pure-comment / option lines are skipped.
    """
    offenses: List[Tuple[int, str, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SystemExit(f"check_requirements_urls: cannot read {path}: {exc}")

    for n, raw in enumerate(text.splitlines(), start=1):
        if _line_has_allow_marker(raw):
            continue
        body = _strip_inline_comment(raw).strip()
        if not body:
            continue
        # Skip pure pip options that aren't --find-links (e.g. --index-url
        # is acceptable; the deployer respects it). We only flag find-links
        # because those are the deploy-fragile case.
        for label, regex in PATTERNS:
            if regex.search(body):
                offenses.append((n, label, raw.rstrip()))
                break  # one label per line is enough — first match wins
    return offenses


def _resolve_targets(root: Path) -> Iterable[Path]:
    """Yield the files we want to scan, in deterministic order."""
    # 1) all requirements*.txt anywhere in the repo (but skip vendored
    #    node_modules / virtualenvs to avoid third-party noise)
    skip_dir_names = {"node_modules", ".venv", "venv", "build", "dist", ".git"}
    for p in sorted(root.rglob("requirements*.txt")):
        if any(part in skip_dir_names for part in p.parts):
            continue
        yield p
    # 2) pyproject.toml at the repo root only (avoid third-party copies)
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        yield pyproject


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--root", default=".", help="repo root to scan (default: cwd)")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"check_requirements_urls: --root {root} is not a directory", file=sys.stderr)
        return 2

    targets = list(_resolve_targets(root))
    if not targets:
        print("check_requirements_urls: no requirements*.txt or pyproject.toml found — nothing to check.")
        return 0

    total = 0
    for path in targets:
        offenses = scan_file(path)
        if not offenses:
            print(f"  ok  {path.relative_to(root)}")
            continue
        total += len(offenses)
        rel = path.relative_to(root)
        for line_no, label, body in offenses:
            # Format the citation as <file>:<line>:<label> <content>
            # so editors can jump straight to it.
            print(f"  ERR {rel}:{line_no}:{label}  {body}", file=sys.stderr)

    if total > 0:
        print(file=sys.stderr)
        print(f"check_requirements_urls: FAILED — {total} offending line(s).", file=sys.stderr)
        print(file=sys.stderr)
        print(ERROR_HINT, file=sys.stderr)
        return 1

    print(f"check_requirements_urls: OK — {len(targets)} file(s) scanned, 0 offenses.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
