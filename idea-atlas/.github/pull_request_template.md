## What this changes

<!-- One paragraph. What behaviour is different after this PR? -->

## Legal-data integrity checklist

Tick every box that applies, or write N/A.

- [ ] No legal text, citation, or holding was written from memory and presented as verified.
- [ ] Any new source is an official government publisher, or its non-official status is recorded on the `Source` row.
- [ ] New or changed records carry an accurate `review_status`. Nothing was promoted to `human_reviewed` or `expert_reviewed` without an actual human review, named in a `ReviewEvent`.
- [ ] Manifest URLs added here are marked `verified: false` unless a human opened them and confirmed.
- [ ] No proprietary editorial content (headnotes, syllabi, citators, paywalled annotations) is ingested or stored.

## Security checklist

- [ ] No secret, key, token, or credential is committed.
- [ ] Any new outbound fetch goes through `app.ingestion.fetcher` / `validate_url` rather than calling `httpx` directly.
- [ ] Retrieved content is treated as untrusted data: not executed, not shell-interpolated, not passed to a model as instructions.
- [ ] New API input is validated by a Pydantic model with `extra="forbid"`.

## Verification

- [ ] `ruff format --check .`
- [ ] `ruff check .`
- [ ] `mypy app tests scripts`
- [ ] `pytest`
- [ ] Migrations round-trip (`alembic upgrade head && alembic downgrade base && alembic upgrade head`)

## Notes for the reviewer

<!-- Anything unverified, deferred, or that you want a second opinion on. -->
