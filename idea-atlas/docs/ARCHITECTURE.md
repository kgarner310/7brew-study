# Architecture

## The thesis

Most "AI legal" products are a prompt wrapped around a model. When the model
changes, the product changes; when the model is confidently wrong, the product
is confidently wrong; and the company owns nothing that survives the model.

IDEA Atlas inverts that. The durable asset is a **verified legal knowledge graph
with provenance**. The model is a swappable accelerator for extraction, never
the source of truth, and the system is fully functional with no model at all.

Three consequences shape everything below:

1. **Primary sources are canonical.** Retrieved government text is stored
   verbatim, hashed, and versioned. Our interpretations live in different tables
   and can never overwrite it.
2. **Provenance is structural, not documentary.** Review status is a database
   column with a database constraint, not a convention.
3. **The system refuses rather than guesses.** `insufficient_coverage` is a
   first-class success response.

## Layers

```
                      ┌───────────────────────────────────┐
   HTTP clients ─────▶│  app/api        FastAPI routers   │
   MCP (phase 4)      │                 Pydantic schemas  │
                      └────────────────┬──────────────────┘
                                       │
                      ┌────────────────▼──────────────────┐
                      │  app/services   research (no LLM) │
                      │                 matching, coverage│
                      │                 tokens, ai/*      │
                      └────────────────┬──────────────────┘
                                       │
   Official  ┌──────────────┐   ┌──────▼──────────────────┐
   .gov  ───▶│app/ingestion │──▶│  app/models  SQLAlchemy │──▶ PostgreSQL 16
   sources   │ url_safety   │   │  app/db      session    │
             │ fetcher      │   └─────────────────────────┘
             │ parsers      │
             │ normalizers  │   ┌─────────────────────────┐
             │ validators   │   │ app/legal   jurisdiction│
             │ pipeline     │◀──│             registry    │
             └──────────────┘   │             taxonomy    │
                     ▲          │ data/source_manifests   │
                     └──────────┤ (declarative YAML)      │
                                └─────────────────────────┘
```

`app/cli` drives ingestion, seeding, migrations, and reporting.

## Key decisions

### Nationwide from the first schema, not from phase 3

Every jurisdiction — 50 states, DC, Puerto Rico, four outlying areas, the Bureau
of Indian Education, plus the 12 federal circuits for precedent scoping — exists
in the schema and in `app/legal/jurisdictions/registry.py` today. Adding
North Carolina's actual statutes is a data task, not a schema migration.

The alternative (build for one state, generalize later) forces a rewrite the
moment the second state disagrees with the first, which it always does.

### One pipeline, many collectors

`IngestionPipeline` is source-agnostic: fetch → parse → normalize → validate →
hash → version → change-detect → persist. Only the `Collector` differs, because
only it knows a given source's shape.

This is what makes 56+ jurisdictions tractable. The alternative — a bespoke
scraper per jurisdiction — is fifty-six programs to maintain, and it is why most
nationwide legal-data efforts stall around state twelve.

### Hash-addressed versions on normalized text

`AuthorityVersion` rows are append-only and keyed by SHA-256 of the *normalized*
text. Normalization (`app/ingestion/normalizers/text.py`) is deterministic and
versioned, so a rotating session id in a footer or reflowed markup does not read
as a legal amendment, while a changed word does.

A partial unique index (`WHERE is_current`) guarantees exactly one current
version per authority, so "the current text" is never ambiguous.

Reversion is handled explicitly: when a source returns to text we already have,
the pipeline reactivates the stored row rather than inserting a duplicate.

### The review gate

`ReviewStatus` has seven values and they are never collapsed:

```
rejected < needs_review < ai_extracted < source_verified
         < cross_validated < human_reviewed < expert_reviewed
```

`SERVABLE_REVIEW_STATUSES` deliberately excludes `ai_extracted`. The research
service serves nothing below `source_verified` unless the caller explicitly
passes `include_unreviewed=true`, and even then the true status and a prominent
warning ride along, and confidence is capped by `CONFIDENCE_CEILING`.

A database `CHECK` constraint enforces that a record claiming `human_reviewed`
or `expert_reviewed` names a reviewer and a review time. You cannot fake review
through the ORM or through `psql`.

### Deterministic research

`app/services/research.py` contains no model call. Concept matching is
word-boundary alias matching; retrieval is SQL; the answer is *assembled* from
stored proposition statements and their citations rather than generated.

This is a feature. The same question returns the same retrieval every time, the
result is explainable to a lawyer line by line, and the answer cannot contain a
sentence that is not in the database.

### Ingestion input is hostile

Everything retrieved from the network is untrusted. It is never executed, never
shell-interpolated, and never handed to a model as instructions —
`wrap_untrusted_document()` fences it and neutralises fence-escape attempts.
See [`THREAT_MODEL.md`](THREAT_MODEL.md).

### Public knowledge and private documents are separated by construction

There is no user-document feature, no upload endpoint, and no student-record
table. That is not an omission; mixing public legal knowledge with private
student data requires a different security architecture (encryption at rest per
tenant, FERPA-aware access control, retention policy). It is deferred to phase 5
with its own design.

## What is deliberately not here

| Not built | Why |
|---|---|
| React/Next.js frontend | Backend correctness first, per the project brief |
| Embeddings / pgvector | `ILIKE` search is exact and explainable; the corpus is small. Phase 3 |
| Concrete LLM providers | The contract and safety rules matter first; `NullProvider` is the default |
| Real authentication | Nothing private to protect yet. The dependency seam exists in `app/api/security.py` |
| Rate limiting middleware | Architecture noted in `SECURITY.md`; belongs at the edge, not in-process |
| Celery / task queue | The CLI is sufficient for scheduled ingestion today |
| Kubernetes | Premature at this scale |
