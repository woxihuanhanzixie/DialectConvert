param(
  [Parameter(Mandatory = $true)]
  [string]$HostName,
  [string]$User = "root",
  [string]$RemoteDir = "/opt/dialect-convert",
  [string]$KeyPath = "C:\Users\34005\Downloads\dialectconvert_key.pem",
  [int]$AppPort = 7860,
  [string]$PublicBaseUrl = ""
)

$ErrorActionPreference = "Stop"

if (!(Test-Path $KeyPath)) {
  throw "SSH private key not found: $KeyPath"
}

$archive = Join-Path $env:TEMP "dialect-convert-deploy.zip"
if (Test-Path $archive) { Remove-Item $archive -Force }

$exclude = @(".git", ".vscode", "runtime_data", "__pycache__", ".pytest_cache", ".venv", "venv")
$items = Get-ChildItem -Force | Where-Object { $exclude -notcontains $_.Name }
Compress-Archive -Path $items.FullName -DestinationPath $archive -Force

$target = "$User@$HostName"
$sshOptions = @("-i", $KeyPath, "-o", "StrictHostKeyChecking=accept-new")
if (!$PublicBaseUrl) {
  $PublicBaseUrl = "http://${HostName}"
}

ssh @sshOptions $target "mkdir -p $RemoteDir"
scp @sshOptions $archive "${target}:/tmp/dialect-convert-deploy.zip"
ssh @sshOptions $target @"
set -e
cd "$RemoteDir"
if command -v unzip >/dev/null 2>&1; then
  unzip -o /tmp/dialect-convert-deploy.zip -d "$RemoteDir"
else
  python3 -m zipfile -e /tmp/dialect-convert-deploy.zip "$RemoteDir"
fi
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
mkdir -p runtime_data/uploads runtime_data/outputs runtime_data/voice_cache
if [ ! -f .env ]; then cp .env.prod.example .env || true; fi
if grep -q '^PUBLIC_BASE_URL=' .env 2>/dev/null; then
  sed -i "s|^PUBLIC_BASE_URL=.*|PUBLIC_BASE_URL=$PublicBaseUrl|" .env
else
  printf '\nPUBLIC_BASE_URL=$PublicBaseUrl\n' >> .env
fi
if grep -q '^PUBLIC_APP_ORIGIN=' .env 2>/dev/null; then
  sed -i "s|^PUBLIC_APP_ORIGIN=.*|PUBLIC_APP_ORIGIN=$PublicBaseUrl|" .env
else
  printf 'PUBLIC_APP_ORIGIN=$PublicBaseUrl\n' >> .env
fi
cat >/etc/systemd/system/dialect-convert.service <<'SERVICE'
[Unit]
Description=Dialect Convert Voice Clone Web Service
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/dialect-convert
EnvironmentFile=/opt/dialect-convert/.env
ExecStart=/opt/dialect-convert/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port APP_PORT_PLACEHOLDER
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE
sed -i "s|APP_PORT_PLACEHOLDER|$AppPort|g" /etc/systemd/system/dialect-convert.service
mkdir -p /etc/nginx/conf.d
[ -f /etc/nginx/conf.d/demo1.conf ] && mv -f /etc/nginx/conf.d/demo1.conf /etc/nginx/conf.d/demo1.conf.bak-dialect || true
[ -f /etc/nginx/conf.d/dialect_public.conf ] && mv -f /etc/nginx/conf.d/dialect_public.conf /etc/nginx/conf.d/dialect_public.conf.bak-dialect || true
cat >/etc/nginx/conf.d/dialect_convert.conf <<'NGINX'
server {
    listen 80;
    listen [::]:80;
    server_name $HostName _;

    client_max_body_size 80m;
    proxy_read_timeout 600s;
    proxy_send_timeout 600s;
    proxy_connect_timeout 60s;

    location / {
        proxy_pass http://127.0.0.1:APP_PORT_PLACEHOLDER;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_set_header Upgrade `$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host `$host;
        proxy_set_header X-Real-IP `$remote_addr;
        proxy_set_header X-Forwarded-For `$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto `$scheme;
    }
}
NGINX
sed -i "s|APP_PORT_PLACEHOLDER|$AppPort|g" /etc/nginx/conf.d/dialect_convert.conf
systemctl daemon-reload
systemctl enable dialect-convert
systemctl restart dialect-convert
nginx -t && systemctl reload nginx
systemctl --no-pager status dialect-convert
"@

Write-Host "Deployment finished. Visit: $PublicBaseUrl"
