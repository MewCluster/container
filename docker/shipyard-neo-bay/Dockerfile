FROM ghcr.io/astrbotdevs/shipyard-neo-bay:latest AS upstream

FROM upstream AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN VIRTUAL_ENV=/app/.venv uv pip install asyncpg --no-cache

FROM upstream

ARG UPSTREAM_VERSION=main
ARG UPSTREAM_SHA

LABEL upstream-repo=AstrBotDevs/shipyard-neo
LABEL org.opencontainers.image.version="${UPSTREAM_VERSION}"
LABEL org.opencontainers.image.revision="${UPSTREAM_SHA}"
LABEL org.opencontainers.image.source="https://github.com/MewCluster/container"

COPY --from=builder /app/.venv /app/.venv