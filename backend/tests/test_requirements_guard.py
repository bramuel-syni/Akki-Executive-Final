"""Self-test for the CI requirements guard.

Synthetic fixtures cover:
  • one PEP 508 direct-reference line (must fail)
  • one direct GitHub URL line (must fail)
  • one VCS pin (`git+…`) line (must fail)
  • one `--find-links` line (must fail)
  • one allow-listed line (must NOT fail)
  • the repo's actual requirements.txt (must NOT fail after the
    Patch-30 spaCy fix)

The check script is invoked as a subprocess (matches how CI runs it).
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_requirements_urls.py"


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_script_exists():
    assert SCRIPT.is_file(), f"missing guard script at {SCRIPT}"


def test_clean_fixture_passes(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text(textwrap.dedent("""\
        fastapi==0.110.1
        pydantic==2.5.0
        # plain comment, ignored
        --index-url https://pypi.org/simple
    """))
    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_pep508_direct_ref_is_flagged(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text(textwrap.dedent("""\
        fastapi==0.110.1
        en_core_web_sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
    """))
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "en_core_web_sm" in result.stderr
    assert "pep508-direct-ref" in result.stderr or "github-url" in result.stderr


def test_github_url_is_flagged(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text(
        "fastapi==0.110.1\n"
        "https://github.com/some/release.whl\n"
    )
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "github" in result.stderr.lower()


def test_vcs_pin_is_flagged(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text(
        "fastapi==0.110.1\n"
        "somepkg @ git+https://github.com/foo/bar.git@v1.0\n"
    )
    result = _run(tmp_path)
    assert result.returncode == 1
    # Either label can match this line; both are correct flags.
    assert "somepkg" in result.stderr


def test_find_links_is_flagged(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text(
        "fastapi==0.110.1\n"
        "--find-links https://internal.wheelhouse.local/packages\n"
    )
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "find-links" in result.stderr


def test_allow_marker_skips_offending_line(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text(
        "fastapi==0.110.1\n"
        "some_internal_wheel @ https://customer-assets.emergentagent.com/library/foo.whl  "
        "# ci-requirements-guard: allow internal mirror, runtime fallback in services/x.py\n"
    )
    result = _run(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_pyproject_toml_is_scanned(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(textwrap.dedent("""\
        [project]
        name = "demo"
        dependencies = [
          "fastapi==0.110.1",
          "thing @ https://github.com/owner/repo/releases/download/v1/thing.whl",
        ]
    """))
    result = _run(tmp_path)
    assert result.returncode == 1
    # The github-url label or pep508-direct-ref label catches this.
    assert "pyproject.toml" in result.stderr


def test_real_requirements_file_is_clean():
    """Lock the current state of `backend/requirements.txt` post-spacy-hotfix."""
    result = _run(REPO_ROOT)
    if result.returncode != 0:
        raise AssertionError(
            "scripts/check_requirements_urls.py reports offenders in the "
            "repo's actual requirements files — the Patch-30 spaCy fix may "
            f"have regressed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
