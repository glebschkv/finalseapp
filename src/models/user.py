"""
User model for authentication and account management.
Implements BR1: Account Management
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import Optional
import bcrypt

from .base import Base


class User(Base):
    """
    User account model.

    Supports:
    - BR1.1: User creates an account
    - BR1.2: User logs-in to their account
    - BR1.3: User logs-out of their account
    - BR1.4: User deletes their account
    """

    __tablename__ = "users"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Account information
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    # Account metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

    # Relationships
    chats = relationship(
        "Chat",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}')>"

    def set_password(self, password: str) -> None:
        """
        Hash and set the user's password.

        Args:
            password: Plain text password to hash
        """
        salt = bcrypt.gensalt(rounds=12)
        self.password_hash = bcrypt.hashpw(
            password.encode("utf-8"),
            salt
        ).decode("utf-8")

    def check_password(self, password: str) -> bool:
        """
        Verify a password against the stored hash.

        Args:
            password: Plain text password to verify

        Returns:
            True if password matches, False otherwise
        """
        return bcrypt.checkpw(
            password.encode("utf-8"),
            self.password_hash.encode("utf-8")
        )

    def update_last_login(self) -> None:
        """Update the last login timestamp."""
        self.last_login = datetime.utcnow()

    @classmethod
    def create(cls, username: str, password: str) -> "User":
        """
        Factory method to create a new user with hashed password.

        Args:
            username: Unique username
            password: Plain text password

        Returns:
            New User instance (not yet committed to database)
        """
        user = cls(username=username)
        user.set_password(password)
        return user

    def to_dict(self) -> dict:
        """Convert user to dictionary (excluding sensitive data)."""
        return {
            "id": self.id,
            "username": self.username,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "is_active": self.is_active
        }
