# plan.md — WatchNexus Licensing Server (FastAPI + React + MongoDB)

## 1) Objectives
- Prove the **core licensing cryptography + activation/validation** flow works end-to-end in isolation (no app yet).
- Build an MVP server + UI that supports: products, licenses, activations, audit trail, builds, API keys, and customer portal.
- Integrate a **Stripe webhook receiver** (verify signatures, issue licenses) plus a server-to-server **mint endpoint** for website-triggered serial issuance.
- Ensure ops readiness: **rate limiting**, server-to-server **API key auth**, webhook event logging, and **daily backups**.
- **(Added / achieved)** Provide a **repeatable dual-domain deployment** (admin + customer portal hostnames) with one-command Ubuntu installer, documented ops, and TLS.
- **(Added / achieved)** Support **runtime-editable secrets** (webhooks/email) via Admin UI without service restarts.

## 2) Implementation Steps

### Phase 1 — Core POC (isolation; must pass before app work)
**User stories**
1. As an integrator, I can generate and verify an **HMAC-signed** license key that can’t be forged.
2. As an integrator, I can generate and verify an **RSA-signed** license key using public-key verification.
3. As an integrator, I can **activate** a license with a fingerprint and receive a signed token.
4. As an integrator, I can **validate** a token and keep working during a short **offline grace** window.
5. As ops, I can verify **Stripe** webhook signatures and parse core fields, or mint a serial server-to-server after website checkout.

**Steps**
1. Web search + notes: current Stripe webhook signature verification docs; token best practices (JWT claims, clock skew).
2. Create `poc/test_core.py` (single script) implementing:
   - HMAC license format + verify
   - RSA license format + verify (cryptography)
   - Activation token signing (PyJWT) with `exp` + `grace_until`, plus fingerprint binding
   - Validate routine: pass if token valid OR within grace window; fail otherwise
   - Webhook signature verification function for Stripe + sample payload fixture
3. Run locally; iterate until all assertions pass; document formats and edge cases in `poc/README.md`.

**Exit criteria**
- Script completes with all tests green; license/token formats locked for v1.

---

### Phase 2 — V1 App Development (build around proven core)
**User stories**
1. As an admin, I can log in (email+password) and stay logged in via JWT session.
2. As an admin, I can create a Product choosing **signing method (HMAC/RSA)** and **fingerprint mode (None/HW/Domain/Both)**.
3. As an admin, I can issue/revoke/extend a license and see it reflected immediately in API responses.
4. As an integrator, I can call `/api/integrate/activate` and `/api/integrate/validate` using an API key.
5. As a customer, I can log in and view licenses, activations, and available builds.

**Backend (FastAPI)**
1. Project skeleton + env config: `MONGODB_URI`, `JWT_SECRET`, RSA key path, rate limit config, seeded admin creds.
2. Mongo models/collections (MVP fields only): `Product`, `License`, `Activation`, `Customer`, `AdminUser`, `ApiKey`, `AuditLog`, `Build`, `WebhookEvent`.
3. Core services (ported from POC):
   - signing/verification (HMAC+RSA), license key format helpers
   - activation token issuance/validation with offline grace + clock skew handling
   - fingerprint policy enforcement per product
4. Auth:
   - Admin: email+password (bcrypt/passlib), JWT
   - Customer: simple register/login JWT (keep minimal)
5. API key middleware for `/api/integrate/*` + per-product scoping.
6. Rate limiting (slowapi) on `/integrate/activate`, `/integrate/validate`, `/admin/login`, `/customer/login`.
7. Endpoints (MVP subset, but complete core flows):
   - Admin: login/me; products CRUD; licenses CRUD + revoke/extend; license activations list + deactivate; audit list; api-keys CRUD; builds CRUD; webhook events list
   - Customer: register/login/me; licenses list; deactivate activation; builds list
   - Integrator: activate/validate/deactivate/mint
   - Webhooks: `/webhooks/stripe` (verify signature, idempotency, create/find customer by email, issue license)
   - Health: `/health`
8. Audit logging: record admin/customer/integrator actions that mutate licenses/activations/api keys/builds.
9. Webhook idempotency: store provider event id; ignore duplicates; persist raw payload.

**Frontend (React + shadcn UI)**
1. App shell + routing: Landing, Admin, Customer, Docs.
2. Admin UI (MVP): login; dashboard stats; products; licenses list + create + detail (activations, revoke/extend, deactivate install); API keys; builds; audit; webhook events.
3. Customer portal (MVP): register/login; licenses list; activation management (deactivate); builds/download links.
4. Integration docs page: curl examples for activate/validate, token semantics, grace period behavior.

**Phase 2 testing (1 round E2E)**
- Run backend+frontend locally; test flows: admin create product/license → integrator activate/validate → customer sees license → admin revoke → validate fails.

**Exit criteria**
- Core flows work with real DB; UI can manage products/licenses/activations; webhook endpoint verifies signatures and issues licenses.

---

### Phase 3 — Hardening + Missing Management Features
**User stories**
1. As an admin, I can bulk-import reseller licenses via CSV and see per-row success/failure.
2. As an admin, I can search/filter licenses by email, key, status, product, expiry.
3. As an admin, I can view activation logs with pagination and export.
4. As ops, I can rotate API keys without downtime (create new, deactivate old).
5. As an integrator, I can handle clock skew and intermittent failures without locking users out.

**Steps**
1. CSV bulk import endpoint + UI (upload, preview, apply; store failures).
2. Stronger validation + pagination across lists; indexes in Mongo for key queries.
3. Webhook robustness: event replay tooling in admin; improved mapping across providers.
4. Security: tighter rate limits; IP logging; optional per-product allowlist; password policy.
5. Add structured logging + request ids.
6. Testing agent run: full regression on admin/customer/integration/webhooks.

**Exit criteria**
- Reseller import works; ops/admin workflows stable; webhook handling resilient.

---

### Phase 4 — Deployment + Ops
**User stories**
1. As ops, I can deploy on Ubuntu VPS with a repeatable process.
2. As ops, I can run daily backups and verify restore.
3. As ops, I can monitor basic health and error rates.
4. As ops, I can safely update without breaking client validation.
5. As ops, I can rotate secrets (JWT/HMAC/RSA) with a documented procedure.

**Steps**
1. Docker Compose (api, ui, mongodb) or systemd + nginx; environment templates.
2. TLS + nginx reverse proxy; CORS/CSRF posture for portals.
3. Backup script: `scripts/backup_mongo.sh` using `mongodump` + retention; cron example.
4. Minimal monitoring: health endpoint checks + log rotation.

---

### Phase 6 — Dual-domain deployment + runtime settings (COMPLETED)
**Goal**
- Ship a production-ready deployment path with **two hostnames**:
  - Admin/API host (e.g. `licenses.watchnexus.ca`)
  - Customer portal host (e.g. `techhub.watchnexus.ca`)
- Allow operators to edit webhook/email secrets **live** from the Admin UI, stored in MongoDB.

**Completed deliverables**
1. **Ubuntu one-shot installer (idempotent, dual-domain):** `deploy/install.sh`
   - Accepts `--admin-domain`, `--customer-domain`, `--email` (+ `--skip-tls`)
   - Installs Docker + Compose plugin, configures UFW
   - Copies repo to `/opt/watchnexus`
   - Generates strong secrets (`JWT_SECRET`, `HMAC_LICENSE_SECRET`) and a random seeded admin password
   - Issues Let's Encrypt certs for **both** hostnames (standalone certbot)
   - Starts full stack via Docker Compose
   - Installs systemd timers (backup + cert renew)
2. **Dual-domain deployment docs rewrite:** `DEPLOY.md`
   - DNS A-record requirements for both hostnames
   - Installer-first deployment instructions + manual fallback
   - Ops, backups/restore, TLS renewal, troubleshooting
3. **Nginx dual-domain edge config:**
   - `deploy/nginx/edge.conf` (dual-domain placeholder config; regenerated by installer)
   - `deploy/nginx/edge.conf.template` (canonical reference template)
4. **MongoDB-backed runtime settings module + UI:**
   - Backend: `runtime_settings.py` (DB-backed settings store)
   - Admin UI: Settings page supports live updates for webhook/email configuration
5. **Hostname-based React routing for Admin vs Portal:**
   - React build routes based on `window.location.hostname` and `REACT_APP_CUSTOMER_PORTAL_HOST`

**Testing / exit criteria**
- `testing_agent_v3` iteration 5: **100% pass**
  - Backend: **11/11** smoke + core flow tests passed
  - Frontend: **27** checks passed
  - **Zero issues**, **no follow-up required**

---

## 3) Status (post-Phase 6)
- POC: passed (HMAC+RSA license, activation+grace, webhook signatures).
- Backend: implemented and live at `/api/*` with admin, customer, integrate, webhooks routers; rate limited; audit logged; backups supported.
- Frontend: Landing, Docs, Admin (incl. Settings + Quickstart), and Customer portal.
- Deployment: dual-domain Ubuntu installer + dual-domain nginx edge config + updated DEPLOY.md.
- Tests: iteration 5 at **100%** for both backend and frontend.

## Next Actions (future phases on demand)
1. Email delivery on purchase (SendGrid/SMTP) — done via `email_sender.py`; extend templates/branding as needed.
2. Additional webhook providers / refinement (as needed) and provider-specific event mapping.
3. Per-route rate limiting tuning + IP allowlists hardening.
4. Deployment enhancements (optional): staging env, log aggregation, offsite backups, Cloudflare/Access docs.
5. Magic-link customer login.

## 4) Success Criteria
- POC script passes: HMAC+RSA license verification, activation token issuance, validate with grace, and webhook signature verification.
- V1 supports product-configured signing + fingerprinting, seat/expiry, activation tracking, revoke/extend, deactivate installs.
- Webhooks verify signatures and auto-issue licenses idempotently.
- Rate limits + API key auth enforced; audit log present; backups runnable on Ubuntu VPS.
- Dual-domain deployment is documented and repeatable; runtime secrets are editable in Admin Settings without restarts.
