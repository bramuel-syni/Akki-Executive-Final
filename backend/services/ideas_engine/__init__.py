"""Phase P5.15 — Ideas by Akki engine.

Sibling system to Solva v2. Generates a weekly synthesis per
tenant across 4 lenses (Strategy / Board Navigation / Capital /
Governance). Every claim is cited to real document chunks via the
sibling `IdeasCitationResolver`; every narration passes the
sibling `refuse_to_decide` validator. The only Solva v2 surface
this package leans on is `llm_adapter.shielded_call` — the
canonical shielded-LLM entry point. Solva v1 + v2 schemas and the
existing Pulse Signals surface stay byte-identical.
"""
from .schema import (
    IDEA_LENSES,
    ConfidenceBand,
    IdeaCard,
    IdeaCitation,
    IdeaLens,
    IdeasDigest,
    UserIdeasPreferences,
)
from .citation_resolver import (
    CitationUnverifiable,
    IdeasCitationResolver,
)
from .refuse_to_decide import (
    RefuseToDecideViolation,
    validate_no_imperatives,
)
from .personalizer import build_personalization_block
from .synthesizer import (
    SynthesisFailure,
    synthesize_digest,
    week_iso_for,
)
from .preferences import (
    DEFAULT_PREFERENCES_LENSES,
    get_or_default_preferences,
    upsert_preferences,
)
from .scheduler import (
    DEFAULT_ACTIVE_WINDOW_DAYS,
    is_scheduler_disabled,
    run_weekly_ideas_sweep,
    sweep_account,
)

__all__ = [
    "IDEA_LENSES",
    "ConfidenceBand",
    "IdeaCard",
    "IdeaCitation",
    "IdeaLens",
    "IdeasDigest",
    "UserIdeasPreferences",
    "CitationUnverifiable",
    "IdeasCitationResolver",
    "RefuseToDecideViolation",
    "validate_no_imperatives",
    "build_personalization_block",
    "SynthesisFailure",
    "synthesize_digest",
    "week_iso_for",
    "DEFAULT_PREFERENCES_LENSES",
    "get_or_default_preferences",
    "upsert_preferences",
    "DEFAULT_ACTIVE_WINDOW_DAYS",
    "is_scheduler_disabled",
    "run_weekly_ideas_sweep",
    "sweep_account",
]
