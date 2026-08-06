# REPLACE-VPS — Updating the Running License Server

> Replaces the currently-running WatchNexus licensing server on the VPS
> with the latest code from this repo. Covers the v1.0.0 release update
> (short 22-char `WNX-<TIER>-XXXX-XXXX-XXXX` serials, subscription
> matrix, server-to-server mint endpoint).
>
> **Target VPS:** Ubuntu 22.04/24.04, Docker Compose stack from `deploy/`.
> **Live domains:** `https://licenses.watchnexus.ca` (admin) and
> `https://techhub.watchnexus.ca` (customer portal).

---

## 1. Before you start

1. **Push the latest code to GitHub** (if not already pushed):

   ```bash
   cd /home/auz/Downloads/git/WN-License-Server
   git push origin dev
   ```

2. **Back up the live database** (mandatory before touching the server):

   ```bash
   ssh root@74.208.48.129
   sudo bash /opt/watchnexus/deploy/backup_host.sh 14
   ls -lh /opt/watchnexus/deploy/backups/ | tail -3
   ```

3. **Note the current version** so you can roll back if needed:

   ```bash
   cd /opt/watchnexus && git log --oneline -1
   ```

4. **Confirm DNS / HTTPS are already healthy** (you should NOT need new
   certs for this update — domains and certs are unchanged):

   ```bash
   curl -i https://licenses.watchnexus.ca/api/health
   # -> 200 {"status":"ok","service":"watchnexus-license"}
   ```

> This update keeps the MongoDB database intact. **No data migration is
> required** — the new short-serial logic validates against the existing
> `licenses` collection and the old HMAC/RSA `signing_method` records
> remain readable. Old long serials in the DB stay valid.

---

## 2. Update the code (in place)

SSH to the VPS and update the existing clone — do **not** re-clone (that
would wipe `.env` and your TLS state):

```bash
ssh root@74.208.48.129
cd /opt/watchnexus
git fetch origin
git checkout dev            # or main — match the branch you pushed
git reset --hard origin/dev
```

> Use `reset --hard` only if you have no local changes to `/opt/watchnexus`
> (you shouldn't — edits live in `deploy/.env`, which is gitignored).
> If unsure, run `git stash` / `git status` first instead of resetting.

---

## 3. Rebuild and restart the stack

```bash
cd /opt/watchnexus/deploy
docker compose up -d --build
docker compose ps          # mongo, backend, web, nginx all healthy
```

### 3.1 Crypto secrets

`JWT_SECRET` and `HMAC_LICENSE_SECRET` in `deploy/.env` are **kept as-is**
(only `change-me` placeholders get replaced on fresh installs). If you
rotate either, all existing sessions and activation tokens become invalid
immediately — only do that during a planned maintenance window.

The short serial format uses **no per-product crypto secret** (validated by
DB lookup in `_resolve_license`), so nothing to migrate in
**Admin → Settings**. Existing RSA/HMAC product configs are vestigial and
can be left untouched.

---

## 4. Verify the update

```bash
# API healthy
curl -i https://licenses.watchnexus.ca/api/health

# New-format serial round-trip (bootstrap/quickstart key, if you have one)
curl -X POST https://licenses.watchnexus.ca/api/integrate/activate \
  -H "X-API-Key: <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"license_key":"WNX-ULT-AAAA-BBBB-CCCC","hardware_id":"test-verify"}' 

# Logs clean
docker compose logs --tail=50 backend
```

Then confirm in a browser:

| URL | Expect |
|---|---|
| `https://licenses.watchnexus.ca/admin/login` | Admin panel login (existing creds) |
| `https://licenses.watchnexus.ca/docs` | OpenAPI docs |
| `https://techhub.watchnexus.ca/portal/login` | Customer portal |
| Admin → Licenses | Old long serials still listed; new `WNX-*` serials issue fine |

---

## 5. Rollback (if the update breaks something)

The stack is the fast rollback path; the DB backup is the safety net:

```bash
# 1. Revert code
cd /opt/watchnexus
git log --oneline -5                      # find the previous SHA
git checkout <previous-SHA>
cd deploy && docker compose up -d --build

# 2. If the DB got corrupted, restore the backup you took in §1:
cd /opt/watchnexus/deploy
docker compose exec -T mongo mongorestore --drop --gzip \
  --archive=/backups/<your-backup>.archive.gz
```

---

## 6. Post-update checklist

- [ ] `git push origin dev` done (code is on GitHub).
- [ ] Backup taken (`backup_host.sh`) — confirmed non-zero size.
- [ ] `docker compose up -d --build` finished with all 4 services healthy.
- [ ] `/api/health` returns 200 over HTTPS.
- [ ] Admin login works with existing credentials.
- [ ] A new `WNX-<TIER>-XXXX-XXXX-XXXX` serial activates and validates.
- [ ] An old long serial (pre-v2) still validates.
- [ ] TLS certs unchanged (renewal timer still armed:
      `systemctl status watchnexus-certbot.timer`).
