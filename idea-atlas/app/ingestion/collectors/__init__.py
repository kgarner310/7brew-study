"""Collectors enumerate the documents a source offers and hand them to the pipeline."""

from app.ingestion.collectors.base import CollectedDocument, Collector
from app.ingestion.collectors.http import FixtureCollector, StaticUrlCollector

__all__ = [
    "CollectedDocument",
    "Collector",
    "FixtureCollector",
    "StaticUrlCollector",
]
