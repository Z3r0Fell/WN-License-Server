"""
Phase 5 Backend Testing - WatchNexus License Hub
Tests:
1. C# client library file structure
2. Per-product Quickstart API (GET /api/admin/quickstart with product_id)
3. Quickstart test endpoint (POST /api/admin/quickstart/test with product_id)
4. Audit filtering (actor_type, action params)
5. Regression tests for Phase 1-4 features
"""
import requests
import sys
import time
from datetime import datetime

BASE_URL = "https://nexus-license-hub.preview.emergentagent.com"
ADMIN_EMAIL = "admin@watchnexus.app"
ADMIN_PASSWORD = "admin12345"

class Phase5Tester:
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

    def login(self):
        """Login as admin and get token"""
        self.log("Logging in as admin...", "info")
        r = requests.post(f"{self.base_url}/api/admin/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
        self.token = r.json()["token"]
        self.log("Login successful", "success")

    def headers(self):
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    # ==================== C# CLIENT LIBRARY TESTS ====================
    def test_csharp_client_exists(self):
        """Verify C# client library file exists with correct structure"""
        import os
        path = "/app/clients/csharp/WatchNexusClient.cs"
        assert os.path.exists(path), f"C# client file not found at {path}"
        
        with open(path, 'r') as f:
            content = f.read()
        
        # Check for class definition
        assert "class WatchNexusClient" in content, "WatchNexusClient class not found"
        
        # Check for required methods
        assert "ActivateAsync" in content, "ActivateAsync method not found"
        assert "ValidateAsync" in content, "ValidateAsync method not found"
        assert "DeactivateAsync" in content, "DeactivateAsync method not found"
        
        # Check braces are balanced
        open_braces = content.count('{')
        close_braces = content.count('}')
        assert open_braces == close_braces, f"Unbalanced braces: {open_braces} open, {close_braces} close"
        
        self.log(f"C# client verified: {open_braces} balanced braces, all methods present", "success")

    def test_csharp_program_exists(self):
        """Verify C# example program exists"""
        import os
        path = "/app/clients/csharp/Program.cs"
        assert os.path.exists(path), f"C# Program.cs not found at {path}"
        
        with open(path, 'r') as f:
            content = f.read()
        
        assert "WatchNexusClient" in content, "Program.cs doesn't use WatchNexusClient"
        assert "ActivateAsync" in content, "Program.cs doesn't call ActivateAsync"
        self.log("C# Program.cs verified", "success")

    def test_csharp_readme_mentions(self):
        """Verify README mentions C# client"""
        import os
        path = "/app/clients/README.md"
        assert os.path.exists(path), f"README.md not found at {path}"
        
        with open(path, 'r') as f:
            content = f.read()
        
        assert ".NET" in content or "C#" in content or "csharp" in content, "README doesn't mention C# client"
        assert "WatchNexusClient" in content, "README doesn't mention WatchNexusClient class"
        self.log("README.md mentions C# client", "success")

    # ==================== QUICKSTART API TESTS ====================
    def test_quickstart_returns_products_array(self):
        """GET /api/admin/quickstart returns products array with all products"""
        r = requests.get(f"{self.base_url}/api/admin/quickstart", headers=self.headers())
        assert r.status_code == 200, f"Quickstart failed: {r.status_code} {r.text}"
        
        data = r.json()
        assert "products" in data, "Response missing 'products' field"
        assert isinstance(data["products"], list), "products is not an array"
        assert len(data["products"]) > 0, "No products returned"
        
        # Check first product has required fields
        p = data["products"][0]
        required_fields = ["id", "name", "slug", "signing_method", "fingerprint_mode", "max_seats_default"]
        for field in required_fields:
            assert field in p, f"Product missing field: {field}"
        
        self.log(f"Products array verified: {len(data['products'])} products", "success")
        return data

    def test_quickstart_has_selected_product_id(self):
        """GET /api/admin/quickstart returns selected_product_id"""
        r = requests.get(f"{self.base_url}/api/admin/quickstart", headers=self.headers())
        assert r.status_code == 200, f"Quickstart failed: {r.status_code}"
        
        data = r.json()
        assert "selected_product_id" in data, "Response missing 'selected_product_id'"
        assert data["selected_product_id"] is not None, "selected_product_id is null"
        
        self.log(f"selected_product_id: {data['selected_product_id']}", "success")
        return data

    def test_quickstart_with_product_id_param(self):
        """GET /api/admin/quickstart?product_id=<id> selects that product"""
        # First get all products
        r = requests.get(f"{self.base_url}/api/admin/quickstart", headers=self.headers())
        assert r.status_code == 200, f"Quickstart failed: {r.status_code}"
        products = r.json()["products"]
        assert len(products) > 0, "No products available"
        
        # Pick a product (use second if available, else first)
        target_product = products[1] if len(products) > 1 else products[0]
        target_id = target_product["id"]
        
        # Request with product_id param
        r = requests.get(f"{self.base_url}/api/admin/quickstart?product_id={target_id}", 
                        headers=self.headers())
        assert r.status_code == 200, f"Quickstart with product_id failed: {r.status_code}"
        
        data = r.json()
        assert data["selected_product_id"] == target_id, \
            f"selected_product_id mismatch: expected {target_id}, got {data['selected_product_id']}"
        
        # Verify demo_license matches the product
        assert "demo_license" in data, "No demo_license returned"
        demo = data["demo_license"]
        assert demo["product_id"] == target_id, \
            f"demo_license product_id mismatch: expected {target_id}, got {demo['product_id']}"
        assert demo["signing_method"] == target_product["signing_method"], \
            f"signing_method mismatch"
        assert demo["fingerprint_mode"] == target_product["fingerprint_mode"], \
            f"fingerprint_mode mismatch"
        
        self.log(f"Product selection verified: {target_product['slug']}", "success")
        return data

    def test_quickstart_creates_bootstrap_license_lazily(self):
        """Quickstart creates bootstrap demo license if missing"""
        # Get quickstart data - should create license if missing
        r = requests.get(f"{self.base_url}/api/admin/quickstart", headers=self.headers())
        assert r.status_code == 200, f"Quickstart failed: {r.status_code}"
        
        data = r.json()
        assert "demo_license" in data, "No demo_license in response"
        demo = data["demo_license"]
        
        # Verify it's a bootstrap license
        assert demo.get("is_bootstrap") == True, "demo_license is not marked as bootstrap"
        assert demo.get("source") == "bootstrap", f"demo_license source is not 'bootstrap': {demo.get('source')}"
        assert demo.get("plan") == "demo", f"demo_license plan is not 'demo': {demo.get('plan')}"
        
        self.log(f"Bootstrap license verified: {demo['key'][:20]}...", "success")

    # ==================== QUICKSTART TEST ENDPOINT ====================
    def test_quickstart_test_with_product_id(self):
        """POST /api/admin/quickstart/test with product_id runs test against that product"""
        # Get a product
        r = requests.get(f"{self.base_url}/api/admin/quickstart", headers=self.headers())
        assert r.status_code == 200, f"Quickstart failed: {r.status_code}"
        products = r.json()["products"]
        assert len(products) > 0, "No products available"
        
        target_product = products[0]
        target_id = target_product["id"]
        
        # Run test with product_id
        r = requests.post(f"{self.base_url}/api/admin/quickstart/test",
                         headers=self.headers(),
                         json={"product_id": target_id})
        assert r.status_code == 200, f"Quickstart test failed: {r.status_code} {r.text}"
        
        result = r.json()
        assert result.get("ok") == True, "Test result not ok"
        assert result["product_slug"] == target_product["slug"], \
            f"product_slug mismatch: expected {target_product['slug']}, got {result['product_slug']}"
        
        # Verify 3 steps
        assert "steps" in result, "No steps in result"
        assert len(result["steps"]) == 3, f"Expected 3 steps, got {len(result['steps'])}"
        
        # Verify each step
        expected_labels = [
            "POST /api/integrate/activate",
            "POST /api/integrate/validate",
            "POST /api/integrate/deactivate"
        ]
        for i, step in enumerate(result["steps"]):
            assert step["label"] == expected_labels[i], \
                f"Step {i} label mismatch: expected '{expected_labels[i]}', got '{step['label']}'"
            assert step["status"] == 200, f"Step {i} status not 200: {step['status']}"
            assert "response" in step, f"Step {i} missing response"
        
        self.log(f"Quickstart test passed for product: {target_product['slug']}", "success")
        return result

    def test_quickstart_test_repeated_5_times(self):
        """Running quickstart test 5 times in a row succeeds (seat recycling)"""
        # Get a product
        r = requests.get(f"{self.base_url}/api/admin/quickstart", headers=self.headers())
        products = r.json()["products"]
        target_id = products[0]["id"]
        
        for i in range(5):
            r = requests.post(f"{self.base_url}/api/admin/quickstart/test",
                             headers=self.headers(),
                             json={"product_id": target_id})
            assert r.status_code == 200, f"Test run {i+1} failed: {r.status_code} {r.text}"
            result = r.json()
            assert result.get("ok") == True, f"Test run {i+1} not ok"
            self.log(f"Test run {i+1}/5 passed", "info")
            time.sleep(0.2)  # Small delay between tests
        
        self.log("All 5 test runs passed (seat recycling works)", "success")

    # ==================== AUDIT FILTERING TESTS ====================
    def test_audit_filter_by_actor_type_admin(self):
        """GET /api/admin/audit?actor_type=admin returns only admin events"""
        r = requests.get(f"{self.base_url}/api/admin/audit?actor_type=admin", 
                        headers=self.headers())
        assert r.status_code == 200, f"Audit query failed: {r.status_code}"
        
        events = r.json()
        assert isinstance(events, list), "Audit response is not an array"
        
        # Verify all events have actor_type == 'admin'
        for event in events:
            assert event.get("actor_type") == "admin", \
                f"Found non-admin event: {event.get('actor_type')}"
        
        self.log(f"Audit filter by actor_type=admin verified: {len(events)} events", "success")

    def test_audit_filter_by_action(self):
        """GET /api/admin/audit?action=quickstart returns only quickstart events"""
        r = requests.get(f"{self.base_url}/api/admin/audit?action=quickstart", 
                        headers=self.headers())
        assert r.status_code == 200, f"Audit query failed: {r.status_code}"
        
        events = r.json()
        assert isinstance(events, list), "Audit response is not an array"
        
        # Verify all events have 'quickstart' in action (case-insensitive substring)
        for event in events:
            action = event.get("action", "").lower()
            assert "quickstart" in action, \
                f"Found non-quickstart event: {event.get('action')}"
        
        self.log(f"Audit filter by action=quickstart verified: {len(events)} events", "success")

    def test_audit_filter_combined(self):
        """GET /api/admin/audit?actor_type=admin&action=login returns admin.login only"""
        r = requests.get(f"{self.base_url}/api/admin/audit?actor_type=admin&action=login", 
                        headers=self.headers())
        assert r.status_code == 200, f"Audit query failed: {r.status_code}"
        
        events = r.json()
        assert isinstance(events, list), "Audit response is not an array"
        assert len(events) > 0, "No admin.login events found (we just logged in!)"
        
        # Verify all events match both filters
        for event in events:
            assert event.get("actor_type") == "admin", \
                f"Found non-admin event: {event.get('actor_type')}"
            action = event.get("action", "").lower()
            assert "login" in action, \
                f"Found non-login event: {event.get('action')}"
        
        self.log(f"Combined audit filter verified: {len(events)} admin login events", "success")

    # ==================== REGRESSION TESTS ====================
    def test_regression_bootstrap_api_key_works(self):
        """Bootstrap API key works on /api/integrate/activate"""
        # Get bootstrap key and demo license
        r = requests.get(f"{self.base_url}/api/admin/quickstart", headers=self.headers())
        assert r.status_code == 200, f"Quickstart failed: {r.status_code}"
        
        data = r.json()
        api_key = data["api_key"]
        license_key = data["demo_license"]["key"]
        
        # Try to activate using bootstrap key
        r = requests.post(f"{self.base_url}/api/integrate/activate",
                         headers={"X-API-Key": api_key, "Content-Type": "application/json"},
                         json={
                             "license_key": license_key,
                             "hardware_id": "TEST-HW-" + str(int(time.time())),
                             "domain": "test.example.com",
                             "device_name": "Test Device"
                         })
        assert r.status_code == 200, f"Activation failed: {r.status_code} {r.text}"
        
        result = r.json()
        assert "activation_token" in result, "No activation_token in response"
        
        self.log("Bootstrap API key activation works", "success")

    def test_regression_rotate_key_works(self):
        """Rotate-key endpoint still works"""
        r = requests.post(f"{self.base_url}/api/admin/quickstart/rotate-key",
                         headers=self.headers())
        assert r.status_code == 200, f"Rotate-key failed: {r.status_code} {r.text}"
        
        result = r.json()
        assert "api_key" in result, "No api_key in rotate response"
        assert result["api_key"].startswith("wnk_"), "Rotated key doesn't have wnk_ prefix"
        
        self.log(f"Rotate-key works: {result['api_key'][:20]}...", "success")

    def test_regression_webhook_endpoints_exist(self):
        """Webhook endpoints still exist"""
        # Just check they return 400/401 (not 404) without proper payload
        webhooks = [
            "/api/webhooks/lemonsqueezy",
            "/api/webhooks/paddle",
            "/api/webhooks/gumroad",
            "/api/webhooks/stripe"
        ]
        
        for webhook in webhooks:
            r = requests.post(f"{self.base_url}{webhook}",
                            headers={"Content-Type": "application/json"},
                            json={})
            # Should not be 404 - endpoint exists
            assert r.status_code != 404, f"Webhook endpoint {webhook} not found (404)"
            self.log(f"Webhook {webhook} exists (status {r.status_code})", "info")
        
        self.log("All webhook endpoints exist", "success")

    # ==================== SUMMARY ====================
    def print_summary(self):
        print("\n" + "="*60)
        print("PHASE 5 BACKEND TEST SUMMARY")
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
    tester = Phase5Tester()
    
    # Login first
    try:
        tester.login()
    except Exception as e:
        print(f"❌ Login failed: {e}")
        return 1
    
    # C# Client Library Tests
    tester.test("C# client file exists with correct structure", tester.test_csharp_client_exists)
    tester.test("C# Program.cs example exists", tester.test_csharp_program_exists)
    tester.test("README mentions C# client", tester.test_csharp_readme_mentions)
    
    # Quickstart API Tests
    tester.test("Quickstart returns products array", tester.test_quickstart_returns_products_array)
    tester.test("Quickstart returns selected_product_id", tester.test_quickstart_has_selected_product_id)
    tester.test("Quickstart with product_id param selects product", tester.test_quickstart_with_product_id_param)
    tester.test("Quickstart creates bootstrap license lazily", tester.test_quickstart_creates_bootstrap_license_lazily)
    
    # Quickstart Test Endpoint
    tester.test("Quickstart test with product_id", tester.test_quickstart_test_with_product_id)
    tester.test("Quickstart test repeated 5 times (seat recycling)", tester.test_quickstart_test_repeated_5_times)
    
    # Audit Filtering
    tester.test("Audit filter by actor_type=admin", tester.test_audit_filter_by_actor_type_admin)
    tester.test("Audit filter by action=quickstart", tester.test_audit_filter_by_action)
    tester.test("Audit combined filters (actor_type + action)", tester.test_audit_filter_combined)
    
    # Regression Tests
    tester.test("Regression: Bootstrap API key works", tester.test_regression_bootstrap_api_key_works)
    tester.test("Regression: Rotate-key works", tester.test_regression_rotate_key_works)
    tester.test("Regression: Webhook endpoints exist", tester.test_regression_webhook_endpoints_exist)
    
    return tester.print_summary()

if __name__ == "__main__":
    sys.exit(main())
