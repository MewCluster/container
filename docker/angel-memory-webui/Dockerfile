FROM python:3.11-slim

ARG UPSTREAM_VERSION=main
ARG UPSTREAM_SHA

LABEL upstream-repo=kawayiYokami/astrbot_plugin_angel_memory
LABEL org.opencontainers.image.version="${UPSTREAM_VERSION}"
LABEL org.opencontainers.image.revision="${UPSTREAM_SHA}"
LABEL org.opencontainers.image.source="https://github.com/MewCluster/container"

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && git clone --depth=1 --branch ${UPSTREAM_VERSION} \
       https://github.com/kawayiYokami/astrbot_plugin_angel_memory.git /tmp/plugin \
    && pip install --no-cache-dir \
       -i https://mirrors.aliyun.com/pypi/simple/ \
       --trusted-host mirrors.aliyun.com \
       streamlit \
       -r /tmp/plugin/debug_tool/requirements.txt \
    && rm -rf /tmp/plugin \
    && apt-get purge -y git && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /AstrBot/data/plugins/astrbot_plugin_angel_memory

ENTRYPOINT ["streamlit", "run", "debug_tool/app.py"]
CMD ["--server.port=8000", "--server.address=0.0.0.0", "--server.headless=true", "--browser.gatherUsageStats=false"]