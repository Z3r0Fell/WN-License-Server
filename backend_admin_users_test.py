"""
Admin User Management Testing - WatchNexus License Hub
Tests all admin user management features including role-based access control

Tests:
1. Admin login returns admin_role
2. GET /api/admin/me returns admin_role + is_active
3. POST /api/admin/me/change-password
4. GET /api/admin/users (both admin and support roles)
5. POST /api/admin/users (admin only, rejects duplicates, blocks support)
6. PATCH /api/admin/users/{id} (admin only, guards)
7. DELETE /api/admin/users/{id} (admin only, guards)
8. POST /api/admin/users/{id}/reset-password (admin only)
9. POST /api/admin/users/invite (admin only)
10. GET /api/admin/users/invites (admin only)
11. DELETE /api/admin/users/invites/{id} (admin only)
12. GET /api/public/invites/{token} (public, no auth)
13. POST /api/public/invites/accept (public)
14. Role gating: support role gets 403 on mutating endpoints
"""
import requests
import sys
import time
from datetime import datetime

BASE_URL = "https://watchnexus-deploy.preview.emergentagent.com"
ADMIN_EMAIL = "admin@watchnexus.app"
ADMIN_PASSWORD = "admin12345"

class AdminUsersTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.admin_token = None
        self.support_token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failed_tests = []
        self.created_users = []  # Track for cleanup
        self.created_invites = []  # Track for cleanup

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

    def headers(self, token=None):
        tok = token or self.admin_token
        return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

    # ==================== AUTHENTICATION TESTS ====================
    def test_admin_login_returns_role(self):
        """Admin login returns admin_role in user payload"""
        self.log("Logging in as admin...", "info")
        r = requests.post(f"{self.base_url}/api/admin/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
        data = r.json()
        assert "token" in data, "No token in login response"
        assert "user" in data, "No user in login response"
        
        user = data["user"]
        assert "admin_role" in user, "admin_role not in user payload"
        assert user["admin_role"] == "admin", f"Expected role 'admin', got '{user['admin_role']}'"
        
        self.admin_token = data["token"]
        self.log(f"Admin login successful, role: {user['admin_role']}", "success")

    def test_admin_me_returns_role_and_active(self):
        """GET /api/admin/me returns admin_role + is_active"""
        r = requests.get(f"{self.base_url}/api/admin/me", headers=self.headers())
        assert r.status_code == 200, f"GET /me failed: {r.status_code} {r.text}"
        
        data = r.json()
        assert "admin_role" in data, "admin_role not in /me response"
        assert "is_active" in data, "is_active not in /me response"
        assert data["admin_role"] == "admin", f"Expected role 'admin', got '{data['admin_role']}'"
        assert data["is_active"] == True, "Expected is_active=True"
        
        self.log(f"GET /me verified: role={data['admin_role']}, is_active={data['is_active']}", "success")

    def test_change_own_password(self):
        """POST /api/admin/me/change-password changes own password"""
        # First, create a test user to avoid changing the main admin password
        test_email = f"test-pwd-{int(time.time())}@example.com"
        r = requests.post(
            f"{self.base_url}/api/admin/users",
            headers=self.headers(),
            json={
                "email": test_email,
                "name": "Test Password User",
                "admin_role": "admin",
                "password": "oldpass123",
                "is_active": True
            }
        )
        assert r.status_code == 200, f"User creation failed: {r.status_code} {r.text}"
        user_data = r.json()
        self.created_users.append(user_data["id"])
        
        # Login as this user
        r = requests.post(f"{self.base_url}/api/admin/login", json={
            "email": test_email,
            "password": "oldpass123"
        })
        assert r.status_code == 200, f"Test user login failed: {r.status_code}"
        test_token = r.json()["token"]
        
        # Change password
        r = requests.post(
            f"{self.base_url}/api/admin/me/change-password",
            headers=self.headers(test_token),
            json={
                "current_password": "oldpass123",
                "new_password": "newpass456"
            }
        )
        assert r.status_code == 200, f"Password change failed: {r.status_code} {r.text}"
        
        # Verify old password doesn't work
        r = requests.post(f"{self.base_url}/api/admin/login", json={
            "email": test_email,
            "password": "oldpass123"
        })
        assert r.status_code == 401, f"Old password should not work, got {r.status_code}"
        
        # Verify new password works
        r = requests.post(f"{self.base_url}/api/admin/login", json={
            "email": test_email,
            "password": "newpass456"
        })
        assert r.status_code == 200, f"New password should work, got {r.status_code}"
        
        self.log("Password change verified", "success")

    def test_change_password_rejects_wrong_current(self):
        """POST /api/admin/me/change-password rejects wrong current_password"""
        r = requests.post(
            f"{self.base_url}/api/admin/me/change-password",
            headers=self.headers(),
            json={
                "current_password": "wrongpassword",
                "new_password": "newpass456"
            }
        )
        assert r.status_code == 400, f"Should reject wrong password with 400, got {r.status_code}"
        self.log("Wrong current password correctly rejected", "success")

    # ==================== USER MANAGEMENT TESTS ====================
    def test_list_users_as_admin(self):
        """GET /api/admin/users returns user list for admin role"""
        r = requests.get(f"{self.base_url}/api/admin/users", headers=self.headers())
        assert r.status_code == 200, f"List users failed: {r.status_code} {r.text}"
        
        users = r.json()
        assert isinstance(users, list), "Response should be a list"
        assert len(users) > 0, "Should have at least the seeded admin"
        
        # Verify seeded admin is present
        admin_user = next((u for u in users if u["email"] == ADMIN_EMAIL), None)
        assert admin_user is not None, "Seeded admin not found in list"
        assert admin_user["admin_role"] == "admin", "Seeded admin should have role 'admin'"
        
        self.log(f"List users verified: {len(users)} users", "success")

    def test_create_user_as_admin(self):
        """POST /api/admin/users creates user with role admin/support"""
        test_email = f"test-user-{int(time.time())}@example.com"
        r = requests.post(
            f"{self.base_url}/api/admin/users",
            headers=self.headers(),
            json={
                "email": test_email,
                "name": "Test User",
                "admin_role": "support",
                "password": "testpass123",
                "is_active": True
            }
        )
        assert r.status_code == 200, f"User creation failed: {r.status_code} {r.text}"
        
        user = r.json()
        assert user["email"] == test_email, "Email mismatch"
        assert user["admin_role"] == "support", "Role should be 'support'"
        assert user["is_active"] == True, "Should be active"
        assert "id" in user, "Should have ID"
        
        self.created_users.append(user["id"])
        self.log(f"User created: {test_email} with role 'support'", "success")
        return user

    def test_create_user_rejects_duplicate_email(self):
        """POST /api/admin/users rejects duplicate emails with 400"""
        # Try to create user with seeded admin email
        r = requests.post(
            f"{self.base_url}/api/admin/users",
            headers=self.headers(),
            json={
                "email": ADMIN_EMAIL,
                "name": "Duplicate",
                "admin_role": "admin",
                "password": "testpass123",
                "is_active": True
            }
        )
        assert r.status_code == 400, f"Should reject duplicate email with 400, got {r.status_code}"
        self.log("Duplicate email correctly rejected", "success")

    def test_create_user_as_support_gets_403(self):
        """POST /api/admin/users blocks support role with 403"""
        # First create a support user
        support_email = f"support-{int(time.time())}@example.com"
        r = requests.post(
            f"{self.base_url}/api/admin/users",
            headers=self.headers(),
            json={
                "email": support_email,
                "name": "Support User",
                "admin_role": "support",
                "password": "supportpass123",
                "is_active": True
            }
        )
        assert r.status_code == 200, f"Support user creation failed: {r.status_code}"
        support_user = r.json()
        self.created_users.append(support_user["id"])
        
        # Login as support user
        r = requests.post(f"{self.base_url}/api/admin/login", json={
            "email": support_email,
            "password": "supportpass123"
        })
        assert r.status_code == 200, f"Support login failed: {r.status_code}"
        self.support_token = r.json()["token"]
        
        # Try to create another user as support
        r = requests.post(
            f"{self.base_url}/api/admin/users",
            headers=self.headers(self.support_token),
            json={
                "email": f"blocked-{int(time.time())}@example.com",
                "name": "Blocked User",
                "admin_role": "admin",
                "password": "testpass123",
                "is_active": True
            }
        )
        assert r.status_code == 403, f"Support should get 403, got {r.status_code}"
        self.log("Support role correctly blocked from creating users", "success")

    def test_update_user_as_admin(self):
        """PATCH /api/admin/users/{id} updates name/role/is_active"""
        # Create a test user
        user = self.test_create_user_as_admin()
        
        # Update the user
        r = requests.patch(
            f"{self.base_url}/api/admin/users/{user['id']}",
            headers=self.headers(),
            json={
                "name": "Updated Name",
                "admin_role": "admin",
                "is_active": False
            }
        )
        assert r.status_code == 200, f"User update failed: {r.status_code} {r.text}"
        
        updated = r.json()
        assert updated["name"] == "Updated Name", "Name not updated"
        assert updated["admin_role"] == "admin", "Role not updated"
        assert updated["is_active"] == False, "is_active not updated"
        
        self.log("User update verified", "success")

    def test_update_user_prevents_self_demotion(self):
        """PATCH /api/admin/users/{id} refuses to demote self"""
        # Get current admin user ID
        r = requests.get(f"{self.base_url}/api/admin/me", headers=self.headers())
        admin_id = r.json()["id"]
        
        # Try to demote self
        r = requests.patch(
            f"{self.base_url}/api/admin/users/{admin_id}",
            headers=self.headers(),
            json={"admin_role": "support"}
        )
        assert r.status_code == 400, f"Should prevent self-demotion with 400, got {r.status_code}"
        self.log("Self-demotion correctly prevented", "success")

    def test_update_user_prevents_self_disable(self):
        """PATCH /api/admin/users/{id} refuses to disable self"""
        r = requests.get(f"{self.base_url}/api/admin/me", headers=self.headers())
        admin_id = r.json()["id"]
        
        r = requests.patch(
            f"{self.base_url}/api/admin/users/{admin_id}",
            headers=self.headers(),
            json={"is_active": False}
        )
        assert r.status_code == 400, f"Should prevent self-disable with 400, got {r.status_code}"
        self.log("Self-disable correctly prevented", "success")

    def test_delete_user_as_admin(self):
        """DELETE /api/admin/users/{id} deletes user"""
        # Create a test user
        test_email = f"delete-me-{int(time.time())}@example.com"
        r = requests.post(
            f"{self.base_url}/api/admin/users",
            headers=self.headers(),
            json={
                "email": test_email,
                "name": "Delete Me",
                "admin_role": "support",
                "password": "testpass123",
                "is_active": True
            }
        )
        assert r.status_code == 200, f"User creation failed: {r.status_code}"
        user_id = r.json()["id"]
        
        # Delete the user
        r = requests.delete(
            f"{self.base_url}/api/admin/users/{user_id}",
            headers=self.headers()
        )
        assert r.status_code == 200, f"User deletion failed: {r.status_code} {r.text}"
        
        # Verify user is gone
        r = requests.get(f"{self.base_url}/api/admin/users", headers=self.headers())
        users = r.json()
        deleted_user = next((u for u in users if u["id"] == user_id), None)
        assert deleted_user is None, "User should be deleted"
        
        self.log("User deletion verified", "success")

    def test_delete_user_prevents_self_delete(self):
        """DELETE /api/admin/users/{id} refuses to delete self"""
        r = requests.get(f"{self.base_url}/api/admin/me", headers=self.headers())
        admin_id = r.json()["id"]
        
        r = requests.delete(
            f"{self.base_url}/api/admin/users/{admin_id}",
            headers=self.headers()
        )
        assert r.status_code == 400, f"Should prevent self-delete with 400, got {r.status_code}"
        self.log("Self-delete correctly prevented", "success")

    def test_reset_password_as_admin(self):
        """POST /api/admin/users/{id}/reset-password sets new password"""
        # Create a test user
        test_email = f"reset-pwd-{int(time.time())}@example.com"
        r = requests.post(
            f"{self.base_url}/api/admin/users",
            headers=self.headers(),
            json={
                "email": test_email,
                "name": "Reset Password User",
                "admin_role": "support",
                "password": "oldpass123",
                "is_active": True
            }
        )
        assert r.status_code == 200, f"User creation failed: {r.status_code}"
        user_id = r.json()["id"]
        self.created_users.append(user_id)
        
        # Reset password
        r = requests.post(
            f"{self.base_url}/api/admin/users/{user_id}/reset-password",
            headers=self.headers(),
            json={"new_password": "resetpass456"}
        )
        assert r.status_code == 200, f"Password reset failed: {r.status_code} {r.text}"
        
        # Verify old password doesn't work
        r = requests.post(f"{self.base_url}/api/admin/login", json={
            "email": test_email,
            "password": "oldpass123"
        })
        assert r.status_code == 401, f"Old password should not work, got {r.status_code}"
        
        # Verify new password works
        r = requests.post(f"{self.base_url}/api/admin/login", json={
            "email": test_email,
            "password": "resetpass456"
        })
        assert r.status_code == 200, f"New password should work, got {r.status_code}"
        
        self.log("Password reset verified", "success")

    # ==================== INVITE FLOW TESTS ====================
    def test_invite_user_as_admin(self):
        """POST /api/admin/users/invite creates invite token"""
        test_email = f"invite-{int(time.time())}@example.com"
        r = requests.post(
            f"{self.base_url}/api/admin/users/invite",
            headers=self.headers(),
            json={
                "email": test_email,
                "name": "Invited User",
                "admin_role": "support"
            }
        )
        assert r.status_code == 200, f"Invite creation failed: {r.status_code} {r.text}"
        
        data = r.json()
        assert data["ok"] == True, "Response should have ok=True"
        assert "invite_id" in data, "Should have invite_id"
        assert "invite_url" in data, "Should have invite_url"
        assert "email_sent" in data, "Should have email_sent flag"
        assert data["email"] == test_email, "Email mismatch"
        
        self.created_invites.append(data["invite_id"])
        self.log(f"Invite created: {test_email}, email_sent={data['email_sent']}", "success")
        return data

    def test_list_invites_as_admin(self):
        """GET /api/admin/users/invites lists invites"""
        # Create an invite first
        invite = self.test_invite_user_as_admin()
        
        # List invites
        r = requests.get(f"{self.base_url}/api/admin/users/invites", headers=self.headers())
        assert r.status_code == 200, f"List invites failed: {r.status_code} {r.text}"
        
        invites = r.json()
        assert isinstance(invites, list), "Response should be a list"
        
        # Find our invite
        our_invite = next((i for i in invites if i["id"] == invite["invite_id"]), None)
        assert our_invite is not None, "Our invite not found in list"
        assert our_invite["status"] == "pending", "Invite should be pending"
        
        self.log(f"List invites verified: {len(invites)} invites", "success")

    def test_revoke_invite_as_admin(self):
        """DELETE /api/admin/users/invites/{id} revokes invite"""
        # Create an invite
        invite = self.test_invite_user_as_admin()
        
        # Revoke it
        r = requests.delete(
            f"{self.base_url}/api/admin/users/invites/{invite['invite_id']}",
            headers=self.headers()
        )
        assert r.status_code == 200, f"Revoke invite failed: {r.status_code} {r.text}"
        
        # Verify it's revoked
        r = requests.get(f"{self.base_url}/api/admin/users/invites", headers=self.headers())
        invites = r.json()
        revoked_invite = next((i for i in invites if i["id"] == invite["invite_id"]), None)
        assert revoked_invite is not None, "Invite should still exist"
        assert revoked_invite["status"] == "revoked", "Invite should be revoked"
        
        self.log("Invite revocation verified", "success")

    def test_preview_invite_public(self):
        """GET /api/public/invites/{token} returns invite preview without auth"""
        # Create an invite
        invite = self.test_invite_user_as_admin()
        
        # Extract token from invite_url
        token = invite["invite_url"].split("token=")[1]
        
        # Preview without auth
        r = requests.get(f"{self.base_url}/api/public/invites/{token}")
        assert r.status_code == 200, f"Preview invite failed: {r.status_code} {r.text}"
        
        data = r.json()
        assert data["email"] == invite["email"], "Email mismatch"
        assert "admin_role" in data, "Should have admin_role"
        assert "expires_at" in data, "Should have expires_at"
        
        self.log("Invite preview verified (public route)", "success")
        return token

    def test_preview_invite_invalid_token(self):
        """GET /api/public/invites/{token} returns 404 for invalid token"""
        r = requests.get(f"{self.base_url}/api/public/invites/invalid-token-12345")
        assert r.status_code == 404, f"Should return 404 for invalid token, got {r.status_code}"
        self.log("Invalid token correctly returns 404", "success")

    def test_accept_invite_public(self):
        """POST /api/public/invites/accept creates user and returns token"""
        # Create an invite
        test_email = f"accept-invite-{int(time.time())}@example.com"
        r = requests.post(
            f"{self.base_url}/api/admin/users/invite",
            headers=self.headers(),
            json={
                "email": test_email,
                "name": "Accept Invite User",
                "admin_role": "support"
            }
        )
        assert r.status_code == 200, f"Invite creation failed: {r.status_code}"
        invite = r.json()
        token = invite["invite_url"].split("token=")[1]
        self.created_invites.append(invite["invite_id"])
        
        # Accept the invite
        r = requests.post(
            f"{self.base_url}/api/public/invites/accept",
            json={
                "token": token,
                "password": "acceptpass123"
            }
        )
        assert r.status_code == 200, f"Accept invite failed: {r.status_code} {r.text}"
        
        data = r.json()
        assert "token" in data, "Should have session token"
        assert "user" in data, "Should have user object"
        assert data["user"]["email"] == test_email, "Email mismatch"
        assert data["user"]["admin_role"] == "support", "Role should be 'support'"
        
        self.created_users.append(data["user"]["id"])
        
        # Verify can login with new password
        r = requests.post(f"{self.base_url}/api/admin/login", json={
            "email": test_email,
            "password": "acceptpass123"
        })
        assert r.status_code == 200, f"Login with accepted invite failed: {r.status_code}"
        
        self.log("Accept invite verified (public route)", "success")

    def test_accept_invite_rejects_existing_email(self):
        """POST /api/public/invites/accept returns 400 if email already exists"""
        # Create an invite with existing email
        r = requests.post(
            f"{self.base_url}/api/admin/users/invite",
            headers=self.headers(),
            json={
                "email": ADMIN_EMAIL,  # Use existing admin email
                "name": "Duplicate",
                "admin_role": "admin"
            }
        )
        assert r.status_code == 200, f"Invite creation failed: {r.status_code}"
        invite = r.json()
        token = invite["invite_url"].split("token=")[1]
        self.created_invites.append(invite["invite_id"])
        
        # Try to accept
        r = requests.post(
            f"{self.base_url}/api/public/invites/accept",
            json={
                "token": token,
                "password": "testpass123"
            }
        )
        assert r.status_code == 400, f"Should reject existing email with 400, got {r.status_code}"
        self.log("Accept invite correctly rejects existing email", "success")

    # ==================== ROLE GATING TESTS ====================
    def test_support_role_can_list_users(self):
        """Support role can GET /api/admin/users"""
        if not self.support_token:
            # Create support user if not exists
            self.test_create_user_as_support_gets_403()
        
        r = requests.get(f"{self.base_url}/api/admin/users", headers=self.headers(self.support_token))
        assert r.status_code == 200, f"Support should be able to list users, got {r.status_code}"
        self.log("Support role can list users", "success")

    def test_support_role_blocked_from_products_create(self):
        """Support role gets 403 on POST /api/admin/products"""
        if not self.support_token:
            self.test_create_user_as_support_gets_403()
        
        r = requests.post(
            f"{self.base_url}/api/admin/products",
            headers=self.headers(self.support_token),
            json={
                "name": "Test Product",
                "slug": f"test-{int(time.time())}",
                "signing_method": "hmac",
                "fingerprint_mode": "both",
                "max_seats_default": 1
            }
        )
        assert r.status_code == 403, f"Support should get 403 on products create, got {r.status_code}"
        self.log("Support role blocked from products create", "success")

    def test_support_role_can_read_products(self):
        """Support role can GET /api/admin/products"""
        if not self.support_token:
            self.test_create_user_as_support_gets_403()
        
        r = requests.get(f"{self.base_url}/api/admin/products", headers=self.headers(self.support_token))
        assert r.status_code == 200, f"Support should be able to read products, got {r.status_code}"
        self.log("Support role can read products", "success")

    def test_support_role_blocked_from_licenses_create(self):
        """Support role gets 403 on POST /api/admin/licenses"""
        if not self.support_token:
            self.test_create_user_as_support_gets_403()
        
        r = requests.post(
            f"{self.base_url}/api/admin/licenses",
            headers=self.headers(self.support_token),
            json={
                "product_id": "test-id",
                "plan": "pro",
                "seats": 1,
                "customer_email": "test@example.com"
            }
        )
        assert r.status_code == 403, f"Support should get 403 on licenses create, got {r.status_code}"
        self.log("Support role blocked from licenses create", "success")

    def test_support_role_blocked_from_api_keys_create(self):
        """Support role gets 403 on POST /api/admin/api-keys"""
        if not self.support_token:
            self.test_create_user_as_support_gets_403()
        
        r = requests.post(
            f"{self.base_url}/api/admin/api-keys",
            headers=self.headers(self.support_token),
            json={
                "name": "Test Key",
                "scopes": ["activate"],
                "allowed_ips": []
            }
        )
        assert r.status_code == 403, f"Support should get 403 on api-keys create, got {r.status_code}"
        self.log("Support role blocked from api-keys create", "success")

    def test_support_role_blocked_from_settings_update(self):
        """Support role gets 403 on PUT /api/admin/settings"""
        if not self.support_token:
            self.test_create_user_as_support_gets_403()
        
        r = requests.put(
            f"{self.base_url}/api/admin/settings",
            headers=self.headers(self.support_token),
            json={"values": {"EMAIL_FROM": "test@example.com"}}
        )
        assert r.status_code == 403, f"Support should get 403 on settings update, got {r.status_code}"
        self.log("Support role blocked from settings update", "success")

    # ==================== CLEANUP ====================
    def cleanup(self):
        """Clean up created test users and invites"""
        self.log("\nCleaning up test data...", "info")
        
        # Delete created users
        for user_id in self.created_users:
            try:
                r = requests.delete(
                    f"{self.base_url}/api/admin/users/{user_id}",
                    headers=self.headers()
                )
                if r.status_code == 200:
                    self.log(f"Deleted user {user_id}", "info")
            except Exception as e:
                self.log(f"Failed to delete user {user_id}: {e}", "warn")
        
        # Revoke created invites
        for invite_id in self.created_invites:
            try:
                r = requests.delete(
                    f"{self.base_url}/api/admin/users/invites/{invite_id}",
                    headers=self.headers()
                )
                if r.status_code == 200:
                    self.log(f"Revoked invite {invite_id}", "info")
            except Exception as e:
                self.log(f"Failed to revoke invite {invite_id}: {e}", "warn")

    # ==================== SUMMARY ====================
    def print_summary(self):
        print("\n" + "="*60)
        print("ADMIN USER MANAGEMENT TEST SUMMARY")
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
    tester = AdminUsersTester()
    
    # Authentication tests
    tester.test("Admin login returns admin_role", tester.test_admin_login_returns_role)
    tester.test("GET /api/admin/me returns role + is_active", tester.test_admin_me_returns_role_and_active)
    tester.test("Change own password", tester.test_change_own_password)
    tester.test("Change password rejects wrong current", tester.test_change_password_rejects_wrong_current)
    
    # User management tests
    tester.test("List users as admin", tester.test_list_users_as_admin)
    tester.test("Create user as admin", tester.test_create_user_as_admin)
    tester.test("Create user rejects duplicate email", tester.test_create_user_rejects_duplicate_email)
    tester.test("Create user as support gets 403", tester.test_create_user_as_support_gets_403)
    tester.test("Update user as admin", tester.test_update_user_as_admin)
    tester.test("Update user prevents self-demotion", tester.test_update_user_prevents_self_demotion)
    tester.test("Update user prevents self-disable", tester.test_update_user_prevents_self_disable)
    tester.test("Delete user as admin", tester.test_delete_user_as_admin)
    tester.test("Delete user prevents self-delete", tester.test_delete_user_prevents_self_delete)
    tester.test("Reset password as admin", tester.test_reset_password_as_admin)
    
    # Invite flow tests
    tester.test("Invite user as admin", tester.test_invite_user_as_admin)
    tester.test("List invites as admin", tester.test_list_invites_as_admin)
    tester.test("Revoke invite as admin", tester.test_revoke_invite_as_admin)
    tester.test("Preview invite (public)", tester.test_preview_invite_public)
    tester.test("Preview invite invalid token", tester.test_preview_invite_invalid_token)
    tester.test("Accept invite (public)", tester.test_accept_invite_public)
    tester.test("Accept invite rejects existing email", tester.test_accept_invite_rejects_existing_email)
    
    # Role gating tests
    tester.test("Support role can list users", tester.test_support_role_can_list_users)
    tester.test("Support role blocked from products create", tester.test_support_role_blocked_from_products_create)
    tester.test("Support role can read products", tester.test_support_role_can_read_products)
    tester.test("Support role blocked from licenses create", tester.test_support_role_blocked_from_licenses_create)
    tester.test("Support role blocked from api-keys create", tester.test_support_role_blocked_from_api_keys_create)
    tester.test("Support role blocked from settings update", tester.test_support_role_blocked_from_settings_update)
    
    # Cleanup
    tester.cleanup()
    
    return tester.print_summary()

if __name__ == "__main__":
    sys.exit(main())
