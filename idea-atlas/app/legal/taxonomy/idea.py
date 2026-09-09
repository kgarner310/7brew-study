"""Starter IDEA subject-matter taxonomy.

Concepts are jurisdiction-neutral topics. Anything that varies by jurisdiction
-- a timeline, a standard, an added state protection -- is a
:class:`~app.models.proposition.Proposition` attached to one of these concepts,
not a separate concept.

``aliases`` drive keyword search and the research endpoint's concept matching.
They include practitioner shorthand ("MTSS", "RTI", "stay put") because that is
how users actually phrase questions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.enums import IdeaPart


@dataclass(frozen=True, slots=True)
class ConceptSeed:
    """A taxonomy node before it reaches the database."""

    slug: str
    name: str
    description: str
    idea_part: IdeaPart = IdeaPart.PART_B
    parent_slug: str | None = None
    aliases: tuple[str, ...] = field(default=())


IDEA_CONCEPTS: tuple[ConceptSeed, ...] = (
    # -- Identification and evaluation ------------------------------------
    ConceptSeed(
        "child-find",
        "Child Find",
        "The affirmative duty to identify, locate, and evaluate all children "
        "with disabilities who need special education and related services, "
        "including children who are advancing grade to grade.",
        aliases=("child find", "identification", "locate and evaluate"),
    ),
    ConceptSeed(
        "evaluation",
        "Evaluation",
        "The assessment process used to determine whether a child has a "
        "disability and the nature and extent of services needed.",
        aliases=("assessment", "testing", "full and individual evaluation"),
    ),
    ConceptSeed(
        "initial-evaluation",
        "Initial Evaluation",
        "The first full and individual evaluation, including consent "
        "requirements and the timeline within which it must be completed.",
        parent_slug="evaluation",
        aliases=(
            "initial evaluation",
            "evaluation timeline",
            "60 day timeline",
            "mtss",
            "rti",
            "multi-tiered system of supports",
            "response to intervention",
            "referral",
        ),
    ),
    ConceptSeed(
        "reevaluation",
        "Reevaluation",
        "Periodic re-assessment of a child's continued eligibility and needs, "
        "including frequency limits and the review-of-existing-data process.",
        parent_slug="evaluation",
        aliases=("reevaluation", "triennial", "re-evaluation"),
    ),
    ConceptSeed(
        "independent-educational-evaluation",
        "Independent Educational Evaluation",
        "A parent's right to an evaluation by a qualified examiner not employed "
        "by the public agency, and the conditions for obtaining one at public "
        "expense.",
        parent_slug="evaluation",
        aliases=("iee", "independent evaluation", "public expense"),
    ),
    ConceptSeed(
        "eligibility",
        "Eligibility",
        "Determination that a child has a qualifying disability and, by reason "
        "thereof, needs special education and related services.",
        aliases=("eligibility determination", "qualifying", "disability category"),
    ),
    ConceptSeed(
        "specific-learning-disability",
        "Specific Learning Disability",
        "The SLD eligibility category, including identification methodology "
        "such as severe discrepancy and response-to-intervention approaches.",
        parent_slug="eligibility",
        aliases=("sld", "learning disability", "dyslexia", "discrepancy model"),
    ),
    ConceptSeed(
        "other-health-impairment",
        "Other Health Impairment",
        "The OHI eligibility category, covering limited strength, vitality, or "
        "alertness, including heightened alertness to environmental stimuli.",
        parent_slug="eligibility",
        aliases=("ohi", "adhd", "other health impaired"),
    ),
    ConceptSeed(
        "autism",
        "Autism",
        "The autism eligibility category under IDEA, distinct from a clinical "
        "or medical diagnosis.",
        parent_slug="eligibility",
        aliases=("autism", "asd", "autism spectrum"),
    ),
    # -- FAPE and the IEP --------------------------------------------------
    ConceptSeed(
        "fape",
        "Free Appropriate Public Education",
        "The substantive right to an education reasonably calculated to enable "
        "a child to make progress appropriate in light of the child's "
        "circumstances.",
        aliases=("fape", "free appropriate public education", "endrew", "rowley"),
    ),
    ConceptSeed(
        "iep",
        "Individualized Education Program",
        "The written statement of a child's special education program, and the "
        "team process and timelines for developing and revising it.",
        parent_slug="fape",
        aliases=("iep", "individualized education program", "iep team"),
    ),
    ConceptSeed(
        "present-levels",
        "Present Levels of Academic Achievement and Functional Performance",
        "The baseline statement of how the child's disability affects "
        "involvement and progress in the general education curriculum.",
        parent_slug="iep",
        aliases=("present levels", "plaafp", "plop", "baseline"),
    ),
    ConceptSeed(
        "annual-goals",
        "Annual Goals",
        "Measurable annual academic and functional goals designed to meet the "
        "child's disability-related needs.",
        parent_slug="iep",
        aliases=("annual goals", "measurable goals", "iep goals", "benchmarks"),
    ),
    ConceptSeed(
        "specially-designed-instruction",
        "Specially Designed Instruction",
        "Adapting content, methodology, or delivery of instruction to address "
        "the child's disability-related needs.",
        parent_slug="iep",
        aliases=("sdi", "specially designed instruction", "special education"),
    ),
    ConceptSeed(
        "related-services",
        "Related Services",
        "Developmental, corrective, and other supportive services required to "
        "assist a child to benefit from special education.",
        parent_slug="iep",
        aliases=("related services", "speech therapy", "occupational therapy", "counseling"),
    ),
    ConceptSeed(
        "supplementary-aids-and-services",
        "Supplementary Aids and Services",
        "Aids, services, and supports provided in general education and other "
        "settings to enable education alongside nondisabled children.",
        parent_slug="iep",
        aliases=("supplementary aids", "accommodations", "supports"),
    ),
    ConceptSeed(
        "transition-services",
        "Transition Services",
        "The coordinated set of activities, and postsecondary goals, required "
        "as a child approaches the end of school-age eligibility.",
        parent_slug="iep",
        aliases=("transition", "postsecondary goals", "age of majority", "transition plan"),
    ),
    ConceptSeed(
        "esy",
        "Extended School Year Services",
        "Special education and related services provided beyond the normal "
        "school year when necessary to provide FAPE.",
        parent_slug="iep",
        aliases=("esy", "extended school year", "summer services", "regression recoupment"),
    ),
    ConceptSeed(
        "assistive-technology",
        "Assistive Technology",
        "Assistive technology devices and services the IEP team must consider "
        "and, where needed, provide.",
        parent_slug="iep",
        aliases=("assistive technology", "at device", "aac", "communication device"),
    ),
    ConceptSeed(
        "transportation",
        "Transportation",
        "Transportation as a related service, including specialized equipment "
        "and door-to-door service where required.",
        parent_slug="related-services",
        aliases=("transportation", "bus", "specialized transportation"),
    ),
    # -- Placement and LRE -------------------------------------------------
    ConceptSeed(
        "lre",
        "Least Restrictive Environment",
        "The requirement that children with disabilities be educated with "
        "nondisabled peers to the maximum extent appropriate.",
        aliases=("lre", "least restrictive environment", "mainstreaming", "inclusion"),
    ),
    ConceptSeed(
        "placement",
        "Placement",
        "Determination of the setting in which the IEP will be delivered, and "
        "the continuum of alternative placements that must be available.",
        parent_slug="lre",
        aliases=("placement", "continuum", "educational placement"),
    ),
    ConceptSeed(
        "change-of-placement",
        "Change of Placement",
        "What constitutes a change in educational placement, and the notice "
        "and procedural consequences that follow.",
        parent_slug="placement",
        aliases=("change of placement", "stay put", "pendency"),
    ),
    ConceptSeed(
        "private-school-placement",
        "Private School Placement",
        "Placement in a private school by the public agency, and the "
        "obligations owed to parentally-placed private school children.",
        parent_slug="placement",
        aliases=("private school", "equitable services", "parentally placed"),
    ),
    ConceptSeed(
        "unilateral-placement",
        "Unilateral Placement",
        "Parental placement in a private school without agency consent, and "
        "the conditions for tuition reimbursement.",
        parent_slug="placement",
        aliases=("unilateral placement", "tuition reimbursement", "burlington carter"),
    ),
    ConceptSeed(
        "interim-alternative-educational-setting",
        "Interim Alternative Educational Setting",
        "The 45-school-day setting available for weapons, drugs, and serious "
        "bodily injury offenses regardless of manifestation.",
        parent_slug="placement",
        aliases=("iaes", "interim alternative educational setting", "45 day"),
    ),
    # -- Procedural safeguards --------------------------------------------
    ConceptSeed(
        "procedural-safeguards",
        "Procedural Safeguards",
        "The set of parental rights and agency obligations that protect the "
        "substantive right to FAPE.",
        idea_part=IdeaPart.CROSS_CUTTING,
        aliases=("procedural safeguards", "parent rights", "safeguards notice"),
    ),
    ConceptSeed(
        "parent-participation",
        "Parent Participation",
        "The right of parents to participate meaningfully in identification, "
        "evaluation, placement, and FAPE decisions.",
        parent_slug="procedural-safeguards",
        aliases=("parent participation", "meaningful participation", "predetermination"),
    ),
    ConceptSeed(
        "prior-written-notice",
        "Prior Written Notice",
        "Written notice required a reasonable time before proposing or "
        "refusing to initiate or change identification, evaluation, placement, "
        "or the provision of FAPE.",
        parent_slug="procedural-safeguards",
        aliases=("pwn", "prior written notice", "notice of proposal", "refusal"),
    ),
    ConceptSeed(
        "state-complaint",
        "State Complaint",
        "The state complaint procedure for alleging violations of Part B, "
        "including the investigation timeline and remedies.",
        parent_slug="procedural-safeguards",
        aliases=("state complaint", "formal complaint", "60 day complaint", "child complaint"),
    ),
    ConceptSeed(
        "due-process",
        "Due Process",
        "The impartial due process hearing procedure, including the complaint "
        "notice, timelines, hearing rights, and appeal.",
        parent_slug="procedural-safeguards",
        aliases=("due process", "hearing", "dph", "impartial hearing", "statute of limitations"),
    ),
    ConceptSeed(
        "mediation",
        "Mediation",
        "The voluntary, confidential mediation process available to resolve disputes.",
        parent_slug="procedural-safeguards",
        aliases=("mediation", "mediator", "voluntary dispute resolution"),
    ),
    ConceptSeed(
        "resolution-session",
        "Resolution Session",
        "The meeting the agency must convene after a due process complaint, "
        "and the conditions for waiving it.",
        parent_slug="due-process",
        aliases=("resolution session", "resolution meeting", "30 day resolution"),
    ),
    ConceptSeed(
        "compensatory-education",
        "Compensatory Education",
        "Equitable relief awarded to remedy a past denial of FAPE.",
        parent_slug="procedural-safeguards",
        aliases=("compensatory education", "comp ed", "remedy", "make-up services"),
    ),
    # -- Discipline --------------------------------------------------------
    ConceptSeed(
        "discipline",
        "Discipline",
        "Disciplinary removals of children with disabilities and the "
        "protections that attach once a removal becomes a change of placement.",
        aliases=("discipline", "suspension", "expulsion", "removal", "10 days"),
    ),
    ConceptSeed(
        "manifestation-determination",
        "Manifestation Determination",
        "The review of whether conduct was caused by, or had a direct and "
        "substantial relationship to, the child's disability or a failure to "
        "implement the IEP.",
        parent_slug="discipline",
        aliases=("manifestation determination", "mdr", "manifestation review"),
    ),
    # -- Administration ----------------------------------------------------
    ConceptSeed(
        "transfer-students",
        "Transfer Students",
        "Obligations when a child with an IEP transfers between districts or "
        "into the state, including comparable services.",
        aliases=("transfer", "comparable services", "moving districts", "interstate transfer"),
    ),
    ConceptSeed(
        "maintenance-of-effort",
        "Maintenance of Effort",
        "The fiscal requirement that an LEA or SEA not reduce its level of "
        "expenditures for special education below the prior year.",
        idea_part=IdeaPart.CROSS_CUTTING,
        aliases=("moe", "maintenance of effort", "fiscal", "supplement not supplant"),
    ),
    # -- Part C ------------------------------------------------------------
    ConceptSeed(
        "part-c",
        "Part C Early Intervention",
        "The Part C system serving infants and toddlers with disabilities from "
        "birth through age two, and their families.",
        idea_part=IdeaPart.PART_C,
        aliases=("part c", "birth to three", "infants and toddlers", "early intervention system"),
    ),
    ConceptSeed(
        "ifsp",
        "Individualized Family Service Plan",
        "The written plan for Part C early intervention services, centered on "
        "the family as well as the child.",
        idea_part=IdeaPart.PART_C,
        parent_slug="part-c",
        aliases=("ifsp", "family service plan", "outcomes"),
    ),
    ConceptSeed(
        "early-intervention-services",
        "Early Intervention Services",
        "The developmental services provided under Part C to meet the needs of "
        "an infant or toddler with a disability.",
        idea_part=IdeaPart.PART_C,
        parent_slug="part-c",
        aliases=("early intervention", "ei services", "developmental services"),
    ),
    ConceptSeed(
        "natural-environments",
        "Natural Environments",
        "The Part C requirement that services be provided in settings natural "
        "or typical for an infant or toddler without a disability.",
        idea_part=IdeaPart.PART_C,
        parent_slug="part-c",
        aliases=("natural environments", "home based", "community settings"),
    ),
    ConceptSeed(
        "part-c-to-part-b-transition",
        "Part C to Part B Transition",
        "The transition from early intervention to preschool special education "
        "by the child's third birthday, including the transition conference.",
        idea_part=IdeaPart.CROSS_CUTTING,
        parent_slug="part-c",
        aliases=(
            "part c to part b",
            "transition conference",
            "third birthday",
            "turning three",
        ),
    ),
)


def concept_by_slug(slug: str) -> ConceptSeed:
    """Look up a concept seed by slug."""
    needle = slug.strip().lower()
    for concept in IDEA_CONCEPTS:
        if concept.slug == needle:
            return concept
    raise KeyError(f"Unknown concept: {slug!r}")
