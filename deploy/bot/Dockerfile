# Build context: thư mục gốc repository (xem deploy/docker-compose.yml).
# Ignore file: Dockerfile.dockerignore cạnh file này (BuildKit), để không thêm
# .dockerignore vào thư mục gốc của upstream.

# --- Stage 1: build Go E2EE bridge (static, không CGO) ---
FROM golang:1.26.10-alpine AS bridge
WORKDIR /src/bridge-e2ee
COPY bridge-e2ee/ ./
RUN --mount=type=cache,target=/root/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/fbchat-bridge-e2ee .

# --- Stage 2: runtime Python tối giản ---
FROM python:3.12-alpine

RUN pip install --no-cache-dir \
        "httpx>=0.27.0,<1" \
        "requests>=2.32.0,<3" \
        "paho-mqtt>=1.6.1,<3" \
        "pyotp>=2.9.0,<3" \
    && apk add --no-cache tini \
    && addgroup -g 1000 fbchat \
    && adduser -D -u 1000 -G fbchat fbchat \
    && mkdir -p /data \
    && chown fbchat:fbchat /data

WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/
# Runner nhiều tài khoản của fork; đặt cạnh main.py để import main.
COPY deploy/multi_main.py deploy/gateway_link.py deploy/connection_history.py deploy/session_keeper.py ./src/
COPY --from=bridge /out/fbchat-bridge-e2ee /app/build/fbchat-bridge-e2ee

USER fbchat
WORKDIR /data
# Mỗi tài khoản: /data/accounts/<tên>/config.json.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FBCHAT_E2EE_BIN=/app/build/fbchat-bridge-e2ee \
    FBCHAT_ACCOUNTS_DIR=/data/accounts \
    FBCHAT_HEALTH_FILE=/tmp/fbchat-health.json

# Healthy khi mọi tài khoản đã sẵn sàng E2EE ("running"). Có GATEWAY_URL thì chưa có
# tài khoản vẫn healthy: tài khoản đầu tiên được thêm từ trang "Tài khoản kênh".
HEALTHCHECK --interval=60s --timeout=5s --start-period=180s --retries=2 \
    CMD ["python", "-c", "import json,os,sys; s=json.load(open(os.environ['FBCHAT_HEALTH_FILE'])); sys.exit(0 if (s or os.environ.get('GATEWAY_URL')) and all(v == 'running' for v in s.values()) else 1)"]

ENTRYPOINT ["/sbin/tini", "--", "sh", "-c", "[ -n \"$GATEWAY_URL\" ] || ls /data/accounts/*/config.json >/dev/null 2>&1 || { echo 'Chưa có tài khoản trong /data/accounts - chạy dịch vụ login trước.' >&2; exit 1; }; exec python /app/src/multi_main.py"]
