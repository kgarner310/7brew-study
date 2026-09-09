"""The IDEA jurisdiction universe."""

from app.legal.jurisdictions.registry import (
    ALL_JURISDICTIONS,
    FEDERAL_CIRCUITS,
    JurisdictionSeed,
    by_slug,
    states_and_equivalents,
)

__all__ = [
    "ALL_JURISDICTIONS",
    "FEDERAL_CIRCUITS",
    "JurisdictionSeed",
    "by_slug",
    "states_and_equivalents",
]
