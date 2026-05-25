"""Tests for auth session rotation."""
import pytest
from src.common.auth import TokenManager

class TestTokenManager:
    @pytest.fixture
    def mgr(self):
        return TokenManager(max_rotations=5)
    
    @pytest.fixture
    def sess(self, mgr):
        return mgr.create_session("u123", "s_abc")
    
    def test_authorized_passes(self, mgr):
        s = mgr.create_session("u", "s1")
        r = mgr.validate_token("s1", s["refresh_token"])
        assert r["valid"] is True
        assert r["session"]["user_id"] == "u"
    
    def test_fresh_auth_active(self, mgr, sess):
        assert mgr.require_fresh_authorization("s_abc") is True
    
    def test_stale_token_denied(self, mgr, sess):
        r1 = mgr.validate_token("s_abc", sess["refresh_token"])
        assert r1["valid"] is True
        r2 = mgr.validate_token("s_abc", sess["refresh_token"])
        assert r2["valid"] is False
        assert "stale" in r2["reason"].lower() or "rotated" in r2["reason"].lower()
    
    def test_stale_no_fresh(self, mgr, sess):
        mgr.validate_token("s_abc", sess["refresh_token"])
        assert mgr.require_fresh_authorization("s_abc") is False
    
    def test_revoked_blocked(self, mgr, sess):
        mgr.revoke_session("s_abc")
        r = mgr.validate_token("s_abc", sess["refresh_token"])
        assert r["valid"] is False
        assert "revoked" in r["reason"].lower()
    
    def test_revoked_no_fresh(self, mgr, sess):
        mgr.revoke_session("s_abc")
        assert mgr.require_fresh_authorization("s_abc") is False
    
    def test_wrong_token(self, mgr, sess):
        r = mgr.validate_token("s_abc", "bad")
        assert r["valid"] is False
    
    def test_unknown_session(self, mgr):
        r = mgr.validate_token("nonexistent", "t")
        assert r["valid"] is False
    
    def test_max_rotation(self, mgr):
        s = mgr.create_session("u", "s")
        t, sid = s["refresh_token"], "s"
        for i in range(5):
            r = mgr.validate_token(sid, t)
            assert r["valid"] is True
            t, sid = r["new_token"], r["new_session_id"]
        r = mgr.validate_token(sid, t)
        assert r["valid"] is False
    
    def test_auth_after_rotation(self, mgr):
        s = mgr.create_session("u", "s")
        r = mgr.validate_token("s", s["refresh_token"])
        assert r["valid"] is True
        assert mgr.require_fresh_authorization(r["new_session_id"]) is True
    
    def test_rotation_state(self, mgr, sess):
        mgr.validate_token("s_abc", sess["refresh_token"])
        st = mgr.check_session_rotation("s_abc")
        assert st["state"] == "stale"
        assert st["fresh"] is False
    
    def test_invalidate_stale(self, mgr, sess):
        mgr.validate_token("s_abc", sess["refresh_token"])
        assert mgr.invalidate_stale_credentials("s_abc") is True
        r = mgr.validate_token("s_abc", sess["refresh_token"])
        assert r["valid"] is False
    
    def test_multi_rotation_works(self, mgr):
        s = mgr.create_session("u", "s")
        t, sid = s["refresh_token"], "s"
        for i in range(3):
            r = mgr.validate_token(sid, t)
            assert r["valid"] is True
            t, sid = r["new_token"], r["new_session_id"]
        assert mgr.require_fresh_authorization(sid) is True
