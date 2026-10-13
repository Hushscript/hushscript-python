ARG PYTHON_VERSION=3.10

FROM python:3.11-slim-bookworm@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89 AS python3.11
FROM python:3.14-slim-bookworm@sha256:48b13b003dda20b16f9442b8475aa05fe21bf6579a8c881db92ffb4d8fd20f83 AS python3.14
FROM python:3.10-slim-bookworm@sha256:5be5aaecb962a41567bc8041f1e9e3432cb085b037fe057f9a562630b2e4b370 AS python3.10
FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS python3.12
FROM python:3.13-slim-bookworm@sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641 AS python3.13
# Build the final 3.15 runtime while the official Docker tags are unavailable.
FROM node:26-bookworm@sha256:f1233c415b41ffcf237c717b3dea92e9d4ea006e0e4c71edcb790605d74f5404 AS python3.15-build
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
WORKDIR /tmp/python-source
RUN timeout 120 curl -fsSL https://www.python.org/ftp/python/3.15.0/Python-3.15.0.tar.xz -o /tmp/python.tar.xz \
    && echo "ba4bed1ba346b916890b76d9e320451420aa69f6408997d33c66482eeae3d575  /tmp/python.tar.xz" | sha256sum -c - \
    && tar -xJf /tmp/python.tar.xz -C /tmp/python-source --strip-components=1 \
    && timeout 300 ./configure --prefix=/opt/python3.15 --enable-shared --with-ensurepip=install LDFLAGS="-Wl,-rpath=/opt/python3.15/lib" \
    && timeout 1800 make -j8 \
    && timeout 600 make install \
    && ln -s python3.15 /opt/python3.15/bin/python

FROM python:3.15-rc-slim-bookworm@sha256:ea93de1a70a03fffd10ad8cfde8f4ba969fe2658f0578af02855d1d32f49e6c2 AS python3.15
COPY --from=python3.15-build /opt/python3.15 /opt/python3.15
ENV PATH=/opt/python3.15/bin:$PATH
RUN python -c 'import sys, ssl, sqlite3, bz2, lzma, ctypes, zlib; assert sys.version_info[:3] == (3, 15, 0); assert sys.version_info.releaselevel == "final"'
FROM ghcr.io/astral-sh/uv:0.12.23@sha256:61d393e44e249f2e4b526b6c7ddcecce245946826e608e11c93ad4f5bba55b21 AS uv

# The runtime stages above are digest-pinned images; the build arg only selects one.
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
