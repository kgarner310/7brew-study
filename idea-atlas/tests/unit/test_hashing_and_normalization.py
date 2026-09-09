"""Hashing, change detection, and text normalization."""

from __future__ import annotations

from app.ingestion.hashing import content_changed, sha256_bytes, sha256_text
from app.ingestion.normalizers import normalize_text


class TestHashing:
    def test_sha256_text_is_stable(self) -> None:
        assert sha256_text("abc") == sha256_text("abc")
        assert len(sha256_text("abc")) == 64

    def test_different_text_different_hash(self) -> None:
        assert sha256_text("60 days") != sha256_text("90 days")

    def test_bytes_and_text_hashes_agree_for_ascii(self) -> None:
        assert sha256_text("abc") == sha256_bytes(b"abc")

    def test_unicode_is_encoded_consistently(self) -> None:
        assert sha256_text("Sec. 300.301") == sha256_bytes(b"Sec. 300.301")


class TestChangeDetection:
    def test_no_previous_hash_is_a_change(self) -> None:
        assert content_changed(None, sha256_text("x")) is True

    def test_same_hash_is_not_a_change(self) -> None:
        digest = sha256_text("x")
        assert content_changed(digest, digest) is False

    def test_different_hash_is_a_change(self) -> None:
        assert content_changed(sha256_text("x"), sha256_text("y")) is True


class TestNormalization:
    def test_collapses_horizontal_whitespace(self) -> None:
        assert normalize_text("a    b\tc") == "a b c"

    def test_folds_crlf(self) -> None:
        assert normalize_text("a\r\nb\rc") == "a\nb\nc"

    def test_collapses_blank_line_runs(self) -> None:
        assert normalize_text("a\n\n\n\n\nb") == "a\n\nb"

    def test_strips_trailing_whitespace_per_line(self) -> None:
        assert normalize_text("a   \nb   ") == "a\nb"

    def test_removes_zero_width_characters(self) -> None:
        assert normalize_text("a\u200bb\ufeffc") == "abc"

    def test_normalizes_nbsp(self) -> None:
        assert normalize_text("a\u00a0b") == "a b"

    def test_is_idempotent(self) -> None:
        raw = "  Sec.  300.301\r\n\n\n\n  text​  "
        once = normalize_text(raw)
        assert normalize_text(once) == once

    def test_cosmetic_change_does_not_alter_hash(self) -> None:
        """Whitespace churn must not read as a legal amendment."""
        a = normalize_text("An initial evaluation must occur.")
        b = normalize_text("An   initial \t evaluation   must occur.   ")
        assert sha256_text(a) == sha256_text(b)

    def test_substantive_change_does_alter_hash(self) -> None:
        a = normalize_text("within 60 days")
        b = normalize_text("within 90 days")
        assert sha256_text(a) != sha256_text(b)
