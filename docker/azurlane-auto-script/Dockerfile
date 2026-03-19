FROM python:3.7-slim
ARG UPSTREAM_VERSION=master
ARG UPSTREAM_SHA

LABEL upstream-repo=LmeSzinc/AzurLaneAutoScript

LABEL org.opencontainers.image.version="${UPSTREAM_VERSION}"
LABEL org.opencontainers.image.revision="${UPSTREAM_SHA}"
LABEL org.opencontainers.image.source="https://github.com/MewCluster/container"

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget git adb libgomp1 openssh-client ca-certificates build-essential \
    libgl1-mesa-glx libglib2.0-0 \
    && git config --global --add safe.directory '*' \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# fix: https://github.com/LmeSzinc/AzurLaneAutoScript/issues/5322
RUN wget -q https://repo.anaconda.com/miniconda/Miniconda3-py313_25.9.1-3-Linux-x86_64.sh \
    -O /tmp/miniconda.sh \
    && bash /tmp/miniconda.sh -b -p /opt/conda \
    && rm /tmp/miniconda.sh

ENV PATH="/opt/conda/bin:${PATH}"

RUN conda config --system --remove channels defaults \
    && conda config --system --add channels conda-forge \
    && conda config --system --set channel_priority strict \
    && conda install -y mamba

WORKDIR /app

ARG REPO_URL=https://github.com/LmeSzinc/AzurLaneAutoScript.git
RUN git clone --depth=1 --branch ${UPSTREAM_VERSION} $REPO_URL AzurLaneAutoScript

WORKDIR /app/AzurLaneAutoScript

RUN AV_VERSION=$(grep -E '^av==' requirements.txt | cut -d '=' -f 3) \
    && echo "Installing av == $AV_VERSION" \
    && mamba install -y "python=3.7" "av==$AV_VERSION" \
    && conda clean --all --yes

RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && grep -Ev '^(av|pywin32|requests)==' requirements.txt > /tmp/requirements_filtered.txt \
    && pip install --no-cache-dir -r /tmp/requirements_filtered.txt \
    && rm /tmp/requirements_filtered.txt \
    && rm -rf ~/.cache/pip

CMD ["python", "gui.py"]