FROM node:24-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POT_PROVIDER_HOME=/opt/bgutil-ytdlp-pot-provider/server

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates ffmpeg git python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN python3 -m venv /opt/venv \
    && pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

ARG BGUTIL_COMMIT=7608dd51ee813b48cf9a6d68c6e42cb197ce10e0
RUN git init /opt/bgutil-ytdlp-pot-provider \
    && git -C /opt/bgutil-ytdlp-pot-provider remote add origin https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git \
    && git -C /opt/bgutil-ytdlp-pot-provider fetch --depth 1 origin "$BGUTIL_COMMIT" \
    && git -C /opt/bgutil-ytdlp-pot-provider checkout --detach FETCH_HEAD \
    && npm --prefix /opt/bgutil-ytdlp-pot-provider/server ci \
    && cd /opt/bgutil-ytdlp-pot-provider/server \
    && npx tsc \
    && rm -rf /opt/bgutil-ytdlp-pot-provider/.git /root/.npm

COPY app.py ./app.py
EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1", "--no-access-log"]
