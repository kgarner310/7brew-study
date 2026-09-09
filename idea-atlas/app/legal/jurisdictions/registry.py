"""The canonical IDEA jurisdiction universe.

Statutory framing (20 U.S.C. Sec. 1401), which drives the ``jurisdiction_type``
values below:

* ``State`` (Sec. 1401(31)) -- the 50 States, the District of Columbia, and the
  Commonwealth of Puerto Rico. All are modelled as full IDEA jurisdictions with
  Part B and Part C obligations.
* ``Outlying area`` (Sec. 1401(24)) -- the United States Virgin Islands, Guam,
  American Samoa, and the Commonwealth of the Northern Mariana Islands.
* ``Bureau of Indian Education`` -- IDEA funds flow to the Secretary of the
  Interior under Sec. 1411(h) for Indian children served by BIE-funded schools.

VERIFICATION STATUS: every field in this module was populated from model
knowledge without network access to official sources, because this environment
blocks outbound ``.gov`` traffic. Federal circuit assignments and SEA names are
stable but MUST be confirmed against primary sources before this data is relied
on. The freely associated states (FSM, RMI, Palau) are deliberately excluded
pending verification -- see docs/JURISDICTIONS.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.enums import JurisdictionType


@dataclass(frozen=True, slots=True)
class JurisdictionSeed:
    """A jurisdiction as it appears in the registry before it reaches the DB."""

    slug: str
    name: str
    jurisdiction_type: JurisdictionType
    postal_code: str | None = None
    federal_circuit: str | None = None
    sea_name: str | None = None
    idea_part_b_applicable: bool = True
    idea_part_c_applicable: bool = True
    parent_slug: str | None = None
    notes: str | None = None
    verification_required: bool = True
    meta: dict[str, str] = field(default_factory=dict)


#: The United States, parent of every domestic jurisdiction below.
FEDERAL = JurisdictionSeed(
    slug="us",
    name="United States (Federal)",
    jurisdiction_type=JurisdictionType.FEDERAL,
    sea_name="U.S. Department of Education, Office of Special Education Programs",
    notes="The federal IDEA floor. State law may add protections but not subtract.",
)

#: Federal circuits, modelled as jurisdictions so circuit precedent can be
#: scoped without inventing a parallel entity type.
FEDERAL_CIRCUITS: tuple[JurisdictionSeed, ...] = tuple(
    JurisdictionSeed(
        slug=f"ca-{slug}",
        name=name,
        jurisdiction_type=JurisdictionType.FEDERAL_CIRCUIT,
        federal_circuit=slug,
        parent_slug="us",
        idea_part_b_applicable=False,
        idea_part_c_applicable=False,
        notes="Precedent-scoping jurisdiction; not an IDEA grantee.",
    )
    for slug, name in (
        ("1st", "U.S. Court of Appeals for the First Circuit"),
        ("2nd", "U.S. Court of Appeals for the Second Circuit"),
        ("3rd", "U.S. Court of Appeals for the Third Circuit"),
        ("4th", "U.S. Court of Appeals for the Fourth Circuit"),
        ("5th", "U.S. Court of Appeals for the Fifth Circuit"),
        ("6th", "U.S. Court of Appeals for the Sixth Circuit"),
        ("7th", "U.S. Court of Appeals for the Seventh Circuit"),
        ("8th", "U.S. Court of Appeals for the Eighth Circuit"),
        ("9th", "U.S. Court of Appeals for the Ninth Circuit"),
        ("10th", "U.S. Court of Appeals for the Tenth Circuit"),
        ("11th", "U.S. Court of Appeals for the Eleventh Circuit"),
        ("dc", "U.S. Court of Appeals for the District of Columbia Circuit"),
    )
)

# (postal, name, circuit, SEA name)
_STATE_ROWS: tuple[tuple[str, str, str, str], ...] = (
    ("AL", "Alabama", "11th", "Alabama State Department of Education"),
    ("AK", "Alaska", "9th", "Alaska Department of Education and Early Development"),
    ("AZ", "Arizona", "9th", "Arizona Department of Education"),
    ("AR", "Arkansas", "8th", "Arkansas Department of Education"),
    ("CA", "California", "9th", "California Department of Education"),
    ("CO", "Colorado", "10th", "Colorado Department of Education"),
    ("CT", "Connecticut", "2nd", "Connecticut State Department of Education"),
    ("DE", "Delaware", "3rd", "Delaware Department of Education"),
    ("FL", "Florida", "11th", "Florida Department of Education"),
    ("GA", "Georgia", "11th", "Georgia Department of Education"),
    ("HI", "Hawaii", "9th", "Hawaii State Department of Education"),
    ("ID", "Idaho", "9th", "Idaho State Department of Education"),
    ("IL", "Illinois", "7th", "Illinois State Board of Education"),
    ("IN", "Indiana", "7th", "Indiana Department of Education"),
    ("IA", "Iowa", "8th", "Iowa Department of Education"),
    ("KS", "Kansas", "10th", "Kansas State Department of Education"),
    ("KY", "Kentucky", "6th", "Kentucky Department of Education"),
    ("LA", "Louisiana", "5th", "Louisiana Department of Education"),
    ("ME", "Maine", "1st", "Maine Department of Education"),
    ("MD", "Maryland", "4th", "Maryland State Department of Education"),
    (
        "MA",
        "Massachusetts",
        "1st",
        "Massachusetts Department of Elementary and Secondary Education",
    ),
    ("MI", "Michigan", "6th", "Michigan Department of Education"),
    ("MN", "Minnesota", "8th", "Minnesota Department of Education"),
    ("MS", "Mississippi", "5th", "Mississippi Department of Education"),
    ("MO", "Missouri", "8th", "Missouri Department of Elementary and Secondary Education"),
    ("MT", "Montana", "9th", "Montana Office of Public Instruction"),
    ("NE", "Nebraska", "8th", "Nebraska Department of Education"),
    ("NV", "Nevada", "9th", "Nevada Department of Education"),
    ("NH", "New Hampshire", "1st", "New Hampshire Department of Education"),
    ("NJ", "New Jersey", "3rd", "New Jersey Department of Education"),
    ("NM", "New Mexico", "10th", "New Mexico Public Education Department"),
    ("NY", "New York", "2nd", "New York State Education Department"),
    ("NC", "North Carolina", "4th", "North Carolina Department of Public Instruction"),
    ("ND", "North Dakota", "8th", "North Dakota Department of Public Instruction"),
    ("OH", "Ohio", "6th", "Ohio Department of Education and Workforce"),
    ("OK", "Oklahoma", "10th", "Oklahoma State Department of Education"),
    ("OR", "Oregon", "9th", "Oregon Department of Education"),
    ("PA", "Pennsylvania", "3rd", "Pennsylvania Department of Education"),
    ("RI", "Rhode Island", "1st", "Rhode Island Department of Elementary and Secondary Education"),
    ("SC", "South Carolina", "4th", "South Carolina Department of Education"),
    ("SD", "South Dakota", "8th", "South Dakota Department of Education"),
    ("TN", "Tennessee", "6th", "Tennessee Department of Education"),
    ("TX", "Texas", "5th", "Texas Education Agency"),
    ("UT", "Utah", "10th", "Utah State Board of Education"),
    ("VT", "Vermont", "2nd", "Vermont Agency of Education"),
    ("VA", "Virginia", "4th", "Virginia Department of Education"),
    ("WA", "Washington", "9th", "Washington Office of Superintendent of Public Instruction"),
    ("WV", "West Virginia", "4th", "West Virginia Department of Education"),
    ("WI", "Wisconsin", "7th", "Wisconsin Department of Public Instruction"),
    ("WY", "Wyoming", "10th", "Wyoming Department of Education"),
)

STATES: tuple[JurisdictionSeed, ...] = tuple(
    JurisdictionSeed(
        slug=postal.lower(),
        name=name,
        jurisdiction_type=JurisdictionType.STATE,
        postal_code=postal,
        federal_circuit=circuit,
        sea_name=sea,
        parent_slug="us",
    )
    for postal, name, circuit, sea in _STATE_ROWS
)

#: DC and Puerto Rico are "States" for IDEA purposes (Sec. 1401(31)) but are
#: typed distinctly so reporting can separate them from the 50 states.
STATE_EQUIVALENTS: tuple[JurisdictionSeed, ...] = (
    JurisdictionSeed(
        slug="dc",
        name="District of Columbia",
        jurisdiction_type=JurisdictionType.DISTRICT,
        postal_code="DC",
        federal_circuit="dc",
        sea_name="District of Columbia Office of the State Superintendent of Education",
        parent_slug="us",
        notes="Treated as a State under 20 U.S.C. Sec. 1401(31).",
    ),
    JurisdictionSeed(
        slug="pr",
        name="Commonwealth of Puerto Rico",
        jurisdiction_type=JurisdictionType.TERRITORY,
        postal_code="PR",
        federal_circuit="1st",
        sea_name="Puerto Rico Department of Education",
        parent_slug="us",
        notes="Named as a State under 20 U.S.C. Sec. 1401(31), not an outlying area.",
    ),
)

#: "Outlying areas" under 20 U.S.C. Sec. 1401(24).
OUTLYING_AREAS: tuple[JurisdictionSeed, ...] = (
    JurisdictionSeed(
        slug="vi",
        name="United States Virgin Islands",
        jurisdiction_type=JurisdictionType.TERRITORY,
        postal_code="VI",
        federal_circuit="3rd",
        sea_name="Virgin Islands Department of Education",
        parent_slug="us",
        notes="Outlying area under Sec. 1401(24).",
    ),
    JurisdictionSeed(
        slug="gu",
        name="Guam",
        jurisdiction_type=JurisdictionType.TERRITORY,
        postal_code="GU",
        federal_circuit="9th",
        sea_name="Guam Department of Education",
        parent_slug="us",
        notes="Outlying area under Sec. 1401(24).",
    ),
    JurisdictionSeed(
        slug="as",
        name="American Samoa",
        jurisdiction_type=JurisdictionType.TERRITORY,
        postal_code="AS",
        federal_circuit=None,
        sea_name="American Samoa Department of Education",
        parent_slug="us",
        notes=(
            "Outlying area under Sec. 1401(24). Federal circuit deliberately left "
            "null: American Samoa has no Article III district court and the "
            "appellate path is unsettled. VERIFY before relying on circuit scoping."
        ),
    ),
    JurisdictionSeed(
        slug="mp",
        name="Commonwealth of the Northern Mariana Islands",
        jurisdiction_type=JurisdictionType.TERRITORY,
        postal_code="MP",
        federal_circuit="9th",
        sea_name="CNMI Public School System",
        parent_slug="us",
        notes="Outlying area under Sec. 1401(24).",
    ),
)

FEDERAL_AGENCIES: tuple[JurisdictionSeed, ...] = (
    JurisdictionSeed(
        slug="bie",
        name="Bureau of Indian Education",
        jurisdiction_type=JurisdictionType.FEDERAL_AGENCY,
        postal_code=None,
        federal_circuit=None,
        sea_name="Bureau of Indian Education, U.S. Department of the Interior",
        parent_slug="us",
        notes=(
            "IDEA Part B funds reach BIE-funded schools through the Secretary of "
            "the Interior under 20 U.S.C. Sec. 1411(h). Part C applicability to BIE "
            "differs from Part B and is flagged for verification."
        ),
        idea_part_c_applicable=False,
    ),
)

ALL_JURISDICTIONS: tuple[JurisdictionSeed, ...] = (
    FEDERAL,
    *FEDERAL_CIRCUITS,
    *STATES,
    *STATE_EQUIVALENTS,
    *OUTLYING_AREAS,
    *FEDERAL_AGENCIES,
)


def states_and_equivalents() -> tuple[JurisdictionSeed, ...]:
    """Every jurisdiction with real IDEA grantee obligations.

    Excludes the federal government itself and the circuit entities, which
    exist only for precedent scoping.
    """
    return (*STATES, *STATE_EQUIVALENTS, *OUTLYING_AREAS, *FEDERAL_AGENCIES)


def by_slug(slug: str) -> JurisdictionSeed:
    """Look up a seed by slug, case-insensitively.

    Accepts postal codes too, so ``NC`` and ``nc`` both resolve.
    """
    needle = slug.strip().lower()
    for seed in ALL_JURISDICTIONS:
        if seed.slug == needle:
            return seed
    raise KeyError(f"Unknown jurisdiction: {slug!r}")
