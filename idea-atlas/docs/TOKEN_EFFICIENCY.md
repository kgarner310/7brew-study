# Token efficiency

Machine consumers pay per token. A structured, jurisdiction-scoped answer with
citations should cost dramatically less than stuffing raw statutory text into a
context window — and that claim should be measured, not asserted.

## Detail levels

`POST /v1/research` takes `detail`, which controls how much is assembled.

| Level | Propositions | Includes | Use |
|---|---|---|---|
| `compact` | up to 3 | Statement + citation | Agent tool calls, quick lookups |
| `standard` | up to 8 | + qualifiers, authority effective dates | Interactive research |
| `research` | up to 25 | + quoted supporting text, full effective dating | Brief writing, deep review |

Omitted propositions are reported in `warnings`, so a caller always knows the
answer was trimmed rather than silently truncated.

## Token budget

`token_budget` (default 1000) caps the assembled answer. When it binds, the
answer is truncated on a word boundary, `truncated: true` is set, and a warning
is added. `token_budget: 0` disables truncation.

Every response reports `estimated_response_tokens`.

## Estimation without a paid tokenizer

`app/services/tokens.py` implements a heuristic. Calling a vendor tokenizer
would make a core feature depend on a paid API and a specific model — exactly
the lock-in this architecture avoids.

Method: `words × 1.32`, plus one token per 6-character subword chunk beyond the
first, plus 0.5 per punctuation mark and per digit run. JSON payloads add 2
tokens of structural overhead per key.

The digit and punctuation terms matter for legal text: `34 C.F.R.
§ 300.301(c)(1)` is far denser than prose of the same length.

**Properties:** deterministic; monotonic in length; biased *high*, because
over-estimating a budget is safer than blowing one. Measured against ordinary
English prose it lands within roughly ±15%.

**It is not a billing-grade tokenizer.** For metered billing (phase 4), call the
provider's real tokenizer at the boundary and keep this heuristic for planning.

### Calibrating against a real tokenizer

```python
# Optional dev-only dependency; never required to run or test the project.
import anthropic

from app.services.tokens import estimate_tokens

client = anthropic.Anthropic()
samples = [...]  # representative responses from /v1/research

for text in samples:
    actual = client.messages.count_tokens(
        model="claude-sonnet-5",
        messages=[{"role": "user", "content": text}],
    ).input_tokens
    print(f"{estimate_tokens(text) / actual:.3f}")
```

If the ratio drifts consistently, adjust `TOKENS_PER_WORD`. Do this per model
family and record the date — tokenizers change.

## Benchmarking plan

Not yet implemented. The point of the platform is that structured retrieval
beats raw context, and that has to be demonstrated with numbers.

### Metrics

| Metric | Definition | Why |
|---|---|---|
| **Raw source context tokens** | Tokens to answer by pasting full statute/regulation text | The baseline being beaten |
| **Structured answer tokens** | Tokens in the `/v1/research` response | The product's cost |
| **Compression ratio** | raw ÷ structured | The headline number |
| **Latency (p50/p95/p99)** | Server time per request | Agent usability |
| **Retrieval count** | Propositions and authorities returned | Precision proxy |
| **Citation accuracy** | Cited authorities that actually support the statement | **Integrity** |
| **Legal-answer accuracy** | Responses a qualified reviewer judges correct | The metric that matters |
| **Refusal correctness** | `insufficient_coverage` returned when and only when appropriate | Both false answers and needless refusals are failures |

### Method

1. Build a graded question set — 100+ real IDEA questions across concepts and
   jurisdictions, each with a reference answer from a qualified reviewer.
2. For each question, measure the raw-context baseline and the structured
   response.
3. Have a qualified reviewer grade citation accuracy and legal accuracy blind to
   which system produced the answer.
4. Report the distribution, not the mean — the tail is where harm lives.

### Honest expectations

Compression should be large, because a structured answer replaces tens of
thousands of tokens of statutory text with a few hundred. **That number is not
the interesting one.** Any retrieval system compresses.

The interesting numbers are citation accuracy and refusal correctness, because
those are what distinguish this from a summarizer. A system that compresses
100:1 and is wrong 5% of the time is worse than useless for a parent deciding
whether to file a due process complaint.

Until the knowledge base holds reviewed propositions, benchmarking would measure
nothing. Blocked on Phase 1 ingestion — see [`ROADMAP.md`](ROADMAP.md).
