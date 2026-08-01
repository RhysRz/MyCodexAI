FROM node:22-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip python3-venv chromium git ca-certificates fonts-liberation \
    && python3 -m pip install --break-system-packages pytest \
    && useradd --create-home --shell /bin/bash sandbox \
    && rm -rf /var/lib/apt/lists/*

ENV BROWSER=/usr/bin/chromium
WORKDIR /workspace
USER sandbox
