# DEPLOY — WatchNexus Licensing Server on a VPS

> Goal: a working server at `https://your-domain.com` in **under 15 minutes**.
> Stack: Docker Compose · MongoDB · FastAPI · React (built static) · nginx · Let's Encrypt.

---

## What you need before you start

1. A **VPS** running **Ubuntu 22.04 or 24.04** (any provider — DigitalOcean, Hetzner, Linode, AWS Lightsail, etc).
2. A **domain name** (e.g. `licenses.example.com`) with a **DNS A record** pointing at your VPS public IP.
   👉 *Wait for DNS to propagate before continuing.* Test:
   `dig +short licenses.example.com` should return your VPS IP.
3. **SSH access** to the VPS as `root` (or any user with sudo).
4. The contents of this repo on your VPS at `/opt/watchnexus`.

---

## Option A — One command (recommended)

```bash
# On your laptop, push the repo to the VPS:
rsync -av --exclude node_modules --exclude __pycache__ /path/to/this/repo/ \
   root@YOUR_VPS_IP:/opt/_watchnexus_src/

# SSH into the VPS:
ssh root@YOUR_VPS_IP

# Run the bootstrap (replace placeholders):
sudo bash /opt/_watchnexus_src/deploy/bootstrap.sh \
     licenses.example.com  you@example.com
```

That's it. The script will:

- Install Docker + Docker Compose plugin
- Configure UFW firewall (only 22, 80, 443 open)
- Generate strong random `JWT_SECRET`, `HMAC_LICENSE_SECRET`, and a fresh admin password
- Issue a Let's Encrypt TLS certificate
- Bring up MongoDB, backend, frontend, nginx
- Enable a **daily backup** systemd timer (03:00 UTC, 14-day retention)
- Enable a **certbot renew** timer (twice daily)

**Watch the bootstrap output** — it prints the seeded admin email and password at the end. Save them.

When it's done, open:

- 🌐  `https://licenses.example.com`
- 🛠️  `https://licenses.example.com/admin/login`  ← log in with the printed admin credentials
- 📚  `https://licenses.example.com/docs`

---

## Option B — Manual (if you prefer to see every step)

### 1. Install Docker on the VPS

```bash
ssh root@YOUR_VPS_IP

apt-get update -y
apt-get install -y ca-certificates curl gnupg ufw rsync

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
ARCH=$(dpkg --print-architecture)
. /etc/os-release
echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $VERSION_CODENAME stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
```

### 2. Open the right ports

```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
```

### 3. Get the code onto the VPS

```bash
mkdir -p /opt/watchnexus
# from your laptop, in another terminal:
rsync -av --exclude node_modules --exclude __pycache__ ./ root@YOUR_VPS_IP:/opt/watchnexus/
```

### 4. Configure environment

```bash
cd /opt/watchnexus/deploy
cp .env.example .env
nano .env    # fill DOMAIN, LETSENCRYPT_EMAIL, secrets, webhook secrets, email

# Generate strong random secrets:
echo "JWT_SECRET=$(openssl rand -hex 32)"
echo "HMAC_LICENSE_SECRET=$(openssl rand -hex 32)"
# paste those values into .env (overwriting the placeholders)

# Replace `your-domain.com` in the nginx config with your real domain:
sed -i "s|your-domain.com|licenses.example.com|g" nginx/edge.conf
```

### 5. Issue the TLS certificate (one-shot, standalone)

```bash
docker run --rm -p 80:80 \
  -v /etc/letsencrypt:/etc/letsencrypt \
  certbot/certbot:latest certonly --standalone --non-interactive --agree-tos \
    -m you@example.com -d licenses.example.com
```

If this fails with "DNS problem": your domain's A record is wrong — fix DNS, wait, retry.

### 6. Start the stack

```bash
cd /opt/watchnexus/deploy
docker compose up -d --build
docker compose ps      # all services should be "running" / "healthy"
```

### 7. Install the daily backup + cert renewal timers

```bash
cp systemd/watchnexus-*.service /etc/systemd/system/
cp systemd/watchnexus-*.timer   /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now watchnexus-backup.timer
systemctl enable --now watchnexus-certbot.timer
```

Done. Open `https://licenses.example.com` and log in at `/admin/login` using the credentials in `.env` (`SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD`).

---

## After-deploy checklist

1. **Change the admin password** — log in, then update via the admin panel (or update `SEED_ADMIN_PASSWORD` in `.env` and `docker compose restart backend`; the seeder only runs when no admin exists).
2. **Create your first product** at `/admin/products`. Pick `signing_method` (HMAC or RSA) and `fingerprint_mode` (none/hw/domain/both).
3. **Create an API key** at `/admin/api-keys`. Copy it once — you will not see the raw value again. Optionally restrict it to specific IPs.
4. **Wire your store webhooks** to one of these endpoints (paste the secret into `.env` and restart):
   - `https://licenses.example.com/api/webhooks/lemonsqueezy`  (`LEMONSQUEEZY_WEBHOOK_SECRET`)
   - `https://licenses.example.com/api/webhooks/paddle`        (`PADDLE_WEBHOOK_SECRET`)
   - `https://licenses.example.com/api/webhooks/gumroad`       (`GUMROAD_WEBHOOK_SECRET`)
   - `https://licenses.example.com/api/webhooks/stripe`        (`STRIPE_WEBHOOK_SECRET`)
5. **Configure email delivery** in `.env` (either `SENDGRID_API_KEY` or the `SMTP_*` block) so customers get their license keys by email automatically. Restart the backend after editing `.env`.
6. **Tell your software** to call:
   ```bash
   POST  https://licenses.example.com/api/integrate/activate
   POST  https://licenses.example.com/api/integrate/validate
   POST  https://licenses.example.com/api/integrate/deactivate
   ```
   with header `X-API-Key: <your key>`. See `/docs` for the full request/response shapes.

---

## Day-to-day operations

### View logs
```bash
cd /opt/watchnexus/deploy
docker compose logs -f --tail=200 backend
docker compose logs -f --tail=200 nginx
```

### Restart a single service after editing `.env`
```bash
docker compose restart backend
```

### Update to a new version of the code
```bash
ssh root@YOUR_VPS_IP
# from your laptop:
rsync -av --exclude node_modules --exclude __pycache__ ./ root@YOUR_VPS_IP:/opt/watchnexus/
ssh root@YOUR_VPS_IP "cd /opt/watchnexus/deploy && docker compose up -d --build"
```

### Backups
- **When**: every day at 03:00 UTC (systemd timer `watchnexus-backup.timer`).
- **Where**: `/opt/watchnexus/deploy/backups/watchnexus_<db>_<timestamp>.tar.gz`.
- **Retention**: 14 days (configurable in the systemd unit).
- **Manual backup right now**:
  ```bash
  cd /opt/watchnexus/deploy
  docker compose exec -T backend bash /app/scripts/backup_mongo.sh 14
  ```
- **Restore from a backup**:
  ```bash
  cd /opt/watchnexus/deploy/backups
  tar -xzf watchnexus_watchnexus_20260101T030000Z.tar.gz
  docker compose cp watchnexus_watchnexus_20260101T030000Z mongo:/restore
  docker compose exec mongo mongorestore --drop /restore
  ```
- **Pull backups offsite** (recommended). Example with rclone:
  ```bash
  rclone sync /opt/watchnexus/deploy/backups remote:watchnexus-backups/
  ```
  Add that to root's crontab to run hourly.

### TLS renewal
- Automatic: `watchnexus-certbot.timer` runs `certbot renew` twice daily and reloads nginx.
- Test it manually: `systemctl start watchnexus-certbot.service && journalctl -u watchnexus-certbot.service -n 50`.

---

## Tying it into your software (the integrator side)

```bash
# 1. Activate (first run)
curl -X POST https://licenses.example.com/api/integrate/activate \
  -H "X-API-Key: $YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "license_key": "WNX-...",
    "hardware_id": "01:23:45:67:89:AB",
    "domain":      "customer.com",
    "device_name": "Marie\u2019s MacBook Pro"
  }'
# -> { activation_token, expires_at, grace_until, ... }
# Persist the activation_token locally on the customer's machine.

# 2. Validate (heartbeat, e.g. on app start + every few hours)
curl -X POST https://licenses.example.com/api/integrate/validate \
  -H "X-API-Key: $YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "activation_token": "$STORED_TOKEN",
    "hardware_id":      "01:23:45:67:89:AB",
    "domain":           "customer.com"
  }'
# Online: { valid:true, mode:"online" }
# Network down? You may still treat the token as valid as long as
#   now <= grace_until inside the JWT (default: +7 days past exp).

# 3. Deactivate (free a seat)
curl -X POST https://licenses.example.com/api/integrate/deactivate \
  -H "X-API-Key: $YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "activation_token": "$STORED_TOKEN" }'
```

For RSA-signed products you can also fetch the public key once at deploy time and verify the license signature **offline** in your client:

```bash
curl https://licenses.example.com/api/public-key
```

---

## Rate limits (per-IP, sliding window)

| Endpoint                       | Limit       |
|--------------------------------|-------------|
| `/api/admin/login`             | 10 / min    |
| `/api/customer/login`          | 15 / min    |
| `/api/customer/register`       | 5 / min     |
| `/api/integrate/activate`      | 60 / min    |
| `/api/integrate/validate`      | 600 / min   |
| `/api/integrate/deactivate`    | 30 / min    |
| `/api/webhooks/*`              | 300 / min   |

`429` responses include `Retry-After`. Tokens within their `grace_until` keep working in the meantime.

For tighter control, set an **IP allowlist** per API key in admin → API keys (CIDR + IPv6 supported, blank = allow all).

---

## Troubleshooting

| Symptom                                             | Fix                                                                                              |
|-----------------------------------------------------|--------------------------------------------------------------------------------------------------|
| `502 Bad Gateway` on the site                       | `docker compose ps` — make sure `backend` is healthy. `docker compose logs backend`.            |
| Certbot failed during bootstrap                     | Check DNS A record. Then re-run: `bash /opt/watchnexus/deploy/bootstrap.sh <domain> <email>`.   |
| Webhook returns 401                                 | The signing secret in `.env` doesn't match what the provider is sending. Update + restart.       |
| Lost admin password                                 | Edit `SEED_ADMIN_PASSWORD` in `.env`, **delete** the admin from Mongo, restart backend (it re-seeds): `docker compose exec mongo mongosh watchnexus --eval 'db.admin_users.deleteMany({})'`. |
| Want to rotate `JWT_SECRET`                         | Edit `.env`, `docker compose restart backend`. **Heads-up**: every existing activation token & admin/customer session becomes invalid immediately. Plan a maintenance window. |
| Need to whitelist a callback IP                     | Admin → API Keys → ✏️ on the key → paste IP/CIDR.                                                |

---

## Uninstall

```bash
cd /opt/watchnexus/deploy
docker compose down -v
systemctl disable --now watchnexus-backup.timer watchnexus-certbot.timer
rm /etc/systemd/system/watchnexus-*
systemctl daemon-reload
rm -rf /opt/watchnexus
```

That's it. Have fun shipping software.
