"""
WatchNexus Admin Security Features Test Suite
Tests: IP allowlist, audit filtering, TOTP 2FA full lifecycle
"""
import requests
import sys
import time
import pyotp
from typing import Optional

BASE_URL = "https://watchnexus-deploy.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@watchnexus.app"
ADMIN_PASSWORD = "admin12345"


class SecurityTester:
    def __init__(self):
        self.token: Optional[str] = None
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failures = []
        self.totp_secret: Optional[str] = None
        self.recovery_codes = []

    def log(self, msg: str, level: str = "INFO"):
        prefix = {
            "INFO": "ℹ️ ",
            "PASS": "✅",
            "FAIL": "❌",
            "WARN": "⚠️ ",
        }.get(level, "  ")
        print(f"{prefix} {msg}")

    def test(self, name: str, condition: bool, details: str = ""):
        self.tests_run += 1
        if condition:
            self.tests_passed += 1
            self.log(f"PASS: {name}", "PASS")
            if details:
                print(f"     {details}")
        else:
            self.tests_failed += 1
            self.failures.append(f"{name}: {details}")
            self.log(f"FAIL: {name} - {details}", "FAIL")

    def login(self, email: str = ADMIN_EMAIL, password: str = ADMIN_PASSWORD) -> dict:
        """Login and return response data"""
        try:
            r = requests.post(f"{BASE_URL}/admin/login", json={"email": email, "password": password}, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if "token" in data:
                    self.token = data["token"]
                return data
            return {"status_code": r.status_code, "error": r.text}
        except Exception as e:
            return {"error": str(e)}

    def headers(self):
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def get_me(self) -> dict:
        """Get current admin user info"""
        try:
            r = requests.get(f"{BASE_URL}/admin/me", headers=self.headers(), timeout=10)
            return r.json() if r.status_code == 200 else {}
        except:
            return {}

    # ==================== IP ALLOWLIST TESTS ====================
    def test_ip_allowlist(self):
        self.log("\n=== Testing IP Allowlist Feature ===", "INFO")
        
        # 1. Get current settings
        r = requests.get(f"{BASE_URL}/admin/settings", headers=self.headers(), timeout=10)
        self.test("GET /admin/settings returns 200", r.status_code == 200)
        
        if r.status_code == 200:
            settings = r.json()
            has_allowlist_key = "ADMIN_LOGIN_IP_ALLOWLIST" in settings
            self.test("ADMIN_LOGIN_IP_ALLOWLIST key exists in settings", has_allowlist_key)
            
            if has_allowlist_key:
                meta = settings["ADMIN_LOGIN_IP_ALLOWLIST"]
                self.test("IP allowlist is in 'security' category", meta.get("category") == "security")
                self.test("IP allowlist is not marked as secret", meta.get("secret") == False)
                
                # 2. Set IP allowlist to exclude current client (use a fake CIDR)
                self.log("Setting IP allowlist to block login...", "INFO")
                r = requests.put(
                    f"{BASE_URL}/admin/settings",
                    headers=self.headers(),
                    json={"values": {"ADMIN_LOGIN_IP_ALLOWLIST": "192.0.2.0/24"}},  # TEST-NET-1, won't match real IPs
                    timeout=10
                )
                self.test("PUT /admin/settings with IP allowlist returns 200", r.status_code == 200)
                
                # 3. Try to login - should get 403
                time.sleep(0.5)  # Brief pause for settings to propagate
                r = requests.post(f"{BASE_URL}/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
                self.test("Login with blocked IP returns 403", r.status_code == 403, f"Got {r.status_code}")
                if r.status_code == 403:
                    self.test("403 response mentions IP restriction", "IP" in r.text or "allowed" in r.text.lower())
                
                # 4. CRITICAL: Clear the IP allowlist to restore normal access
                self.log("Clearing IP allowlist to restore access...", "WARN")
                r = requests.put(
                    f"{BASE_URL}/admin/settings",
                    headers=self.headers(),
                    json={"values": {"ADMIN_LOGIN_IP_ALLOWLIST": ""}},
                    timeout=10
                )
                self.test("Clearing IP allowlist returns 200", r.status_code == 200)
                
                # 5. Verify login works again
                time.sleep(0.5)
                r = requests.post(f"{BASE_URL}/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
                self.test("Login after clearing IP allowlist returns 200", r.status_code == 200, f"Got {r.status_code}")
                if r.status_code == 200:
                    self.token = r.json().get("token")  # Refresh token

    # ==================== AUDIT FILTERING TESTS ====================
    def test_audit_filtering(self):
        self.log("\n=== Testing Audit Log Filtering ===", "INFO")
        
        # 1. Get audit actors list
        r = requests.get(f"{BASE_URL}/admin/audit/actors", headers=self.headers(), timeout=10)
        self.test("GET /admin/audit/actors returns 200", r.status_code == 200)
        
        actors = []
        if r.status_code == 200:
            actors = r.json()
            self.test("Audit actors list is an array", isinstance(actors, list))
            if actors:
                self.log(f"Found {len(actors)} distinct actors in audit log", "INFO")
        
        # 2. Get all audit events
        r = requests.get(f"{BASE_URL}/admin/audit", headers=self.headers(), timeout=10)
        self.test("GET /admin/audit returns 200", r.status_code == 200)
        
        all_events = []
        if r.status_code == 200:
            all_events = r.json()
            self.test("Audit events is an array", isinstance(all_events, list))
            self.log(f"Total audit events: {len(all_events)}", "INFO")
        
        # 3. Filter by actor_email (admin)
        r = requests.get(
            f"{BASE_URL}/admin/audit",
            headers=self.headers(),
            params={"actor_email": ADMIN_EMAIL},
            timeout=10
        )
        self.test("GET /admin/audit with actor_email filter returns 200", r.status_code == 200)
        
        if r.status_code == 200:
            filtered = r.json()
            self.test("Filtered events is an array", isinstance(filtered, list))
            if filtered:
                # Verify all returned events match the filter
                all_match = all(ADMIN_EMAIL.lower() in (e.get("actor_email") or "").lower() for e in filtered)
                self.test("All filtered events match actor_email", all_match)
        
        # 4. Filter by severity
        for severity in ["info", "warning", "error"]:
            r = requests.get(
                f"{BASE_URL}/admin/audit",
                headers=self.headers(),
                params={"severity": severity},
                timeout=10
            )
            if r.status_code == 200:
                filtered = r.json()
                if filtered:
                    all_match = all(e.get("severity") == severity for e in filtered)
                    self.test(f"Severity filter '{severity}' works correctly", all_match)
                else:
                    self.log(f"No events with severity '{severity}'", "INFO")

    # ==================== 2FA FULL LIFECYCLE TESTS ====================
    def test_2fa_lifecycle(self):
        self.log("\n=== Testing 2FA Full Lifecycle ===", "INFO")
        
        # 1. Enroll - get secret and QR
        r = requests.post(f"{BASE_URL}/admin/me/2fa/enroll", headers=self.headers(), timeout=10)
        self.test("POST /admin/me/2fa/enroll returns 200", r.status_code == 200)
        
        if r.status_code == 200:
            enroll_data = r.json()
            has_secret = "secret" in enroll_data
            has_uri = "otpauth_uri" in enroll_data
            has_qr = "qr_png_data_uri" in enroll_data
            
            self.test("Enroll response has 'secret'", has_secret)
            self.test("Enroll response has 'otpauth_uri'", has_uri)
            self.test("Enroll response has 'qr_png_data_uri'", has_qr)
            
            if has_qr:
                qr_data = enroll_data["qr_png_data_uri"]
                self.test("QR data is a data URI", qr_data.startswith("data:image/png;base64,"))
            
            if has_secret:
                self.totp_secret = enroll_data["secret"]
                self.log(f"Got TOTP secret: {self.totp_secret[:8]}...", "INFO")
                
                # 2. Verify with a live TOTP code
                totp = pyotp.TOTP(self.totp_secret)
                code = totp.now()
                self.log(f"Generated TOTP code: {code}", "INFO")
                
                r = requests.post(
                    f"{BASE_URL}/admin/me/2fa/verify",
                    headers=self.headers(),
                    json={"secret": self.totp_secret, "code": code, "current_password": ADMIN_PASSWORD},
                    timeout=10
                )
                self.test("POST /admin/me/2fa/verify with valid code returns 200", r.status_code == 200, f"Got {r.status_code}")
                
                if r.status_code == 200:
                    verify_data = r.json()
                    has_recovery = "recovery_codes" in verify_data
                    self.test("Verify response has 'recovery_codes'", has_recovery)
                    
                    if has_recovery:
                        self.recovery_codes = verify_data["recovery_codes"]
                        self.test("Got 10 recovery codes", len(self.recovery_codes) == 10)
                        if self.recovery_codes:
                            self.log(f"Sample recovery code: {self.recovery_codes[0]}", "INFO")
                    
                    # 3. Verify 2FA is now enabled
                    me = self.get_me()
                    self.test("User totp_enabled is True", me.get("totp_enabled") == True)
                    self.test("User has 10 recovery codes", me.get("recovery_codes_remaining") == 10)
                    
                    # 4. Test login now requires 2FA
                    self.log("Testing login with 2FA enabled...", "INFO")
                    r = requests.post(f"{BASE_URL}/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
                    self.test("Login with 2FA enabled returns 200", r.status_code == 200)
                    
                    if r.status_code == 200:
                        login_data = r.json()
                        self.test("Login response has 'require_2fa': true", login_data.get("require_2fa") == True)
                        self.test("Login response has 'mfa_token'", "mfa_token" in login_data)
                        
                        if "mfa_token" in login_data:
                            mfa_token = login_data["mfa_token"]
                            
                            # 5. Complete 2FA login with TOTP code
                            code = totp.now()
                            r = requests.post(
                                f"{BASE_URL}/admin/login/2fa",
                                json={"mfa_token": mfa_token, "code": code},
                                timeout=10
                            )
                            self.test("POST /admin/login/2fa with valid code returns 200", r.status_code == 200, f"Got {r.status_code}")
                            
                            if r.status_code == 200:
                                login2fa_data = r.json()
                                self.test("2FA login response has 'token'", "token" in login2fa_data)
                                if "token" in login2fa_data:
                                    self.token = login2fa_data["token"]  # Update token
                            
                            # 6. Test recovery code usage
                            if self.recovery_codes:
                                self.log("Testing recovery code login...", "INFO")
                                
                                # Get new mfa_token
                                r = requests.post(f"{BASE_URL}/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
                                if r.status_code == 200 and "mfa_token" in r.json():
                                    mfa_token = r.json()["mfa_token"]
                                    recovery_code = self.recovery_codes[0]
                                    
                                    r = requests.post(
                                        f"{BASE_URL}/admin/login/2fa",
                                        json={"mfa_token": mfa_token, "recovery_code": recovery_code},
                                        timeout=10
                                    )
                                    self.test("Login with recovery code returns 200", r.status_code == 200, f"Got {r.status_code}")
                                    
                                    if r.status_code == 200:
                                        recovery_data = r.json()
                                        self.test("Recovery login has 'used_recovery_code': true", recovery_data.get("used_recovery_code") == True)
                                        self.test("Recovery codes remaining is 9", recovery_data.get("recovery_codes_remaining") == 9)
                                        
                                        if "token" in recovery_data:
                                            self.token = recovery_data["token"]
                                        
                                        # 7. Try to use same recovery code again (should fail)
                                        r = requests.post(f"{BASE_URL}/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
                                        if r.status_code == 200 and "mfa_token" in r.json():
                                            mfa_token = r.json()["mfa_token"]
                                            r = requests.post(
                                                f"{BASE_URL}/admin/login/2fa",
                                                json={"mfa_token": mfa_token, "recovery_code": recovery_code},
                                                timeout=10
                                            )
                                            self.test("Reusing recovery code returns 401", r.status_code == 401, f"Got {r.status_code}")
                            
                            # 8. Test regenerate recovery codes
                            self.log("Testing recovery code regeneration...", "INFO")
                            code = totp.now()
                            r = requests.post(
                                f"{BASE_URL}/admin/me/2fa/regenerate-recovery",
                                headers=self.headers(),
                                json={"current_password": ADMIN_PASSWORD, "code": code},
                                timeout=10
                            )
                            self.test("POST /admin/me/2fa/regenerate-recovery returns 200", r.status_code == 200, f"Got {r.status_code}")
                            
                            if r.status_code == 200:
                                regen_data = r.json()
                                self.test("Regenerate response has 'recovery_codes'", "recovery_codes" in regen_data)
                                if "recovery_codes" in regen_data:
                                    new_codes = regen_data["recovery_codes"]
                                    self.test("Got 10 new recovery codes", len(new_codes) == 10)
                                    # Verify old code is different from new codes
                                    if self.recovery_codes:
                                        old_code = self.recovery_codes[1]  # Use second code (first was consumed)
                                        self.test("Old recovery code not in new batch", old_code not in new_codes)
                    
                    # 9. CRITICAL: Disable 2FA to restore normal login
                    self.log("CRITICAL: Disabling 2FA to restore normal login...", "WARN")
                    code = totp.now()
                    r = requests.post(
                        f"{BASE_URL}/admin/me/2fa/disable",
                        headers=self.headers(),
                        json={"current_password": ADMIN_PASSWORD, "code": code},
                        timeout=10
                    )
                    self.test("POST /admin/me/2fa/disable returns 200", r.status_code == 200, f"Got {r.status_code}")
                    
                    if r.status_code == 200:
                        # Verify 2FA is disabled
                        me = self.get_me()
                        self.test("User totp_enabled is False after disable", me.get("totp_enabled") == False)
                        
                        # Verify normal login works
                        r = requests.post(f"{BASE_URL}/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
                        self.test("Normal login works after disabling 2FA", r.status_code == 200 and "token" in r.json())

    # ==================== ERROR HANDLING TESTS ====================
    def test_error_handling(self):
        self.log("\n=== Testing Error Handling ===", "INFO")
        
        # Wrong password
        r = requests.post(f"{BASE_URL}/admin/login", json={"email": ADMIN_EMAIL, "password": "wrongpassword"}, timeout=10)
        self.test("Wrong password returns 401", r.status_code == 401)
        
        # Wrong email
        r = requests.post(f"{BASE_URL}/admin/login", json={"email": "nonexistent@example.com", "password": ADMIN_PASSWORD}, timeout=10)
        self.test("Wrong email returns 401", r.status_code == 401)

    # ==================== MAIN TEST RUNNER ====================
    def run_all_tests(self):
        self.log("=" * 60, "INFO")
        self.log("WatchNexus Admin Security Features Test Suite", "INFO")
        self.log("=" * 60, "INFO")
        
        # Initial login
        self.log("\nLogging in as admin...", "INFO")
        login_data = self.login()
        if "token" not in login_data:
            self.log(f"FATAL: Cannot login - {login_data}", "FAIL")
            return 1
        self.log(f"Logged in successfully, token: {self.token[:20]}...", "PASS")
        
        # Run test suites
        try:
            self.test_ip_allowlist()
            self.test_audit_filtering()
            self.test_2fa_lifecycle()
            self.test_error_handling()
        except Exception as e:
            self.log(f"Test suite error: {e}", "FAIL")
            import traceback
            traceback.print_exc()
        
        # Summary
        self.log("\n" + "=" * 60, "INFO")
        self.log("TEST SUMMARY", "INFO")
        self.log("=" * 60, "INFO")
        self.log(f"Total tests: {self.tests_run}", "INFO")
        self.log(f"Passed: {self.tests_passed}", "PASS")
        self.log(f"Failed: {self.tests_failed}", "FAIL" if self.tests_failed > 0 else "INFO")
        
        if self.failures:
            self.log("\nFailed tests:", "FAIL")
            for f in self.failures:
                self.log(f"  - {f}", "FAIL")
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        self.log(f"\nSuccess rate: {success_rate:.1f}%", "INFO")
        
        return 0 if self.tests_failed == 0 else 1


if __name__ == "__main__":
    tester = SecurityTester()
    sys.exit(tester.run_all_tests())
