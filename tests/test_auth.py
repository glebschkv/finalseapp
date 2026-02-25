"""
Tests for Authentication Service.
Tests BR1: Account Management
"""

import pytest
from src.services.auth_service import AuthService, AuthenticationError
from src.models.base import init_database


class TestAuthentication:
    """Test suite for BR1: Account Management."""

    @pytest.fixture(autouse=True)
    def setup(self, test_db):
        """Set up test database."""
        init_database()
        AuthService._sessions.clear()

    def test_user_registration_success(self):
        """BR1.1: User creates an account successfully."""
        user = AuthService.register("testuser", "password123")

        assert user is not None
        assert user.username == "testuser"
        assert user.id is not None

    def test_user_registration_duplicate_username(self):
        """BR1.1: Registration fails with duplicate username."""
        AuthService.register("duplicate_user", "password123")

        with pytest.raises(AuthenticationError) as exc_info:
            AuthService.register("duplicate_user", "password456")

        assert "already taken" in str(exc_info.value)

    def test_user_registration_invalid_username_too_short(self):
        """BR1.1: Registration fails with short username."""
        with pytest.raises(AuthenticationError) as exc_info:
            AuthService.register("ab", "password123")

        assert "at least 3 characters" in str(exc_info.value)

    def test_user_registration_invalid_password_too_short(self):
        """BR1.1: Registration fails with short password."""
        with pytest.raises(AuthenticationError) as exc_info:
            AuthService.register("validuser", "12345")

        assert "at least 6 characters" in str(exc_info.value)

    def test_user_login_valid_credentials(self):
        """BR1.2: User logs in with valid credentials."""
        AuthService.register("logintest", "password123")
        user, token = AuthService.login("logintest", "password123")

        assert user is not None
        assert user.username == "logintest"
        assert token is not None
        assert len(token) > 0

    def test_user_login_invalid_username(self):
        """BR1.2: Login fails with invalid username."""
        with pytest.raises(AuthenticationError) as exc_info:
            AuthService.login("nonexistent", "password123")

        assert "Invalid username or password" in str(exc_info.value)

    def test_user_login_invalid_password(self):
        """BR1.2: Login fails with invalid password."""
        AuthService.register("wrongpass", "correctpassword")

        with pytest.raises(AuthenticationError) as exc_info:
            AuthService.login("wrongpass", "wrongpassword")

        assert "Invalid username or password" in str(exc_info.value)

    def test_user_logout(self):
        """BR1.3: User logs out successfully."""
        AuthService.register("logouttest", "password123")
        user, token = AuthService.login("logouttest", "password123")

        # Verify session exists
        assert AuthService.validate_session(token) is not None

        # Logout
        result = AuthService.logout(token)
        assert result is True

        # Verify session is gone
        assert AuthService.validate_session(token) is None

    def test_user_logout_invalid_token(self):
        """BR1.3: Logout with invalid token returns False."""
        result = AuthService.logout("invalid_token")
        assert result is False

    def test_user_account_deletion(self):
        """BR1.4: User deletes their account."""
        user = AuthService.register("deletetest", "password123")
        user_id = user.id

        result = AuthService.delete_account(user_id, "password123")
        assert result is True

        # Verify can't login anymore
        with pytest.raises(AuthenticationError):
            AuthService.login("deletetest", "password123")

    def test_user_account_deletion_wrong_password(self):
        """BR1.4: Account deletion fails with wrong password."""
        user = AuthService.register("deletetest2", "password123")

        with pytest.raises(AuthenticationError) as exc_info:
            AuthService.delete_account(user.id, "wrongpassword")

        assert "Invalid password" in str(exc_info.value)

    def test_session_validation(self):
        """Test session token validation."""
        AuthService.register("sessiontest", "password123")
        user, token = AuthService.login("sessiontest", "password123")

        # Valid token
        validated_user = AuthService.validate_session(token)
        assert validated_user is not None
        assert validated_user.username == "sessiontest"

        # Invalid token
        invalid_user = AuthService.validate_session("invalid_token_123")
        assert invalid_user is None

    def test_password_change(self):
        """Test password change functionality."""
        user = AuthService.register("passchange", "oldpassword")

        result = AuthService.change_password(user.id, "oldpassword", "newpassword")
        assert result is True

        # Login with new password should work
        user, token = AuthService.login("passchange", "newpassword")
        assert user is not None

        # Login with old password should fail
        with pytest.raises(AuthenticationError):
            AuthService.login("passchange", "oldpassword")
