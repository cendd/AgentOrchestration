"""Tests for authentication module with session rotation."""
import pytest
import time
from src.common.auth import TokenManager


class TestTokenValidation:
    """Test basic token validation (fresh, stale, revoked)."""

    def setup_method(self):
        self.tm = TokenManager(token_ttl=3600)
        self.token = self.tm.issue_token("user1", ["admin"])

    def test_fresh_token_passes(self):
        assert self.tm.validate_token(self.token) is True

    def test_valid_token_with_correct_scope_succeeds(self):
        assert self.tm.is_authorized(self.token, "admin") is True

    def test_nonexistent_token_fails(self):
        assert self.tm.validate_token("invalid_token") is False

    def test_expired_token_fails(self):
        tm = TokenManager(token_ttl=-1)  # expires immediately
        expired_token = tm.issue_token("user2", ["viewer"])
        assert tm.validate_token(expired_token) is False

    def test_revoked_token_blocked(self):
        self.tm.revoke_token(self.token)
        assert self.tm.validate_token(self.token) is False

    def test_stale_token_denied(self):
        """Stale tokens from rotated sessions are denied."""
        self.tm.revoke_all_user_tokens("user1")
        # After revoke_all, token should be revoked
        assert self.tm.validate_token(self.token) is False


class TestSessionRotation:
    """Test session rotation enforcement."""

    def test_rotated_session_denied(self):
        tm = TokenManager()
        old_token = tm.issue_token("alice", ["user"])
        # Issuing a new token rotates the old session
        new_token = tm.issue_token("alice", ["user"])
        # Check old token — should fail session rotation check
        assert tm.check_session_rotation(old_token) is False
        # Old token validate should fail (session inactive)
        assert tm.validate_token(old_token) is False
        # New token should pass
        assert tm.check_session_rotation(new_token) is True
        assert tm.validate_token(new_token) is True

    def test_multiple_users_independent_rotation(self):
        tm = TokenManager()
        alice_token1 = tm.issue_token("alice", ["admin"])
        bob_token = tm.issue_token("bob", ["viewer"])
        # Alice rotates
        alice_token2 = tm.issue_token("alice", ["admin"])
        # Alice's old token fails
        assert tm.validate_token(alice_token1) is False
        assert tm.check_session_rotation(alice_token1) is False
        # Bob's token still works
        assert tm.validate_token(bob_token) is True
        assert tm.check_session_rotation(bob_token) is True

    def test_session_rotation_does_not_affect_other_users(self):
        tm = TokenManager()
        user_a = tm.issue_token("a", ["admin"])
        user_b = tm.issue_token("b", ["read"])
        _ = tm.issue_token("a", ["admin"])  # rotate A
        # B unaffected
        assert tm.validate_token(user_b) is True


class TestAuthorization:
    """Test role-based authorization."""

    def test_insufficient_scope_denied(self):
        tm = TokenManager()
        token = tm.issue_token("user", ["viewer"])
        assert tm.is_authorized(token, "admin") is False

    def test_authorized_user_succeeds(self):
        tm = TokenManager()
        token = tm.issue_token("user", ["admin", "viewer"])
        assert tm.is_authorized(token, "admin") is True
        assert tm.is_authorized(token, "viewer") is True

    def test_unauthorized_anonymous_denied(self):
        tm = TokenManager()
        # No token at all
        assert tm.is_authorized("fake", "any_role") is False


class TestIntegration:
    """Integration: middleware-level checks via TokenManager."""

    def test_middleware_auth_flow(self):
        """Simulate the middleware auth flow end-to-end."""
        tm = TokenManager()
        token = tm.issue_token("test_user", ["operator"])
        # Middleware check 1: validate
        assert tm.validate_token(token) is True
        # Middleware check 2: session rotation
        assert tm.check_session_rotation(token) is True
        # Middleware check 3: optional role gate
        assert tm.is_authorized(token, "operator") is True
        # After session rotation
        tm.issue_token("test_user", ["operator"])
        # All checks should fail for old token
        assert tm.validate_token(token) is False
        assert tm.check_session_rotation(token) is False
