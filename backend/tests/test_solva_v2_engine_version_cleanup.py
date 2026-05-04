"""Phase 15.3 — unit tests for placeholder/stub label retirement.

After Phase 15.3 the ENGINE_VERSIONS table must NOT contain any string
matching the patterns `@0.x-stub` or `placeholder@*`. New audit entries
must use `reflection@1.0` for the reflection layer (was `placeholder`).
"""
import re

from services.solva_v2.llm_adapter import ENGINE_VERSIONS


def test_no_stub_versions_in_engine_table():
    bad = [v for v in ENGINE_VERSIONS.values() if re.search(r"-stub|placeholder", v)]
    assert bad == [], f"stub/placeholder versions still present: {bad}"


def test_engine_table_has_reflection_v1():
    assert ENGINE_VERSIONS.get("reflection") == "reflection@1.0"


def test_no_placeholder_engine_key():
    assert "placeholder" not in ENGINE_VERSIONS


def test_refusal_bumped_to_15_3():
    """Refusal engine ENGINE_VERSION moved from 0.1-stub → 1.1 in 15.3."""
    assert ENGINE_VERSIONS["refusal"] == "refusal@1.1"


def test_guardrail_engine_registered():
    """Phase 15.3 — guardrail is a new pure-deterministic engine."""
    assert ENGINE_VERSIONS.get("guardrail") == "guardrail@1.0"


def test_all_engine_versions_match_semver_pattern():
    """Every value must look like `name@<version>` where version is either
    semver (e.g. `1.0`, `1.1`) or a milestone label (e.g. `phase11`)."""
    pat = re.compile(r"^[a-z_]+@(?:\d+\.\d+([a-zA-Z0-9._-]*)|phase\d+)$")
    for k, v in ENGINE_VERSIONS.items():
        assert pat.match(v), f"engine_version for {k!r} does not match pattern: {v!r}"
