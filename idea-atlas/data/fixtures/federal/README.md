# Offline ingestion fixtures

**These files are SYNTHETIC. They are not the text of any federal regulation.**

They exist because this repository was built in an environment whose network
policy blocks outbound `.gov` traffic, so no live retrieval was possible. Rather
than fabricate regulatory text — which would poison the knowledge base with
plausible-looking fiction — each fixture is an obviously-marked placeholder that
describes what the real provision covers without pretending to quote it.

Their job is to exercise the full ingestion path offline: fetch-substitute →
parse → normalize → validate → hash → version → change-detect → persist.

Records created from these files are marked:

- `AuthorityVersion.review_status = needs_review` (never `source_verified`)
- `AuthorityVersion.metadata.synthetic_fixture = true`
- `AuthorityVersion.metadata.retrieval = "fixture"`

Running live ingestion against the real eCFR API will create a *new* version row
with the genuine text and a different hash, which is exactly the change-detection
behaviour the pipeline is built for. See `docs/INGESTION.md`.
