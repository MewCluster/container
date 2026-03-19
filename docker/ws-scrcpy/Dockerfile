FROM node:20-bookworm-slim AS builder
ARG UPSTREAM_VERSION=master
ARG UPSTREAM_SHA

LABEL upstream-repo=NetrisTV/ws-scrcpy
LABEL org.opencontainers.image.version="${UPSTREAM_VERSION}"
LABEL org.opencontainers.image.revision="${UPSTREAM_SHA}"
LABEL org.opencontainers.image.source="https://github.com/MewCluster/container"

RUN apt-get update && apt-get install -y git build-essential python3 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ARG REPO_URL=https://github.com/NetrisTV/ws-scrcpy.git
RUN git clone --depth=1 --branch ${UPSTREAM_VERSION} $REPO_URL .

RUN npm install
RUN npm run dist

FROM node:20-bookworm-slim

ARG UPSTREAM_VERSION
ARG UPSTREAM_SHA

LABEL upstream-repo=NetrisTV/ws-scrcpy
LABEL org.opencontainers.image.version="${UPSTREAM_VERSION}"
LABEL org.opencontainers.image.revision="${UPSTREAM_SHA}"
LABEL org.opencontainers.image.source="https://github.com/your-org/container"

RUN apt-get update && apt-get install -y --no-install-recommends \
    git build-essential python3 \
    android-tools-adb \
    jq curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/dist ./dist
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]