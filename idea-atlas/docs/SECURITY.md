# Security

Controls implemented now, and controls deliberately deferred with the reason.
Attack analysis lives in [`THREAT_MODEL.md`](THREAT_MODEL.md).

## Current security posture

This phase serves **public legal information only**. There are:

- no user accounts, no child accounts
- no private student records
- no document upload
- no personalized legal-advice engine

That is a deliberate scope decision. Private user documents require a different
architecture (per-tenant encryption, FERPA-aware access control, retention
policy) and are deferred to roadmap phase 5 with their own design and review.

The main asset to protect today is **integrity**: the knowledge base must not be
poisoned, and the review gate must not be bypassable.

---

## Implemented

### Secrets

- All configuration is environment-driven (`app/core/config.py`, `IDEA_ATLAS_` prefix)
- No secret has a usable default value
- `.gitignore` excludes `.env`, `*.pem`, `*.key`; only `.env.example` is committed
- Provider API keys are read from the provider's own conventional variable, so
  `.env` never has to hold one
- Secrets are never logged. `Settings` is frozen and never serialized to a response
- `docker-compose.yml` credentials are development-only, on a loopback-bound port

### Outbound requests (SSRF) — `app/ingestion/url_safety.py`

The highest-risk surface: a service that fetches attacker-influencable URLs.

1. `https` only; no embedded credentials; default port only
2. Domain allowlist — `.gov`/`.mil` wholesale (closed, government-verified
   TLDs); every other host explicitly listed
3. DNS resolution checked against private, loopback, link-local, multicast,
   reserved, and unspecified ranges — including IPv4-mapped and 6to4 IPv6 forms,
   so `::ffff:169.254.169.254` cannot slip through
4. **Redirects followed manually, revalidating every hop** — an allowlisted host
   cannot bounce ingestion into the private network. Capped at 5 hops
5. Validation happens *before* any connection is attempted

Disabling the allowlist (test harness only) does **not** disable the IP checks.
There is a test asserting exactly that.

### Response handling — `app/ingestion/fetcher.py`

- `Content-Length` rejected up front when over cap
- Body streamed with a running byte counter, so a lying or absent header cannot
  exhaust memory (default cap 25 MiB)
- `Content-Type` allowlist checked before the body is read
- Bounded retries with exponential backoff, on transport errors and 5xx/429 only
- No cookies, no auth headers, no credential forwarding
- Honest User-Agent, applied per-request so an injected client cannot drop it

### Untrusted input handling

Retrieved content is hostile input:

- never executed, never `eval`'d, never interpolated into a shell — there is no
  shell execution anywhere in the ingestion path
- `<script>`, `<style>`, and HTML comments stripped before text extraction
- fixture paths contained to the fixture root (`is_relative_to` check) so a
  manifest cannot read `/etc/passwd`
- database errors are logged by exception **type only**, because SQLAlchemy
  error strings can carry the full offending row including document text

### Prompt injection — `app/services/ai/base.py`

- Source text is fenced by `wrap_untrusted_document()` with an explicit preamble
  telling the model that fenced content is data and must never be obeyed
- Fence markers appearing *inside* the document are neutralised, so a document
  cannot close the fence early and escape into instruction context
- Models never receive secrets — prompts are built from public legal text and
  our own taxonomy
- Model output is not trusted: candidates must carry a verbatim supporting quote
  or they are discarded

### API

- Pydantic v2 validation on every input; `extra="forbid"` on request models, so
  an unexpected field is a 422 rather than silently ignored
- Request body size limit (default 1 MiB) via `MaxBodySizeMiddleware`
- **CORS deny-by-default** — an empty origin allowlist means no cross-origin
  browser access; credentials are never allowed
- Only `GET` and `POST` are permitted when CORS is enabled
- Paging bounded (`limit` max 200) so a client cannot request the world
- Error handlers return stable messages; internals go to the structured log
- Every request gets an `x-request-id`, echoed back and bound to the log context

### SQL injection

All database access goes through SQLAlchemy ORM constructs with bound
parameters. There is no string-formatted SQL anywhere in `app/`.

### Container

- Multi-stage build; the runtime image carries no build toolchain
- Runs as an unprivileged user (uid 10001, `nologin`)
- `read_only: true`, `cap_drop: ALL`, `no-new-privileges:true` in compose
- Migrations are **not** run on container start — schema change is an explicit,
  auditable step

### Auditability

- `ingestion_run` records every attempt including failures
- `review_event` is an append-only trail whose `entity_id` is deliberately not a
  foreign key, so it outlives the row it describes
- `authority_version` is append-only and hash-addressed; both normalized and raw
  hashes are stored, so tampering is detectable
- Database `CHECK` constraint prevents claiming human review without a reviewer

### Supply chain

- Dependencies pinned to minimum versions in `pyproject.toml`; `uv` resolves
- `ruff` runs `flake8-bandit` (`S`) rules in CI
- CI has `permissions: contents: read` only

---

## Separation of ingestion and API privileges

**Design (documented; not yet enforced in code.)** The API is read-mostly; the
ingestion worker writes. They should not share a database role.

```sql
-- API role: read everything, write nothing.
CREATE ROLE idea_atlas_api LOGIN PASSWORD :'api_password';
GRANT CONNECT ON DATABASE idea_atlas TO idea_atlas_api;
GRANT USAGE ON SCHEMA public TO idea_atlas_api;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO idea_atlas_api;

-- Ingestion role: write the tables it owns, and nothing else.
CREATE ROLE idea_atlas_ingest LOGIN PASSWORD :'ingest_password';
GRANT CONNECT ON DATABASE idea_atlas TO idea_atlas_ingest;
GRANT USAGE ON SCHEMA public TO idea_atlas_ingest;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO idea_atlas_ingest;
GRANT INSERT, UPDATE ON authority, authority_version, ingestion_run, source
    TO idea_atlas_ingest;
GRANT INSERT ON review_event TO idea_atlas_ingest;

-- The review trail is append-only for everyone except the migration role.
REVOKE UPDATE, DELETE ON review_event FROM idea_atlas_api, idea_atlas_ingest;

-- Migrations run as a separate owner role, used only by `idea-atlas db upgrade`.
```

Tracked in [`NEXT_STEPS.md`](NEXT_STEPS.md).

## Rate limiting

**Design (deferred).** Belongs at the edge, not in-process, so it survives
multiple API replicas.

- Anonymous read endpoints: per-IP token bucket at the reverse proxy or CDN
- `POST /v1/research`: lower limit — it is the most expensive endpoint
- Phase 4 API keys: per-key quotas with usage metering, enforced in a shared
  store (Redis), not per-process memory
- Ingestion is self-limiting per source via `crawl_frequency`

The `Principal` seam in `app/api/security.py` is where per-key limits attach.

## Authentication

`app/api/security.py` defines `Principal` and `Scope` and a `current_principal`
dependency that today returns anonymous read-only. The `Authorization` header is
accepted and ignored rather than rejected, so clients can start sending
credentials before the server enforces them.

This is deliberately not overbuilt: there is nothing private to protect yet.
Phase 4 implements API keys against this seam without restructuring the API.

## Reporting a vulnerability

Open a private security advisory on the repository. Do not open a public issue
for anything exploitable.
