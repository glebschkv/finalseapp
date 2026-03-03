"""
Persistent session model for teleport session recovery.
Stores session tokens in the database so sessions can survive app restarts.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from typing import Optional

from .base import Base


class PersistentSession(Base):
    """
    Persistent session model for teleport recovery.

    Allows users to resume their session after app restart
    by providing the session ID via --teleport CLI flag.
    """

    __tablename__ = "persistent_sessions"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Session identifier (used for --teleport lookup)
    session_id = Column(String(100), unique=True, nullable=False, index=True)

    # Session token (the auth token used in-memory)
    session_token = Column(String(100), unique=True, nullable=False)

    # Foreign key to user
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

    # Whether the session is still active
    is_active = Column(Boolean, default=True)

    # Relationships
    user = relationship("User")

    def __repr__(self) -> str:
        return f"<PersistentSession(id={self.id}, session_id='{self.session_id}', user_id={self.user_id})>"

    @property
    def is_expired(self) -> bool:
        """Check if the session has expired."""
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if the session is both active and not expired."""
        return self.is_active and not self.is_expired

    def deactivate(self) -> None:
        """Mark this session as inactive."""
        self.is_active = False

    def to_dict(self) -> dict:
        """Convert session to dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active,
            "is_expired": self.is_expired,
        }
