"""News-aggregator regression — the 4 stale RSS sources removed during
the 2026-05-26 redeploy-cleanup MUST NOT reappear in the source list.

This file is a pure JSON-schema check (no network calls). The full RSS
sweep is exercised by the existing aggregator tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

SOURCES_PATH = Path(__file__).resolve().parents[1] / "data" / "news_sources.json"

DEAD_IDS_REMOVED_2026_05_26 = {"iod", "frc-uk", "hbr", "reuters-biz"}


def test_news_sources_json_loads():
    assert SOURCES_PATH.exists(), f"sources file missing: {SOURCES_PATH}"
    blob = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    assert isinstance(blob, dict)
    assert "sources" in blob and isinstance(blob["sources"], list)
    assert len(blob["sources"]) > 0


@pytest.mark.parametrize("dead_id", sorted(DEAD_IDS_REMOVED_2026_05_26))
def test_dead_source_not_re_added(dead_id: str):
    blob = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    live_ids = {s["id"] for s in blob["sources"]}
    assert dead_id not in live_ids, (
        f"Stale RSS source `{dead_id}` was re-added to news_sources.json. "
        f"It was removed on 2026-05-26 after HEAD probes confirmed the "
        f"endpoint is dead. See `_removed_2026_05_26_redeploy_cleanup` "
        f"section in news_sources.json for context."
    )


def test_removal_audit_note_present():
    """The audit-trail comment block must remain — future maintainers
    need to see why these were removed."""
    blob = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    assert "_removed_2026_05_26_redeploy_cleanup" in blob, (
        "audit-trail note for the 2026-05-26 removal is missing"
    )
    note = blob["_removed_2026_05_26_redeploy_cleanup"]
    assert isinstance(note, list)
    text = " ".join(note)
    for dead_id in DEAD_IDS_REMOVED_2026_05_26:
        assert dead_id in text, (
            f"removal note missing reference to `{dead_id}`"
        )


def test_remaining_sources_all_have_required_keys():
    """Live entries must keep the required schema keys."""
    blob = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    required = {"id", "name", "url", "regions", "enabled"}
    for s in blob["sources"]:
        missing = required - set(s.keys())
        assert not missing, (
            f"source `{s.get('id', '?')}` missing keys: {missing}"
        )
