"""Jurisdiction registry, taxonomy, and manifest integrity."""

from __future__ import annotations

import pytest

from app.core.enums import JurisdictionType
from app.legal.jurisdictions import ALL_JURISDICTIONS, by_slug, states_and_equivalents
from app.legal.manifests import (
    SITE_CATEGORIES,
    load_all_jurisdiction_manifests,
    load_federal_manifest,
)
from app.legal.taxonomy import IDEA_CONCEPTS, concept_by_slug

#: Concepts the product specification requires.
REQUIRED_CONCEPTS = {
    "child-find",
    "evaluation",
    "initial-evaluation",
    "reevaluation",
    "eligibility",
    "specific-learning-disability",
    "other-health-impairment",
    "autism",
    "fape",
    "iep",
    "present-levels",
    "annual-goals",
    "specially-designed-instruction",
    "related-services",
    "supplementary-aids-and-services",
    "lre",
    "placement",
    "parent-participation",
    "prior-written-notice",
    "procedural-safeguards",
    "independent-educational-evaluation",
    "state-complaint",
    "due-process",
    "mediation",
    "resolution-session",
    "discipline",
    "manifestation-determination",
    "change-of-placement",
    "interim-alternative-educational-setting",
    "esy",
    "transportation",
    "assistive-technology",
    "transition-services",
    "transfer-students",
    "private-school-placement",
    "unilateral-placement",
    "compensatory-education",
    "maintenance-of-effort",
    "part-c",
    "ifsp",
    "early-intervention-services",
    "natural-environments",
    "part-c-to-part-b-transition",
}


class TestJurisdictionRegistry:
    def test_has_exactly_fifty_states(self) -> None:
        states = [j for j in ALL_JURISDICTIONS if j.jurisdiction_type is JurisdictionType.STATE]
        assert len(states) == 50

    def test_covers_dc_pr_and_the_four_outlying_areas(self) -> None:
        slugs = {j.slug for j in ALL_JURISDICTIONS}
        assert {"dc", "pr", "vi", "gu", "as", "mp", "bie"} <= slugs

    def test_grantee_count_is_fifty_seven(self) -> None:
        """50 states + DC + PR + 4 outlying areas + BIE."""
        assert len(states_and_equivalents()) == 57

    def test_slugs_are_unique(self) -> None:
        slugs = [j.slug for j in ALL_JURISDICTIONS]
        assert len(slugs) == len(set(slugs))

    def test_postal_codes_are_unique_and_uppercase(self) -> None:
        codes = [j.postal_code for j in ALL_JURISDICTIONS if j.postal_code]
        assert len(codes) == len(set(codes))
        assert all(code == code.upper() and len(code) == 2 for code in codes)

    def test_every_parent_slug_resolves(self) -> None:
        slugs = {j.slug for j in ALL_JURISDICTIONS}
        assert all(j.parent_slug in slugs for j in ALL_JURISDICTIONS if j.parent_slug)

    def test_every_state_has_a_circuit(self) -> None:
        states = [j for j in ALL_JURISDICTIONS if j.jurisdiction_type is JurisdictionType.STATE]
        assert all(j.federal_circuit for j in states)

    def test_american_samoa_circuit_left_null_pending_verification(self) -> None:
        """Guessing here would be worse than admitting the gap."""
        assert by_slug("as").federal_circuit is None
        assert "VERIFY" in (by_slug("as").notes or "")

    @pytest.mark.parametrize(("query", "expected"), [("NC", "nc"), ("nc", "nc"), (" Nc ", "nc")])
    def test_lookup_is_case_and_space_insensitive(self, query: str, expected: str) -> None:
        assert by_slug(query).slug == expected

    def test_unknown_slug_raises(self) -> None:
        with pytest.raises(KeyError):
            by_slug("atlantis")

    def test_everything_is_flagged_for_verification(self) -> None:
        """Nothing in this registry was confirmed against a primary source."""
        assert all(j.verification_required for j in ALL_JURISDICTIONS)


class TestTaxonomy:
    def test_covers_every_required_concept(self) -> None:
        assert {c.slug for c in IDEA_CONCEPTS} >= REQUIRED_CONCEPTS

    def test_slugs_unique(self) -> None:
        slugs = [c.slug for c in IDEA_CONCEPTS]
        assert len(slugs) == len(set(slugs))

    def test_no_dangling_parents(self) -> None:
        slugs = {c.slug for c in IDEA_CONCEPTS}
        assert all(c.parent_slug in slugs for c in IDEA_CONCEPTS if c.parent_slug)

    def test_no_parent_cycles(self) -> None:
        parents = {c.slug: c.parent_slug for c in IDEA_CONCEPTS}
        for slug in parents:
            seen: set[str] = set()
            cursor: str | None = slug
            while cursor is not None:
                assert cursor not in seen, f"cycle through {slug}"
                seen.add(cursor)
                cursor = parents.get(cursor)

    def test_mtss_and_rti_route_to_initial_evaluation(self) -> None:
        aliases = concept_by_slug("initial-evaluation").aliases
        assert "mtss" in aliases
        assert "rti" in aliases

    def test_every_concept_has_a_description(self) -> None:
        assert all(len(c.description) > 20 for c in IDEA_CONCEPTS)


class TestManifests:
    def test_one_manifest_per_grantee_jurisdiction(self) -> None:
        manifests = load_all_jurisdiction_manifests()
        assert len(manifests) == 57
        assert {m.jurisdiction for m in manifests} == {j.slug for j in states_and_equivalents()}

    def test_every_manifest_declares_all_site_categories(self) -> None:
        for manifest in load_all_jurisdiction_manifests():
            assert set(manifest.official_sites) == set(SITE_CATEGORIES)

    def test_no_jurisdiction_url_claims_verification(self) -> None:
        """Coverage must not be overstated: nothing has been verified yet."""
        for manifest in load_all_jurisdiction_manifests():
            assert manifest.verified_site_count == 0
            assert manifest.verification.status == "unverified"

    def test_federal_manifest_covers_the_required_source_families(self) -> None:
        slugs = {s.slug for s in load_federal_manifest().sources}
        assert "olrc-uscode-title20-ch33" in slugs  # statute
        assert "ecfr-34-cfr-300" in slugs  # Part B regs
        assert "ecfr-34-cfr-303" in slugs  # Part C regs
        assert "osep-policy-letters" in slugs  # OSEP
        assert "ocr-guidance" in slugs  # OCR intersection
        assert "supremecourt-opinions" in slugs  # SCOTUS
        assert "govinfo-uscourts" in slugs  # federal appellate

    def test_federal_manifest_is_marked_unverified(self) -> None:
        manifest = load_federal_manifest()
        assert manifest.verification.status == "unverified"
        assert all(not source.url_verified for source in manifest.sources)

    def test_no_commercial_publisher_is_a_primary_source(self) -> None:
        """Westlaw/Lexis and friends must never appear in the source registry."""
        banned = ("westlaw", "lexis", "bloomberglaw", "casetext", "fastcase")
        for source in load_federal_manifest().sources:
            haystack = f"{source.base_url} {source.publisher} {source.name}".lower()
            assert not any(term in haystack for term in banned)
