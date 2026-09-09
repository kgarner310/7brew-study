---
name: Jurisdiction source verification
about: Populate and verify the official source URLs for one jurisdiction
title: "Verify sources: <JURISDICTION NAME>"
labels: ["jurisdiction-coverage", "needs-verification"]
---

## Jurisdiction

Slug: `<e.g. nc>`
Manifest: `data/source_manifests/jurisdictions/<slug>.yaml`

## Task

For each category below, find the **official** SEA or state-government URL,
open it to confirm it is the authoritative page, then set `url`, `verified: true`,
`verified_by`, and `verified_at` in the manifest.

- [ ] `statutes` — the state special-education statute
- [ ] `regulations` — the state administrative rules
- [ ] `special_education` — the SEA special-education homepage
- [ ] `procedural_safeguards` — the procedural safeguards notice
- [ ] `due_process_decisions` — the due process decision archive
- [ ] `state_complaints` — the state complaint decision archive
- [ ] `guidance` — SEA guidance documents
- [ ] `forms` — official IEP / evaluation forms

## Rules

- Official government sources only. No commercial publishers.
- Leave a category `null` with a note if no public archive exists — a documented
  gap is a correct answer, a guessed URL is not.
- Record the copyright and terms-of-service posture in `notes`.

## Definition of done

- [ ] `idea-atlas verify-sources` shows the new verified count for this jurisdiction
- [ ] Manifest `verification.status` updated and `reviewed_by` set
