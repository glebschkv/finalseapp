"""
Chat and Message models for conversation management.
Implements BR3: Chat History and BR8: Danger Level
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import Optional, List
import enum
import json

from .base import Base


class SeverityLevel(enum.Enum):
    """Severity levels for BR8: Danger Level categorization."""
    CRITICAL = "critical"  # Red - severe issue requiring immediate action
    WARNING = "warning"    # Amber - moderate issue requiring attention
    NORMAL = "normal"      # Green - mild or no issue


class Chat(Base):
    """
    Chat session model.

    Supports:
    - BR2.1: User uploads a valid log file (stores parsed data)
    - BR3.1: User views chat history
    - BR3.2: User deletes chat history
    - BR3.3: User renames chat log
    - BR3.4: User exports chat log
    """

    __tablename__ = "chats"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to user
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Chat metadata
    name = Column(String(100), default="New Chat")
    vehicle_info = Column(String(200), nullable=True)  # Optional vehicle description

    # OBD-II data storage
    obd_log_path = Column(String(500), nullable=True)
    parsed_metrics = Column(JSON, nullable=True)  # Stored as JSON
    fault_codes = Column(JSON, nullable=True)     # Stored as JSON

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="chats")
    messages = relationship(
        "Message",
        back_populates="chat",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
        lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<Chat(id={self.id}, name='{self.name}', user_id={self.user_id})>"

    def rename(self, new_name: str) -> None:
        """Rename the chat (BR3.3)."""
        self.name = new_name
        self.updated_at = datetime.utcnow()

    def set_parsed_data(self, metrics: dict, fault_codes: list) -> None:
        """Store parsed OBD-II data."""
        self.parsed_metrics = metrics
        self.fault_codes = fault_codes
        self.updated_at = datetime.utcnow()

    def get_messages_list(self) -> List["Message"]:
        """Get all messages as a list."""
        return self.messages.all()

    def add_message(self, role: str, content: str, severity: str = "normal") -> "Message":
        """Add a new message to the chat."""
        message = Message(
            chat_id=self.id,
            role=role,
            content=content,
            severity=severity
        )
        return message

    def export_to_text(self) -> str:
        """
        Export chat to plain text format (BR3.4).

        Returns:
            Formatted string of the chat history
        """
        lines = [
            f"Chat: {self.name}",
            f"Created: {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Vehicle: {self.vehicle_info or 'Not specified'}",
            "-" * 50,
            ""
        ]

        for message in self.messages.all():
            role_label = "You" if message.role == "user" else "InsightBot"
            timestamp = message.created_at.strftime("%H:%M:%S")
            lines.append(f"[{timestamp}] {role_label}:")
            lines.append(message.content)
            lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Convert chat to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "vehicle_info": self.vehicle_info,
            "obd_log_path": self.obd_log_path,
            "parsed_metrics": self.parsed_metrics,
            "fault_codes": self.fault_codes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_count": self.messages.count()
        }


class Message(Base):
    """
    Individual message in a chat.

    Supports:
    - BR4: General Vehicle Status Queries
    - BR5: Fault Code Explanation
    - BR8: Danger Level (severity classification)
    """

    __tablename__ = "messages"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to chat
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)

    # Message content
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)

    # Severity for BR8 (danger level categorization)
    severity = Column(String(20), default="normal")  # 'critical', 'warning', 'normal'

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Additional data (e.g., source documents for RAG)
    extra_data = Column(JSON, nullable=True)

    # Relationships
    chat = relationship("Chat", back_populates="messages")

    def __repr__(self) -> str:
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<Message(id={self.id}, role='{self.role}', preview='{preview}')>"

    @property
    def is_user_message(self) -> bool:
        """Check if this is a user message."""
        return self.role == "user"

    @property
    def is_assistant_message(self) -> bool:
        """Check if this is an assistant message."""
        return self.role == "assistant"

    @property
    def severity_level(self) -> SeverityLevel:
        """Get severity as enum."""
        try:
            return SeverityLevel(self.severity)
        except ValueError:
            return SeverityLevel.NORMAL

    def to_dict(self) -> dict:
        """Convert message to dictionary."""
        return {
            "id": self.id,
            "chat_id": self.chat_id,
            "role": self.role,
            "content": self.content,
            "severity": self.severity,
            "timestamp": self.created_at.isoformat() if self.created_at else None,
            "metadata": self.extra_data
        }
