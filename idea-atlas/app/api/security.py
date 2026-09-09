"""Authentication and authorization hooks.

Deliberately minimal for this phase. The platform currently serves only public
legal information: there are no user accounts, no private documents, and
nothing to authorize. What exists here is the *seam* -- a dependency every
protected route can adopt without restructuring the API later.

When real auth arrives (see docs/ROADMAP.md phase 4), implement
:class:`Principal` resolution against an API-key or OIDC backend and keep the
dependency signature unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from fastapi import Header


class Scope(StrEnum):
    """Coarse permission scopes, reserved for future use."""

    READ_PUBLIC = "read:public"
    READ_INTERNAL = "read:internal"
    WRITE_REVIEW = "write:review"
    RUN_INGESTION = "run:ingestion"


@dataclass(frozen=True, slots=True)
class Principal:
    """Whoever is making the request."""

    subject: str
    scopes: frozenset[Scope] = field(default_factory=frozenset)
    authenticated: bool = False

    def has(self, scope: Scope) -> bool:
        return scope in self.scopes


ANONYMOUS = Principal(
    subject="anonymous",
    scopes=frozenset({Scope.READ_PUBLIC}),
    authenticated=False,
)


async def current_principal(
    authorization: str | None = Header(default=None, include_in_schema=False),
) -> Principal:
    """Resolve the caller.

    Today every caller is anonymous with read-only public scope. The header is
    accepted and ignored rather than rejected so that clients can start sending
    credentials before the server enforces them.
    """
    return ANONYMOUS
