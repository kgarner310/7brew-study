"""Deterministic concept matching.

No model involved: an issue string is matched against concept names and
aliases by whole-word containment, scored by specificity. Deterministic
matching is a feature, not a limitation -- the same question must produce the
same retrieval every time, and the result must be explainable to a lawyer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LegalConcept

_NON_WORD = re.compile(r"[^a-z0-9]+")


def normalize_query(text: str) -> str:
    """Lowercase and collapse to single-spaced alphanumeric tokens."""
    return _NON_WORD.sub(" ", text.lower()).strip()


@dataclass(frozen=True, slots=True)
class ConceptMatch:
    """A matched concept and why it matched."""

    concept: LegalConcept
    score: float
    matched_terms: tuple[str, ...]


def _term_hits(haystack: str, term: str) -> bool:
    """Whole-phrase, word-boundary containment."""
    needle = normalize_query(term)
    if not needle:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", haystack) is not None


def match_concepts(session: Session, issue: str, *, limit: int = 5) -> list[ConceptMatch]:
    """Return the concepts an issue statement most likely concerns.

    Scoring rewards longer matched phrases, so "manifestation determination"
    outranks a bare "determination" and "prior written notice" outranks "notice".
    """
    haystack = normalize_query(issue)
    if not haystack:
        return []

    matches: list[ConceptMatch] = []
    for concept in session.scalars(select(LegalConcept)).all():
        terms = (concept.name, *concept.aliases)
        hits = tuple(term for term in terms if _term_hits(haystack, term))
        if not hits:
            continue
        # Longest hit dominates; additional hits add a small corroboration bonus.
        longest = max(len(normalize_query(term).split()) for term in hits)
        score = float(longest) + 0.1 * (len(hits) - 1)
        matches.append(ConceptMatch(concept=concept, score=score, matched_terms=hits))

    matches.sort(key=lambda m: (-m.score, m.concept.slug))
    return matches[:limit]
