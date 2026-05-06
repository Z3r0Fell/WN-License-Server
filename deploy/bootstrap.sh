#!/usr/bin/env bash
# Bootstrap script for WatchNexus on a fresh Ubuntu 22.04 / 24.04 VPS.
# Idempotent: safe to run multiple times.
set -euo pipefail

DOMAIN="${1:-}"
LETSENCRYPT_EMAIL="${2:-}"

if [[ -z "$DOMAIN" || -z "$LETSENCRYPT_EMAIL" ]]; then
  echo "Usage: sudo bash bootstrap.sh <domain> <letsencrypt-email>"
  echo "Example: sudo bash bootstrap.sh licenses.example.com you@example.com"
  exit 1
fi

INSTALL_DIR="/opt/watchnexus"

echo "==> Installing system packages"
apt-get update -y
apt-get install -y --no-install-recommends ca-certificates curl gnupg lsb-release ufw

if ! command -v docker >/dev/null 2>&1; then
  echo "==> Installing Docker"
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  ARCH=$(dpkg --print-architecture)
  CODENAME=$(. /etc/os-release && echo "$VERSION_CODENAME")
  echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $CODENAME stable" > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

systemctl enable --now docker

echo "==> Configuring firewall"
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "==> Preparing $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
rsync -a --delete /opt/_watchnexus_src/  "$INSTALL_DIR/" 2>/dev/null || true

if [[ ! -f "$INSTALL_DIR/deploy/.env" ]]; then
  cp "$INSTALL_DIR/deploy/.env.example" "$INSTALL_DIR/deploy/.env"
  # Generate strong random secrets
  JWT=$(openssl rand -hex 32)
  HMACS=$(openssl rand -hex 32)
  ADMINPW=$(openssl rand -hex 12)
  sed -i "s|^DOMAIN=.*|DOMAIN=$DOMAIN|" "$INSTALL_DIR/deploy/.env"
  sed -i "s|^LETSENCRYPT_EMAIL=.*|LETSENCRYPT_EMAIL=$LETSENCRYPT_EMAIL|" "$INSTALL_DIR/deploy/.env"
  sed -i "s|^JWT_SECRET=.*|JWT_SECRET=$JWT|" "$INSTALL_DIR/deploy/.env"
  sed -i "s|^HMAC_LICENSE_SECRET=.*|HMAC_LICENSE_SECRET=$HMACS|" "$INSTALL_DIR/deploy/.env"
  sed -i "s|^SEED_ADMIN_EMAIL=.*|SEED_ADMIN_EMAIL=admin@$DOMAIN|" "$INSTALL_DIR/deploy/.env"
  sed -i "s|^SEED_ADMIN_PASSWORD=.*|SEED_ADMIN_PASSWORD=$ADMINPW|" "$INSTALL_DIR/deploy/.env"
  sed -i "s|^APP_PUBLIC_URL=.*|APP_PUBLIC_URL=https://$DOMAIN|" "$INSTALL_DIR/deploy/.env"
  sed -i "s|^EMAIL_FROM=.*|EMAIL_FROM=licenses@$DOMAIN|" "$INSTALL_DIR/deploy/.env"
  echo ""
  echo "=============================================="
  echo "Generated initial admin credentials:"
  echo "  email:    admin@$DOMAIN"
  echo "  password: $ADMINPW"
  echo "  (also stored in $INSTALL_DIR/deploy/.env as SEED_ADMIN_PASSWORD)"
  echo "=============================================="
fi

# Wire domain into the edge nginx config
sed -i "s|your-domain.com|$DOMAIN|g" "$INSTALL_DIR/deploy/nginx/edge.conf"

echo "==> Issuing TLS certificate via certbot (initial)"
mkdir -p /etc/letsencrypt
cd "$INSTALL_DIR/deploy"
# Bring up everything except edge nginx so port 80 is free for HTTP-01 standalone
docker compose up -d mongo backend web
sleep 8
# Use a one-shot certbot in standalone mode for the first cert
docker run --rm \
  -p 80:80 \
  -v /etc/letsencrypt:/etc/letsencrypt \
  certbot/certbot:latest certonly --standalone --non-interactive --agree-tos \
    -m "$LETSENCRYPT_EMAIL" -d "$DOMAIN" || {
  echo "!! Certbot failed. Make sure DNS A/AAAA for $DOMAIN points to this server,"
  echo "   then re-run this script. Continuing anyway so you can fix later."
}

echo "==> Starting full stack"
docker compose up -d --build

echo "==> Installing systemd timers (backup + certbot renew)"
cp "$INSTALL_DIR/deploy/systemd/"watchnexus-*.service /etc/systemd/system/
cp "$INSTALL_DIR/deploy/systemd/"watchnexus-*.timer   /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now watchnexus-backup.timer
systemctl enable --now watchnexus-certbot.timer

echo ""
echo "============================================================="
echo "  WatchNexus is up."
echo "  Site:   https://$DOMAIN"
echo "  Admin:  https://$DOMAIN/admin/login"
echo "  Docs:   https://$DOMAIN/docs"
echo "  Logs:   docker compose -f $INSTALL_DIR/deploy/docker-compose.yml logs -f"
echo "  Backups go to $INSTALL_DIR/deploy/backups (daily at 03:00 UTC)"
echo "============================================================="
