# Local and free AI setup

How to develop this repository using free or local models for the bulk of the
work, spending frontier-model budget only where it actually pays.

## Environment detection (this build machine)

The project brief asked for Windows tooling detection. **This build ran on Linux
(Ubuntu 24.04), not Windows**, so no Windows-specific installation was performed.
What was detected:

| Tool | Status |
|---|---|
| Git 2.43 | present |
| Python 3.12.3 / 3.13.12 | present |
| uv 0.8.17 | present |
| Node 22.22 | present |
| Docker client 29.3 | present, **daemon not running** |
| PostgreSQL 16.13 | present, used for real testing |
| GitHub CLI (`gh`) | **not installed** |
| Ollama | **not installed** |
| VS Code | not installed (headless container) |

No system packages were installed and no destructive change was made. If you are
on Windows, the setup below is what to run there.

## The routing principle

Not all coding work needs the same model. Route by *failure cost*:

| Work | Model tier | Why |
|---|---|---|
| Boilerplate, CRUD routers, test scaffolding | **Local (Ollama)** | Cheap, private, failure is instantly visible |
| Docstrings, type annotations, renames | **Local** | Mechanical; the typechecker catches errors |
| Jurisdiction manifest URL filling | **Local + human check** | Volume work; a human verifies anyway |
| Collectors and parsers for a new source | **Free cloud tier** | Needs some reasoning, low blast radius |
| Test authoring | **Free cloud tier** | Correctness matters but is verifiable by running them |
| Schema and migration design | **Frontier** | Expensive to reverse once data exists |
| Security controls (SSRF, auth, injection) | **Frontier** | Failure is silent and severe |
| Legal data modelling and review workflow | **Frontier + human expert** | Wrong law harms families |
| Anything touching `review_status` | **Frontier + human expert** | This is the integrity boundary |

The cheap rule: **if a mistake would be caught by `pytest`, use a cheap model.
If a mistake would be caught by a lawyer six months later, use the best model
you have and then have a human check it.**

## Ollama (local, free, private)

```bash
# Linux / WSL
curl -fsSL https://ollama.com/install.sh | sh

# macOS: brew install ollama       Windows: winget install Ollama.Ollama
ollama serve
```

**Check resources before pulling.** Model size must fit in RAM (or VRAM):

```bash
free -h          # Linux
nvidia-smi       # if you have a GPU
```

| RAM / VRAM | Reasonable choice | Notes |
|---|---|---|
| 8 GB | `qwen2.5-coder:7b` | Solid for boilerplate |
| 16 GB | `qwen2.5-coder:14b` | Good default for this repo |
| 32 GB+ | `qwen2.5-coder:32b` | Handles multi-file edits |
| 64 GB+ | `deepseek-coder-v2:16b` or larger | Diminishing returns for this codebase |

```bash
ollama pull qwen2.5-coder:14b     # ~9 GB download; do not pull blind
```

Do not automatically pull large models on a machine you have not checked — a
70B pull on a 16 GB laptop will thrash and fail slowly.

### Wiring Ollama into IDEA Atlas

The provider seam already exists. Implement `AIProvider` against Ollama's
OpenAI-compatible endpoint and register it:

```python
# app/services/ai/ollama.py
from app.services.ai.base import AIProvider, ExtractionRequest, PropositionCandidate
from app.services.ai.registry import register_provider


class OllamaProvider:
    name = "ollama"

    def __init__(self, settings):
        self.model = settings.ai_model or "qwen2.5-coder:14b"
        self.base_url = settings.ai_base_url or "http://localhost:11434"

    @property
    def available(self) -> bool: ...  # ping /api/tags

    def extract_propositions(self, request: ExtractionRequest) -> list[PropositionCandidate]:
        # MUST wrap source text: wrap_untrusted_document(request.document_text)
        # MUST require a verbatim supporting_quote; discard ungrounded candidates
        ...


register_provider("ollama", OllamaProvider)
```

```bash
IDEA_ATLAS_AI_PROVIDER=ollama
IDEA_ATLAS_AI_MODEL=qwen2.5-coder:14b
IDEA_ATLAS_AI_BASE_URL=http://localhost:11434
```

Same safety rules apply to a local model as to a paid one: fence source text,
require verbatim quotes, write `review_status=ai_extracted`, never let it set a
review status. A local model is cheaper, not more trustworthy.

## Gemini Code Assist (free tier)

Generous individual free tier with a large context window — useful for
whole-file review and for asking "does this module do what its docstring says".

- VS Code / JetBrains: install the **Gemini Code Assist** extension, sign in
  with a personal Google account
- CLI: `npm install -g @google/gemini-cli` then `gemini`

Good for: reviewing a whole module, drafting docs, explaining unfamiliar
SQLAlchemy behaviour.

## GitHub Copilot Free

Free tier gives a monthly allowance of completions and chat messages.

- VS Code: install **GitHub Copilot**, sign in
- Enable for Python; disable for `data/source_manifests/**` — autocompleting a
  plausible-looking `.gov` URL into a manifest is exactly the failure mode this
  project is built to prevent

Good for: inline completion of repetitive code (routers, schemas, test
parametrize blocks).

## Cline / OpenCode (agentic, bring your own model)

**Cline** (VS Code extension) runs an agent loop against any provider including
a local Ollama endpoint — so you can get agentic multi-file edits at zero
marginal cost.

1. Install **Cline** from the VS Code marketplace
2. API Provider → **Ollama**, base URL `http://localhost:11434`
3. Select `qwen2.5-coder:14b`
4. Point it at a narrow task ("add a collector for 34 CFR part 303 following
   `app/ingestion/collectors/http.py`")

**OpenCode** is a terminal alternative with the same idea:
`npm install -g opencode-ai`.

Keep agentic local runs scoped to one module. Small models drift on large
refactors, and this repo's `mypy --strict` will surface that immediately —
which is the point.

## Claude Code

What built this repository. Best used here for the frontier-tier rows in the
routing table: schema design, security controls, legal data modelling, and
review of anything a cheaper model produced near the integrity boundary.

```bash
npm install -g @anthropic-ai/claude-code
cd idea-atlas
claude
```

The repository is already set up to help any agent work safely in it:

- `mypy --strict` and `ruff` catch most machine-generated mistakes immediately
- 274 tests, 95% coverage — regressions surface fast
- `CODEOWNERS` flags the files where mistakes are expensive
- The PR template's legal-integrity checklist is designed to be answered
  honestly by a human, not a model

## A concrete low-cost workflow

1. **Plan** with a frontier model. Get the approach and the failure modes right;
   this is the cheapest place to spend real money.
2. **Implement** with a local model via Cline, one module at a time.
3. **Verify** with the toolchain, not with a model:
   ```bash
   ruff format . && ruff check . && mypy app tests scripts && pytest -q
   ```
4. **Review** security- and legal-critical diffs with a frontier model, then a
   human.
5. **Never** let any model — local or frontier — promote a `review_status`. That
   requires a human and a `ReviewEvent`, and the database enforces it.

The economics work because steps 2 and 3 are the bulk of the hours and cost
nothing, while steps 1 and 4 are where correctness is actually determined.
