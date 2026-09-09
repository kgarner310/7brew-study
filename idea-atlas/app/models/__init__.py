"""SQLAlchemy models.

Importing this package registers every table on ``Base.metadata``; Alembic
autogenerate depends on that, so keep the re-exports exhaustive.
"""

from app.db.base import Base
from app.models.authority import Authority, AuthorityRelationship, AuthorityVersion
from app.models.concept import LegalConcept
from app.models.ingestion import IngestionRun
from app.models.jurisdiction import Jurisdiction
from app.models.proposition import Proposition, PropositionAuthority
from app.models.review import ReviewEvent
from app.models.source import Source

__all__ = [
    "Authority",
    "AuthorityRelationship",
    "AuthorityVersion",
    "Base",
    "IngestionRun",
    "Jurisdiction",
    "LegalConcept",
    "Proposition",
    "PropositionAuthority",
    "ReviewEvent",
    "Source",
]
