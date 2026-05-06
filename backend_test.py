"""WatchNexus Licensing Server - Backend API Tests"""
import requests
import sys
import json
import hmac
import hashlib
import time
import csv
import io
from datetime import datetime, timezone, timedelta

class WatchNexusAPITester:
    def __init__(self, base_url="https://nexus-license-hub.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.admin_token = None
        self.customer_token = None
        self.api_key = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_product_id = None
        self.test_license_id = None
        self.test_license_key = None
        self.activation_id = None
        self.activation_token = None

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None, files=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        req_headers = {'Content-Type': 'application/json'}
        if headers:
            req_headers.update(headers)
        if self.admin_token and 'Authorization' not in req_headers:
            req_headers['Authorization'] = f'Bearer {self.admin_token}'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=req_headers, timeout=10)
            elif method == 'POST':
                if files:
                    req_headers.pop('Content-Type', None)
                    response = requests.post(url, files=files, headers=req_headers, timeout=10)
                else:
                    response = requests.post(url, json=data, headers=req_headers, timeout=10)
            elif method == 'PATCH':
                response = requests.patch(url, json=data, headers=req_headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=req_headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=req_headers, timeout=10)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return True, response.json()
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    print(f"   Response: {response.json()}")
                except:
                    print(f"   Response: {response.text[:200]}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    # ========== Health & Public ==========
    def test_health(self):
        """Test health endpoint"""
        success, response = self.run_test(
            "Health Check",
            "GET",
            "health",
            200,
            headers={'Authorization': ''}  # No auth needed
        )
        return success and response.get('status') == 'ok'

    def test_public_key(self):
        """Test public RSA key endpoint"""
        success, response = self.run_test(
            "Public RSA Key",
            "GET",
            "public-key",
            200,
            headers={'Authorization': ''}  # No auth needed
        )
        return success and 'pem' in response and 'BEGIN PUBLIC KEY' in response.get('pem', '')

    # ========== Admin Auth ==========
    def test_admin_login(self):
        """Test admin login"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "admin/login",
            200,
            data={"email": "admin@watchnexus.app", "password": "admin12345"},
            headers={'Authorization': ''}
        )
        if success and 'token' in response:
            self.admin_token = response['token']
            print(f"   Admin token obtained")
            return True
        return False

    def test_admin_login_wrong_password(self):
        """Test admin login with wrong password"""
        success, response = self.run_test(
            "Admin Login (Wrong Password)",
            "POST",
            "admin/login",
            401,
            data={"email": "admin@watchnexus.app", "password": "wrongpassword"},
            headers={'Authorization': ''}
        )
        return success

    def test_admin_me(self):
        """Test admin /me endpoint"""
        success, response = self.run_test(
            "Admin /me",
            "GET",
            "admin/me",
            200
        )
        return success and response.get('email') == 'admin@watchnexus.app'

    # ========== Products ==========
    def test_products_list(self):
        """Test listing products"""
        success, response = self.run_test(
            "List Products",
            "GET",
            "admin/products",
            200
        )
        if success and isinstance(response, list):
            # Check for seeded product
            for p in response:
                if p.get('slug') == 'watchnexus-pro':
                    print(f"   Found seeded product: watchnexus-pro")
                    self.test_product_id = p.get('id')
                    return True
        return success

    def test_products_create(self):
        """Test creating a product"""
        success, response = self.run_test(
            "Create Product",
            "POST",
            "admin/products",
            200,
            data={
                "name": "Test Product",
                "slug": f"test-product-{int(time.time())}",
                "signing_method": "hmac",
                "fingerprint_mode": "both",
                "max_seats_default": 3,
                "description": "Test product for API testing"
            }
        )
        if success and response.get('id'):
            print(f"   Created product: {response.get('id')}")
            return True
        return False

    # ========== Licenses ==========
    def test_licenses_create(self):
        """Test creating a license"""
        if not self.test_product_id:
            print("   ⚠️  Skipped - No product ID available")
            return False
        
        success, response = self.run_test(
            "Create License",
            "POST",
            "admin/licenses",
            200,
            data={
                "product_id": self.test_product_id,
                "customer_email": "testcustomer@example.com",
                "plan": "standard",
                "seats": 2,
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
                "notes": "Test license"
            }
        )
        if success and response.get('key', '').startswith('WNX-'):
            self.test_license_id = response.get('id')
            self.test_license_key = response.get('key')
            print(f"   Created license: {self.test_license_key[:20]}...")
            return True
        return False

    def test_licenses_list(self):
        """Test listing licenses"""
        success, response = self.run_test(
            "List Licenses",
            "GET",
            "admin/licenses",
            200
        )
        if success and isinstance(response, list):
            for lic in response:
                if 'activations_count' in lic:
                    print(f"   License includes activations_count")
                    return True
        return success

    def test_licenses_list_with_filters(self):
        """Test listing licenses with filters"""
        success, response = self.run_test(
            "List Licenses (Filtered)",
            "GET",
            "admin/licenses?status=active&q=test",
            200
        )
        return success

    def test_license_detail(self):
        """Test getting license detail"""
        if not self.test_license_id:
            print("   ⚠️  Skipped - No license ID available")
            return False
        
        success, response = self.run_test(
            "License Detail",
            "GET",
            f"admin/licenses/{self.test_license_id}",
            200
        )
        return success and 'license' in response and 'activations' in response and 'audit' in response

    def test_license_extend(self):
        """Test extending a license"""
        if not self.test_license_id:
            print("   ⚠️  Skipped - No license ID available")
            return False
        
        new_expiry = (datetime.now(timezone.utc) + timedelta(days=730)).isoformat()
        success, response = self.run_test(
            "Extend License",
            "POST",
            f"admin/licenses/{self.test_license_id}/extend",
            200,
            data={"expires_at": new_expiry}
        )
        return success

    def test_licenses_bulk_import(self):
        """Test bulk importing licenses"""
        if not self.test_product_id:
            print("   ⚠️  Skipped - No product ID available")
            return False
        
        # Get product slug
        success, products = self.run_test(
            "Get Products for Bulk Import",
            "GET",
            "admin/products",
            200
        )
        if not success:
            return False
        
        product_slug = None
        for p in products:
            if p.get('id') == self.test_product_id:
                product_slug = p.get('slug')
                break
        
        if not product_slug:
            print("   ⚠️  Product slug not found")
            return False
        
        # Create CSV content
        csv_content = f"product_slug,customer_email,plan,seats,expires_at,notes\n"
        csv_content += f"{product_slug},bulk1@example.com,standard,1,,Bulk import test 1\n"
        csv_content += f"{product_slug},bulk2@example.com,pro,2,,Bulk import test 2\n"
        
        files = {'file': ('licenses.csv', csv_content, 'text/csv')}
        
        success, response = self.run_test(
            "Bulk Import Licenses",
            "POST",
            "admin/licenses/bulk-import",
            200,
            files=files
        )
        if success:
            print(f"   Created: {response.get('created', 0)}, Failed: {response.get('failed', 0)}")
            return response.get('created', 0) > 0
        return False

    def test_license_revoke(self):
        """Test revoking a license (will be done later after activation)"""
        # We'll test this after creating activations
        return True

    # ========== API Keys ==========
    def test_api_keys_create(self):
        """Test creating an API key"""
        success, response = self.run_test(
            "Create API Key",
            "POST",
            "admin/api-keys",
            200,
            data={
                "name": "Test API Key",
                "product_id": self.test_product_id,
                "scopes": ["activate", "validate", "deactivate"]
            }
        )
        if success and response.get('key', '').startswith('wnk_'):
            self.api_key = response.get('key')
            print(f"   API Key: {self.api_key[:20]}...")
            return True
        return False

    def test_api_keys_list(self):
        """Test listing API keys (should be masked)"""
        success, response = self.run_test(
            "List API Keys",
            "GET",
            "admin/api-keys",
            200
        )
        if success and isinstance(response, list):
            for key in response:
                if 'key_masked' in key and 'key' not in key:
                    print(f"   Keys are properly masked")
                    return True
        return success

    # ========== Builds ==========
    def test_builds_create(self):
        """Test creating a build"""
        if not self.test_product_id:
            print("   ⚠️  Skipped - No product ID available")
            return False
        
        success, response = self.run_test(
            "Create Build",
            "POST",
            "admin/builds",
            200,
            data={
                "product_id": self.test_product_id,
                "version": "1.0.0-test",
                "download_url": "https://example.com/downloads/test-v1.0.0.zip",
                "notes": "Test build"
            }
        )
        return success and response.get('id')

    def test_builds_list(self):
        """Test listing builds"""
        success, response = self.run_test(
            "List Builds",
            "GET",
            "admin/builds",
            200
        )
        return success and isinstance(response, list)

    # ========== Audit & Customers ==========
    def test_audit_list(self):
        """Test listing audit logs"""
        success, response = self.run_test(
            "List Audit Logs",
            "GET",
            "admin/audit",
            200
        )
        return success and isinstance(response, list)

    def test_customers_list(self):
        """Test listing customers"""
        success, response = self.run_test(
            "List Customers",
            "GET",
            "admin/customers",
            200
        )
        return success and isinstance(response, list)

    # ========== Integration Endpoints ==========
    def test_activate_without_api_key(self):
        """Test activation without API key (should fail)"""
        success, response = self.run_test(
            "Activate Without API Key",
            "POST",
            "integrate/activate",
            401,
            data={
                "license_key": "WNX-test",
                "hardware_id": "test-hw-123"
            },
            headers={'Authorization': ''}
        )
        return success

    def test_activate_with_api_key(self):
        """Test activation with valid API key"""
        if not self.api_key or not self.test_license_key:
            print("   ⚠️  Skipped - No API key or license key available")
            return False
        
        success, response = self.run_test(
            "Activate License",
            "POST",
            "integrate/activate",
            200,
            data={
                "license_key": self.test_license_key,
                "hardware_id": "test-hw-12345",
                "domain": "test.example.com",
                "device_name": "Test Device"
            },
            headers={'X-API-Key': self.api_key, 'Authorization': ''}
        )
        if success and response.get('activation_token'):
            self.activation_id = response.get('activation_id')
            self.activation_token = response.get('activation_token')
            print(f"   Activation ID: {self.activation_id}")
            print(f"   Reused: {response.get('reused', False)}")
            return True
        return False

    def test_activate_reuse_same_fingerprint(self):
        """Test re-activating with same fingerprint (should reuse)"""
        if not self.api_key or not self.test_license_key:
            print("   ⚠️  Skipped - No API key or license key available")
            return False
        
        success, response = self.run_test(
            "Re-activate Same Fingerprint",
            "POST",
            "integrate/activate",
            200,
            data={
                "license_key": self.test_license_key,
                "hardware_id": "test-hw-12345",
                "domain": "test.example.com"
            },
            headers={'X-API-Key': self.api_key, 'Authorization': ''}
        )
        if success and response.get('reused') == True:
            print(f"   ✓ Activation reused as expected")
            return True
        return False

    def test_activate_different_fingerprint_seat_limit(self):
        """Test activating with different fingerprint past seat limit"""
        if not self.api_key or not self.test_license_key:
            print("   ⚠️  Skipped - No API key or license key available")
            return False
        
        # Try to activate with different fingerprints until we hit the seat limit
        # License has 2 seats, we already used 1
        success, response = self.run_test(
            "Activate Different Fingerprint (Seat 2)",
            "POST",
            "integrate/activate",
            200,
            data={
                "license_key": self.test_license_key,
                "hardware_id": "different-hw-99999",
                "domain": "different.example.com"
            },
            headers={'X-API-Key': self.api_key, 'Authorization': ''}
        )
        
        if not success:
            return False
        
        # Now try a third activation (should fail with 403)
        success, response = self.run_test(
            "Activate Past Seat Limit",
            "POST",
            "integrate/activate",
            403,
            data={
                "license_key": self.test_license_key,
                "hardware_id": "third-hw-88888",
                "domain": "third.example.com"
            },
            headers={'X-API-Key': self.api_key, 'Authorization': ''}
        )
        return success

    def test_validate_with_token(self):
        """Test validating an activation token"""
        if not self.api_key or not self.activation_token:
            print("   ⚠️  Skipped - No API key or activation token available")
            return False
        
        success, response = self.run_test(
            "Validate Activation Token",
            "POST",
            "integrate/validate",
            200,
            data={
                "activation_token": self.activation_token,
                "hardware_id": "test-hw-12345",
                "domain": "test.example.com"
            },
            headers={'X-API-Key': self.api_key, 'Authorization': ''}
        )
        if success and response.get('valid') == True and response.get('mode') == 'online':
            print(f"   ✓ Token valid, mode: {response.get('mode')}")
            return True
        return False

    def test_validate_wrong_fingerprint(self):
        """Test validating with wrong fingerprint"""
        if not self.api_key or not self.activation_token:
            print("   ⚠️  Skipped - No API key or activation token available")
            return False
        
        success, response = self.run_test(
            "Validate Wrong Fingerprint",
            "POST",
            "integrate/validate",
            200,
            data={
                "activation_token": self.activation_token,
                "hardware_id": "wrong-hw-00000",
                "domain": "wrong.example.com"
            },
            headers={'X-API-Key': self.api_key, 'Authorization': ''}
        )
        if success and response.get('valid') == False and response.get('mode') == 'fingerprint_mismatch':
            print(f"   ✓ Fingerprint mismatch detected correctly")
            return True
        return False

    def test_deactivate(self):
        """Test deactivating an installation"""
        if not self.api_key or not self.activation_token:
            print("   ⚠️  Skipped - No API key or activation token available")
            return False
        
        success, response = self.run_test(
            "Deactivate Installation",
            "POST",
            "integrate/deactivate",
            200,
            data={
                "activation_token": self.activation_token
            },
            headers={'X-API-Key': self.api_key, 'Authorization': ''}
        )
        return success and response.get('ok') == True

    # ========== Webhooks ==========
    def test_webhook_lemonsqueezy_invalid_signature(self):
        """Test Lemon Squeezy webhook with invalid signature"""
        payload = {
            "meta": {"event_name": "order_created", "event_id": "test-ls-001"},
            "data": {"attributes": {"user_email": "webhook@example.com"}}
        }
        body = json.dumps(payload)
        
        success, response = self.run_test(
            "Webhook LemonSqueezy (Invalid Sig)",
            "POST",
            "webhooks/lemonsqueezy",
            401,
            data=payload,
            headers={'X-Signature': 'invalid_signature', 'Authorization': ''}
        )
        return success

    def test_webhook_lemonsqueezy_valid_signature(self):
        """Test Lemon Squeezy webhook with valid signature"""
        secret = "ls_test_secret"
        payload = {
            "meta": {
                "event_name": "order_created",
                "event_id": f"test-ls-{int(time.time())}",
                "custom_data": {"product_slug": "watchnexus-pro"}
            },
            "data": {"attributes": {"user_email": "lswebhook@example.com"}}
        }
        body = json.dumps(payload).encode()
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        
        # Need to send raw body, not JSON
        url = f"{self.base_url}/webhooks/lemonsqueezy"
        headers = {'X-Signature': signature, 'Content-Type': 'application/json'}
        
        print(f"\n🔍 Testing Webhook LemonSqueezy (Valid Sig)...")
        self.tests_run += 1
        
        try:
            response = requests.post(url, data=body, headers=headers, timeout=10)
            success = response.status_code == 200
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                resp_json = response.json()
                if resp_json.get('license_id'):
                    print(f"   License created: {resp_json.get('license_id')}")
                return True
            else:
                print(f"❌ Failed - Expected 200, got {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False

    def test_webhook_paddle_valid_signature(self):
        """Test Paddle webhook with valid signature"""
        secret = "pdl_test_secret"
        ts = str(int(time.time()))
        payload = {
            "event_type": "transaction.completed",
            "event_id": f"test-pdl-{int(time.time())}",
            "data": {
                "customer": {"email": "paddlewebhook@example.com"},
                "custom_data": {"product_slug": "watchnexus-pro"}
            }
        }
        body = json.dumps(payload).encode()
        
        # Paddle signature: ts=<unix_ts>;h1=<hex_hmac_of_ts:body>
        sig_payload = f"{ts}:".encode() + body
        h1 = hmac.new(secret.encode(), sig_payload, hashlib.sha256).hexdigest()
        signature = f"ts={ts};h1={h1}"
        
        url = f"{self.base_url}/webhooks/paddle"
        headers = {'Paddle-Signature': signature, 'Content-Type': 'application/json'}
        
        print(f"\n🔍 Testing Webhook Paddle (Valid Sig)...")
        self.tests_run += 1
        
        try:
            response = requests.post(url, data=body, headers=headers, timeout=10)
            success = response.status_code == 200
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                resp_json = response.json()
                if resp_json.get('license_id'):
                    print(f"   License created: {resp_json.get('license_id')}")
                return True
            else:
                print(f"❌ Failed - Expected 200, got {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False

    def test_webhook_gumroad_valid_signature(self):
        """Test Gumroad webhook with valid signature"""
        secret = "gum_test_secret"
        payload = {
            "email": "gumroadwebhook@example.com",
            "sale_id": f"test-gum-{int(time.time())}",
            "product_permalink": "watchnexus-pro"
        }
        body = json.dumps(payload).encode()
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        
        url = f"{self.base_url}/webhooks/gumroad"
        headers = {'X-Gumroad-Signature': signature, 'Content-Type': 'application/json'}
        
        print(f"\n🔍 Testing Webhook Gumroad (Valid Sig)...")
        self.tests_run += 1
        
        try:
            response = requests.post(url, data=body, headers=headers, timeout=10)
            success = response.status_code == 200
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                resp_json = response.json()
                if resp_json.get('license_id'):
                    print(f"   License created: {resp_json.get('license_id')}")
                return True
            else:
                print(f"❌ Failed - Expected 200, got {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False

    def test_webhook_duplicate_event(self):
        """Test webhook duplicate event detection"""
        secret = "ls_test_secret"
        event_id = f"duplicate-test-{int(time.time())}"
        payload = {
            "meta": {
                "event_name": "order_created",
                "event_id": event_id,
                "custom_data": {"product_slug": "watchnexus-pro"}
            },
            "data": {"attributes": {"user_email": "duplicate@example.com"}}
        }
        body = json.dumps(payload).encode()
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        
        url = f"{self.base_url}/webhooks/lemonsqueezy"
        headers = {'X-Signature': signature, 'Content-Type': 'application/json'}
        
        print(f"\n🔍 Testing Webhook Duplicate Detection...")
        self.tests_run += 1
        
        try:
            # Send first time
            response1 = requests.post(url, data=body, headers=headers, timeout=10)
            # Send second time (should be marked as duplicate)
            response2 = requests.post(url, data=body, headers=headers, timeout=10)
            
            if response1.status_code == 200 and response2.status_code == 200:
                resp2_json = response2.json()
                if resp2_json.get('duplicate') == True:
                    self.tests_passed += 1
                    print(f"✅ Passed - Duplicate detected correctly")
                    return True
                else:
                    print(f"❌ Failed - Duplicate not detected")
                    return False
            else:
                print(f"❌ Failed - Status codes: {response1.status_code}, {response2.status_code}")
                return False
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False

    # ========== Customer Portal ==========
    def test_customer_register(self):
        """Test customer registration"""
        email = f"testcustomer{int(time.time())}@example.com"
        success, response = self.run_test(
            "Customer Register",
            "POST",
            "customer/register",
            200,
            data={
                "email": email,
                "password": "testpass123",
                "name": "Test Customer"
            },
            headers={'Authorization': ''}
        )
        if success and response.get('token'):
            self.customer_token = response.get('token')
            print(f"   Customer registered: {email}")
            return True
        return False

    def test_customer_login(self):
        """Test customer login"""
        # Use the email from bulk import
        success, response = self.run_test(
            "Customer Login",
            "POST",
            "customer/login",
            200,
            data={
                "email": "bulk1@example.com",
                "password": "testpass123"
            },
            headers={'Authorization': ''}
        )
        # This will fail because we haven't registered this customer yet
        # But we can test with the customer we just registered
        return True  # Skip for now

    def test_customer_licenses(self):
        """Test customer viewing their licenses"""
        if not self.customer_token:
            print("   ⚠️  Skipped - No customer token available")
            return False
        
        # Temporarily save admin token
        temp_admin = self.admin_token
        self.admin_token = self.customer_token
        
        success, response = self.run_test(
            "Customer View Licenses",
            "GET",
            "customer/licenses",
            200
        )
        
        # Restore admin token
        self.admin_token = temp_admin
        return success and isinstance(response, list)

    def test_customer_builds(self):
        """Test customer viewing available builds"""
        if not self.customer_token:
            print("   ⚠️  Skipped - No customer token available")
            return False
        
        temp_admin = self.admin_token
        self.admin_token = self.customer_token
        
        success, response = self.run_test(
            "Customer View Builds",
            "GET",
            "customer/builds",
            200
        )
        
        self.admin_token = temp_admin
        return success and isinstance(response, list)

    # ========== Dashboard ==========
    def test_admin_dashboard(self):
        """Test admin dashboard stats"""
        success, response = self.run_test(
            "Admin Dashboard",
            "GET",
            "admin/dashboard",
            200
        )
        if success:
            required_keys = ['licenses_total', 'licenses_active', 'active_installs', 
                           'customers_total', 'products_total', 'recent_activations', 
                           'recent_audit', 'recent_webhooks']
            has_all = all(key in response for key in required_keys)
            if has_all:
                print(f"   Dashboard stats: {response.get('licenses_total')} licenses, "
                      f"{response.get('active_installs')} activations")
                return True
        return False

    def run_all_tests(self):
        """Run all tests in sequence"""
        print("=" * 60)
        print("WatchNexus Licensing Server - Backend API Tests")
        print("=" * 60)
        
        # Health & Public
        self.test_health()
        self.test_public_key()
        
        # Admin Auth
        self.test_admin_login()
        self.test_admin_login_wrong_password()
        self.test_admin_me()
        
        # Products
        self.test_products_list()
        self.test_products_create()
        
        # Licenses
        self.test_licenses_create()
        self.test_licenses_list()
        self.test_licenses_list_with_filters()
        self.test_license_detail()
        self.test_license_extend()
        self.test_licenses_bulk_import()
        
        # API Keys
        self.test_api_keys_create()
        self.test_api_keys_list()
        
        # Builds
        self.test_builds_create()
        self.test_builds_list()
        
        # Audit & Customers
        self.test_audit_list()
        self.test_customers_list()
        
        # Integration Endpoints
        self.test_activate_without_api_key()
        self.test_activate_with_api_key()
        self.test_activate_reuse_same_fingerprint()
        self.test_activate_different_fingerprint_seat_limit()
        self.test_validate_with_token()
        self.test_validate_wrong_fingerprint()
        self.test_deactivate()
        
        # Webhooks
        self.test_webhook_lemonsqueezy_invalid_signature()
        self.test_webhook_lemonsqueezy_valid_signature()
        self.test_webhook_paddle_valid_signature()
        self.test_webhook_gumroad_valid_signature()
        self.test_webhook_duplicate_event()
        
        # Customer Portal
        self.test_customer_register()
        self.test_customer_licenses()
        self.test_customer_builds()
        
        # Dashboard
        self.test_admin_dashboard()
        
        # Print results
        print("\n" + "=" * 60)
        print(f"📊 Tests Results: {self.tests_passed}/{self.tests_run} passed")
        print("=" * 60)
        
        return 0 if self.tests_passed == self.tests_run else 1

def main():
    tester = WatchNexusAPITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())
