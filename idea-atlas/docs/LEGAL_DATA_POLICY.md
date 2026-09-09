# Legal data policy

Rules governing what this platform ingests, stores, asserts, and serves.
These are product requirements enforced in code, not aspirations.

> **Nothing in this repository has been reviewed by a lawyer.** This document
> describes the policy the system implements. It is not a legal opinion, and
> counsel review is required before production-scale ingestion — see
> [Open questions](#open-questions-for-counsel).

---

## 1. Primary sources first

Ingest from the government body that publishes of record. In order of
preference:

1. The promulgating or publishing agency (eCFR, OLRC, the issuing court)
2. GovInfo / GPO authenticated collections
3. State SEA official sites
4. Non-official public-domain mirrors (Caselaw Access Project, LII), **only**
   for backfill and corroboration, and always with `official_source=false`

Every `Source` row records `publisher`, `base_url`, `official_source`,
`copyright_status`, `commercial_reuse_status`, `license_notes`, and
`terms_of_service_url`.

## 2. Never ingest proprietary editorial content

**Prohibited, without exception:**

- Westlaw, LexisNexis, Bloomberg Law, and equivalent subscription products
- Headnotes, syllabi (publisher-written), key number systems, topic hierarchies
- Proprietary citators (Shepard's, KeyCite) and their signals
- Editorial annotations, practice commentary, publisher-written summaries
- Star pagination apparatus and other publisher-added editorial features
- Anything behind a paywall or requiring authentication we do not hold

The underlying judicial opinion is an uncopyrightable edict of government
(*Banks v. Manchester*; *Georgia v. Public.Resource.Org*, 590 U.S. 255 (2020)).
The publisher's editorial layer around it is not. Take the former, never the
latter.

Enforcement: `app/ingestion/validators/document.py` warns when retrieved text
carries proprietary-publisher markers, and a test asserts that no commercial
publisher appears in the source registry.

## 3. Copyright posture is a column

| `copyright_status` | Meaning |
|---|---|
| `us_government_public_domain` | Federal work, no copyright (17 U.S.C. § 105) |
| `government_edict` | Uncopyrightable edict — judicial opinions, state codes |
| `public_domain_other` | Public domain on other grounds |
| `proprietary` | Copyrighted. **Do not ingest** |
| `mixed` | Free primary text inside a proprietary container. Extract carefully or skip |
| `unknown` | Default. **Requires review before scale ingestion** |

`commercial_reuse_status` is tracked separately, because "we may read it" and
"we may redistribute it commercially" are different questions.

## 4. Government text and our annotations never mix

`authority_version.raw_text` and `normalized_text` hold retrieved source text
and are never edited. Our interpretations live in `proposition`,
`proposition_authority.notes`, and `legal_concept` — different tables entirely.

There is no code path that writes an interpretation into an authority version.

## 5. Review status is never collapsed

Seven statuses, ordered. `ai_extracted` is **not** servable. The research
endpoint serves nothing below `source_verified` unless the caller explicitly
opts in, and then:

- the true `review_status` is returned unchanged
- a `NOT REVIEWED` warning is included
- `confidence` is capped by `CONFIDENCE_CEILING` (0.25 for `needs_review`)

A database `CHECK` constraint prevents any row from claiming `human_reviewed` or
`expert_reviewed` without naming a reviewer and a timestamp.

**AI-generated interpretation is never presented as human-reviewed.** This is
the single most important rule in the project.

## 6. Every proposition traces to authority

A proposition without a linked authority is `authority_status='unsupported'`.
The research service reports these explicitly rather than serving them silently.

AI-extracted candidates must carry a `supporting_quote` that appears **verbatim**
in the source text. `filter_grounded()` discards those that do not — an invented
quote is a hallucination by definition and never reaches the database.

## 7. Refuse rather than guess

When the knowledge base cannot support an answer, the response is
`sufficient_coverage: false` with an empty answer and an explanation. It is
never filled with plausible prose.

The same rule applies to data authoring: an unverified URL stays `verified:
false`, an uncertain jurisdiction question is documented in
[`JURISDICTIONS.md`](JURISDICTIONS.md) rather than resolved by guessing, and a
manifest with no confirmed sources reports zero coverage.

## 8. Legal information, not legal advice

The product is research infrastructure. It describes what sources say. It does
not:

- apply law to a specific child's facts
- recommend a course of action
- create an attorney-client relationship

Every research response carries a disclaimer. Unauthorized-practice-of-law rules
vary by state; counsel review is required before any parent-facing or
advice-shaped feature (roadmap phase 5).

## 9. Robots, rate limits, and terms

- Respect `robots.txt` and published rate limits
- Identify honestly via User-Agent (`idea-atlas/0.1 (+repo URL)`)
- Prefer official APIs and bulk downloads over HTML scraping
- Where terms are unclear, mark `commercial_reuse_status=requires_legal_review`
  and do not ingest at scale until reviewed
- Where terms prohibit automated access, set `retrieval_method=manual`

## 10. Corrections

Incorrect legal information is a defect with real consequences for families.
Use the "Legal data correction" issue template. A correction must cite a primary
source; a correction without one cannot be applied.

---

## Open questions for counsel

Recorded honestly rather than assumed away:

1. **State code copyright.** *Georgia v. Public.Resource.Org* covers annotations
   produced by legislative authority. Several states publish codes through
   vendors that assert copyright in the compilation. Per-state analysis needed.
2. **Terms of service versus copyright.** A public-domain document served under
   restrictive terms raises a contract question independent of copyright.
3. **Due process and complaint decisions.** Redaction practice varies by state.
   Some publish decisions containing student-identifying information. We need a
   policy for what we will *not* republish even when the state does.
4. **Commercial redistribution.** Reading is not redistributing. Before any paid
   API tier (phase 4), confirm reuse posture source by source.
5. **UPL exposure.** At what point does jurisdiction-specific, issue-specific
   output become legal advice in the strictest states?
6. **Caselaw Access Project terms.** Current terms need confirmation before
   commercial use.
