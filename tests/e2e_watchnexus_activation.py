"""Cross-system E2E: purchase on the license server -> serial -> activate in a
real WatchNexus container -> tier unlocked + activation recorded server-side.

Requires a LOCAL license-server stack (see e2e_license_flow.py) whose docker
network WatchNexus can join, and a built WatchNexus image:

    LS_URL=http://localhost:18101 LS_NETWORK=wnls-test_internal \
    ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=... \
    WN_IMAGE=wn-local:e2e python tests/e2e_watchnexus_activation.py
"""
import os
import secrets
import subprocess
import sys
import time
import uuid

import requests

LS = os.environ.get("LS_URL", "http://localhost:18101").rstrip("/")
LS_NET = os.environ.get("LS_NETWORK", "wnls-test_internal")
LS_INTERNAL = os.environ.get("LS_INTERNAL_URL", "http://backend:8001")
WN_IMAGE = os.environ.get("WN_IMAGE", "wn-local:e2e")
WN_PORT = 18011
WN = f"http://localhost:{WN_PORT}"
WN_ADMIN = ("owner@example.com", "Wn-E2e-Owner-Pass-1!")
failures: list[str] = []


def check(name, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  -> {detail}" if not cond else ""))
    if not cond:
        failures.append(name)


def sh(*args):
    return subprocess.run(args, capture_output=True, text=True)


def ls_admin():
    r = requests.post(f"{LS}/api/admin/login", timeout=15,
                      json={"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def buy(plan, email, adm):
    order = requests.post(f"{LS}/api/orders", json={"plan": plan, "email": email}, timeout=15).json()
    return requests.post(f"{LS}/api/admin/orders/{order['id']}/mark-paid", json={}, headers=adm, timeout=15).json()


def ls_activations(license_id, adm):
    d = requests.get(f"{LS}/api/admin/licenses/{license_id}", headers=adm, timeout=15).json()
    return d["activations"]


def start_wn(volume, api_key):
    sh("docker", "rm", "-f", "wn-e2e")
    r = sh("docker", "run", "-d", "--name", "wn-e2e", "--network", LS_NET, "-p", f"{WN_PORT}:8001",
           "-v", f"{volume}:/app/data", "-e", "WATCHNEXUS_DATA_DIR=/app/data",
           "-e", f"JWT_SECRET={JWT}", "-e", f"LICENSE_SERVER_URL={LS_INTERNAL}",
           *(["-e", f"LICENSE_SERVER_API_KEY={api_key}"] if api_key else []),
           "-e", f"WATCHNEXUS_SEED_ADMIN_EMAIL={WN_ADMIN[0]}",
           "-e", f"WATCHNEXUS_SEED_ADMIN_PASSWORD={WN_ADMIN[1]}", WN_IMAGE)
    assert r.returncode == 0, r.stderr
    for _ in range(60):
        try:
            if requests.get(f"{WN}/api/health", timeout=2).ok:
                break
        except requests.RequestException:
            pass
        time.sleep(1)
    tok = requests.post(f"{WN}/api/auth/login", timeout=15,
                        json={"email": WN_ADMIN[0], "password": WN_ADMIN[1]}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def wn_activate(h, serial):
    return requests.post(f"{WN}/api/cellar/activate", json={"serial": serial}, headers=h, timeout=30)


def wn_tier(h):
    return requests.get(f"{WN}/api/cellar/status", headers=h, timeout=15).json().get("tier")


JWT = secrets.token_hex(32)


def main():
    adm = ls_admin()
    # WN_USE_BUILTIN_KEY=1: rely on the client key baked into the image
    # (official-image behaviour) instead of passing an operator key.
    api_key = None if os.environ.get("WN_USE_BUILTIN_KEY") == "1" else \
        requests.get(f"{LS}/api/admin/quickstart", headers=adm, timeout=15).json()["api_key"]
    run = uuid.uuid4().hex[:8]
    vol = f"wn-e2e-{run}"
    pro = buy("pro", f"wn-pro-{run}@example.com", adm)
    ult = buy("ultra", f"wn-ult-{run}@example.com", adm)
    check("purchase issues PRO and ULT serials",
          pro["license_key"].startswith("WNX-PRO-") and ult["license_key"].startswith("WNX-ULT-"),
          (pro.get("license_key"), ult.get("license_key")))
    try:
        h = start_wn(vol, api_key)
        check("fresh WatchNexus starts on Standard", wn_tier(h) == "standard")

        r = wn_activate(h, pro["license_key"])
        check("activate PRO serial in WatchNexus", r.ok and r.json().get("tier") == "pro", r.text)
        check("WatchNexus reports tier=pro", wn_tier(h) == "pro")
        acts = [a for a in ls_activations(pro["license_id"], adm) if a["status"] == "active"]
        check("license server records the PRO activation",
              len(acts) == 1 and acts[0]["device_name"].startswith("WatchNexus-"), acts)
        install_id = acts[0]["hardware_id"] if acts else None

        r = wn_activate(h, ult["license_key"])
        check("upgrade to ULTRA in WatchNexus", r.ok and r.json().get("tier") == "ultra", r.text)
        check("WatchNexus reports tier=ultra", wn_tier(h) == "ultra")
        pro_active = [a for a in ls_activations(pro["license_id"], adm) if a["status"] == "active"]
        ult_active = [a for a in ls_activations(ult["license_id"], adm) if a["status"] == "active"]
        check("upgrade released the PRO seat on the license server", pro_active == [], pro_active)
        check("license server records the ULTRA activation", len(ult_active) == 1, ult_active)

        r = wn_activate(h, pro["license_key"])
        check("downgrade attempt rejected", r.status_code == 400, r.text)
        pro_active = [a for a in ls_activations(pro["license_id"], adm) if a["status"] == "active"]
        check("rejected downgrade does not hold a PRO seat", pro_active == [], pro_active)

        # Container recreate (e.g. image update) keeps the same install id.
        h = start_wn(vol, api_key)
        check("tier survives container recreate", wn_tier(h) == "ultra")
        r = wn_activate(h, ult["license_key"])
        ult_acts = ls_activations(ult["license_id"], adm)
        active = [a for a in ult_acts if a["status"] == "active"]
        check("re-entering serial after recreate reuses the seat (no new activation)",
              len(ult_acts) == 1 and len(active) == 1 and active[0]["hardware_id"] == ult_active[0]["hardware_id"],
              ult_acts)
        check("same install id used for every activation",
              install_id is not None and active and active[0]["hardware_id"] == install_id)

        r = requests.post(f"{WN}/api/cellar/deactivate", headers=h, timeout=30)
        check("deactivate in WatchNexus -> Standard", r.ok and wn_tier(h) == "standard", r.text)
        ult_active = [a for a in ls_activations(ult["license_id"], adm) if a["status"] == "active"]
        check("deactivation released the ULTRA seat on the license server", ult_active == [], ult_active)
    finally:
        sh("docker", "rm", "-f", "wn-e2e")
        sh("docker", "volume", "rm", vol)

    print(f"\n{len(failures)} failure(s)" if failures else "\nALL PASSED")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
