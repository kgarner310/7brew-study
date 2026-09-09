# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# IDEA Atlas API image.
# Multi-stage: dependencies resolve in a builder, the runtime carries no
# toolchain and runs as an unprivileged user.
# ---------------------------------------------------------------------------
ARG PYTHON_VERSION=3.12

# --- builder ---------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /build

# Dependency layer: cached until pyproject.toml changes.
COPY pyproject.toml README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv /opt/venv && \
    VIRTUAL_ENV=/opt/venv uv pip install --no-cache .

COPY app ./app
RUN --mount=type=cache,target=/root/.cache/uv \
    VIRTUAL_ENV=/opt/venv uv pip install --no-cache --no-deps .

# --- runtime ---------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

# libpq is needed by psycopg; curl is the healthcheck client.
RUN apt-get update && \
    apt-get install --no-install-recommends -y libpq5 curl && \
    rm -rf /var/lib/apt/lists/* && \
    useradd --create-home --uid 10001 --shell /usr/sbin/nologin atlas

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    IDEA_ATLAS_API_HOST=0.0.0.0 \
    IDEA_ATLAS_API_PORT=8000

COPY --from=builder /opt/venv /opt/venv

WORKDIR /srv/idea-atlas
COPY --chown=atlas:atlas app ./app
COPY --chown=atlas:atlas migrations ./migrations
COPY --chown=atlas:atlas data ./data
COPY --chown=atlas:atlas alembic.ini pyproject.toml README.md ./

USER atlas
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# No migrations on start: schema changes are an explicit, auditable step.
# Run `idea-atlas db upgrade` as a separate job before rolling out.
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
