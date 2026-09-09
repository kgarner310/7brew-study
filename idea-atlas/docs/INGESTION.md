# Ingestion

## The pipeline

One pipeline serves every source. Only the `Collector` differs.

```
Collector.discover()        yields CollectedDocument (URL + legal identity)
        │
        ▼
DocumentFetcher.fetch()     validate_url → allowlist → DNS/IP check
        │                   redirect revalidation, size cap, content-type check
        ▼
Parser.parse()              HTML/plain → text; scripts, styles, comments stripped
        │
        ▼
normalize_text()            deterministic, versioned; what the hash covers
        │
        ▼
validate_document()         reject error pages, empty and too-short documents
        │
        ▼
sha256_text()               change detection against the current version
        │
        ├── same hash            → unchanged, no row written
        ├── known non-current    → reversion, reactivate that row
        └── new hash             → new AuthorityVersion, previous is_current=False
```

Every run writes an `IngestionRun` row, success or failure. Each document runs
inside its own savepoint, so one bad document cannot roll back the batch.

## Running it

```bash
# Offline, using the fixtures shipped in the repo
idea-atlas ingest-source ecfr-34-cfr-300 --fixtures

# Report what would change without writing
idea-atlas ingest-source ecfr-34-cfr-300 --fixtures --dry-run

# Live (refuses unless the source's URLs are verified)
idea-atlas ingest-source ecfr-34-cfr-300

# Deliberate override of that refusal
idea-atlas ingest-source ecfr-34-cfr-300 --force
```

## The offline fixture path

**No live ingestion has been run.** The build environment blocked `.gov` egress,
so `data/fixtures/federal/` holds **clearly-labelled synthetic** documents that
exercise the whole pipeline without a network.

The fixtures do **not** reproduce or paraphrase regulatory text. Inventing
plausible regulatory language would poison the knowledge base with fiction that
looks authoritative, which is worse than having no text at all. Each fixture
says what the real provision covers and states plainly that it is a placeholder.

Records created from fixtures are marked:

- `AuthorityVersion.review_status = needs_review` — never `source_verified`
- `metadata.synthetic_fixture = true`
- `metadata.retrieval = "fixture"`

Reading a file off disk is not evidence about what a publisher served, so it
cannot earn `source_verified`. There is a test asserting exactly that.

When live ingestion runs later, the real text produces a different hash and the
pipeline creates a **new version**, preserving the fixture row as history. That
is the change-detection path working as designed.

## Going live: the recommended first target

**34 C.F.R. Part 300 via the eCFR versioner API.** It is the best first target
because it is official, keyless, structured XML, and exposes amendment dates —
which is precisely what `AuthorityVersion.effective_from` needs.

```
https://www.ecfr.gov/api/versioner/v1/versions/title-34.json?part=300
https://www.ecfr.gov/api/versioner/v1/full/{date}/title-34.xml?part=300
https://www.ecfr.gov/api/versioner/v1/structure/{date}/title-34.json
```

All URLs in `data/source_manifests/federal/federal.yaml` are
`url_verified: false` and unconfirmed. Start by checking they still resolve:

```bash
idea-atlas verify-sources --live    # requires outbound .gov access
```

Then set `url_verified: true` for the sources that resolve, re-run
`idea-atlas seed`, and the CLI will permit live ingestion.

## Writing a collector

A collector answers one question: *what documents does this source offer, and
what is each one's legal identity?* Everything after that is shared.

```python
from collections.abc import Iterator
from dataclasses import dataclass

from app.core.enums import AuthorityType, IdeaPart
from app.ingestion.collectors.base import CollectedDocument


@dataclass(slots=True)
class EcfrPartCollector:
    """Enumerates sections of one CFR part via the eCFR structure API."""

    part: str
    name: str = "ecfr_part"
    version: str = "1"

    def discover(self) -> Iterator[CollectedDocument]:
        # Fetch the structure JSON through DocumentFetcher so the URL policy
        # applies. Never call httpx directly.
        for section in self._sections():
            yield CollectedDocument(
                url=f"https://www.ecfr.gov/api/versioner/v1/full/"
                f"{section.date}/title-34.xml?section={section.number}",
                canonical_citation=f"34 C.F.R. {section.number}",
                title=section.heading,
                authority_type=AuthorityType.FEDERAL_REGULATION,
                idea_part=IdeaPart.PART_B if self.part == "300" else IdeaPart.PART_C,
                court_or_agency="U.S. Department of Education",
                effective_date=section.effective_date,
                meta={"part": self.part, "section": section.number},
            )
```

Rules:

1. **Never call `httpx` directly.** Go through `DocumentFetcher` so URL
   validation, size caps, content-type checks, and retries apply.
2. **Set the legal identity accurately.** `canonical_citation` is the uniqueness
   key within a jurisdiction; a wrong one silently merges two authorities.
3. **Yield lazily.** Large sources should not be materialized in memory.
4. **Do not persist.** The pipeline owns writes.
5. **Prefer APIs and bulk downloads** over HTML scraping — more stable, cheaper,
   and usually explicitly permitted.

Add a parser only if the content type is not already handled; register it with
`register_parser()`.

## Change detection details

The hash covers **normalized** text, so:

- reflowed markup, whitespace churn, and rotating footer ids → *unchanged*
- a changed word, number, or deadline → *changed*

`NORMALIZER_VERSION` in `app/ingestion/hashing.py` must be bumped whenever
normalization changes output for unchanged input; it is stored on every version
as part of `parser_version` (e.g. `1+norm1`) so historical hashes remain
interpretable.

## Scheduling

Not yet automated. Today, run the CLI from cron or a scheduled CI job. Suggested
cadence follows `Source.crawl_frequency`:

| Source type | Frequency |
|---|---|
| Federal Register (change trigger for eCFR) | weekly |
| eCFR parts 300/303 | monthly |
| OSEP/OSERS guidance | monthly |
| Supreme Court opinions | weekly |
| State statutes and regulations | quarterly |
| Due process / complaint decisions | monthly |

A queue (Celery, or GitHub Actions on a schedule) is a phase-2 concern; the CLI
is sufficient until there are enough verified sources to need one.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `refusing live ingestion: crawl_status=urls_unverified` | Source URLs never confirmed | Verify the URL, set `url_verified: true`, re-seed, or use `--force` |
| `Host 'x' is not an allowlisted official source domain` | Non-`.gov` host | Add it to `DEFAULT_EXTRA_ALLOWED_HOSTS` only if it is genuinely official |
| `content matches an error-page signature` | Source returned a 200 error page | Check the URL by hand; the guard is working |
| `document is N chars, below the 200 floor` | Parser found the wrong container | Add a selector to `_CONTENT_SELECTORS` |
| `Content-Type 'application/octet-stream' is not permitted` | Source serves an unexpected type | Confirm it is legitimate, then extend `ALLOWED_CONTENT_TYPES` and add a parser |
| `database error (IntegrityError)` | Usually a duplicate citation | Check `canonical_citation` uniqueness within the jurisdiction |
