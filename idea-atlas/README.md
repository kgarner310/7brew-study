# IDEA Atlas

Jurisdiction-aware legal information infrastructure for the **Individuals with
Disabilities Education Act (IDEA)**.

IDEA Atlas is not a chatbot with a legal prompt. The durable asset is a
**verified legal knowledge graph with source provenance**: primary-source text,
addressed by content hash and versioned over time, linked to jurisdiction-scoped
legal propositions that each trace back to the authority that supports them. The
language model is optional, replaceable, and never authoritative.

> **Legal information, not legal advice.** Every substantive API response
> reports the review status of the records behind it and carries a disclaimer.
> See [`docs/LEGAL_DATA_POLICY.md`](docs/LEGAL_DATA_POLICY.md).

---

## Honest status

This is a **working foundation**, not a populated knowledge base. Read this
before you trust anything the system returns.

| Area | State |
|---|---|
| Schema, migrations, API, CLI, ingestion pipeline | Working and tested (274 tests, 95% coverage) |
| Nationwide jurisdiction model | Complete — 70 jurisdictions, 57 IDEA grantees |
| IDEA concept taxonomy | Complete — 43 concepts |
| Jurisdiction source manifests | 57 files exist; **0 URLs verified** |
| Federal source manifest | 13 sources declared; **0 URLs verified** |
| Ingested primary-source text | **None.** Only synthetic fixtures |
| Legal propositions | 4 demo propositions, all `needs_review`, none servable |

**No legal text has been ingested from any official source.** The build
environment blocked outbound `.gov` traffic, so the ingestion path was proved
end-to-end against clearly-labelled synthetic fixtures instead. Nothing in this
repository was verified against primary sources. See
[`NEXT_STEPS.md`](NEXT_STEPS.md).

Because of that, `POST /v1/research` currently answers **`sufficient_coverage:
false`** for every question. That is the system working correctly: it refuses to
answer beyond its evidence.

---

## Quick start from a clean machine

### Option A — Docker (nothing but Docker required)

```bash
git clone https://github.com/kgarner310/idea-atlas.git
cd idea-atlas
cp .env.example .env

docker compose up -d db          # Postgres 16, waits until healthy
docker compose run --rm migrate  # apply migrations
docker compose up -d api         # API on http://127.0.0.1:8000

curl -s http://127.0.0.1:8000/health
```

### Option B — Local Python (what the maintainers run)

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and a reachable
PostgreSQL 16.

```bash
git clone https://github.com/kgarner310/idea-atlas.git
cd idea-atlas
cp .env.example .env                       # edit IDEA_ATLAS_DATABASE_URL if needed

uv venv --python 3.12
source .venv/bin/activate                  # Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"

# Start Postgres however you like; with Docker:
docker compose up -d db

idea-atlas db upgrade head                 # create the schema
idea-atlas seed --reference-only           # 70 jurisdictions, 43 concepts, 13 sources
idea-atlas ingest-source ecfr-34-cfr-300 --fixtures   # offline end-to-end ingestion
idea-atlas seed                            # demo propositions (now that authorities exist)

idea-atlas show-coverage                   # nationwide coverage table
idea-atlas run-api                         # http://127.0.0.1:8000/docs
```

### Verify it works

```bash
curl -s localhost:8000/health
curl -s "localhost:8000/v1/jurisdictions?jurisdiction_type=state&limit=1"
curl -s localhost:8000/v1/concepts/initial-evaluation

# Refuses to answer — nothing has cleared review. This is correct.
curl -s -X POST localhost:8000/v1/research \
  -H 'content-type: application/json' \
  -d '{"issue":"Can MTSS delay an IDEA evaluation?","jurisdiction":"NC"}'

# Same query, explicitly asking to see unreviewed material.
curl -s -X POST localhost:8000/v1/research \
  -H 'content-type: application/json' \
  -d '{"issue":"Can MTSS delay an IDEA evaluation?","jurisdiction":"NC","include_unreviewed":true}'
```

---

## Running the checks

```bash
ruff format --check .          # formatting
ruff check .                   # lint (incl. flake8-bandit security rules)
mypy app tests scripts         # strict type checking
pytest -q                      # 274 tests; needs the test database

# Migrations must round-trip cleanly:
alembic upgrade head && alembic downgrade base && alembic upgrade head
```

`pytest` uses `IDEA_ATLAS_TEST_DATABASE_URL` and refuses to run unless
`IDEA_ATLAS_ENV=test`, so it can never touch your development data.

---

## CLI

| Command | What it does |
|---|---|
| `idea-atlas version` | Version and resolved environment |
| `idea-atlas db upgrade head` | Apply migrations |
| `idea-atlas db downgrade base` | Revert (drops enum types too) |
| `idea-atlas seed` | Reference data + demo propositions |
| `idea-atlas seed --reference-only` | Jurisdictions, concepts, sources only |
| `idea-atlas ingest-source <slug> --fixtures` | Offline ingestion |
| `idea-atlas ingest-source <slug>` | Live ingestion (refuses unverified URLs) |
| `idea-atlas ingest-jurisdiction <slug>` | Ingest a jurisdiction's verified sources |
| `idea-atlas verify-sources` | Audit which URLs are declared vs verified |
| `idea-atlas verify-sources --live` | Actually fetch each URL (needs `.gov` access) |
| `idea-atlas show-coverage` | Nationwide coverage table |
| `idea-atlas run-api` | Start the API |
| `idea-atlas export-openapi` | Write `openapi.json` |

---

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness plus database reachability |
| `GET` | `/v1/jurisdictions` | List jurisdictions |
| `GET` | `/v1/jurisdictions/{slug}` | One jurisdiction with real coverage counts |
| `GET` | `/v1/concepts` | The IDEA taxonomy |
| `GET` | `/v1/concepts/{slug}` | One concept with children and aliases |
| `GET` | `/v1/authorities` | List authorities |
| `GET` | `/v1/authorities/{id}` | One authority with version history |
| `GET` | `/v1/propositions` | List propositions (review status always shown) |
| `GET` | `/v1/propositions/{id}` | One proposition with supporting authorities |
| `GET` | `/v1/search?q=` | Keyword search across concepts, propositions, authorities |
| `POST` | `/v1/research` | Jurisdiction-scoped research, DB-backed and deterministic |

Interactive docs at `/docs`; OpenAPI at `/openapi.json`.

---

## Documentation

| Document | What it covers |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System shape and the decisions behind it |
| [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) | Every table, constraint, and why it exists |
| [`docs/LEGAL_DATA_POLICY.md`](docs/LEGAL_DATA_POLICY.md) | Copyright, sourcing rules, review statuses |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Controls implemented and deliberately deferred |
| [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) | Adversaries, attack paths, residual risk |
| [`docs/JURISDICTIONS.md`](docs/JURISDICTIONS.md) | Coverage universe and open verification questions |
| [`docs/INGESTION.md`](docs/INGESTION.md) | How to add a collector and run live ingestion |
| [`docs/TOKEN_EFFICIENCY.md`](docs/TOKEN_EFFICIENCY.md) | Detail levels, estimation, benchmarking plan |
| [`docs/LOCAL_AI.md`](docs/LOCAL_AI.md) | Free and local model workflow for development |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Phases 1–5 |
| [`NEXT_STEPS.md`](NEXT_STEPS.md) | What is done, blocked, and exactly what to run next |

---

## Stack

Python 3.12 · FastAPI · SQLAlchemy 2.x · Alembic · PostgreSQL 16 · Pydantic v2 ·
httpx · Typer · structlog · pytest · Ruff · mypy (strict) · Docker · GitHub Actions

No paid service is required to run, develop, or test this project.

## Licence

Apache-2.0 for the code. Ingested primary-source legal text carries its own
provenance and licensing metadata per source — see
[`docs/LEGAL_DATA_POLICY.md`](docs/LEGAL_DATA_POLICY.md).
