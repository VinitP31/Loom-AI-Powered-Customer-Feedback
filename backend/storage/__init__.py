"""Multi-week persistence: one Postgres table storing each upload's
already-computed aggregate result (validation_report + analytics +
summary), timestamped. Aggregate-only by design — no per-ticket `items`
are stored (see docs/Loom_Source_of_Truth.md, Deferred Extensions).
Postgres (not SQLite) so the same instance can later hold RAG embeddings
via the `pgvector` extension.
"""
