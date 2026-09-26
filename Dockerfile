# syntax=docker/dockerfile:1.7

ARG GO_VERSION=1.26.6
ARG PYTHON_VERSION=3.12

FROM golang:${GO_VERSION}-bookworm AS bridge-builder
WORKDIR /build/bridge-e2ee

COPY bridge-e2ee/go.mod bridge-e2ee/go.sum ./
COPY bridge-e2ee/meta ./meta
RUN test -f meta/go.mod || (echo "bridge-e2ee/meta is missing; initialize git submodules before building" >&2; exit 1)
RUN --mount=type=cache,target=/go/pkg/mod,sharing=locked go mod download

COPY bridge-e2ee/main.go ./main.go
COPY bridge-e2ee/bridge ./bridge
RUN --mount=type=cache,target=/root/.cache/go-build,sharing=locked \
    CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/fbchat-bridge-e2ee .

FROM python:${PYTHON_VERSION}-slim-bookworm AS python-builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /build

COPY pyproject.toml README.md README_EN.md CHANGELOG.md LICENSE ./
COPY src/fbchat_v2 ./src/fbchat_v2
RUN python -m pip install --prefix=/install ".[service]"

FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FBCHAT_E2EE_BIN=/usr/local/bin/fbchat-bridge-e2ee \
    FBCHAT_E2EE_REQUIRED=true \
    FBCHAT_STATE_DIR=/var/lib/fbchat

RUN groupadd --gid 10001 fbchat \
    && useradd --uid 10001 --gid fbchat --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin fbchat \
    && install -d -o fbchat -g fbchat -m 0700 /var/lib/fbchat

COPY --from=python-builder /install /usr/local
COPY --from=bridge-builder --chown=root:root /out/fbchat-bridge-e2ee /usr/local/bin/fbchat-bridge-e2ee

USER 10001:10001
WORKDIR /var/lib/fbchat
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/readyz', timeout=3).read()"]

CMD ["python", "-m", "uvicorn", "fbchat_v2.service:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
