"""End-to-end checks for the purchase -> serial -> activation flow.

Run against a LOCAL or STAGING stack only — it creates orders, licenses,
customers and API keys:

    BASE_URL=http://localhost:18101 \
    ADMIN_EMAIL=admin@lstest.local ADMIN_PASSWORD=... \
    STRIPE_WEBHOOK_SECRET=whsec_... \
    python tests/e2e_license_flow.py
"""
import concurrent.futures as cf
import hashlib
import hmac
import json
import os
import sys
import time
import uuid

import requests

BASE = os.environ.get("BASE_URL", "http://localhost:18101").rstrip("/")
ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
STRIPE_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

failures: list[str] = []


def check(name: str, cond: bool, detail: object = "") -> None:
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  -> {detail}" if not cond else ""))
    if not cond:
        failures.append(name)


def admin_headers() -> dict:
    r = requests.post(f"{BASE}/api/admin/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def buy(plan: str, email: str, adm: dict) -> dict:
    order = requests.post(f"{BASE}/api/orders", json={"plan": plan, "email": email}, timeout=15).json()
    paid = requests.post(f"{BASE}/api/admin/orders/{order['id']}/mark-paid", json={},
                         headers=adm, timeout=15).json()
    return paid


def stripe_post(event: dict) -> requests.Response:
    body = json.dumps(event).encode()
    ts = str(int(time.time()))
    sig = hmac.new(STRIPE_SECRET.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return requests.post(f"{BASE}/api/webhooks/stripe", data=body, timeout=15,
                         headers={"Stripe-Signature": f"t={ts},v1={sig}",
                                  "Content-Type": "application/json"})


def main() -> int:
    adm = admin_headers()
    qs = requests.get(f"{BASE}/api/admin/quickstart", headers=adm, timeout=15).json()
    key = {"X-API-Key": qs["api_key"]}
    run = uuid.uuid4().hex[:8]

    # 1. Purchase -> serial carries the right tier
    for plan, prefix, tier in (("pro", "WNX-PRO-", "pro"), ("ultra", "WNX-ULT-", "ultra")):
        paid = buy(plan, f"buyer-{plan}-{run}@example.com", adm)
        serial = paid.get("license_key") or ""
        check(f"{plan}: mark-paid issues {prefix} serial", paid.get("status") == "paid"
              and serial.startswith(prefix), paid)
        r = requests.post(f"{BASE}/api/integrate/activate", headers=key, timeout=15,
                          json={"license_key": serial, "hardware_id": f"hw-{run}"})
        lic = r.json().get("license", {})
        check(f"{plan}: activation returns tier={tier}", r.status_code == 200
              and lic.get("tier") == tier and lic.get("plan") == plan, r.text)
        tok = r.json().get("activation_token")
        v = requests.post(f"{BASE}/api/integrate/validate", headers=key, timeout=15,
                          json={"activation_token": tok, "hardware_id": f"hw-{run}"}).json()
        check(f"{plan}: validate ok with tier", v.get("valid") and v.get("license", {}).get("tier") == tier, v)
        again = requests.post(f"{BASE}/api/integrate/activate", headers=key, timeout=15,
                              json={"license_key": serial, "hardware_id": f"hw-{run}"}).json()
        check(f"{plan}: re-activation on same machine reuses seat", again.get("reused") is True, again)
        other = requests.post(f"{BASE}/api/integrate/activate", headers=key, timeout=15,
                              json={"license_key": serial, "hardware_id": f"other-{run}"})
        check(f"{plan}: second machine blocked by 1-seat cap", other.status_code == 403, other.text)
        detail = requests.get(f"{BASE}/api/admin/licenses/{paid['license_id']}", headers=adm, timeout=15).json()
        acts = [a for a in detail["activations"] if a["status"] == "active"]
        check(f"{plan}: license server shows exactly 1 active activation",
              len(acts) == 1 and acts[0]["hardware_id"] == f"hw-{run}", detail["activations"])

    # 2. Concurrent activations on a 1-seat license never exceed the cap
    paid = buy("pro", f"race-{run}@example.com", adm)
    with cf.ThreadPoolExecutor(10) as ex:
        codes = list(ex.map(lambda i: requests.post(
            f"{BASE}/api/integrate/activate", headers=key, timeout=30,
            json={"license_key": paid["license_key"], "hardware_id": f"race-{run}-{i}"}).status_code,
            range(10)))
    detail = requests.get(f"{BASE}/api/admin/licenses/{paid['license_id']}", headers=adm, timeout=15).json()
    active = sum(a["status"] == "active" for a in detail["activations"])
    check("concurrent activations respect seat cap", active == 1 and codes.count(200) == 1,
          {"codes": codes, "active": active})

    # 3. Double mark-paid issues exactly one license
    order = requests.post(f"{BASE}/api/orders", json={"plan": "ultra", "email": f"dbl-{run}@example.com"},
                          timeout=15).json()
    with cf.ThreadPoolExecutor(6) as ex:
        list(ex.map(lambda _: requests.post(f"{BASE}/api/admin/orders/{order['id']}/mark-paid",
                                            json={}, headers=adm, timeout=30), range(6)))
    lics = requests.get(f"{BASE}/api/admin/licenses", params={"q": f"dbl-{run}"}, headers=adm, timeout=15).json()
    check("concurrent mark-paid issues one license", len(lics) == 1, len(lics))

    # 4. API key scopes are enforced on activate (fresh license: a 403 must
    #    come from the scope check, not from an exhausted seat)
    fresh = buy("pro", f"scope-{run}@example.com", adm)
    mk = requests.post(f"{BASE}/api/admin/api-keys", headers=adm, timeout=15,
                       json={"name": f"mint-only-{run}", "scopes": ["mint"]}).json()
    r = requests.post(f"{BASE}/api/integrate/activate", headers={"X-API-Key": mk["key"]}, timeout=15,
                      json={"license_key": fresh["license_key"], "hardware_id": "x"})
    check("mint-only key cannot activate", r.status_code == 403 and "scope" in r.text, r.text)

    # 5. Spoofed X-Forwarded-For does not satisfy an IP allowlist
    ak = requests.post(f"{BASE}/api/admin/api-keys", headers=adm, timeout=15,
                       json={"name": f"ip-locked-{run}", "scopes": ["activate"],
                             "allowed_ips": ["203.0.113.77"]}).json()
    r = requests.post(f"{BASE}/api/integrate/activate", timeout=15,
                      headers={"X-API-Key": ak["key"], "X-Forwarded-For": "203.0.113.77"},
                      json={"license_key": fresh["license_key"], "hardware_id": "x"})
    check("spoofed X-Forwarded-For rejected by allowlist",
          r.status_code == 403 and "not allowed" in r.text, r.text)

    # 6. Customer lockout only after repeated failures
    email = f"lock-{run}@example.com"
    codes = [requests.post(f"{BASE}/api/customer/login", json={"email": email, "password": "nope"},
                           timeout=15).status_code for _ in range(6)]
    check("1st-5th bad logins are 401 (no instant lockout), 6th is locked",
          codes[:5] == [401] * 5 and codes[5] == 403, codes)

    # 7. Stripe: one serial per checkout, correct tier, no fulfilment before payment
    if STRIPE_SECRET:
        order = requests.post(f"{BASE}/api/orders", json={"plan": "pro", "email": f"stripe-{run}@example.com"},
                              timeout=15).json()
        sess = {"id": f"cs_{run}", "object": "checkout.session", "mode": "payment",
                "customer_email": order["email"], "amount_total": int(round(order["price_cad"] * 100)),
                "metadata": {"order_ref": order["reference"], "plan": "pro"}}
        stripe_post({"id": f"evt_unpaid_{run}", "type": "checkout.session.completed",
                     "data": {"object": {**sess, "payment_status": "unpaid"}}})
        st = requests.get(f"{BASE}/api/orders/{order['reference']}", timeout=15).json()["status"]
        check("stripe: unpaid checkout does not fulfil", st == "pending_payment", st)
        stripe_post({"id": f"evt_paid_{run}", "type": "checkout.session.completed",
                     "data": {"object": {**sess, "payment_status": "paid"}}})
        stripe_post({"id": f"evt_pi_{run}", "type": "payment_intent.succeeded",
                     "data": {"object": {"id": f"pi_{run}", "object": "payment_intent",
                                         "receipt_email": order["email"], "metadata": {}}}})
        st = requests.get(f"{BASE}/api/orders/{order['reference']}", timeout=15).json()
        lics = requests.get(f"{BASE}/api/admin/licenses", params={"q": f"stripe-{run}"}, headers=adm,
                            timeout=15).json()
        check("stripe: paid checkout fulfils with PRO serial",
              st["status"] == "paid" and st["license_key"].startswith("WNX-PRO-"), st)
        check("stripe: payment_intent.succeeded does not mint a second serial", len(lics) == 1,
              [l["key"] for l in lics])

    print(f"\n{len(failures)} failure(s)" if failures else "\nALL PASSED")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
