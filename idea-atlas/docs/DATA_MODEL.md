# Data model

Ten tables, eighteen native PostgreSQL enum types, fifteen check constraints.
Everything below is created by
`migrations/versions/2fdcaa0173ae_initial_legal_knowledge_schema.py`.

Conventions: UUID primary keys generated application-side; all timestamps
`timestamptz` in UTC; free-form JSON in a `metadata` JSONB column exposed on the
model as `.meta`; constraint names follow the convention in `app/db/base.py` so
Alembic autogenerate is stable.

## Entity relationships

```
 Jurisdiction ──┬──< Source ──< IngestionRun
   │  (self-ref)│      │
   │            └──────┴──< Authority ──< AuthorityVersion   (hash-addressed)
   │                          │  │
   │                          │  └──< AuthorityRelationship >──┐ (self-ref graph)
   │                          │                                │
   │                          └──< PropositionAuthority >──┐   │
   │                                                       │   │
   └──< Proposition >─────────────────────────────────────┘   │
            │                                                  │
     LegalConcept (self-ref tree)                               │
                                                                │
     ReviewEvent  ── entity_type + entity_id (no FK, by design) ┘
```

## Tables

### `jurisdiction`
The IDEA coverage universe: 50 states, DC, Puerto Rico, four outlying areas, the
Bureau of Indian Education, the federal government, and the 12 federal circuits.

Circuits are modelled as jurisdictions (`jurisdiction_type='federal_circuit'`,
both IDEA flags false) so circuit precedent can be scoped without a parallel
entity type.

Constraints: unique `slug`; a jurisdiction cannot be its own parent;
`postal_code` must be uppercase.

### `source`
The source registry — every place we retrieve text from, with its **copyright
posture** (`copyright_status`, `commercial_reuse_status`, `license_notes`,
`terms_of_service_url`) recorded as columns, not prose. `official_source` is
true only for the government body that publishes of record.

`crawl_status` gates ingestion: the CLI refuses live ingestion unless a source
is `urls_verified`.

### `authority`
A single legal authority — a statute section, a regulation, an opinion, a policy
letter. This row is the **stable identity**; the text lives in
`authority_version`, because authorities are amended and every historical text
must remain retrievable with its dates.

Constraints: unique `(jurisdiction_id, canonical_citation)`;
`superseded_date >= effective_date`.

### `authority_version`
One retrieved text, addressed by SHA-256. Append-only.

- `sha256` — hash of `normalized_text`; this is what change detection compares
- `raw_sha256` — hash of the untouched bytes, for byte-level integrity audit
- `parser_name` / `parser_version` — records `1+norm1`, so a normalizer change
  is traceable
- `is_current` — exactly one per authority, enforced by a **partial unique
  index** `WHERE is_current`
- `review_status` — `source_verified` only for real network retrieval;
  fixture-loaded text is `needs_review`

Constraints: unique `(authority_id, sha256)`; both hashes exactly 64 chars;
effective dates ordered.

### `authority_relationship`
Directed citator-style edges: `cites`, `interprets`, `supersedes`, `overrules`,
`distinguishes`, `applies`, `implements`, `abrogates`.

Constraints: no self-edges; unique per `(source, target, relationship_type)` —
so A can both `cite` and `distinguish` B, but not `cite` it twice.

### `legal_concept`
The IDEA subject-matter taxonomy: 43 jurisdiction-neutral concepts in a tree.
`aliases` (text array) carries practitioner shorthand — `mtss`, `rti`,
`stay put`, `comp ed` — which is what drives search and research matching.

Anything that varies by jurisdiction is a proposition, not a concept.

### `proposition`
The unit the platform answers with: one normative statement, scoped to a
concept, a jurisdiction (`NULL` means the universal federal floor), and a time
window.

Constraints:
- `confidence` between 0 and 1
- `statement` not blank
- effective dates ordered
- **`reviewed_records_name_a_reviewer`** — a row claiming `human_reviewed` or
  `expert_reviewed` must have both `reviewed_by` and `reviewed_at`. This is the
  database refusing to let anyone fake human review.

### `proposition_authority`
Which authority supports (or limits, or contradicts) which proposition, with
`weight` for citation ordering, `pin_cite`, and `quoted_text` for the verbatim
supporting excerpt.

A proposition with no rows here is `authority_status='unsupported'` and the
research service flags it.

### `ingestion_run`
Every ingestion attempt, including failures. `documents_seen`, `new_documents`,
`changed_documents`, `unchanged_documents`, `error_count`, and an `errors` text
column that holds error *summaries only* — never response bodies.

### `review_event`
The append-only review trail: who asserted what status, when, with what note.

`entity_id` is deliberately **not** a foreign key. The trail must outlive the
row it describes; a deleted authority does not erase the record that someone
once marked it verified. Nothing in the application updates or deletes these
rows, and production should enforce that with database grants
(see [`SECURITY.md`](SECURITY.md)).

## Review status vocabulary

| Status | Meaning |
|---|---|
| `rejected` | Reviewed and found wrong |
| `needs_review` | Default. Includes all fixture and seed data |
| `ai_extracted` | Produced by a model. **Never servable** |
| `source_verified` | Text provably matches the retrieved official source, hash-checked |
| `cross_validated` | Corroborated by an independent source or method |
| `human_reviewed` | A person reviewed it (requires a named reviewer) |
| `expert_reviewed` | A qualified special-education legal professional reviewed it |

`SERVABLE_REVIEW_STATUSES` = the bottom four of `source_verified` upward.

## Why native enums

Every bounded vocabulary is a real PostgreSQL enum type, not a varchar with a
convention. The database rejects out-of-vocabulary values, so a typo in a script
fails loudly instead of quietly creating a new "review status" nobody notices.

The cost is that adding a value requires a migration. That friction is the
point: these vocabularies encode legal meaning.

Note that the autogenerated Alembic `downgrade` does **not** drop native enum
types; the initial migration adds explicit `DROP TYPE` statements so a
downgrade-then-upgrade cycle works. CI verifies that round-trip on every run.
