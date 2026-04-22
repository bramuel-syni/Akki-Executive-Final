"""
AKKI Sandbox G1 Backend Tests
Tests: Auth, Multi-tenancy, Invitations, Audit Log, Export, MFA, LLM Scaffolding
"""
import pytest
import requests
import os
import time
import uuid
import pyotp

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
ADMIN_EMAIL = "admin@akki.ai"
ADMIN_PASSWORD = "AkkiAdmin2026!"

class TestHealthEndpoints:
    """Test basic health and root endpoints"""
    
    def test_root_endpoint(self):
        """GET /api/ returns ok"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "app" in data
        print(f"✓ Root endpoint: {data}")
    
    def test_health_endpoint(self):
        """GET /api/health returns ok with db status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["db"] == "up"
        print(f"✓ Health endpoint: {data}")


class TestAuthRegistration:
    """Test user registration flow"""
    
    def test_register_new_user(self):
        """POST /api/auth/register creates user + auto-provisions tenant"""
        unique_id = str(uuid.uuid4())[:8]
        email = f"test.exec.{unique_id}@akki.ai"
        
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": email,
                "password": "TestExec2026!",
                "name": "Test Executive",
                "tenant_name": "Test Bank"
            }
        )
        assert response.status_code == 200, f"Registration failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "user" in data
        assert "tenants" in data
        assert "access_token" in data
        assert len(data["tenants"]) >= 1
        
        # Verify user data
        assert data["user"]["email"] == email.lower()
        assert data["user"]["name"] == "Test Executive"
        assert "id" in data["user"]
        
        # Verify tenant was created
        assert data["tenants"][0]["name"] == "Test Bank"
        assert data["tenants"][0]["owner_user_id"] == data["user"]["id"]
        
        # Verify cookies are set (httpOnly)
        cookies = response.cookies
        assert "access_token" in cookies or "access_token" in response.headers.get("Set-Cookie", "")
        
        # Verify no password_hash or _id leakage
        assert "password_hash" not in str(data)
        assert "_id" not in str(data)
        
        print(f"✓ Registration successful: {email}")
        return data
    
    def test_register_duplicate_email(self):
        """Registration with existing email returns 409"""
        # First registration
        unique_id = str(uuid.uuid4())[:8]
        email = f"dup.test.{unique_id}@akki.ai"
        
        requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": email, "password": "TestPass2026!", "name": "Dup Test"}
        )
        
        # Second registration with same email
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": email, "password": "TestPass2026!", "name": "Dup Test 2"}
        )
        assert response.status_code == 409
        print(f"✓ Duplicate email rejected: {email}")


class TestAuthLogin:
    """Test login flow including brute force protection"""
    
    def test_admin_login(self):
        """POST /api/auth/login with admin credentials"""
        session = requests.Session()
        response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        
        assert "user" in data
        assert "tenants" in data
        assert "access_token" in data
        assert data["user"]["email"] == ADMIN_EMAIL
        
        # Verify default tenant "Syni.ai HQ" exists
        tenant_names = [t["name"] for t in data["tenants"]]
        assert "Syni.ai HQ" in tenant_names, f"Expected 'Syni.ai HQ' in {tenant_names}"
        
        print(f"✓ Admin login successful, tenants: {tenant_names}")
        return session, data
    
    def test_login_invalid_credentials(self):
        """POST /api/auth/login with bad credentials returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "wrong@akki.ai", "password": "wrongpass"}
        )
        assert response.status_code == 401
        print("✓ Invalid credentials rejected")
    
    def test_brute_force_lockout(self):
        """5 bad attempts from same ip+email → 6th returns 429"""
        unique_email = f"bruteforce.{uuid.uuid4().hex[:8]}@akki.ai"
        
        # Make 5 bad attempts
        for i in range(5):
            response = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": unique_email, "password": "wrongpass"}
            )
            assert response.status_code == 401, f"Attempt {i+1} should be 401"
        
        # 6th attempt should be locked out
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": unique_email, "password": "wrongpass"}
        )
        assert response.status_code == 429, f"Expected 429 lockout, got {response.status_code}"
        print("✓ Brute force lockout working (429 after 5 attempts)")


class TestAuthMe:
    """Test /auth/me endpoint"""
    
    def test_me_authenticated(self):
        """GET /api/auth/me returns user + tenants with my_role"""
        session = requests.Session()
        login_resp = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert login_resp.status_code == 200
        
        me_resp = session.get(f"{BASE_URL}/api/auth/me")
        assert me_resp.status_code == 200
        data = me_resp.json()
        
        assert "user" in data
        assert "tenants" in data
        assert data["user"]["email"] == ADMIN_EMAIL
        
        # Verify my_role decoration
        for tenant in data["tenants"]:
            assert "my_role" in tenant
        
        print(f"✓ /auth/me returns user with {len(data['tenants'])} tenants")
    
    def test_me_unauthenticated(self):
        """GET /api/auth/me without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401
        print("✓ /auth/me returns 401 for unauthenticated")


class TestAuthLogout:
    """Test logout flow"""
    
    def test_logout_clears_cookies(self):
        """POST /api/auth/logout clears cookies"""
        session = requests.Session()
        session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        
        logout_resp = session.post(f"{BASE_URL}/api/auth/logout")
        assert logout_resp.status_code == 200
        assert logout_resp.json().get("ok") == True
        
        # Verify session is invalidated
        me_resp = session.get(f"{BASE_URL}/api/auth/me")
        assert me_resp.status_code == 401
        print("✓ Logout clears session")


class TestAuthRefresh:
    """Test token refresh"""
    
    def test_refresh_token(self):
        """POST /api/auth/refresh uses refresh_token cookie"""
        session = requests.Session()
        session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        
        refresh_resp = session.post(f"{BASE_URL}/api/auth/refresh")
        assert refresh_resp.status_code == 200
        assert refresh_resp.json().get("ok") == True
        print("✓ Token refresh successful")


class TestTenantCRUD:
    """Test tenant creation, rename, archive"""
    
    @pytest.fixture
    def auth_session(self):
        """Get authenticated session"""
        session = requests.Session()
        resp = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        data = resp.json()
        return session, data
    
    def test_create_tenant(self, auth_session):
        """POST /api/tenants creates additional tenant"""
        session, login_data = auth_session
        
        response = session.post(
            f"{BASE_URL}/api/tenants",
            json={"name": f"Test Tenant {uuid.uuid4().hex[:6]}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert "name" in data
        assert data["owner_user_id"] == login_data["user"]["id"]
        print(f"✓ Created tenant: {data['name']}")
        return data
    
    def test_rename_tenant_owner(self, auth_session):
        """PATCH /api/tenants/{id} renames tenant (owner only)"""
        session, _ = auth_session
        
        # Create a tenant first
        create_resp = session.post(
            f"{BASE_URL}/api/tenants",
            json={"name": f"Rename Test {uuid.uuid4().hex[:6]}"}
        )
        tenant = create_resp.json()
        
        # Rename it
        new_name = f"Renamed {uuid.uuid4().hex[:6]}"
        rename_resp = session.patch(
            f"{BASE_URL}/api/tenants/{tenant['id']}",
            json={"name": new_name}
        )
        assert rename_resp.status_code == 200
        assert rename_resp.json()["name"] == new_name
        print(f"✓ Renamed tenant to: {new_name}")
    
    def test_archive_tenant(self, auth_session):
        """DELETE /api/tenants/{id} archives tenant (owner only)"""
        session, _ = auth_session
        
        # Create a tenant first
        create_resp = session.post(
            f"{BASE_URL}/api/tenants",
            json={"name": f"Archive Test {uuid.uuid4().hex[:6]}"}
        )
        tenant = create_resp.json()
        
        # Archive it
        archive_resp = session.delete(f"{BASE_URL}/api/tenants/{tenant['id']}")
        assert archive_resp.status_code == 200
        assert archive_resp.json()["status"] == "archived"
        print(f"✓ Archived tenant: {tenant['id']}")


class TestTenantMembership:
    """Test tenant membership isolation"""
    
    def test_non_member_access_denied(self):
        """Non-member calling tenant endpoint returns 403"""
        # Create two separate users
        user1_email = f"user1.{uuid.uuid4().hex[:6]}@akki.ai"
        user2_email = f"user2.{uuid.uuid4().hex[:6]}@akki.ai"
        
        # Register user1
        session1 = requests.Session()
        resp1 = session1.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": user1_email, "password": "TestPass2026!", "name": "User One"}
        )
        user1_tenant_id = resp1.json()["tenants"][0]["id"]
        
        # Register user2
        session2 = requests.Session()
        session2.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": user2_email, "password": "TestPass2026!", "name": "User Two"}
        )
        
        # User2 tries to access User1's tenant
        response = session2.get(f"{BASE_URL}/api/tenants/{user1_tenant_id}/members")
        assert response.status_code == 403
        print("✓ Non-member access denied (403)")
    
    def test_unknown_tenant_returns_404(self):
        """Unknown tenant_id returns 404"""
        session = requests.Session()
        session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        
        fake_tenant_id = str(uuid.uuid4())
        response = session.get(f"{BASE_URL}/api/tenants/{fake_tenant_id}/members")
        assert response.status_code == 404
        print("✓ Unknown tenant returns 404")


class TestInvitations:
    """Test invitation flow"""
    
    @pytest.fixture
    def owner_session(self):
        """Get authenticated owner session with tenant"""
        session = requests.Session()
        resp = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        data = resp.json()
        tenant_id = data["tenants"][0]["id"]
        return session, tenant_id
    
    def test_create_invitation(self, owner_session):
        """POST /api/tenants/{id}/invitations creates invitation"""
        session, tenant_id = owner_session
        invite_email = f"invite.{uuid.uuid4().hex[:6]}@example.com"
        
        response = session.post(
            f"{BASE_URL}/api/tenants/{tenant_id}/invitations",
            json={"email": invite_email, "role": "collaborator"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["email"] == invite_email.lower()
        assert data["role"] == "collaborator"
        assert data["status"] == "pending"
        assert "accept_url" in data
        assert "expires_at" in data
        assert "id" in data
        
        print(f"✓ Created invitation: {data['accept_url']}")
        return data
    
    def test_duplicate_invitation_returns_409(self, owner_session):
        """Duplicate pending invite for same email returns 409"""
        session, tenant_id = owner_session
        invite_email = f"dup.invite.{uuid.uuid4().hex[:6]}@example.com"
        
        # First invitation
        session.post(
            f"{BASE_URL}/api/tenants/{tenant_id}/invitations",
            json={"email": invite_email, "role": "collaborator"}
        )
        
        # Duplicate invitation
        response = session.post(
            f"{BASE_URL}/api/tenants/{tenant_id}/invitations",
            json={"email": invite_email, "role": "collaborator"}
        )
        assert response.status_code == 409
        print("✓ Duplicate invitation rejected (409)")
    
    def test_invite_existing_member_returns_409(self, owner_session):
        """Inviting an existing member returns 409"""
        session, tenant_id = owner_session
        
        # Try to invite the admin (who is already a member)
        response = session.post(
            f"{BASE_URL}/api/tenants/{tenant_id}/invitations",
            json={"email": ADMIN_EMAIL, "role": "collaborator"}
        )
        assert response.status_code == 409
        print("✓ Inviting existing member rejected (409)")
    
    def test_list_invitations(self, owner_session):
        """GET /api/tenants/{id}/invitations lists pending"""
        session, tenant_id = owner_session
        
        response = session.get(f"{BASE_URL}/api/tenants/{tenant_id}/invitations")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        print(f"✓ Listed {len(response.json())} pending invitations")
    
    def test_revoke_invitation(self, owner_session):
        """DELETE /api/tenants/{id}/invitations/{invitation_id} revokes"""
        session, tenant_id = owner_session
        invite_email = f"revoke.{uuid.uuid4().hex[:6]}@example.com"
        
        # Create invitation
        create_resp = session.post(
            f"{BASE_URL}/api/tenants/{tenant_id}/invitations",
            json={"email": invite_email, "role": "collaborator"}
        )
        invite_id = create_resp.json()["id"]
        
        # Revoke it
        revoke_resp = session.delete(
            f"{BASE_URL}/api/tenants/{tenant_id}/invitations/{invite_id}"
        )
        assert revoke_resp.status_code == 200
        assert revoke_resp.json()["ok"] == True
        print(f"✓ Revoked invitation: {invite_id}")


class TestInvitationToken:
    """Test invitation token preview and accept"""
    
    def test_preview_invitation_by_token(self):
        """GET /api/invitations/by-token/{token} returns preview"""
        # Login as admin and create invitation
        session = requests.Session()
        login_resp = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        tenant_id = login_resp.json()["tenants"][0]["id"]
        
        invite_email = f"preview.{uuid.uuid4().hex[:6]}@example.com"
        create_resp = session.post(
            f"{BASE_URL}/api/tenants/{tenant_id}/invitations",
            json={"email": invite_email, "role": "collaborator"}
        )
        accept_url = create_resp.json()["accept_url"]
        token = accept_url.split("/invite/")[-1]
        
        # Preview without auth
        preview_resp = requests.get(f"{BASE_URL}/api/invitations/by-token/{token}")
        assert preview_resp.status_code == 200
        data = preview_resp.json()
        
        assert data["email"] == invite_email.lower()
        assert data["role"] == "collaborator"
        assert "tenant_name" in data
        print(f"✓ Preview invitation: {data}")
    
    def test_preview_unknown_token_returns_404(self):
        """Unknown/revoked token returns 404"""
        response = requests.get(f"{BASE_URL}/api/invitations/by-token/invalid-token-xyz")
        assert response.status_code == 404
        print("✓ Unknown token returns 404")
    
    def test_accept_invitation(self):
        """POST /api/invitations/{token}/accept creates membership"""
        # Create invitation as admin
        admin_session = requests.Session()
        login_resp = admin_session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        tenant_id = login_resp.json()["tenants"][0]["id"]
        
        # Create new user email for invitation
        invite_email = f"accept.{uuid.uuid4().hex[:6]}@akki.ai"
        create_resp = admin_session.post(
            f"{BASE_URL}/api/tenants/{tenant_id}/invitations",
            json={"email": invite_email, "role": "collaborator"}
        )
        accept_url = create_resp.json()["accept_url"]
        token = accept_url.split("/invite/")[-1]
        
        # Register the invited user
        invitee_session = requests.Session()
        invitee_session.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": invite_email, "password": "TestPass2026!", "name": "Invitee"}
        )
        
        # Accept invitation
        accept_resp = invitee_session.post(f"{BASE_URL}/api/invitations/{token}/accept")
        assert accept_resp.status_code == 200
        data = accept_resp.json()
        
        assert data["ok"] == True
        assert "tenant" in data
        print(f"✓ Accepted invitation, joined tenant: {data['tenant']['name']}")
    
    def test_accept_wrong_email_returns_403(self):
        """Accept with mismatched email returns 403"""
        # Create invitation as admin
        admin_session = requests.Session()
        login_resp = admin_session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        tenant_id = login_resp.json()["tenants"][0]["id"]
        
        invite_email = f"wrong.{uuid.uuid4().hex[:6]}@example.com"
        create_resp = admin_session.post(
            f"{BASE_URL}/api/tenants/{tenant_id}/invitations",
            json={"email": invite_email, "role": "collaborator"}
        )
        token = create_resp.json()["accept_url"].split("/invite/")[-1]
        
        # Try to accept with different user
        other_session = requests.Session()
        other_session.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": f"other.{uuid.uuid4().hex[:6]}@akki.ai", "password": "TestPass2026!", "name": "Other"}
        )
        
        accept_resp = other_session.post(f"{BASE_URL}/api/invitations/{token}/accept")
        assert accept_resp.status_code == 403
        print("✓ Accept with wrong email returns 403")


class TestMembers:
    """Test member listing and removal"""
    
    def test_list_members(self):
        """GET /api/tenants/{id}/members lists members"""
        session = requests.Session()
        login_resp = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        tenant_id = login_resp.json()["tenants"][0]["id"]
        
        response = session.get(f"{BASE_URL}/api/tenants/{tenant_id}/members")
        assert response.status_code == 200
        members = response.json()
        
        assert isinstance(members, list)
        assert len(members) >= 1
        
        # Verify member structure
        for m in members:
            assert "user_id" in m
            assert "email" in m
            assert "role" in m
            assert "joined_at" in m
        
        print(f"✓ Listed {len(members)} members")
    
    def test_remove_member(self):
        """DELETE /api/tenants/{id}/members/{user_id} removes member"""
        # Create owner and collaborator
        owner_email = f"owner.{uuid.uuid4().hex[:6]}@akki.ai"
        collab_email = f"collab.{uuid.uuid4().hex[:6]}@akki.ai"
        
        # Register owner
        owner_session = requests.Session()
        owner_resp = owner_session.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": owner_email, "password": "TestPass2026!", "name": "Owner"}
        )
        tenant_id = owner_resp.json()["tenants"][0]["id"]
        
        # Create invitation for collaborator
        invite_resp = owner_session.post(
            f"{BASE_URL}/api/tenants/{tenant_id}/invitations",
            json={"email": collab_email, "role": "collaborator"}
        )
        token = invite_resp.json()["accept_url"].split("/invite/")[-1]
        
        # Register and accept as collaborator
        collab_session = requests.Session()
        collab_resp = collab_session.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": collab_email, "password": "TestPass2026!", "name": "Collab"}
        )
        collab_user_id = collab_resp.json()["user"]["id"]
        collab_session.post(f"{BASE_URL}/api/invitations/{token}/accept")
        
        # Owner removes collaborator
        remove_resp = owner_session.delete(
            f"{BASE_URL}/api/tenants/{tenant_id}/members/{collab_user_id}"
        )
        assert remove_resp.status_code == 200
        assert remove_resp.json()["ok"] == True
        print("✓ Removed member successfully")
    
    def test_cannot_remove_owner(self):
        """Cannot remove the tenant owner → 400"""
        session = requests.Session()
        login_resp = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        data = login_resp.json()
        tenant_id = data["tenants"][0]["id"]
        owner_user_id = data["user"]["id"]
        
        response = session.delete(
            f"{BASE_URL}/api/tenants/{tenant_id}/members/{owner_user_id}"
        )
        assert response.status_code == 400
        print("✓ Cannot remove owner (400)")


class TestAuditLog:
    """Test audit log"""
    
    def test_audit_log_entries(self):
        """GET /api/tenants/{id}/audit-log returns entries with actor_email"""
        session = requests.Session()
        login_resp = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        tenant_id = login_resp.json()["tenants"][0]["id"]
        
        response = session.get(f"{BASE_URL}/api/tenants/{tenant_id}/audit-log")
        assert response.status_code == 200
        entries = response.json()
        
        assert isinstance(entries, list)
        
        # Verify entry structure
        if entries:
            entry = entries[0]
            assert "action" in entry
            assert "created_at" in entry
            assert "actor_email" in entry
            
            # Check for expected action types
            actions = [e["action"] for e in entries]
            print(f"✓ Audit log has {len(entries)} entries, actions: {set(actions)}")
        else:
            print("✓ Audit log is empty (new tenant)")


class TestExport:
    """Test tenant data export"""
    
    def test_export_tenant_json(self):
        """POST /api/tenants/{id}/export returns JSON download"""
        session = requests.Session()
        login_resp = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        tenant_id = login_resp.json()["tenants"][0]["id"]
        
        response = session.post(f"{BASE_URL}/api/tenants/{tenant_id}/export")
        assert response.status_code == 200
        
        # Verify content type
        assert "application/json" in response.headers.get("Content-Type", "")
        
        # Verify content disposition
        content_disp = response.headers.get("Content-Disposition", "")
        assert "attachment" in content_disp
        assert "akki-export" in content_disp
        
        # Verify JSON structure
        data = response.json()
        assert "export_version" in data
        assert "exported_at" in data
        assert "tenant" in data
        assert "users" in data
        assert "memberships" in data
        assert "invitations" in data
        assert "audit_log" in data
        
        # Verify no password_hash or mfa_secret in users
        for user in data.get("users", []):
            assert "password_hash" not in user
            assert "mfa_secret" not in user
        
        print(f"✓ Export successful, keys: {list(data.keys())}")


class TestMFA:
    """Test MFA (TOTP) setup and verification"""
    
    def test_mfa_setup(self):
        """POST /api/auth/mfa/setup returns QR and secret"""
        session = requests.Session()
        session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        
        response = session.post(f"{BASE_URL}/api/auth/mfa/setup")
        assert response.status_code == 200
        data = response.json()
        
        assert "otpauth_url" in data
        assert "qr_data_url" in data
        assert "secret" in data
        assert data["qr_data_url"].startswith("data:image/png;base64,")
        
        print(f"✓ MFA setup returned secret: {data['secret'][:8]}...")
        return data
    
    def test_mfa_verify_invalid_code(self):
        """POST /api/auth/mfa/verify with invalid code returns 400"""
        session = requests.Session()
        session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        
        # Setup MFA first
        session.post(f"{BASE_URL}/api/auth/mfa/setup")
        
        # Try invalid code
        response = session.post(
            f"{BASE_URL}/api/auth/mfa/verify",
            json={"code": "000000"}
        )
        assert response.status_code == 400
        print("✓ Invalid MFA code rejected (400)")
    
    def test_mfa_full_flow(self):
        """Full MFA setup → verify → disable flow"""
        # Create a fresh user for this test
        unique_email = f"mfa.test.{uuid.uuid4().hex[:6]}@akki.ai"
        session = requests.Session()
        session.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": unique_email, "password": "TestPass2026!", "name": "MFA Test"}
        )
        
        # Setup MFA
        setup_resp = session.post(f"{BASE_URL}/api/auth/mfa/setup")
        secret = setup_resp.json()["secret"]
        
        # Generate valid TOTP code
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()
        
        # Verify with valid code
        verify_resp = session.post(
            f"{BASE_URL}/api/auth/mfa/verify",
            json={"code": valid_code}
        )
        assert verify_resp.status_code == 200
        assert verify_resp.json()["mfa_enabled"] == True
        print("✓ MFA verified and enabled")
        
        # Disable MFA
        disable_resp = session.post(f"{BASE_URL}/api/auth/mfa/disable")
        assert disable_resp.status_code == 200
        assert disable_resp.json()["mfa_enabled"] == False
        print("✓ MFA disabled")


class TestLLMProbe:
    """Test LLM scaffolding probe"""
    
    def test_llm_probe_mock(self):
        """POST /api/tenants/{id}/llm/probe returns mock response"""
        session = requests.Session()
        login_resp = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        tenant_id = login_resp.json()["tenants"][0]["id"]
        
        response = session.post(
            f"{BASE_URL}/api/tenants/{tenant_id}/llm/probe",
            json={"module": "signals", "query": "What are the key risks?"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "layers" in data
        assert "response" in data
        assert "mode" in data
        assert "sources" in data
        
        # Verify layers
        layers = data["layers"]
        assert "layer_1_system" in layers
        assert "layer_2_context_object" in layers
        assert "layer_3_module" in layers
        assert "layer_4_session_context" in layers
        assert "layer_5_data_trust" in layers
        assert "layer_6_user_query" in layers
        
        # Verify mock mode
        assert data["mode"] == "mock-scaffolding"
        assert data["sources"] == []
        
        print(f"✓ LLM probe returned mock response with {len(layers)} layers")


class TestTelemetry:
    """Test telemetry events"""
    
    def test_record_event(self):
        """POST /api/events records telemetry event"""
        session = requests.Session()
        login_resp = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        tenant_id = login_resp.json()["tenants"][0]["id"]
        
        response = session.post(
            f"{BASE_URL}/api/events",
            json={
                "event_name": "test.event",
                "tenant_id": tenant_id,
                "properties": {"test": True}
            }
        )
        assert response.status_code == 200
        assert response.json()["ok"] == True
        print("✓ Telemetry event recorded")
    
    def test_event_requires_membership(self):
        """Event with tenant_id requires membership"""
        # Create two users
        user1_email = f"event1.{uuid.uuid4().hex[:6]}@akki.ai"
        user2_email = f"event2.{uuid.uuid4().hex[:6]}@akki.ai"
        
        session1 = requests.Session()
        resp1 = session1.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": user1_email, "password": "TestPass2026!", "name": "User1"}
        )
        tenant_id = resp1.json()["tenants"][0]["id"]
        
        session2 = requests.Session()
        session2.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": user2_email, "password": "TestPass2026!", "name": "User2"}
        )
        
        # User2 tries to record event for User1's tenant
        response = session2.post(
            f"{BASE_URL}/api/events",
            json={"event_name": "test.event", "tenant_id": tenant_id}
        )
        assert response.status_code == 403
        print("✓ Event requires tenant membership (403)")


class TestDataHygiene:
    """Test MongoDB data hygiene - no _id or sensitive data leakage"""
    
    def test_no_id_leakage_in_responses(self):
        """Verify no _id in any JSON response"""
        session = requests.Session()
        login_resp = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        tenant_id = login_resp.json()["tenants"][0]["id"]
        
        # Check various endpoints
        endpoints = [
            f"/api/auth/me",
            f"/api/tenants/{tenant_id}",
            f"/api/tenants/{tenant_id}/members",
            f"/api/tenants/{tenant_id}/invitations",
            f"/api/tenants/{tenant_id}/audit-log",
        ]
        
        for endpoint in endpoints:
            resp = session.get(f"{BASE_URL}{endpoint}")
            if resp.status_code == 200:
                text = resp.text
                assert '"_id"' not in text, f"_id found in {endpoint}"
        
        print("✓ No _id leakage in responses")
    
    def test_no_password_hash_in_responses(self):
        """Verify password_hash never returned"""
        session = requests.Session()
        login_resp = session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        
        # Check login response
        assert "password_hash" not in login_resp.text
        
        # Check /me response
        me_resp = session.get(f"{BASE_URL}/api/auth/me")
        assert "password_hash" not in me_resp.text
        
        print("✓ No password_hash in responses")


class TestCollaboratorPermissions:
    """Test that collaborators cannot perform owner-only actions"""
    
    def test_collaborator_cannot_rename_tenant(self):
        """Collaborator calling PATCH /api/tenants/{id} returns 403"""
        # Create owner
        owner_email = f"owner.perm.{uuid.uuid4().hex[:6]}@akki.ai"
        collab_email = f"collab.perm.{uuid.uuid4().hex[:6]}@akki.ai"
        
        owner_session = requests.Session()
        owner_resp = owner_session.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": owner_email, "password": "TestPass2026!", "name": "Owner"}
        )
        tenant_id = owner_resp.json()["tenants"][0]["id"]
        
        # Invite collaborator
        invite_resp = owner_session.post(
            f"{BASE_URL}/api/tenants/{tenant_id}/invitations",
            json={"email": collab_email, "role": "collaborator"}
        )
        token = invite_resp.json()["accept_url"].split("/invite/")[-1]
        
        # Register and accept as collaborator
        collab_session = requests.Session()
        collab_session.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": collab_email, "password": "TestPass2026!", "name": "Collab"}
        )
        collab_session.post(f"{BASE_URL}/api/invitations/{token}/accept")
        
        # Collaborator tries to rename
        rename_resp = collab_session.patch(
            f"{BASE_URL}/api/tenants/{tenant_id}",
            json={"name": "Hacked Name"}
        )
        assert rename_resp.status_code == 403
        print("✓ Collaborator cannot rename tenant (403)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
