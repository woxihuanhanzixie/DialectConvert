#!/usr/bin/env bash
set -euo pipefail

HOST_NAME="${1:-43.139.53.84}"
USER_NAME="${2:-root}"
REMOTE_DIR="${3:-/opt/dialect-convert}"
APP_PORT="${4:-7860}"
PUBLIC_BASE_URL="${5:-http://${HOST_NAME}}"
KEY_PATH="${DIALECT_DEPLOY_KEY:-$HOME/.ssh/dialectconvert_key.pem}"

if [[ ! -f "$KEY_PATH" ]]; then
  echo "SSH private key not found: $KEY_PATH" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARCHIVE="/tmp/dialect-convert-deploy.tar.gz"
TARGET="${USER_NAME}@${HOST_NAME}"
SSH_OPTS=(-i "$KEY_PATH" -o StrictHostKeyChecking=accept-new)

cd "$ROOT_DIR"
git archive --format=tar.gz -o "$ARCHIVE" HEAD

ssh "${SSH_OPTS[@]}" "$TARGET" "mkdir -p '$REMOTE_DIR'"
scp "${SSH_OPTS[@]}" "$ARCHIVE" "${TARGET}:/tmp/dialect-convert-deploy.tar.gz"

ssh "${SSH_OPTS[@]}" "$TARGET" bash -s -- "$REMOTE_DIR" "$APP_PORT" "$PUBLIC_BASE_URL" "$HOST_NAME" <<'REMOTE'
set -euo pipefail

REMOTE_DIR="$1"
APP_PORT="$2"
PUBLIC_BASE_URL="$3"
HOST_NAME="$4"

cd "$REMOTE_DIR"
tar -xzf /tmp/dialect-convert-deploy.tar.gz -C "$REMOTE_DIR"

python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

mkdir -p runtime_data/uploads runtime_data/outputs runtime_data/voice_cache
if [[ ! -f .env ]]; then
  cp .env.prod.example .env || true
fi

python3 - "$PUBLIC_BASE_URL" <<'PYENV'
from pathlib import Path
import sys

public_base_url = sys.argv[1]
path = Path(".env")
raw = path.read_text(encoding="utf-8-sig") if path.exists() else ""
lines = [line for line in raw.replace("\ufeff", "").splitlines() if line.strip()]
updates = {
    "PUBLIC_BASE_URL": public_base_url,
    "PUBLIC_APP_ORIGIN": public_base_url,
    "TTS_PROVIDER": "dashscope_cosyvoice",
    "VOICE_MATCH_PROVIDER": "cosyvoice_clone",
    "QWEN_TTS_BASE_URL": "https://dashscope.aliyuncs.com",
    "QWEN_TTS_MODEL": "cosyvoice-v3-flash",
    "QWEN_TTS_VOICE": "longanyang",
    "QWEN_VOICE_ENROLLMENT_MODEL": "voice-enrollment",
    "QWEN_VOICE_TARGET_MODEL": "cosyvoice-v3-flash",
    "QWEN_TTS_VC_MODEL": "cosyvoice-v3-flash",
    "QWEN_VOICE_ENROLLMENT_URL": "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization",
}
seen = set()
out = []
for line in lines:
    key = line.split("=", 1)[0].strip()
    if key in updates:
        if key not in seen:
            out.append(f"{key}={updates[key]}")
            seen.add(key)
    else:
        out.append(line)
for key, value in updates.items():
    if key not in seen:
        out.append(f"{key}={value}")
path.write_text("\n".join(out) + "\n", encoding="utf-8")
PYENV

cat >/etc/systemd/system/dialect-convert.service <<SERVICE
[Unit]
Description=Dialect Convert Voice Clone Web Service
After=network.target

[Service]
Type=simple
WorkingDirectory=$REMOTE_DIR
EnvironmentFile=$REMOTE_DIR/.env
ExecStart=$REMOTE_DIR/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port $APP_PORT
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

mkdir -p /etc/nginx/conf.d
[[ -f /etc/nginx/conf.d/demo1.conf ]] && mv -f /etc/nginx/conf.d/demo1.conf /etc/nginx/conf.d/demo1.conf.bak-dialect || true
[[ -f /etc/nginx/conf.d/dialect_public.conf ]] && mv -f /etc/nginx/conf.d/dialect_public.conf /etc/nginx/conf.d/dialect_public.conf.bak-dialect || true

cat >/etc/nginx/conf.d/dialect_convert.conf <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name $HOST_NAME _;

    client_max_body_size 80m;
    proxy_read_timeout 600s;
    proxy_send_timeout 600s;
    proxy_connect_timeout 60s;

    location / {
        proxy_pass http://127.0.0.1:$APP_PORT;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX

systemctl daemon-reload
systemctl enable dialect-convert
systemctl restart dialect-convert
nginx -t
systemctl reload nginx
systemctl --no-pager --full status dialect-convert
grep -n "\\\\u8bf7\\\\u7528\\\\u5e7f\\\\u4e1c\\\\u8bdd\\\\u8868\\\\u8fbe" app/pipeline.py
REMOTE

echo "Deployment finished. Visit: $PUBLIC_BASE_URL"
