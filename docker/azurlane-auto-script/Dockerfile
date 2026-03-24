# ─── Stage 1: build conda env ────────────────────────────────────────────────
FROM continuumio/miniconda3:25.9.1-3 AS builder

ARG UPSTREAM_VERSION=master
ARG REPO_URL=https://github.com/LmeSzinc/AzurLaneAutoScript.git

RUN apt-get update && apt-get install -y --no-install-recommends \
        git build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN git clone --depth=1 --branch "${UPSTREAM_VERSION}" "${REPO_URL}" alas

RUN conda config --system --add channels conda-forge \
    && conda config --system --set channel_priority strict \
    && conda install -y -n base mamba \
    && conda clean -afy

RUN AV_VERSION=$(grep -E '^av==' /build/alas/requirements.txt | cut -d= -f3) \
    && mamba create -y -p /opt/alas_env \
        python=3.7 "av==${AV_VERSION}" \
    && conda clean -afy

RUN /opt/alas_env/bin/pip install --no-cache-dir --upgrade pip setuptools wheel \
    && grep -Ev '^(av|pywin32)==' /build/alas/requirements.txt \
        > /tmp/req_pip.txt \
    && /opt/alas_env/bin/pip install --no-cache-dir -r /tmp/req_pip.txt

# ─── Stage 2: runtime ────────────────────────────────────────────────────────
FROM debian:bookworm-slim

ARG UPSTREAM_VERSION
ARG UPSTREAM_SHA

LABEL upstream-repo=LmeSzinc/AzurLaneAutoScript \
    org.opencontainers.image.version="${UPSTREAM_VERSION}" \
    org.opencontainers.image.revision="${UPSTREAM_SHA}" \
    org.opencontainers.image.source="https://github.com/MewCluster/container"

RUN apt-get update && apt-get install -y --no-install-recommends \
        adb \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        ca-certificates \
        openssh-client \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/alas_env /opt/alas_env
COPY --from=builder /build/alas    /app/AzurLaneAutoScript

WORKDIR /app/AzurLaneAutoScript

ENV PATH="/opt/alas_env/bin:${PATH}" \
    PYTHONPATH="/app/AzurLaneAutoScript" \
    PYTHONUNBUFFERED=1

CMD ["python", "gui.py"]