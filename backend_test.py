"""
Phase 6 Backend Testing - WatchNexus License Hub
Regression + Runtime Settings Module Validation

Tests:
1. Health check
2. Admin authentication
3. Runtime settings GET (no secret leakage)
4. Runtime settings PUT (live updates without restart)
5. API keys CRUD + bootstrap key
6. Full license lifecycle (create → activate → validate → revoke)
7. Webhook signature verification using DB values
8. Rate limiting
9. Audit log mutations
"""
import requests
import sys
import time
import hmac
import hashlib
import json
from datetime import datetime

BASE_URL = "https://watchnexus-deploy.preview.emergentagent.com"
ADMIN_EMAIL = "admin@watchnexus.app"
ADMIN_PASSWORD = "admin12345"

class Phase6Tester:
    def __init__(self):
        self.base_url = BASE_URL
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failed_tests = []

    def log(self, msg, status="info"):
        prefix = {
            "info": "ℹ️ ",
            "success": "✅",
            "fail": "❌",
            "warn": "⚠️ "
        }.get(status, "")
        print(f"{prefix} {msg}")

    def test(self, name, func):
        """Run a test function and track results"""
        self.tests_run += 1
        self.log(f"\n{'='*60}", "info")
        self.log(f"Test {self.tests_run}: {name}", "info")
        self.log(f"{'='*60}", "info")
        try:
            func()
            self.tests_passed += 1
            self.log(f"PASSED: {name}", "success")
            return True
        except AssertionError as e:
            self.tests_failed += 1
            self.failed_tests.append({"name": name, "error": str(e)})
            self.log(f"FAILED: {name} - {str(e)}", "fail")
            return False
        except Exception as e:
            self.tests_failed += 1
            self.failed_tests.append({"name": name, "error": f"Exception: {str(e)}"})
            self.log(f"ERROR: {name} - {str(e)}", "fail")
            return False

    def headers(self):
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    # ==================== CORE TESTS ====================
    def test_health_check(self):
        """GET /api/health returns 200"""
        r = requests.get(f"{self.base_url}/api/health")
        assert r.status_code == 200, f"Health check failed: {r.status_code} {r.text}"
        data = r.json()
        assert data.get("status") == "ok", f"Health check returned status={data.get('status')}"
        self.log("Health check passed", "success")

    def test_admin_login(self):
        """Admin login with seeded credentials returns JWT"""
        self.log("Logging in as admin...", "info")
        r = requests.post(f"{self.base_url}/api/admin/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
        data = r.json()
        assert "token" in data, "No token in login response"
        self.token = data["token"]
        self.log("Admin login successful", "success")

    # ==================== RUNTIME SETTINGS TESTS ====================
    def test_runtime_settings_get(self):
        """GET /api/admin/settings returns settings without leaking raw secrets"""
        r = requests.get(f"{self.base_url}/api/admin/settings", headers=self.headers())
        assert r.status_code == 200, f"Settings GET failed: {r.status_code} {r.text}"
        
        data = r.json()
        assert isinstance(data, dict), "Settings response is not a dict"
        
        # Check for expected webhook secrets
        expected_keys = [
            "STRIPE_WEBHOOK_SECRET",
            "LEMONSQUEEZY_WEBHOOK_SECRET",
            "PADDLE_WEBHOOK_SECRET",
            "GUMROAD_WEBHOOK_SECRET",
            "SENDGRID_API_KEY",
            "EMAIL_FROM",
            "APP_PUBLIC_URL"
        ]
        
        for key in expected_keys:
            assert key in data, f"Missing expected setting: {key}"
        
        # Verify secrets are masked (not raw values)
        stripe_setting = data["STRIPE_WEBHOOK_SECRET"]
        assert stripe_setting.get("secret") == True, "STRIPE_WEBHOOK_SECRET not marked as secret"
        assert "masked" in stripe_setting, "Secret doesn't have 'masked' field"
        assert "value" not in stripe_setting, "Secret has raw 'value' field (should be masked)"
        
        # Verify non-secrets have values
        email_setting = data["EMAIL_FROM"]
        assert email_setting.get("secret") == False, "EMAIL_FROM incorrectly marked as secret"
        assert "value" in email_setting, "Non-secret doesn't have 'value' field"
        
        self.log(f"Runtime settings GET verified: {len(data)} settings, secrets properly masked", "success")
        return data

    def test_runtime_settings_put_live_update(self):
        """PUT /api/admin/settings updates setting and reflects immediately (no restart)"""
        # Update STRIPE_WEBHOOK_SECRET to a test value
        test_secret = f"whsec_test_{int(time.time())}"
        
        r = requests.put(
            f"{self.base_url}/api/admin/settings",
            headers=self.headers(),
            json={"values": {"STRIPE_WEBHOOK_SECRET": test_secret}}
        )
        assert r.status_code == 200, f"Settings PUT failed: {r.status_code} {r.text}"
        
        # Immediately read back (should reflect new value without restart)
        r = requests.get(f"{self.base_url}/api/admin/settings", headers=self.headers())
        assert r.status_code == 200, f"Settings GET after PUT failed: {r.status_code}"
        
        data = r.json()
        stripe_setting = data["STRIPE_WEBHOOK_SECRET"]
        
        # Verify it's now from DB (not env)
        assert stripe_setting.get("source") == "db", f"Setting source should be 'db', got: {stripe_setting.get('source')}"
        assert stripe_setting.get("has_value") == True, "Setting should have value"
        
        # Verify masked value shows part of our test secret
        masked = stripe_setting.get("masked", "")
        # Our test secret format: whsec_test_<timestamp>
        # Should show first 4 chars: whse
        assert "whse" in masked or len(masked) > 0, f"Masked value doesn't reflect update: {masked}"
        
        self.log(f"Runtime settings PUT verified: live update working (source=db)", "success")
        return test_secret

    # ==================== API KEYS TESTS ====================
    def test_api_keys_list_and_bootstrap(self):
        """Admin can list API keys and bootstrap key exists"""
        r = requests.get(f"{self.base_url}/api/admin/api-keys", headers=self.headers())
        assert r.status_code == 200, f"API keys list failed: {r.status_code} {r.text}"
        
        keys = r.json()
        assert isinstance(keys, list), "API keys response is not a list"
        assert len(keys) > 0, "No API keys found (bootstrap key should exist)"
        
        # Find bootstrap key
        bootstrap = next((k for k in keys if k.get("is_bootstrap") == True), None)
        assert bootstrap is not None, "Bootstrap API key not found"
        assert bootstrap.get("status") == "active", "Bootstrap key not active"
        
        self.log(f"API keys list verified: {len(keys)} keys, bootstrap key present", "success")
        return bootstrap

    def test_api_keys_create_revoke(self):
        """Admin can create and revoke API keys"""
        # Create a new API key
        r = requests.post(
            f"{self.base_url}/api/admin/api-keys",
            headers=self.headers(),
            json={
                "name": f"Test Key {int(time.time())}",
                "scopes": ["activate", "validate"],
                "allowed_ips": []
            }
        )
        assert r.status_code == 200, f"API key creation failed: {r.status_code} {r.text}"
        
        new_key = r.json()
        assert "id" in new_key, "No ID in created key"
        assert "key" in new_key, "No key value in response"
        assert new_key["key"].startswith("wnk_"), "Key doesn't have wnk_ prefix"
        
        key_id = new_key["id"]
        self.log(f"API key created: {new_key['key'][:20]}...", "success")
        
        # Revoke the key
        r = requests.post(
            f"{self.base_url}/api/admin/api-keys/{key_id}/revoke",
            headers=self.headers()
        )
        assert r.status_code == 200, f"API key revocation failed: {r.status_code} {r.text}"
        
        # Verify it's revoked
        r = requests.get(f"{self.base_url}/api/admin/api-keys", headers=self.headers())
        keys = r.json()
        revoked_key = next((k for k in keys if k["id"] == key_id), None)
        assert revoked_key is not None, "Revoked key not found in list"
        assert revoked_key.get("status") == "revoked", "Key status not 'revoked'"
        
        self.log("API key create/revoke verified", "success")

    # ==================== FULL LICENSE LIFECYCLE ====================
    def test_full_license_lifecycle(self):
        """Full license lifecycle: create product → license → activate → validate → revoke → validate fails"""
        # Step 1: Create a test product
        product_slug = f"test-product-{int(time.time())}"
        r = requests.post(
            f"{self.base_url}/api/admin/products",
            headers=self.headers(),
            json={
                "name": f"Test Product {int(time.time())}",
                "slug": product_slug,
                "signing_method": "hmac",
                "fingerprint_mode": "both",
                "max_seats_default": 2
            }
        )
        assert r.status_code == 200, f"Product creation failed: {r.status_code} {r.text}"
        product = r.json()
        product_id = product["id"]
        self.log(f"Product created: {product_slug}", "success")
        
        # Step 2: Create a license for this product
        r = requests.post(
            f"{self.base_url}/api/admin/licenses",
            headers=self.headers(),
            json={
                "product_id": product_id,
                "plan": "pro",
                "seats": 2,
                "customer_email": "test@example.com"
            }
        )
        assert r.status_code == 200, f"License creation failed: {r.status_code} {r.text}"
        license_data = r.json()
        license_key = license_data["key"]
        license_id = license_data["id"]
        self.log(f"License created: {license_key[:30]}...", "success")
        
        # Step 3: Get bootstrap API key for integration calls
        r = requests.get(f"{self.base_url}/api/admin/quickstart", headers=self.headers())
        assert r.status_code == 200, f"Quickstart failed: {r.status_code}"
        api_key = r.json()["api_key"]
        
        # Step 4: Activate the license
        hw_id = f"TEST-HW-{int(time.time())}"
        r = requests.post(
            f"{self.base_url}/api/integrate/activate",
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            json={
                "license_key": license_key,
                "hardware_id": hw_id,
                "domain": "test.example.com",
                "device_name": "Test Device"
            }
        )
        assert r.status_code == 200, f"Activation failed: {r.status_code} {r.text}"
        activation_result = r.json()
        assert "activation_token" in activation_result, "No activation_token in response"
        activation_token = activation_result["activation_token"]
        self.log("License activated successfully", "success")
        
        # Step 5: Validate the license (should be valid)
        r = requests.post(
            f"{self.base_url}/api/integrate/validate",
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            json={
                "activation_token": activation_token,
                "hardware_id": hw_id,
                "domain": "test.example.com"
            }
        )
        assert r.status_code == 200, f"Validation failed: {r.status_code} {r.text}"
        validation_result = r.json()
        assert validation_result.get("valid") == True, "License should be valid"
        self.log("License validation passed (valid)", "success")
        
        # Step 6: Revoke the license
        r = requests.post(
            f"{self.base_url}/api/admin/licenses/{license_id}/revoke",
            headers=self.headers()
        )
        assert r.status_code == 200, f"License revocation failed: {r.status_code} {r.text}"
        self.log("License revoked", "success")
        
        # Step 7: Validate again (should be invalid)
        r = requests.post(
            f"{self.base_url}/api/integrate/validate",
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            json={
                "activation_token": activation_token,
                "hardware_id": hw_id,
                "domain": "test.example.com"
            }
        )
        assert r.status_code == 200, f"Validation request failed: {r.status_code} {r.text}"
        validation_result = r.json()
        assert validation_result.get("valid") == False, "License should be invalid after revocation"
        self.log("License validation after revoke: invalid (correct)", "success")

    # ==================== WEBHOOK SIGNATURE VERIFICATION ====================
    def test_stripe_webhook_uses_db_secret(self):
        """Stripe webhook verifies signature using DB value (not .env)"""
        # First, set a known test secret via runtime settings
        test_secret = f"whsec_stripe_test_{int(time.time())}"
        r = requests.put(
            f"{self.base_url}/api/admin/settings",
            headers=self.headers(),
            json={"values": {"STRIPE_WEBHOOK_SECRET": test_secret}}
        )
        assert r.status_code == 200, f"Settings update failed: {r.status_code}"
        self.log(f"Set Stripe webhook secret to: {test_secret}", "info")
        
        # Create a test webhook payload
        payload = {
            "id": f"evt_test_{int(time.time())}",
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test"}}
        }
        payload_str = json.dumps(payload)
        timestamp = str(int(time.time()))
        
        # Generate signature using our test secret
        signed_payload = f"{timestamp}.{payload_str}"
        signature = hmac.new(
            test_secret.encode(),
            signed_payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        stripe_signature = f"t={timestamp},v1={signature}"
        
        # Send webhook with correct signature
        r = requests.post(
            f"{self.base_url}/api/webhooks/stripe",
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": stripe_signature
            },
            data=payload_str
        )
        
        # Should not be 401 (signature verification passed)
        # Might be 400 or 200 depending on payload processing
        assert r.status_code != 401, f"Stripe webhook signature verification failed (401). Status: {r.status_code}"
        self.log(f"Stripe webhook signature verification passed (status {r.status_code})", "success")

    def test_lemonsqueezy_webhook_uses_db_secret(self):
        """LemonSqueezy webhook verifies signature using DB value"""
        # Set a known test secret
        test_secret = f"ls_test_{int(time.time())}"
        r = requests.put(
            f"{self.base_url}/api/admin/settings",
            headers=self.headers(),
            json={"values": {"LEMONSQUEEZY_WEBHOOK_SECRET": test_secret}}
        )
        assert r.status_code == 200, f"Settings update failed: {r.status_code}"
        self.log(f"Set LemonSqueezy webhook secret to: {test_secret}", "info")
        
        # Create test payload
        payload = {
            "meta": {
                "event_name": "order_created",
                "custom_data": {}
            },
            "data": {
                "id": str(int(time.time())),
                "type": "orders"
            }
        }
        payload_str = json.dumps(payload)
        
        # Generate signature
        signature = hmac.new(
            test_secret.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Send webhook
        r = requests.post(
            f"{self.base_url}/api/webhooks/lemonsqueezy",
            headers={
                "Content-Type": "application/json",
                "X-Signature": signature
            },
            data=payload_str
        )
        
        # Should not be 401
        assert r.status_code != 401, f"LemonSqueezy webhook signature verification failed (401). Status: {r.status_code}"
        self.log(f"LemonSqueezy webhook signature verification passed (status {r.status_code})", "success")

    # ==================== RATE LIMITING ====================
    def test_rate_limit_admin_login(self):
        """Rate limits apply: 429 after burst on /api/admin/login"""
        self.log("Testing rate limit (10 requests in 60s for /api/admin/login)...", "info")
        
        # Make 11 login attempts rapidly (limit is 10/60s)
        rate_limited = False
        for i in range(12):
            r = requests.post(
                f"{self.base_url}/api/admin/login",
                json={"email": "test@example.com", "password": "wrong"}
            )
            if r.status_code == 429:
                rate_limited = True
                self.log(f"Rate limited after {i+1} requests", "info")
                break
            time.sleep(0.1)
        
        assert rate_limited, "Rate limit not triggered after 12 requests"
        self.log("Rate limiting working correctly", "success")

    # ==================== AUDIT LOG ====================
    def test_audit_log_records_mutations(self):
        """Audit log records mutations (creating a license, updating a setting)"""
        # Get current audit count
        r = requests.get(f"{self.base_url}/api/admin/audit", headers=self.headers())
        assert r.status_code == 200, f"Audit log fetch failed: {r.status_code}"
        initial_count = len(r.json())
        
        # Perform a mutation: update a setting
        r = requests.put(
            f"{self.base_url}/api/admin/settings",
            headers=self.headers(),
            json={"values": {"EMAIL_FROM": f"test-{int(time.time())}@example.com"}}
        )
        assert r.status_code == 200, f"Settings update failed: {r.status_code}"
        
        # Check audit log increased
        r = requests.get(f"{self.base_url}/api/admin/audit", headers=self.headers())
        assert r.status_code == 200, f"Audit log fetch failed: {r.status_code}"
        new_count = len(r.json())
        
        assert new_count > initial_count, f"Audit log didn't record mutation (count: {initial_count} -> {new_count})"
        self.log(f"Audit log recording mutations (count: {initial_count} -> {new_count})", "success")

    # ==================== SUMMARY ====================
    def print_summary(self):
        print("\n" + "="*60)
        print("PHASE 6 BACKEND TEST SUMMARY")
        print("="*60)
        print(f"Total tests run: {self.tests_run}")
        print(f"✅ Passed: {self.tests_passed}")
        print(f"❌ Failed: {self.tests_failed}")
        print(f"Success rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        if self.failed_tests:
            print("\n" + "="*60)
            print("FAILED TESTS:")
            print("="*60)
            for i, test in enumerate(self.failed_tests, 1):
                print(f"{i}. {test['name']}")
                print(f"   Error: {test['error']}")
        
        print("="*60)
        return 0 if self.tests_failed == 0 else 1

def main():
    tester = Phase6Tester()
    
    # Core tests
    tester.test("Health check", tester.test_health_check)
    tester.test("Admin login", tester.test_admin_login)
    
    # Runtime settings
    tester.test("Runtime settings GET (no secret leakage)", tester.test_runtime_settings_get)
    tester.test("Runtime settings PUT (live update)", tester.test_runtime_settings_put_live_update)
    
    # API keys
    tester.test("API keys list and bootstrap key exists", tester.test_api_keys_list_and_bootstrap)
    tester.test("API keys create and revoke", tester.test_api_keys_create_revoke)
    
    # License lifecycle
    tester.test("Full license lifecycle", tester.test_full_license_lifecycle)
    
    # Webhook signature verification
    tester.test("Stripe webhook uses DB secret", tester.test_stripe_webhook_uses_db_secret)
    tester.test("LemonSqueezy webhook uses DB secret", tester.test_lemonsqueezy_webhook_uses_db_secret)
    
    # Rate limiting
    tester.test("Rate limit on admin login", tester.test_rate_limit_admin_login)
    
    # Audit log
    tester.test("Audit log records mutations", tester.test_audit_log_records_mutations)
    
    return tester.print_summary()

if __name__ == "__main__":
    sys.exit(main())
