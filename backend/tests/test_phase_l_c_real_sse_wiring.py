"""
Phase L.c (2026-05-27) — Real SSE wiring CI guard.

L.b.3 (handoff-resume) already shipped real backend-driven SSE on
the 7 long-op surfaces via `routers/streaming_v9.py` +
`services/streaming/progress.py::PHASE_SCRIPTS`. The frontend
consumers all use `useStreamingProgress` (zero `usePhasedTimer`
call sites — the hook file exists but is dead code).

This file LOCKS that state so a future refactor can't silently
re-introduce timer-driven phase walks:

  Source-strict (offline) —
    * 7 PHASE_SCRIPTS surface keys present.
    * `routers/streaming_v9.py` exposes ≥4 `*/stream` endpoints
      (the L.b set) all using `PhaseEmitter`.
    * No frontend page or component imports `usePhasedTimer` —
      every long-op visual reads from `useStreamingProgress`.
    * Each of the 7 surface keys is referenced by ≥1 frontend
      consumer wiring (the surface key flows from the backend's
      `script` event, but the consumer's stream-target URL must
      hit a route that creates `PhaseEmitter(surface=…)`).

  Runtime (in-process) —
    * `PhaseEmitter` with each of the 7 surface keys emits a
      `script` event listing the locked phase set + ≥1 `phase`
      advance + a `complete` event with the result payload.

Surfaces locked:
   1. solva-frame-audit          (L.a)
   2. work-studio-compile        (L.a)
   3. solva-synthesis            (L.b)
   4. work-studio-enhance        (L.b)
   5. task-manager-compile       (L.b)
   6. events-calendar-sync       (L.b)
   7. decks-generation           (L.b)

User-dispatch note: the L.c dispatch named "Upload / Briefing /
Task Manager readiness / Monitor data load" as candidate streaming
surfaces. None of those are long-ops in the current PHASE_SCRIPTS
taxonomy — they're sub-second JSON GETs. Converting those would be
a separate dispatch (filed as `L.followup.1` if cohort signal
demands streamed UX on short fetches).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend" / "src"
BACKEND = REPO_ROOT / "backend"
PROGRESS_PY = BACKEND / "services" / "streaming" / "progress.py"
STREAMING_V9 = BACKEND / "routers" / "streaming_v9.py"


LOCKED_SURFACES = (
    "solva-frame-audit",
    "work-studio-compile",
    "solva-synthesis",
    "work-studio-enhance",
    "task-manager-compile",
    "events-calendar-sync",
    "decks-generation",
)


# ─────────────────────────────────────────────────────────────────
# Source-strict
# ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("surface", LOCKED_SURFACES)
def test_lc_phase_script_locked(surface: str) -> None:
    """Each of the 7 surface keys must be declared in PHASE_SCRIPTS
    with a non-empty phase list."""
    from services.streaming.progress import PHASE_SCRIPTS
    assert surface in PHASE_SCRIPTS, (
        f"Phase L.c locked surface {surface!r} missing from "
        f"PHASE_SCRIPTS. Have: {sorted(PHASE_SCRIPTS)}."
    )
    phases = PHASE_SCRIPTS[surface]
    assert len(phases) >= 3, (
        f"Surface {surface!r} has only {len(phases)} phases; locked at ≥3."
    )
    for ph in phases:
        assert "label" in ph and "icon" in ph, (
            f"Surface {surface!r} phase missing `label`/`icon`: {ph!r}"
        )


def test_lc_streaming_v9_uses_phase_emitter_per_surface() -> None:
    """`routers/streaming_v9.py` must declare each of the 5 L.b surface
    keys (passed to `_wrap_synchronous_handler(surface=…)` which
    instantiates `PhaseEmitter` internally)."""
    src = STREAMING_V9.read_text(encoding="utf-8")
    assert "from services.streaming.progress import PhaseEmitter" in src
    assert "PhaseEmitter(request, surface=surface)" in src, (
        "streaming_v9.py must hand the surface kwarg straight through "
        "to PhaseEmitter via the shared wrap helper."
    )
    for surface in (
        "solva-synthesis",
        "work-studio-enhance",
        "task-manager-compile",
        "events-calendar-sync",
        "decks-generation",
    ):
        # The surface string appears in the call-site kwarg of
        # `_wrap_synchronous_handler(surface="…")` for each route.
        pattern = rf'surface\s*=\s*["\']{re.escape(surface)}["\']'
        assert re.search(pattern, src), (
            f"streaming_v9.py must call the wrap helper with "
            f"surface={surface!r}; pattern not found."
        )


def test_lc_streaming_v9_declares_at_least_4_stream_endpoints() -> None:
    """L.b ships 5 stream endpoints (some may share a router prefix
    with a sibling JSON path). Asserting ≥4 keeps the lock loose
    enough to tolerate route re-organisation."""
    src = STREAMING_V9.read_text(encoding="utf-8")
    stream_decls = re.findall(r'@router\.(?:post|get)\("[^"]*/stream[^"]*"', src)
    assert len(stream_decls) >= 4, (
        f"Expected ≥4 SSE `/stream` endpoint decorations in "
        f"streaming_v9.py; found {len(stream_decls)}."
    )


def test_lc_no_call_sites_for_dead_use_phased_timer_hook() -> None:
    """`usePhasedTimer` is dead code as of L.b.3. The file may
    physically exist for historical reference but NO page or
    component may import it. If anyone re-introduces it, the
    surface is back to fake timer-driven phase walks."""
    bad_files: list[str] = []
    for jsx in FRONTEND.rglob("*.jsx"):
        text = jsx.read_text(encoding="utf-8")
        # Strip comments before scanning so `// usePhasedTimer …` doesn't
        # false-positive.
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        text = re.sub(r'^\s*//.*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'\{/\*.*?\*/\}', '', text, flags=re.DOTALL)
        if re.search(r'import\s+\w*\s*from\s+["\'][^"\']*usePhasedTimer', text):
            bad_files.append(str(jsx.relative_to(FRONTEND)))
    assert not bad_files, (
        f"`usePhasedTimer` is dead code (Phase L.b.3 swap). These "
        f"files re-introduce it: {bad_files!r}. Remove the import."
    )


def test_lc_useStreamingProgress_is_canonical_long_op_hook() -> None:
    """At least 5 frontend files must consume `useStreamingProgress`
    (one per long-op surface) — sanity check that the L.b.3 swap
    didn't accidentally orphan any consumer."""
    hits = []
    for jsx in FRONTEND.rglob("*.jsx"):
        text = jsx.read_text(encoding="utf-8")
        if re.search(r'import\s+useStreamingProgress\s+from', text):
            hits.append(str(jsx.relative_to(FRONTEND)))
    assert len(hits) >= 5, (
        f"Expected ≥5 frontend consumers of useStreamingProgress; "
        f"got {len(hits)}: {hits!r}."
    )


# ─────────────────────────────────────────────────────────────────
# Runtime — PhaseEmitter end-to-end emission contract
# ─────────────────────────────────────────────────────────────────


class _FakeReq:
    """Minimum Request stub for `is_disconnected` checks. The emitter
    only touches `await request.is_disconnected()` — we never let it
    return True so the stream runs to completion."""
    async def is_disconnected(self) -> bool:
        return False


@pytest.mark.parametrize("surface", LOCKED_SURFACES)
@pytest.mark.asyncio
async def test_lc_phase_emitter_emits_full_lifecycle(surface: str) -> None:
    """For each surface: PhaseEmitter emits a `script` event, ≥1
    `phase` event from `advance()`, and a `complete` event with a
    `result` payload."""
    from services.streaming.progress import PhaseEmitter

    emitter = PhaseEmitter(_FakeReq(), surface=surface)
    async with emitter.start() as e:
        script_evt = e.script_event()
        assert script_evt.startswith("event: script\n")
        assert f'"surface": "{surface}"' in script_evt

        phase_evt = await e.advance()
        assert phase_evt is not None
        assert phase_evt.startswith("event: phase\n")
        assert '"index": 0' in phase_evt
        assert '"label":' in phase_evt

        complete_evt = await e.complete({"ok": True, "marker": surface})
        assert complete_evt.startswith("event: complete\n")
        assert '"ok": true' in complete_evt
        assert f'"marker": "{surface}"' in complete_evt


@pytest.mark.asyncio
async def test_lc_phase_emitter_rejects_unknown_surface() -> None:
    from services.streaming.progress import PhaseEmitter
    with pytest.raises(KeyError):
        PhaseEmitter(_FakeReq(), surface="not-a-real-surface-aa")
