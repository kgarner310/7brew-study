#!/usr/bin/env python
"""Generate a source manifest for every IDEA jurisdiction.

Idempotent and non-destructive: an existing manifest is left untouched unless
``--force`` is passed, so human verification work is never overwritten by a
regeneration.

Every generated manifest starts with null URLs and ``verified: false``. That is
deliberate. A manifest full of plausible-looking unverified URLs would let the
coverage report claim progress that does not exist.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import MANIFEST_DIR
from app.core.enums import CrawlStatus
from app.legal.jurisdictions import states_and_equivalents
from app.legal.manifests import (
    SITE_CATEGORIES,
    JurisdictionManifest,
    ManifestVerification,
    OfficialSite,
    dump_jurisdiction_manifest,
)

VERIFICATION_NOTE = (
    "Auto-generated skeleton. No official URL has been identified or verified for "
    "this jurisdiction yet. Populate each official_sites entry with the SEA's "
    "authoritative URL, confirm it by opening it, then set verified: true and "
    "record verified_by/verified_at. Until then this jurisdiction reports zero "
    "coverage, which is the accurate state."
)


def build_manifest(seed_slug: str) -> JurisdictionManifest:
    from app.legal.jurisdictions import by_slug

    seed = by_slug(seed_slug)
    return JurisdictionManifest(
        jurisdiction=seed.slug,
        jurisdiction_name=seed.name,
        sea=seed.sea_name,
        federal_circuit=seed.federal_circuit,
        idea_part_b_applicable=seed.idea_part_b_applicable,
        idea_part_c_applicable=seed.idea_part_c_applicable,
        official_sites={category: OfficialSite() for category in SITE_CATEGORIES},
        sources=[],
        crawl_status=CrawlStatus.NOT_STARTED,
        verification=ManifestVerification(
            status="unverified",
            populated_by="generator",
            notes=VERIFICATION_NOTE,
        ),
        notes=seed.notes,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="overwrite existing manifests")
    parser.add_argument(
        "--out",
        type=Path,
        default=MANIFEST_DIR / "jurisdictions",
        help="output directory",
    )
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    written = skipped = 0

    for seed in states_and_equivalents():
        path = args.out / f"{seed.slug}.yaml"
        if path.exists() and not args.force:
            skipped += 1
            continue
        dump_jurisdiction_manifest(build_manifest(seed.slug), path)
        written += 1

    print(f"manifests written: {written}, skipped (already present): {skipped}")
    print(f"output directory: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
