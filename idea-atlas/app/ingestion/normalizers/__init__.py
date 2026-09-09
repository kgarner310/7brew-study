"""Text normalization. Deterministic and versioned; the hash depends on it."""

from app.ingestion.normalizers.text import normalize_text

__all__ = ["normalize_text"]
