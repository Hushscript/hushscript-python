ARG PYTHON_VERSION=3.11

FROM python:3.11-slim-bookworm@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89 AS python3.11
FROM python:3.14-slim-bookworm@sha256:48b13b003dda20b16f9442b8475aa05fe21bf6579a8c881db92ffb4d8fd20f83 AS python3.14
FROM ghcr.io/astral-sh/uv:0.12.23@sha256:61d393e44e249f2e4b526b6c7ddcecce245946826e608e11c93ad4f5bba55b21 AS uv

# python3.11 and python3.14 above are the digest-pinned images; the build arg only selects one.
# hadolint ignore=DL3006
FROM python${PYTHON_VERSION} AS base
RUN groupadd --gid 10001 dev && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin dev
COPY --from=uv /uv /usr/local/bin/uv
ENV HOME=/tmp \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_CACHE_DIR=/tmp/uv-cache \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON_PREFERENCE=only-system \
    UV_NO_PROGRESS=1
WORKDIR /work

FROM base AS deps
COPY pyproject.toml uv.lock ./
RUN UV_PROJECT_ENVIRONMENT=/work/.venv uv sync --frozen --no-install-project

# The tools live in /work/.venv/bin; src is on PYTHONPATH instead of being installed, so the
# read-only container never has to write into the environment.
FROM base AS dev
ENV PATH=/work/.venv/bin:$PATH \
    PYTHONPATH=/work/src \
    RUFF_CACHE_DIR=/tmp/ruff-cache \
    COVERAGE_FILE=/tmp/.coverage \
    HYPOTHESIS_STORAGE_DIRECTORY=/tmp/hypothesis
COPY --from=deps /work/.venv .venv
COPY --chown=10001:10001 . .
USER 10001:10001

# Runtime dependencies only: `just build` installs the built wheel next to these with no network.
FROM base AS proddeps
COPY pyproject.toml uv.lock ./
RUN UV_PROJECT_ENVIRONMENT=/opt/venv uv sync --frozen --no-install-project --no-dev
