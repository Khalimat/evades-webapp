# Build context is the repo root's `backend/` directory (see docker-compose.yml)
# so this image shares the exact same app/ code as the API — only the
# installed binaries differ.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        hmmer \
        wget \
        ca-certificates \
        tar \
    && rm -rf /var/lib/apt/lists/*

# Foldseek: static Linux binary from the official release.
# TARGETARCH is set automatically by Docker's buildx (amd64 on most
# cloud VMs / Intel Macs, arm64 on Apple Silicon Macs) — this picks
# the matching native build so Apple Silicon runs without emulation.
ARG TARGETARCH
RUN case "${TARGETARCH}" in \
        "arm64") FOLDSEEK_URL="https://mmseqs.com/foldseek/foldseek-linux-arm64.tar.gz" ;; \
        "amd64") FOLDSEEK_URL="https://mmseqs.com/foldseek/foldseek-linux-avx2.tar.gz" ;; \
        *) echo "Unsupported architecture: ${TARGETARCH}" && exit 1 ;; \
    esac \
    && wget -q "${FOLDSEEK_URL}" -O /tmp/foldseek.tar.gz \
    && tar -xzf /tmp/foldseek.tar.gz -C /usr/local \
    && ln -s /usr/local/foldseek/bin/foldseek /usr/local/bin/foldseek \
    && rm /tmp/foldseek.tar.gz

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

CMD ["rq", "worker", "--url", "redis://redis:6379/0", "default"]
