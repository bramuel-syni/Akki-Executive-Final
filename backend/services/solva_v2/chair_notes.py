"""Z2.8 (2026-02) — chair-notes shared composer (facade).

The canonical implementation of `_compose_chair_notes` remains in
`pptx_exporter.py` (the original site, untouched by this dispatch).
This facade re-exports it under the public name `compose_chair_notes`
and exposes a `chair_notes_dict(payload)` builder so the new
`/v2/chair_notes` endpoint and the on-screen `<ChairNotesStrip>`
component consume the SAME strings the PPTX exporter writes into
slide notes. Locked by `tests/test_phase_z2_batch5.py` (contract:
both code paths return byte-identical dicts for the same session).
"""
from typing import Dict, List

from services.solva_v2.pptx_exporter import (
    LOCKED_DECK_ORDER,
    _compose_chair_notes as compose_chair_notes,
)


def chair_notes_dict(payload) -> Dict[str, List[str]]:
    return {k: compose_chair_notes(k, payload) for k in LOCKED_DECK_ORDER}
