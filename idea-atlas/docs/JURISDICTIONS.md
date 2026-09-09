# Jurisdiction coverage

## Verification status — read this first

> **Nothing in this document or in `app/legal/jurisdictions/registry.py` has
> been verified against a primary source.**
>
> The repository was built in an environment whose network policy blocked
> outbound `.gov` traffic. Every statutory citation, federal circuit assignment,
> and SEA name below was written from model knowledge and **must be confirmed**
> before anyone relies on it. Every `JurisdictionSeed` carries
> `verification_required=True`, and a test asserts that.

Statutory citations below are given so a reviewer knows *where to look*, not as
verified assertions of what those provisions say.

---

## The coverage universe

**70 jurisdictions total**, of which **57 are IDEA grantees**.

### States — 50

All 50 states are "States" under IDEA's definition (cited as 20 U.S.C.
§ 1401(31)) with both Part B and Part C obligations. Each carries a federal
circuit for precedent scoping.

### State-equivalents — 2

| Slug | Jurisdiction | Note |
|---|---|---|
| `dc` | District of Columbia | Named as a State in § 1401(31). Typed `district` so reporting can separate it |
| `pr` | Commonwealth of Puerto Rico | Named as a State in § 1401(31) — **not** an outlying area |

### Outlying areas — 4

Cited as 20 U.S.C. § 1401(24).

| Slug | Jurisdiction | Circuit |
|---|---|---|
| `vi` | United States Virgin Islands | 3rd |
| `gu` | Guam | 9th |
| `as` | American Samoa | **null — see open question 1** |
| `mp` | Commonwealth of the Northern Mariana Islands | 9th |

### Federal agency — 1

| Slug | Jurisdiction | Note |
|---|---|---|
| `bie` | Bureau of Indian Education | Part B funds flow via the Secretary of the Interior (cited as § 1411(h)). Part C applicability differs — **open question 2** |

### Non-grantee jurisdictions — 13

Present in the schema for scoping, not because they receive IDEA funds:

- `us` — the federal government (the IDEA floor)
- `ca-1st` … `ca-11th`, `ca-dc` — the 12 federal circuits, modelled as
  jurisdictions so circuit precedent can be scoped without a parallel entity
  type. Both IDEA flags are false.

---

## Open questions requiring verification

### 1. American Samoa's federal circuit — UNRESOLVED

`federal_circuit` is deliberately **null**. American Samoa has no Article III
district court, and the appellate path for federal claims arising there is not
something I can state reliably. Guessing "9th" would have been plausible and
possibly wrong, and circuit assignment drives which precedent we treat as
binding — a wrong value produces confidently wrong answers.

**To resolve:** confirm the federal judicial path for IDEA claims arising in
American Samoa. Until then, research responses for `as` fall back to the federal
baseline without circuit-specific precedent.

### 2. Part C applicability to the Bureau of Indian Education — UNRESOLVED

`idea_part_c_applicable=False` is set for BIE. Part B funding to the Secretary
of the Interior is well established; Part C early intervention for infants and
toddlers in Indian country involves a different funding and service structure
that I cannot state confidently.

**To resolve:** confirm against Part C regulations and current BIE/OSEP
structure. This flag controls whether Part C propositions are served for `bie`.

### 3. Freely Associated States — DELIBERATELY EXCLUDED

The Federated States of Micronesia, the Republic of the Marshall Islands, and
Palau are **not** in the registry.

These jurisdictions have historically received U.S. education funding under
Compact of Free Association arrangements, and appear in some Department of
Education program contexts. Whether they are currently IDEA-covered
jurisdictions, and under what authority, is exactly the kind of question where
model knowledge is likely stale.

**Excluding them is the honest default:** a missing jurisdiction is a visible
gap, while a wrongly-included one silently implies coverage that may not exist.

**To resolve:** confirm current IDEA applicability. If covered, add with
`jurisdiction_type=outlying_area` and regenerate manifests.

### 4. Federal circuit assignments — PLAUSIBLE, UNVERIFIED

Circuit assignments for the 50 states are stable and I am reasonably confident,
but "reasonably confident" is not verification. A single wrong assignment
produces wrong binding-precedent scoping for that state.

**To resolve:** confirm all 50 against the official circuit map. This is a
one-hour task and should be done before any precedent ingestion.

### 5. SEA names — LIKELY STALE

State educational agency names change (Ohio's became "Department of Education
and Workforce"; others have been reorganized). Several entries are probably out
of date.

**Impact is low** — the field is descriptive, not functional — but it should be
corrected during per-jurisdiction verification.

---

## Manifests

One YAML file per grantee jurisdiction in `data/source_manifests/jurisdictions/`
(57 files), each declaring eight site categories:

`statutes` · `regulations` · `special_education` · `procedural_safeguards` ·
`due_process_decisions` · `state_complaints` · `guidance` · `forms`

**Every URL is currently `null` with `verified: false`.** That is deliberate: a
manifest pre-filled with plausible-but-unchecked URLs would let the coverage
report imply progress that does not exist, and would create verification work
that looks finished.

### Verifying a jurisdiction

1. Open the manifest, e.g. `data/source_manifests/jurisdictions/nc.yaml`
2. For each category, find the **official** SEA or state-government URL
3. **Open it** and confirm it is the authoritative page
4. Set `url`, `verified: true`, `verified_by`, `verified_at`
5. Record copyright and terms-of-service posture in `notes`
6. Leave a category `null` with a note where no public archive exists — a
   documented gap is a correct answer
7. Set `verification.status` and `reviewed_by`
8. Run `idea-atlas verify-sources` to confirm the count moved

Use the "Jurisdiction source verification" issue template to track each one.

### Suggested verification order

Highest population and litigation volume first, so early coverage helps the most
families:

`ca` · `tx` · `fl` · `ny` · `pa` · `il` · `oh` · `ga` · `nc` · `mi`

Then the rest of the states, then DC and Puerto Rico, then the outlying areas
and BIE (whose sources are hardest to locate and should not block the states).

### Regenerating manifests

```bash
python scripts/generate_jurisdiction_manifests.py          # non-destructive
python scripts/generate_jurisdiction_manifests.py --force  # overwrites verified work
```

The generator skips existing files by default so human verification is never
clobbered. `--force` will destroy verification work — use with care.
