"""Shared SQLAlchemy type helpers."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Enum as SAEnum


def pg_enum[E: StrEnum](enum_cls: type[E], name: str) -> SAEnum:
    """Build a native PostgreSQL enum that stores member *values*.

    Without ``values_callable`` SQLAlchemy persists member *names*, which would
    put ``PART_B`` in the database where the API and manifests all speak
    ``part_b``.
    """
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        create_constraint=False,
        validate_strings=True,
        values_callable=lambda enum: [member.value for member in enum],
    )
