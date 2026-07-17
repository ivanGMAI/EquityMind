# syntax=docker/dockerfile:1

# =============================================================================
# EquityMind — container image
# -----------------------------------------------------------------------------
# Multi-stage build using uv for fast, reproducible dependency installation.
# Stage 1 resolves the locked environment; stage 2 is a slim runtime image.
# =============================================================================

# ---- Stage 1: build the virtual environment from the lockfile ---------------
FROM python:3.12-slim AS builder

# Install uv from PyPI: ghcr.io (its official image registry) is unreachable
# from some networks, while PyPI is consistently available.
RUN pip install --no-cache-dir uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Install dependencies first (cached layer) using only the lock + manifest,
# so application-code changes don't invalidate the dependency cache.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Now copy the source and install the project itself.
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---- Stage 2: minimal runtime ----------------------------------------------
FROM python:3.12-slim AS runtime

# Run as a non-root user.
RUN useradd --create-home --uid 1000 equity
WORKDIR /app

# Bring over the resolved virtualenv and the application code.
COPY --from=builder --chown=equity:equity /app /app

# Put the venv on PATH so `equitymind` / `uvicorn` are directly callable.
# PYTHONPATH pins imports to /app/src: uv's cached project wheel can leave a
# stale copy in site-packages, and the live source must always win over it.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    EQUITYMIND_CONFIG=config/config.yaml

USER equity
EXPOSE 8000

# Default: serve the FastAPI backend. Override the command to use the CLI,
# e.g. `docker run --rm equitymind equitymind run AAPL MSFT --no-ai`.
CMD ["uvicorn", "equitymind.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
