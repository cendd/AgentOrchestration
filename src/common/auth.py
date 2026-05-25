"""Authentication module with session rotation support."""
import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TokenData:
    """Stored token metadata — never expose the raw token value in logs."""
    token_hash: str
    user_id: str
    roles: List[str]
    session_id: str
    issued_at: float
    expires_at: float
    is_stale: bool = False
    is_revoked: bool = False


@dataclass
class Session:
    """User session with rotation tracking."""
    session_id: str
    user_id: str
    roles: List[str]
    created_at: float
    current_token_hash: str
    token_count: int = 0
    active: bool = True


class TokenManager:
    """Manages token validation, session rotation, and credential invalidation."""

    def __init__(self, token_ttl: float = 3600.0):
        self.token_ttl = token_ttl
        self._tokens: Dict[str, TokenData] = {}
        self._sessions: Dict[str, Session] = {}
        self._user_sessions: Dict[str, List[str]] = {}

    def _hash_token(self, token: str) -> str:
        """Simple hash for token storage (never store raw tokens)."""
        import hashlib
        return hashlib.sha256(token.encode()).hexdigest()[:32]

    def issue_token(self, user_id: str, roles: List[str]) -> str:
        """Issue a new token, rotating the previous session."""
        # Rotate: mark previous session for this user as inactive
        if user_id in self._user_sessions:
            for old_sid in self._user_sessions[user_id]:
                old_session = self._sessions.get(old_sid)
                if old_session and old_session.active:
                    old_session.active = False
                    logger.info("Rotated session %s for user %s", old_sid[:8], user_id)

        session_id = str(uuid.uuid4())
        raw_token = str(uuid.uuid4())
        token_hash = self._hash_token(raw_token)
        now = time.time()

        token_data = TokenData(
            token_hash=token_hash,
            user_id=user_id,
            roles=roles,
            session_id=session_id,
            issued_at=now,
            expires_at=now + self.token_ttl,
        )
        session = Session(
            session_id=session_id,
            user_id=user_id,
            roles=roles,
            created_at=now,
            current_token_hash=token_hash,
            active=True,
        )

        self._tokens[token_hash] = token_data
        self._sessions[session_id] = session
        if user_id not in self._user_sessions:
            self._user_sessions[user_id] = []
        self._user_sessions[user_id].append(session_id)

        logger.info("Issued token for user %s (session %s)", user_id, session_id[:8])
        return raw_token

    def validate_token(self, token: str) -> bool:
        """Check if token is valid: exists, not expired, not stale, not revoked."""
        token_hash = self._hash_token(token)
        tok = self._tokens.get(token_hash)
        if not tok:
            return False
        if tok.is_revoked:
            logger.debug("Token %s is revoked", token_hash[:8])
            return False
        if tok.is_stale:
            logger.debug("Token %s is stale", token_hash[:8])
            return False
        if time.time() > tok.expires_at:
            logger.debug("Token %s expired", token_hash[:8])
            return False
        return True

    def check_session_rotation(self, token: str) -> bool:
        """Verify token belongs to an active (non-rotated) session."""
        token_hash = self._hash_token(token)
        tok = self._tokens.get(token_hash)
        if not tok:
            return False

        session = self._sessions.get(tok.session_id)
        if not session:
            return False
        if not session.active:
            logger.debug("Session %s has been rotated", tok.session_id[:8])
            return False
        if session.current_token_hash != token_hash:
            logger.debug("Token is not the current token for session %s", tok.session_id[:8])
            return False
        return True

    def invalidate_stale_credentials(self, session_id: str) -> None:
        """Mark all tokens for a session except the current one as stale."""
        session = self._sessions.get(session_id)
        if not session:
            return
        current_hash = session.current_token_hash
        for tok in self._tokens.values():
            if tok.session_id == session_id and tok.token_hash != current_hash:
                tok.is_stale = True
                logger.info("Invalidated stale token %s in session %s", tok.token_hash[:8], session_id[:8])

    def revoke_token(self, token: str) -> bool:
        """Revoke a specific token."""
        token_hash = self._hash_token(token)
        tok = self._tokens.get(token_hash)
        if not tok:
            return False
        tok.is_revoked = True
        logger.info("Revoked token %s", token_hash[:8])
        return True

    def is_authorized(self, token: str, required_role: str) -> bool:
        """Check role-based authorization."""
        token_hash = self._hash_token(token)
        tok = self._tokens.get(token_hash)
        if not tok or not self.validate_token(token):
            return False
        return required_role in tok.roles

    def get_user_id(self, token: str) -> Optional[str]:
        """Get user ID from token (for middleware)."""
        token_hash = self._hash_token(token)
        tok = self._tokens.get(token_hash)
        if not tok:
            return None
        return tok.user_id

    def revoke_all_user_tokens(self, user_id: str) -> int:
        """Revoke all tokens for a user."""
        count = 0
        for tok in self._tokens.values():
            if tok.user_id == user_id and not tok.is_revoked:
                tok.is_revoked = True
                count += 1
        logger.info("Revoked %d tokens for user %s", count, user_id)
        return count

    def list_sessions(self, user_id: str) -> List[Session]:
        """List all sessions for a user (for audit)."""
        return [
            self._sessions[sid] for sid in self._user_sessions.get(user_id, [])
            if sid in self._sessions
        ]
