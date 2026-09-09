"""Token estimation without a paid tokenizer.

Why this exists: the research API promises a ``token_budget`` and reports
``estimated_response_tokens``. Calling a vendor tokenizer to do that would make
a core feature depend on a paid API and a specific model -- exactly the
lock-in the architecture avoids.

Method: a hybrid word/character heuristic. Modern BPE tokenizers split English
prose at roughly 0.75 tokens per whitespace word, with extra tokens for
punctuation, digit runs, and long words that fragment into subwords. Legal text
is denser than prose because citations ("34 C.F.R. Sec. 300.301(c)(1)") are
punctuation- and digit-heavy.

Accuracy: this is deliberately a *conservative over-estimate* -- budgeting is
safer when it errs high. Measured against typical English prose it lands within
roughly +/-15%. It is not a substitute for a real tokenizer at billing time.
See docs/TOKEN_EFFICIENCY.md for the calibration procedure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Average tokens per whitespace-delimited word for English prose under BPE.
TOKENS_PER_WORD = 1.32
#: Long words fragment; each additional chunk beyond this length adds a token.
SUBWORD_CHUNK_CHARS = 6
#: JSON structural overhead per object key in a serialized response.
JSON_KEY_OVERHEAD_TOKENS = 2

_WORD_RE = re.compile(r"\S+")
_PUNCT_RE = re.compile(r"[^\w\s]")
_DIGIT_RUN_RE = re.compile(r"\d+")


@dataclass(frozen=True, slots=True)
class TokenEstimate:
    """An estimate with the inputs that produced it, for auditability."""

    tokens: int
    characters: int
    words: int
    method: str = "heuristic-v1"

    def __int__(self) -> int:
        return self.tokens


def estimate_tokens(text: str) -> int:
    """Estimate the token count of ``text``. Conservative (biased high)."""
    return estimate_tokens_detailed(text).tokens


def estimate_tokens_detailed(text: str) -> TokenEstimate:
    """Estimate tokens and return the intermediate counts."""
    if not text:
        return TokenEstimate(tokens=0, characters=0, words=0)

    words = _WORD_RE.findall(text)
    word_count = len(words)

    # Base cost.
    total = word_count * TOKENS_PER_WORD

    # Long words fragment into subwords.
    for word in words:
        extra = (len(word) - 1) // SUBWORD_CHUNK_CHARS
        if extra > 0:
            total += extra

    # Punctuation and digit runs usually become their own tokens.
    total += len(_PUNCT_RE.findall(text)) * 0.5
    total += len(_DIGIT_RUN_RE.findall(text)) * 0.5

    return TokenEstimate(
        tokens=max(1, round(total)),
        characters=len(text),
        words=word_count,
    )


def estimate_payload_tokens(payload: object) -> int:
    """Estimate tokens for a JSON-serializable response payload.

    Counts string content plus a fixed structural overhead per key, which is
    what makes ``detail=compact`` measurably cheaper than ``detail=research``
    rather than merely shorter-looking.
    """
    if payload is None:
        return 0
    if isinstance(payload, str):
        return estimate_tokens(payload)
    if isinstance(payload, bool):
        return 1
    if isinstance(payload, int | float):
        return 1
    if isinstance(payload, dict):
        total = 0
        for key, value in payload.items():
            total += JSON_KEY_OVERHEAD_TOKENS + estimate_tokens(str(key))
            total += estimate_payload_tokens(value)
        return total
    if isinstance(payload, list | tuple):
        return 2 + sum(estimate_payload_tokens(item) for item in payload)
    return estimate_tokens(str(payload))


def truncate_to_budget(text: str, budget_tokens: int) -> tuple[str, bool]:
    """Trim ``text`` to fit ``budget_tokens``, cutting on a word boundary.

    Returns ``(text, was_truncated)``.
    """
    if budget_tokens <= 0:
        return "", bool(text)
    if estimate_tokens(text) <= budget_tokens:
        return text, False

    words = text.split()
    low, high = 0, len(words)
    while low < high:
        mid = (low + high + 1) // 2
        if estimate_tokens(" ".join(words[:mid])) <= budget_tokens:
            low = mid
        else:
            high = mid - 1
    return " ".join(words[:low]), True
