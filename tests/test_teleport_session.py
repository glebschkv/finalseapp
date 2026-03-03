"""
Tests for Teleport Session Recovery.
Tests persistent session storage and recovery via --teleport flag.
"""

import pytest
from datetime import datetime, timedelta
from src.services.auth_service import AuthService, AuthenticationError
from src.models.base import init_database, DatabaseSession
from src.models.session import PersistentSession


class TestPersistentSessionModel:
    """Test suite for PersistentSession model."""

    @pytest.fixture(autouse=True)
    def setup(self, test_db):
        """Set up test database."""
        init_database()
        AuthService._sessions.clear()

    def test_persistent_session_created_on_login(self):
        """A persistent session is created when a user logs in."""
        AuthService.register("teleuser", "password123")
        user, token = AuthService.login("teleuser", "password123")

        with DatabaseSession() as session:
            persistent = session.query(PersistentSession).filter(
                PersistentSession.user_id == user.id,
                PersistentSession.is_active == True
            ).first()

            assert persistent is not None
            assert persistent.session_token == token
            assert persistent.user_id == user.id
            assert persistent.is_active is True
            assert persistent.session_id is not None
            assert len(persistent.session_id) > 0

    def test_persistent_session_deactivated_on_logout(self):
        """Persistent session is deactivated when user logs out."""
        AuthService.register("logoutuser", "password123")
        user, token = AuthService.login("logoutuser", "password123")

        AuthService.logout(token)

        with DatabaseSession() as session:
            persistent = session.query(PersistentSession).filter(
                PersistentSession.user_id == user.id
            ).first()

            assert persistent is not None
            assert persistent.is_active is False

    def test_old_sessions_deactivated_on_new_login(self):
        """Previous persistent sessions are deactivated on new login."""
        AuthService.register("multilogin", "password123")

        # First login
        user1, token1 = AuthService.login("multilogin", "password123")

        with DatabaseSession() as session:
            first_persistent = session.query(PersistentSession).filter(
                PersistentSession.session_token == token1
            ).first()
            first_session_id = first_persistent.session_id

        # Second login (should deactivate first)
        user2, token2 = AuthService.login("multilogin", "password123")

        with DatabaseSession() as session:
            old = session.query(PersistentSession).filter(
                PersistentSession.session_id == first_session_id
            ).first()
            assert old.is_active is False

            new = session.query(PersistentSession).filter(
                PersistentSession.session_token == token2,
                PersistentSession.is_active == True
            ).first()
            assert new is not None

    def test_persistent_session_is_expired(self):
        """Test the is_expired property."""
        with DatabaseSession() as session:
            # Create an expired session directly
            expired = PersistentSession(
                session_id="expired_test",
                session_token="expired_token",
                user_id=999,
                expires_at=datetime.utcnow() - timedelta(hours=1),
                is_active=True,
            )
            assert expired.is_expired is True
            assert expired.is_valid is False

    def test_persistent_session_is_valid(self):
        """Test the is_valid property."""
        ps = PersistentSession(
            session_id="valid_test",
            session_token="valid_token",
            user_id=999,
            expires_at=datetime.utcnow() + timedelta(hours=1),
            is_active=True,
        )
        assert ps.is_valid is True

        ps.deactivate()
        assert ps.is_valid is False

    def test_persistent_session_to_dict(self):
        """Test to_dict serialization."""
        ps = PersistentSession(
            session_id="dict_test",
            session_token="dict_token",
            user_id=42,
            expires_at=datetime.utcnow() + timedelta(hours=1),
            is_active=True,
        )
        d = ps.to_dict()
        assert d["session_id"] == "dict_test"
        assert d["user_id"] == 42
        assert d["is_active"] is True
        assert d["is_expired"] is False


class TestTeleportRecovery:
    """Test suite for teleport session recovery."""

    @pytest.fixture(autouse=True)
    def setup(self, test_db):
        """Set up test database."""
        init_database()
        AuthService._sessions.clear()

    def _get_session_id_for_user(self, user_id):
        """Helper to get the active session ID for a user."""
        with DatabaseSession() as session:
            persistent = session.query(PersistentSession).filter(
                PersistentSession.user_id == user_id,
                PersistentSession.is_active == True
            ).first()
            return persistent.session_id if persistent else None

    def test_recover_valid_session(self):
        """Teleport recovery works with a valid session ID."""
        AuthService.register("recoveruser", "password123")
        user, token = AuthService.login("recoveruser", "password123")
        session_id = self._get_session_id_for_user(user.id)

        # Clear in-memory sessions (simulating app restart)
        AuthService._sessions.clear()

        # Recover via teleport
        result = AuthService.recover_session(session_id)
        assert result is not None

        recovered_user, recovered_token = result
        assert recovered_user.username == "recoveruser"
        assert recovered_token == token

        # Verify the in-memory session was restored
        assert token in AuthService._sessions

    def test_recover_invalid_session_id(self):
        """Teleport recovery returns None for unknown session ID."""
        result = AuthService.recover_session("nonexistent_session_id")
        assert result is None

    def test_recover_expired_session(self):
        """Teleport recovery returns None for expired sessions."""
        AuthService.register("expireduser", "password123")
        user, token = AuthService.login("expireduser", "password123")
        session_id = self._get_session_id_for_user(user.id)

        # Manually expire the session
        with DatabaseSession() as session:
            persistent = session.query(PersistentSession).filter(
                PersistentSession.session_id == session_id
            ).first()
            persistent.expires_at = datetime.utcnow() - timedelta(hours=1)

        # Clear in-memory sessions
        AuthService._sessions.clear()

        # Attempt recovery
        result = AuthService.recover_session(session_id)
        assert result is None

    def test_recover_deactivated_session(self):
        """Teleport recovery returns None for deactivated sessions."""
        AuthService.register("deactuser", "password123")
        user, token = AuthService.login("deactuser", "password123")
        session_id = self._get_session_id_for_user(user.id)

        # Logout to deactivate the persistent session
        AuthService.logout(token)

        # Clear in-memory sessions
        AuthService._sessions.clear()

        # Attempt recovery
        result = AuthService.recover_session(session_id)
        assert result is None

    def test_recover_deleted_user(self):
        """Teleport recovery returns None if the user was deleted."""
        AuthService.register("deleteduser", "password123")
        user, token = AuthService.login("deleteduser", "password123")
        session_id = self._get_session_id_for_user(user.id)

        # Delete the user
        AuthService.delete_account(user.id, "password123")

        # Clear in-memory sessions
        AuthService._sessions.clear()

        # Attempt recovery
        result = AuthService.recover_session(session_id)
        assert result is None

    def test_get_session_id_for_token(self):
        """Can retrieve session ID from a session token."""
        AuthService.register("siduser", "password123")
        user, token = AuthService.login("siduser", "password123")

        session_id = AuthService.get_session_id_for_token(token)
        assert session_id is not None
        assert len(session_id) > 0

    def test_get_session_id_for_invalid_token(self):
        """Returns None for an invalid session token."""
        session_id = AuthService.get_session_id_for_token("invalid_token")
        assert session_id is None

    def test_recover_restores_working_session(self):
        """After teleport recovery, the session token is fully functional."""
        AuthService.register("workuser", "password123")
        user, token = AuthService.login("workuser", "password123")
        session_id = self._get_session_id_for_user(user.id)

        # Clear in-memory sessions
        AuthService._sessions.clear()

        # Recover
        result = AuthService.recover_session(session_id)
        assert result is not None

        _, recovered_token = result

        # Validate the recovered session works
        validated_user = AuthService.validate_session(recovered_token)
        assert validated_user is not None
        assert validated_user.username == "workuser"
