"""
Chat management service.
Implements BR3: Chat History
Enhanced with multiple export formats (TXT, JSON, Markdown).
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime
import json

from ..models.base import DatabaseSession
from ..models.chat import Chat, Message
from ..config.logging_config import get_logger

logger = get_logger(__name__)


class ExportFormat:
    """Supported export formats."""
    TXT = "txt"
    JSON = "json"
    MARKDOWN = "md"

    @classmethod
    def all(cls) -> List[str]:
        return [cls.TXT, cls.JSON, cls.MARKDOWN]


class ChatService:
    """
    Service for managing chat sessions.

    Implements:
    - BR3.1: User views chat history
    - BR3.2: User deletes chat history
    - BR3.3: User renames chat log
    - BR3.4: User exports chat log
    """

    @staticmethod
    def create_chat(user_id: int, obd_log_path: str, parsed_data: dict, name: Optional[str] = None) -> Chat:
        """
        Create a new chat session with parsed OBD data.

        Args:
            user_id: ID of the user creating the chat
            obd_log_path: Path to the uploaded OBD-II log file
            parsed_data: Parsed OBD-II data from OBDParser
            name: Optional name for the chat

        Returns:
            Created Chat object
        """
        with DatabaseSession() as session:
            chat = Chat(
                user_id=user_id,
                name=name or f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                obd_log_path=obd_log_path,
                parsed_metrics=parsed_data.get("metrics"),
                fault_codes=parsed_data.get("fault_codes")
            )
            session.add(chat)
            session.flush()

            logger.info(f"Created chat {chat.id} for user {user_id}")

            # Detach from session
            session.expunge(chat)
            return chat

    @staticmethod
    def get_user_chats(user_id: int) -> List[Chat]:
        """
        Get all chats for a user (BR3.1).

        Args:
            user_id: User's ID

        Returns:
            List of Chat objects, ordered by most recent first
        """
        with DatabaseSession() as session:
            chats = session.query(Chat).filter(
                Chat.user_id == user_id
            ).order_by(Chat.updated_at.desc()).all()

            # Detach all chats from session
            for chat in chats:
                session.expunge(chat)

            return chats

    @staticmethod
    def get_chat(chat_id: int, user_id: int) -> Optional[Chat]:
        """
        Get a specific chat by ID.

        Args:
            chat_id: Chat ID
            user_id: User ID (for authorization)

        Returns:
            Chat object if found and owned by user, None otherwise
        """
        with DatabaseSession() as session:
            chat = session.query(Chat).filter(
                Chat.id == chat_id,
                Chat.user_id == user_id
            ).first()

            if chat:
                session.expunge(chat)

            return chat

    @staticmethod
    def get_chat_messages(chat_id: int, user_id: int) -> List[Message]:
        """
        Get all messages for a chat.

        Args:
            chat_id: Chat ID
            user_id: User ID (for authorization)

        Returns:
            List of Message objects
        """
        with DatabaseSession() as session:
            # Verify ownership
            chat = session.query(Chat).filter(
                Chat.id == chat_id,
                Chat.user_id == user_id
            ).first()

            if not chat:
                return []

            messages = session.query(Message).filter(
                Message.chat_id == chat_id
            ).order_by(Message.created_at).all()

            for message in messages:
                session.expunge(message)

            return messages

    @staticmethod
    def add_message(chat_id: int, role: str, content: str, severity: str = "normal", metadata: dict = None) -> Message:
        """
        Add a message to a chat.

        Args:
            chat_id: Chat ID
            role: Message role ('user' or 'assistant')
            content: Message content
            severity: Severity level for BR8 ('critical', 'warning', 'normal')
            metadata: Optional metadata (e.g., source documents)

        Returns:
            Created Message object
        """
        with DatabaseSession() as session:
            message = Message(
                chat_id=chat_id,
                role=role,
                content=content,
                severity=severity,
                extra_data=metadata
            )
            session.add(message)

            # Update chat's updated_at
            chat = session.query(Chat).filter(Chat.id == chat_id).first()
            if chat:
                chat.updated_at = datetime.utcnow()

            session.flush()
            session.expunge(message)

            logger.debug(f"Added {role} message to chat {chat_id}")
            return message

    @staticmethod
    def rename_chat(chat_id: int, user_id: int, new_name: str) -> Optional[Chat]:
        """
        Rename a chat (BR3.3).

        Args:
            chat_id: Chat ID
            user_id: User ID (for authorization)
            new_name: New name for the chat

        Returns:
            Updated Chat object, or None if not found
        """
        with DatabaseSession() as session:
            chat = session.query(Chat).filter(
                Chat.id == chat_id,
                Chat.user_id == user_id
            ).first()

            if not chat:
                return None

            old_name = chat.name
            chat.rename(new_name)
            session.flush()

            logger.info(f"Renamed chat {chat_id}: '{old_name}' -> '{new_name}'")

            session.expunge(chat)
            return chat

    @staticmethod
    def delete_chat(chat_id: int, user_id: int) -> bool:
        """
        Delete a chat and all its messages (BR3.2).

        Args:
            chat_id: Chat ID
            user_id: User ID (for authorization)

        Returns:
            True if deleted, False if not found
        """
        with DatabaseSession() as session:
            chat = session.query(Chat).filter(
                Chat.id == chat_id,
                Chat.user_id == user_id
            ).first()

            if not chat:
                return False

            session.delete(chat)
            logger.info(f"Deleted chat {chat_id}")
            return True

    @staticmethod
    def delete_multiple_chats(chat_ids: List[int], user_id: int) -> int:
        """
        Delete multiple chats (BR3.2).

        Args:
            chat_ids: List of chat IDs to delete
            user_id: User ID (for authorization)

        Returns:
            Number of chats deleted
        """
        deleted_count = 0
        with DatabaseSession() as session:
            for chat_id in chat_ids:
                chat = session.query(Chat).filter(
                    Chat.id == chat_id,
                    Chat.user_id == user_id
                ).first()

                if chat:
                    session.delete(chat)
                    deleted_count += 1

            logger.info(f"Deleted {deleted_count} chats for user {user_id}")

        return deleted_count

    @staticmethod
    def export_chat(chat_id: int, user_id: int, export_format: str = "txt") -> Optional[str]:
        """
        Export a chat to a file (BR3.4).

        Args:
            chat_id: Chat ID
            user_id: User ID (for authorization)
            export_format: Export format ('txt', 'json', 'md')

        Returns:
            Exported content as string, or None if not found
        """
        with DatabaseSession() as session:
            chat = session.query(Chat).filter(
                Chat.id == chat_id,
                Chat.user_id == user_id
            ).first()

            if not chat:
                return None

            # Load messages
            messages = session.query(Message).filter(
                Message.chat_id == chat_id
            ).order_by(Message.created_at).all()

            format_lower = export_format.lower()
            if format_lower == ExportFormat.TXT:
                return ChatService._export_to_txt(chat, messages)
            elif format_lower == ExportFormat.JSON:
                return ChatService._export_to_json(chat, messages)
            elif format_lower in [ExportFormat.MARKDOWN, "markdown"]:
                return ChatService._export_to_markdown(chat, messages)
            else:
                logger.warning(f"Unsupported export format: {export_format}")
                return None

    @staticmethod
    def _export_to_txt(chat: Chat, messages: List[Message]) -> str:
        """Export chat to plain text format."""
        lines = [
            "=" * 60,
            f"OBD InsightBot - Chat Export",
            "=" * 60,
            f"Chat Name: {chat.name}",
            f"Created: {chat.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Last Updated: {chat.updated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "-" * 60,
            ""
        ]

        # Add parsed data summary if available
        if chat.parsed_metrics:
            lines.append("VEHICLE METRICS SUMMARY:")
            for metric in chat.parsed_metrics:
                status_icon = {"critical": "[!]", "warning": "[*]", "normal": "[+]"}.get(metric.get("status"), "[ ]")
                lines.append(f"  {status_icon} {metric.get('name', 'Unknown')}: {metric.get('value', 'N/A')} {metric.get('unit', '')}")
            lines.append("")

        if chat.fault_codes:
            lines.append("FAULT CODES:")
            for code in chat.fault_codes:
                lines.append(f"  - {code.get('code', 'Unknown')}: {code.get('description', 'No description')}")
            lines.append("")

        lines.append("-" * 60)
        lines.append("CONVERSATION:")
        lines.append("-" * 60)
        lines.append("")

        for message in messages:
            role_label = "You" if message.role == "user" else "InsightBot"
            timestamp = message.created_at.strftime("%H:%M:%S")
            severity_marker = ""
            if message.severity == "critical":
                severity_marker = " [CRITICAL]"
            elif message.severity == "warning":
                severity_marker = " [WARNING]"

            lines.append(f"[{timestamp}] {role_label}{severity_marker}:")
            lines.append(message.content)
            lines.append("")

        lines.append("=" * 60)
        lines.append("End of Export")
        lines.append("=" * 60)

        return "\n".join(lines)

    @staticmethod
    def _export_to_json(chat: Chat, messages: List[Message]) -> str:
        """Export chat to JSON format."""
        export_data = {
            "export_info": {
                "format": "json",
                "version": "1.0",
                "exported_at": datetime.utcnow().isoformat(),
                "application": "OBD InsightBot"
            },
            "chat": {
                "id": chat.id,
                "name": chat.name,
                "created_at": chat.created_at.isoformat() if chat.created_at else None,
                "updated_at": chat.updated_at.isoformat() if chat.updated_at else None,
                "obd_log_path": chat.obd_log_path
            },
            "vehicle_data": {
                "metrics": chat.parsed_metrics or [],
                "fault_codes": chat.fault_codes or [],
                "summary": {
                    "total_metrics": len(chat.parsed_metrics) if chat.parsed_metrics else 0,
                    "total_fault_codes": len(chat.fault_codes) if chat.fault_codes else 0,
                    "has_critical": any(
                        m.get("status") == "critical"
                        for m in (chat.parsed_metrics or [])
                    ) or any(
                        f.get("severity") == "critical"
                        for f in (chat.fault_codes or [])
                    ),
                    "has_warning": any(
                        m.get("status") == "warning"
                        for m in (chat.parsed_metrics or [])
                    ) or any(
                        f.get("severity") == "warning"
                        for f in (chat.fault_codes or [])
                    )
                }
            },
            "messages": [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "severity": msg.severity,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                    "extra_data": msg.extra_data
                }
                for msg in messages
            ]
        }

        return json.dumps(export_data, indent=2, ensure_ascii=False)

    @staticmethod
    def _export_to_markdown(chat: Chat, messages: List[Message]) -> str:
        """Export chat to Markdown format."""
        lines = [
            f"# OBD InsightBot - Chat Export",
            "",
            f"**Chat Name:** {chat.name}",
            f"**Created:** {chat.created_at.strftime('%Y-%m-%d %H:%M:%S') if chat.created_at else 'N/A'}",
            f"**Last Updated:** {chat.updated_at.strftime('%Y-%m-%d %H:%M:%S') if chat.updated_at else 'N/A'}",
            "",
            "---",
            ""
        ]

        # Vehicle metrics summary
        if chat.parsed_metrics:
            lines.append("## Vehicle Metrics Summary")
            lines.append("")
            lines.append("| Metric | Value | Unit | Status |")
            lines.append("|--------|-------|------|--------|")

            for metric in chat.parsed_metrics:
                status = metric.get("status", "unknown")
                status_emoji = {"critical": "🔴", "warning": "🟡", "normal": "🟢"}.get(status, "⚪")
                lines.append(
                    f"| {metric.get('name', 'Unknown')} | "
                    f"{metric.get('value', 'N/A')} | "
                    f"{metric.get('unit', '')} | "
                    f"{status_emoji} {status.capitalize()} |"
                )
            lines.append("")

        # Fault codes
        if chat.fault_codes:
            lines.append("## Fault Codes")
            lines.append("")

            for code in chat.fault_codes:
                severity = code.get("severity", "unknown")
                severity_emoji = {"critical": "🔴", "warning": "🟡", "info": "ℹ️"}.get(severity, "⚪")
                lines.append(f"### {severity_emoji} {code.get('code', 'Unknown')}")
                lines.append("")
                lines.append(f"**Description:** {code.get('description', 'No description')}")
                lines.append(f"**Severity:** {severity.capitalize()}")
                lines.append(f"**Category:** {code.get('category', 'Unknown')}")

                if code.get("possible_causes"):
                    lines.append("")
                    lines.append("**Possible Causes:**")
                    for cause in code.get("possible_causes", []):
                        lines.append(f"- {cause}")

                if code.get("recommended_action"):
                    lines.append("")
                    lines.append(f"**Recommended Action:** {code.get('recommended_action')}")

                lines.append("")
        else:
            lines.append("## Fault Codes")
            lines.append("")
            lines.append("✅ No fault codes detected")
            lines.append("")

        # Conversation
        lines.append("---")
        lines.append("")
        lines.append("## Conversation")
        lines.append("")

        for message in messages:
            role_label = "👤 **You**" if message.role == "user" else "🤖 **InsightBot**"
            timestamp = message.created_at.strftime("%H:%M:%S") if message.created_at else ""

            severity_badge = ""
            if message.severity == "critical":
                severity_badge = " 🔴 `CRITICAL`"
            elif message.severity == "warning":
                severity_badge = " 🟡 `WARNING`"

            lines.append(f"### {role_label}{severity_badge}")
            lines.append(f"*{timestamp}*")
            lines.append("")
            lines.append(message.content)
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("*Exported from OBD InsightBot*")

        return "\n".join(lines)

    @staticmethod
    def get_chats_by_date(user_id: int, date: datetime) -> List[Chat]:
        """
        Get chats for a specific date (BR3.1).

        Args:
            user_id: User's ID
            date: Date to filter by

        Returns:
            List of chats created on the specified date
        """
        with DatabaseSession() as session:
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = date.replace(hour=23, minute=59, second=59, microsecond=999999)

            chats = session.query(Chat).filter(
                Chat.user_id == user_id,
                Chat.created_at >= start_of_day,
                Chat.created_at <= end_of_day
            ).order_by(Chat.created_at.desc()).all()

            for chat in chats:
                session.expunge(chat)

            return chats

    @staticmethod
    def search_chats(user_id: int, query: str) -> List[Chat]:
        """
        Search chats by name or content.

        Args:
            user_id: User's ID
            query: Search query

        Returns:
            List of matching chats
        """
        with DatabaseSession() as session:
            chats = session.query(Chat).filter(
                Chat.user_id == user_id,
                Chat.name.ilike(f"%{query}%")
            ).order_by(Chat.updated_at.desc()).all()

            for chat in chats:
                session.expunge(chat)

            return chats
