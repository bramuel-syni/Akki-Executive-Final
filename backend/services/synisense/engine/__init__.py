"""Synisense Engine — behavioural analytics function (Phase A stub).

Phase A scope:
- `signal_types` : canonical catalogue (matches §3.1 of the brief).
- `signal_seeder` : derive plausible signals from existing Mongo so the
  engine has content from day-1. Every seeded signal carries
  `derivation_source: "seeded_from_<collection>"` so it can NEVER be
  confused with a real-ingestion signal.
- `signal_query` : paginated retrieval, strict tenant scoping.
- `subscription` : stub — returns `{subscription_id, status: "pending"}`
  per the resync brief. Real delivery is Phase F.

Out of scope for Phase A: real Kafka/CDC ingestion, real schema versioning,
ML-derived behavioural vectors, cross-region replication.
"""
