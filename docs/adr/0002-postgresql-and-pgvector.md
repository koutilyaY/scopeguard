# ADR-0002: PostgreSQL and pgvector

## Status
Accepted

## Context
We need a relational store for normalized domain entities plus vector similarity
search for contract-clause retrieval, all free and local.

## Decision
Use PostgreSQL 16 with the `pgvector` extension (via the `pgvector/pgvector:pg16`
image). Clause embeddings are stored in a `Vector(768)` column with an HNSW cosine
index. A single database with row-level `organization_id` scoping serves all tenants.

## Consequences
- One system provides both relational integrity (foreign keys, check constraints,
  unique constraints) and vector search — no separate vector database.
- The embedding dimension is fixed at migration time; switching to an embedding model
  with a different dimension requires a new migration.
- Retrieval filters by `organization_id` (and client/project/date) in SQL before
  similarity ordering, guaranteeing no cross-tenant vector leakage.
