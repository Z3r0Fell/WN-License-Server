#!/usr/bin/env bash
# =============================================================================
#  WatchNexus Licensing Server - one-shot Ubuntu installer
# =============================================================================
#  Tested on Ubuntu 22.04 LTS / 24.04 LTS (fresh VPS, root or sudo).
#  Idempotent: safe to re-run.
#
#  Usage:
#    sudo bash install.sh \
#      --admin-domain    licenses.watchnexus.ca    \
#      --customer-domain techhub.watchnexus.ca    \
#      --email           you@watchnexus.ca
#
#  Optional flags:
#    --skip-tls          # skip Let's Encrypt (use this if DNS isn't ready yet)
#    --source-dir <dir>  # path to the watchnexus repo (defaults to script's parent)
# =============================================================================
set -Eeuo pipefail

# ---------- helpers ----------
color()   { printf '\033[%sm%s\033[0m\n' "$1" "$2"; }
blue()    { color '1;34' "$*"; }
green()   { color '1;32' "$*"; }
yellow()  { color '1;33' "$*"; }
red()     { color '1;31' "$*"; }
banner()  { blue "=================================================================="; blue "$*"; blue "=================================================================="; }

require_root() {
  if [[ $EUID -ne 0 ]]; then red "Please run as root (sudo bash install.sh ...)"; exit 1; fi
}

require_ubuntu() {
  if ! grep -qiE 'ubuntu' /etc/os-release 2>/dev/null; then
    yellow "WARNING: this installer is tested on Ubuntu only. Continuing anyway."
  fi
}

# ---------- args ----------
ADMIN_DOMAIN=""
CUSTOMER_DOMAIN=""
LE_EMAIL=""
SKIP_TLS=0
SOURCE_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --admin-domain)     ADMIN_DOMAIN="$2"; shift 2;;
    --customer-domain)  CUSTOMER_DOMAIN="$2"; shift 2;;
    --email)            LE_EMAIL="$2"; shift 2;;
    --skip-tls)         SKIP_TLS=1; shift;;
    --source-dir)       SOURCE_DIR="$2"; shift 2;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//' | head -n 40
      exit 0;;
    *) red "Unknown argument: $1"; exit 1;;
  esac
done

if [[ -z "$ADMIN_DOMAIN" || -z "$CUSTOMER_DOMAIN" || -z "$LE_EMAIL" ]]; then
  red "Missing required arguments."
  echo
  echo "Usage:"
  echo "  sudo bash install.sh \\"
  echo "    --admin-domain    licenses.watchnexus.ca \\"
  echo "    --customer-domain techhub.watchnexus.ca \\"
  echo "    --email           you@watchnexus.ca"
  exit 1
fi

require_root
require_ubuntu

INSTALL_DIR="/opt/watchnexus"
DEPLOY_DIR="$INSTALL_DIR/deploy"

if [[ -z "$SOURCE_DIR" ]]; then
  SOURCE_DIR="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd || pwd)"
fi

banner "WatchNexus installer"
echo "  admin-domain    : $ADMIN_DOMAIN"
echo "  customer-domain : $CUSTOMER_DOMAIN"
echo "  email           : $LE_EMAIL"
echo "  source-dir      : $SOURCE_DIR"
echo "  install-dir     : $INSTALL_DIR"
[[ $SKIP_TLS -eq 1 ]] && yellow "  TLS issuance is SKIPPED (--skip-tls)"
echo

# ---------- 1. system packages ----------
banner "Step 1/7 - System packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg lsb-release ufw rsync openssl jq git

# ---------- 2. docker ----------
banner "Step 2/7 - Docker"
if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  ARCH=$(dpkg --print-architecture)
  CODENAME=$(. /etc/os-release && echo "$VERSION_CODENAME")
  echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $CODENAME stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker
docker --version
docker compose version

# ---------- 3. firewall ----------
banner "Step 3/7 - Firewall (UFW)"
ufw allow OpenSSH || true
ufw allow 80/tcp  || true
ufw allow 443/tcp || true
yes | ufw enable >/dev/null 2>&1 || true
ufw status | head -n 10

# ---------- 4. copy code ----------
banner "Step 4/7 - Project files -> $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

# If we're already running from inside the install dir (typical `git clone`
# straight to /opt/watchnexus flow), skip the rsync — copying a dir onto
# itself with --delete is destructive.
SRC_REAL="$(readlink -f "$SOURCE_DIR")"
DST_REAL="$(readlink -f "$INSTALL_DIR")"
if [[ "$SRC_REAL" == "$DST_REAL" ]]; then
  green "  source and install dir are the same ($DST_REAL) — skipping rsync."
else
  rsync -a --delete --exclude='node_modules' --exclude='__pycache__' --exclude='backups' \
        --exclude='.git' --exclude='build' --exclude='*.pyc' \
        "$SOURCE_DIR/" "$INSTALL_DIR/"
fi
chmod +x "$INSTALL_DIR/backend/scripts/backup_mongo.sh" 2>/dev/null || true
chmod +x "$INSTALL_DIR/deploy/backup_host.sh" 2>/dev/null || true

# ---------- 5. .env ----------
banner "Step 5/7 - Configuration (.env)"
ENV_FILE="$DEPLOY_DIR/.env"
# Accept either `.env.example` (canonical) or `env.example` (in case the
# dotfile got dropped by a .gitignore upstream).
ENV_EXAMPLE=""
for candidate in "$DEPLOY_DIR/.env.example" "$DEPLOY_DIR/env.example"; do
  if [[ -f "$candidate" ]]; then ENV_EXAMPLE="$candidate"; break; fi
done

if [[ ! -f "$ENV_FILE" ]]; then
  if [[ -z "$ENV_EXAMPLE" ]]; then
    red "  Could not find .env.example or env.example in $DEPLOY_DIR"
    red "  Re-clone the repo or pull the latest commit and retry."
    exit 1
  fi
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  green "  created $ENV_FILE from $(basename "$ENV_EXAMPLE")"
fi

jwt=$(openssl rand -hex 32)
hmacs=$(openssl rand -hex 32)
adminpw=$(openssl rand -hex 12)

upsert() {
  local key="$1" val="$2"
  if grep -qE "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
  else
    echo "${key}=${val}" >> "$ENV_FILE"
  fi
}

# Only generate fresh secrets if the placeholders are still in place.
if grep -q '^JWT_SECRET=change-me' "$ENV_FILE" || ! grep -qE '^JWT_SECRET=.{20}' "$ENV_FILE"; then
  upsert JWT_SECRET "$jwt"
fi
if grep -q '^HMAC_LICENSE_SECRET=change-me' "$ENV_FILE" || ! grep -qE '^HMAC_LICENSE_SECRET=.{20}' "$ENV_FILE"; then
  upsert HMAC_LICENSE_SECRET "$hmacs"
fi
if grep -q '^SEED_ADMIN_PASSWORD=change-this' "$ENV_FILE" || grep -q '^SEED_ADMIN_PASSWORD=admin12345' "$ENV_FILE" || ! grep -qE '^SEED_ADMIN_PASSWORD=.{8}' "$ENV_FILE"; then
  upsert SEED_ADMIN_PASSWORD "$adminpw"
fi

upsert DOMAIN "$ADMIN_DOMAIN"
upsert CUSTOMER_DOMAIN "$CUSTOMER_DOMAIN"
upsert LETSENCRYPT_EMAIL "$LE_EMAIL"
upsert SEED_ADMIN_EMAIL "admin@$ADMIN_DOMAIN"
upsert APP_PUBLIC_URL "https://$ADMIN_DOMAIN"
upsert CUSTOMER_PORTAL_URL "https://$CUSTOMER_DOMAIN"
upsert EMAIL_FROM "licenses@$ADMIN_DOMAIN"
upsert CORS_ORIGINS "https://$ADMIN_DOMAIN,https://$CUSTOMER_DOMAIN"

# Bake REACT_APP_BACKEND_URL="" + REACT_APP_CUSTOMER_PORTAL_HOST for the frontend build
upsert REACT_APP_CUSTOMER_PORTAL_HOST "$CUSTOMER_DOMAIN"

# ---------- 6. nginx config ----------
banner "Step 6/7 - Edge nginx (two server blocks)"
NGINX_TEMPLATE="$DEPLOY_DIR/nginx/edge.conf.template"
NGINX_LIVE="$DEPLOY_DIR/nginx/edge.conf"

# Build a multi-server-block edge config that handles BOTH hostnames.
cat > "$NGINX_LIVE" << EOF
# Auto-generated by install.sh - do not edit; re-run installer to update.

# Plain HTTP -> HTTPS redirect (and ACME challenge passthrough)
server {
    listen 80;
    listen [::]:80;
    server_name $ADMIN_DOMAIN $CUSTOMER_DOMAIN;

    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://\$host\$request_uri; }
}

# Admin / API host
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name $ADMIN_DOMAIN;

    ssl_certificate     /etc/letsencrypt/live/$ADMIN_DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$ADMIN_DOMAIN/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    client_max_body_size 10m;

    location /api/ {
        proxy_pass http://backend:8001;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location / {
        proxy_pass http://web:80;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}

# Customer portal host
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name $CUSTOMER_DOMAIN;

    ssl_certificate     /etc/letsencrypt/live/$CUSTOMER_DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$CUSTOMER_DOMAIN/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    client_max_body_size 10m;

    location /api/ {
        proxy_pass http://backend:8001;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Customer portal subdomain - the SPA also auto-redirects '/' to /portal/login
    location / {
        proxy_pass http://web:80;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

green "  wrote $NGINX_LIVE"

# ---------- 6.5. Let's Encrypt ----------
banner "Step 6/7 - Let's Encrypt certificates"
if [[ $SKIP_TLS -eq 1 ]]; then
  yellow "Skipping certificate issuance (--skip-tls)."
  yellow "You MUST run certbot before nginx can start with TLS."
else
  mkdir -p /etc/letsencrypt /var/log/letsencrypt
  for dom in "$ADMIN_DOMAIN" "$CUSTOMER_DOMAIN"; do
    if [[ -d "/etc/letsencrypt/live/$dom" ]]; then
      green "  cert for $dom already exists, skipping."
      continue
    fi
    blue "  Requesting cert for $dom ..."
    docker run --rm -p 80:80 \
      -v /etc/letsencrypt:/etc/letsencrypt \
      -v /var/log/letsencrypt:/var/log/letsencrypt \
      certbot/certbot:latest certonly --standalone --non-interactive --agree-tos \
        -m "$LE_EMAIL" -d "$dom" || {
          red "  Certbot failed for $dom. Common cause: DNS A-record not pointing at this VPS yet."
          red "  Resolve DNS, then re-run: sudo bash install.sh ... (idempotent)"
        }
  done
fi

# ---------- 7. Start stack ----------
banner "Step 7/7 - Starting Docker stack"
cd "$DEPLOY_DIR"
docker compose up -d --build

# systemd units
blue "  installing systemd timers (backup + cert renewal)"
cp "$DEPLOY_DIR/systemd/"watchnexus-*.service /etc/systemd/system/
cp "$DEPLOY_DIR/systemd/"watchnexus-*.timer   /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now watchnexus-backup.timer  || yellow "backup timer not enabled"
systemctl enable --now watchnexus-certbot.timer || yellow "certbot timer not enabled"

# Bring the host nginx back up once certs exist
if [[ $SKIP_TLS -ne 1 ]]; then
  docker compose restart nginx 2>/dev/null || true
fi

# ---------- Summary ----------
banner "All done"
echo
green "  Admin URL    :  https://$ADMIN_DOMAIN"
green "  Customer URL :  https://$CUSTOMER_DOMAIN"
green "  Docs         :  https://$ADMIN_DOMAIN/docs"
echo
green "  Seeded admin :"
green "    email      :  admin@$ADMIN_DOMAIN"
green "    password   :  $(grep '^SEED_ADMIN_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"
echo
yellow "Verify with:"
echo "  curl -i https://$ADMIN_DOMAIN/api/health"
echo "  docker compose -f $DEPLOY_DIR/docker-compose.yml ps"
echo
yellow "If DNS isn't ready yet, you can re-run this script when it is - it's idempotent."
