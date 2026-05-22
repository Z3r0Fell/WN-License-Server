# DEPLOY — WatchNexus Licensing Server on an Ubuntu VPS

> **Goal:** Working server reachable at **two** HTTPS domains in **under 15 minutes**:
> &nbsp;&nbsp;`https://licenses.watchnexus.ca` — admin panel + REST API
> &nbsp;&nbsp;`https://techhub.watchnexus.ca` — customer self-serve portal
>
> **Stack:** Docker Compose · MongoDB · FastAPI · React (built static) · nginx · Let's Encrypt.
> **Tested on:** Ubuntu 22.04 LTS & 24.04 LTS, fresh VPS.
> **This guide assumes:** VPS public IP `74.208.48.129` and repo `https://github.com/Z3r0Fell/WN-License-Server` (substitute your own if different).

---

## 0. Why two domains?

WatchNexus serves **one backend** and **one React build**, but uses two public hostnames so:

- Customers never see the admin URL.
- Each domain gets its own TLS certificate.
- You can lock the admin domain behind Cloudflare Access / a VPN later without breaking customer logins.

The React SPA looks at `window.location.hostname` at runtime to decide which set of routes to show:

| Hostname                          | Lands on            |
|-----------------------------------|---------------------|
| `licenses.watchnexus.ca` (admin)  | `/admin/login`      |
| `techhub.watchnexus.ca` (portal)  | `/portal/login`     |
| anything else (e.g. raw VPS IP)   | `/admin/login`      |

You can use **any** two hostnames — just pass them on the installer command line.

---

## 1. Pre-flight checklist

You'll need:

1. **An Ubuntu 22.04 or 24.04 VPS** with `sudo` / root SSH access.
   - This guide uses VPS IP `74.208.48.129` — substitute yours.
2. **A domain you control** (e.g. `watchnexus.ca`).
3. **Two DNS A records**, both pointing at the VPS's public IPv4 address:

   | Type | Name      | Value             | TTL |
   |------|-----------|-------------------|-----|
   | A    | `licenses`| `74.208.48.129`   | 300 |
   | A    | `techhub` | `74.208.48.129`   | 300 |

   (If you use Cloudflare, set the proxy status to **DNS only** — the grey cloud — during initial TLS issuance. You can re-enable proxying after both certs are live.)

4. **Confirm DNS resolves before continuing:**

   ```bash
   dig +short licenses.watchnexus.ca
   dig +short techhub.watchnexus.ca
   ```

   Both must return `74.208.48.129`. If they don't, wait a few minutes and retry. **Don't skip this** — the most common installer failure is Let's Encrypt failing because DNS isn't ready yet.

---

## 2. One-command install (recommended)

This is the path you should use. Two terminal commands total on the VPS.

### 2.1 SSH to the VPS

```bash
ssh root@74.208.48.129
```

(If you log in as a non-root user, prefix everything below with `sudo`.)

### 2.2 Install git (it might already be there) and clone the repo

```bash
apt-get update -y && apt-get install -y git
git clone https://github.com/Z3r0Fell/WN-License-Server.git /opt/watchnexus
```

> Already cloned earlier? Update to latest instead:
> ```bash
> cd /opt/watchnexus && git pull
> ```

### 2.3 Run the installer

```bash
sudo bash /opt/watchnexus/deploy/install.sh \
    --admin-domain    licenses.watchnexus.ca \
    --customer-domain techhub.watchnexus.ca  \
    --email           you@watchnexus.ca
```

The installer is **idempotent** — re-running it is safe and will pick up any DNS / cert changes.

It performs:

1. Installs Docker CE + the Compose plugin.
2. Configures UFW (only ports 22, 80, 443 open).
3. Skips the file-copy step (you're already in `/opt/watchnexus`).
4. Generates strong `JWT_SECRET`, `HMAC_LICENSE_SECRET`, and a random `SEED_ADMIN_PASSWORD`.
5. Writes a dual-domain Nginx config from the template.
6. Requests two Let's Encrypt certificates (`certbot/certbot` standalone), one per hostname.
7. Builds and starts the Compose stack (`mongo`, `backend`, `web`, `nginx`).
8. Installs systemd timers for:
   - **Daily MongoDB backup** at 03:00 UTC (14-day retention).
   - **TLS cert renewal** (`certbot renew`, twice daily).

At the end the script prints something like:

```
Admin URL    :  https://licenses.watchnexus.ca
Customer URL :  https://techhub.watchnexus.ca
Docs         :  https://licenses.watchnexus.ca/docs

Seeded admin :
  email      :  admin@licenses.watchnexus.ca
  password   :  <random hex you should save>
```

⚠️ **Save the printed admin credentials.** They are not stored anywhere else in plaintext.

### 2.4 Quick verification

```bash
curl -i https://licenses.watchnexus.ca/api/health
# -> HTTP/2 200 ... {"status":"ok","service":"watchnexus-license"}
```

If you get `200`, you're done. Open the admin URL in a browser.

### Re-running the installer (idempotent)

Same command as 2.3. Specifically:

- Existing TLS certs are **kept** (cert issuance is skipped if `/etc/letsencrypt/live/<domain>` exists).
- Existing secrets in `.env` are **kept** (only `change-me` placeholders are replaced).
- The Nginx config is **always rewritten** so swapping domains is a single re-run.

### What if DNS isn't ready yet?

Pass `--skip-tls` to do everything except cert issuance:

```bash
sudo bash /opt/watchnexus/deploy/install.sh \
    --admin-domain    licenses.watchnexus.ca \
    --customer-domain techhub.watchnexus.ca  \
    --email           you@watchnexus.ca      \
    --skip-tls
```

Then later, once `dig` shows the VPS IP for both names, drop the flag and re-run.

---

## 3. First-login checklist

1. Visit **`https://licenses.watchnexus.ca/admin/login`**.
2. Sign in with the email + password printed by the installer.
3. Open **Settings** (admin sidebar) and paste in your live secrets — these are stored in MongoDB and override any `.env` values **without** a backend restart:
   - Stripe webhook secret
   - Lemon Squeezy / Paddle / Gumroad webhook secrets (if used)
   - SendGrid API key (or SMTP host/port/user/pass)
   - Default "from" email + brand name
4. Open **Quickstart** → copy the **bootstrap API key**, then:
   - Create your first **Product** (HMAC or RSA signing, fingerprint mode).
   - Issue a **License** to yourself for end-to-end testing.
5. Visit **`https://techhub.watchnexus.ca/portal/login`** as the customer to confirm the portal works.
6. Wire your payment provider webhooks to the admin domain:

   | Provider       | URL                                                           | Settings field                  |
   |----------------|---------------------------------------------------------------|---------------------------------|
   | Stripe         | `https://licenses.watchnexus.ca/api/webhooks/stripe`          | `stripe_webhook_secret`         |
   | Lemon Squeezy  | `https://licenses.watchnexus.ca/api/webhooks/lemonsqueezy`    | `lemonsqueezy_webhook_secret`   |
   | Paddle         | `https://licenses.watchnexus.ca/api/webhooks/paddle`          | `paddle_webhook_secret`         |
   | Gumroad        | `https://licenses.watchnexus.ca/api/webhooks/gumroad`         | `gumroad_webhook_secret`        |

---

## 4. Manual install (if you prefer to see every step)

### 4.1 Install Docker + git

```bash
apt-get update -y
apt-get install -y ca-certificates curl gnupg ufw rsync openssl git

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

### 4.2 Firewall

```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
```

### 4.3 Clone the repo

```bash
git clone https://github.com/Z3r0Fell/WN-License-Server.git /opt/watchnexus
cd /opt/watchnexus
```

### 4.4 Configure `.env`

```bash
cd /opt/watchnexus/deploy
cp .env.example .env   # or `cp env.example .env` if the dotfile is missing
nano .env
```

Required values:

```ini
DOMAIN=licenses.watchnexus.ca
CUSTOMER_DOMAIN=techhub.watchnexus.ca
LETSENCRYPT_EMAIL=you@watchnexus.ca

JWT_SECRET=$(openssl rand -hex 32)
HMAC_LICENSE_SECRET=$(openssl rand -hex 32)

SEED_ADMIN_EMAIL=admin@licenses.watchnexus.ca
SEED_ADMIN_PASSWORD=<pick something strong>

APP_PUBLIC_URL=https://licenses.watchnexus.ca
CUSTOMER_PORTAL_URL=https://techhub.watchnexus.ca

REACT_APP_CUSTOMER_PORTAL_HOST=techhub.watchnexus.ca
CORS_ORIGINS=https://licenses.watchnexus.ca,https://techhub.watchnexus.ca
```

(Generate the `openssl rand` values manually and paste them in — the `$(...)` syntax won't expand inside nano.)

Webhook + email secrets can be left blank here and filled in later from the **Settings** UI (they live in MongoDB and override `.env`).

### 4.5 Render the Nginx config

```bash
cd /opt/watchnexus/deploy/nginx
sed -e "s|__ADMIN_DOMAIN__|licenses.watchnexus.ca|g" \
    -e "s|__CUSTOMER_DOMAIN__|techhub.watchnexus.ca|g" \
    edge.conf.template > edge.conf
```

(Or just re-run `install.sh`, which writes the same file.)

### 4.6 Issue both TLS certificates

```bash
for dom in licenses.watchnexus.ca techhub.watchnexus.ca; do
  docker run --rm -p 80:80 \
    -v /etc/letsencrypt:/etc/letsencrypt \
    certbot/certbot:latest certonly --standalone --non-interactive --agree-tos \
      -m you@watchnexus.ca -d "$dom"
done
```

If certbot fails with a DNS / network error, fix the A-record, wait, and retry.

### 4.7 Start the stack

```bash
cd /opt/watchnexus/deploy
docker compose up -d --build
docker compose ps      # all services should be running / healthy
```

### 4.8 Install the systemd timers

```bash
cp systemd/watchnexus-*.service /etc/systemd/system/
cp systemd/watchnexus-*.timer   /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now watchnexus-backup.timer
systemctl enable --now watchnexus-certbot.timer
```

Done. Visit `https://licenses.watchnexus.ca/admin/login` and `https://techhub.watchnexus.ca/portal/login`.

---

## 5. Day-to-day operations

### 5.1 View logs

```bash
cd /opt/watchnexus/deploy
docker compose logs -f --tail=200 backend
docker compose logs -f --tail=200 nginx
```

### 5.2 Restart after editing `.env`

```bash
docker compose restart backend
```

> Most live settings (webhook secrets, email config) can now be edited in **Admin → Settings** without a restart. Only crypto secrets (`JWT_SECRET`, `HMAC_LICENSE_SECRET`) require a restart.

### 5.3 Update to a new version

```bash
ssh root@74.208.48.129
cd /opt/watchnexus
git pull
cd deploy
docker compose up -d --build
```

> If you ever want to start clean from upstream and your local changes are throw-away:
> ```bash
> cd /opt/watchnexus && git fetch && git reset --hard origin/main
> ```

### 5.4 Backups

- **Schedule:** every day at 03:00 UTC (`watchnexus-backup.timer`).
- **Location:** `/opt/watchnexus/deploy/backups/watchnexus_<db>_<timestamp>.tar.gz`.
- **Retention:** 14 days.
- **Manual backup right now:**
  ```bash
  cd /opt/watchnexus/deploy
  docker compose exec -T backend bash /app/scripts/backup_mongo.sh 14
  ```
- **Restore from a backup:**
  ```bash
  cd /opt/watchnexus/deploy/backups
  tar -xzf watchnexus_watchnexus_20260101T030000Z.tar.gz
  docker compose cp watchnexus_watchnexus_20260101T030000Z mongo:/restore
  docker compose exec mongo mongorestore --drop /restore
  ```
- **Offsite copy (recommended).** Example with rclone:
  ```bash
  rclone sync /opt/watchnexus/deploy/backups remote:watchnexus-backups/
  ```

### 5.5 TLS renewal

- Automatic via `watchnexus-certbot.timer` (twice daily).
- Manual: `systemctl start watchnexus-certbot.service && journalctl -u watchnexus-certbot.service -n 50`.

---

## 6. Integrating your software (the integrator side)

Use the admin domain for all API calls. Each call needs an `X-API-Key` header.

```bash
# 1. Activate (first run on a new install)
curl -X POST https://licenses.watchnexus.ca/api/integrate/activate \
  -H "X-API-Key: $YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "license_key": "WNX-...",
    "hardware_id": "01:23:45:67:89:AB",
    "domain":      "customer.com",
    "device_name": "Marie\u2019s MacBook Pro"
  }'
# -> { activation_token, expires_at, grace_until, ... }
```

```bash
# 2. Validate (on app start + every few hours)
curl -X POST https://licenses.watchnexus.ca/api/integrate/validate \
  -H "X-API-Key: $YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "activation_token": "$STORED_TOKEN",
    "hardware_id":      "01:23:45:67:89:AB",
    "domain":           "customer.com"
  }'
# Online: { valid:true, mode:"online" }
# Offline (within grace_until): treat as valid.
```

```bash
# 3. Deactivate (release a seat)
curl -X POST https://licenses.watchnexus.ca/api/integrate/deactivate \
  -H "X-API-Key: $YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "activation_token": "$STORED_TOKEN" }'
```

For RSA-signed products you can ship the public key with the client and verify the license **fully offline**:

```bash
curl https://licenses.watchnexus.ca/api/public-key
```

Drop-in clients live in `/opt/watchnexus/clients/{python,javascript,csharp}` — they're also downloadable from the admin **Quickstart** page.

---

## 7. Rate limits (per-IP, sliding window)

| Endpoint                        | Limit     |
|---------------------------------|-----------|
| `/api/admin/login`              | 10 / min  |
| `/api/customer/login`           | 15 / min  |
| `/api/customer/register`        | 5  / min  |
| `/api/integrate/activate`       | 60 / min  |
| `/api/integrate/validate`       | 600/ min  |
| `/api/integrate/deactivate`     | 30 / min  |
| `/api/webhooks/*`               | 300/ min  |

`429` responses include `Retry-After`. Tokens within their `grace_until` keep working through transient 429s.

For tighter control set an **IP allowlist** per API key under **Admin → API Keys** (CIDR + IPv6 supported, blank = allow all).

---

## 8. Troubleshooting

| Symptom                                          | Fix                                                                                                                            |
|--------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------|
| `git: command not found`                         | `apt-get update -y && apt-get install -y git`                                                                                  |
| `.env.example: No such file or directory` after clone | Your old clone predates the `.gitignore` fix that ships envs. Pull latest: `cd /opt/watchnexus && git pull`. As a fallback, `cp env.example .env` (the non-dotfile copy is also tracked). |
| `install.sh: No such file or directory`          | You haven't cloned the repo yet. Run the `git clone` step in §2.2 first.                                                       |
| `Permission denied (publickey)` when cloning     | The repo is public — use the HTTPS URL `https://github.com/Z3r0Fell/WN-License-Server.git`, not the SSH `git@github.com:...` URL. |
| `fatal: destination path '/opt/watchnexus' already exists` | Either delete it (`rm -rf /opt/watchnexus`) and re-clone, or update in place: `cd /opt/watchnexus && git pull`.        |
| `dig` doesn't return your VPS IP                 | DNS hasn't propagated yet. Wait or check the A-record at your registrar. Use `--skip-tls` and re-run later.                    |
| Certbot fails ("Connection refused" on :80)      | Port 80 isn't open OR another service is bound to it. `ufw status`, then `lsof -i :80` / `ss -ltnp | grep :80`.                |
| Certbot fails ("DNS problem" / "unauthorized")   | A-record wrong / not propagated. Fix DNS, re-run `install.sh` (idempotent).                                                    |
| Certbot fails with rate-limit error              | You hit Let's Encrypt's 5-failures-per-hour rate limit by retrying too fast. Wait an hour, fix the real problem, then retry.   |
| `502 Bad Gateway` in the browser                 | `docker compose ps` — make sure `backend` is healthy. `docker compose logs backend`.                                            |
| Browser shows admin login on the customer domain | Hostname mismatch. Check `REACT_APP_CUSTOMER_PORTAL_HOST` in `.env` matches the customer DNS name, then `docker compose up -d --build web`. |
| Webhook returns 401                              | Signing secret in **Admin → Settings** (or `.env`) doesn't match what the provider is sending. Update + retry.                 |
| Lost admin password                              | Edit `SEED_ADMIN_PASSWORD` in `.env`, delete the admin row, restart backend: `docker compose exec mongo mongosh watchnexus --eval 'db.admin_users.deleteMany({})' && docker compose restart backend`. |
| Want to rotate `JWT_SECRET`                      | Edit `.env`, `docker compose restart backend`. **All sessions and activation tokens become invalid immediately** — plan a window. |
| One domain works, the other returns no host / wrong cert | Re-run `install.sh` to regenerate Nginx config + request the missing cert.                                              |

---

## 9. Uninstall

```bash
cd /opt/watchnexus/deploy
docker compose down -v
systemctl disable --now watchnexus-backup.timer watchnexus-certbot.timer
rm /etc/systemd/system/watchnexus-*
systemctl daemon-reload
rm -rf /opt/watchnexus
```

Backups in `/opt/watchnexus/deploy/backups/` are removed by the `rm -rf` above — copy them off first if you want to keep them.

---

That's it. If something breaks, run `docker compose logs backend` first — 90% of issues are visible there.
