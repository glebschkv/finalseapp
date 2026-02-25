"""
Tests for Chat Service.
Tests BR3: Chat History
"""

import pytest
from src.services.chat_service import ChatService
from src.services.auth_service import AuthService
from src.models.base import init_database


class TestChatService:
    """Test suite for BR3: Chat History."""

    @pytest.fixture(autouse=True)
    def setup(self, test_db):
        """Set up test database and create test user."""
        init_database()
        AuthService._sessions.clear()
        self.user = AuthService.register("chatuser", "password123")

    def test_create_chat(self, sample_obd_csv):
        """Test chat creation."""
        from src.services.obd_parser import OBDParser
        parser = OBDParser()
        parsed_data = parser.parse_csv(sample_obd_csv)

        chat = ChatService.create_chat(
            user_id=self.user.id,
            obd_log_path=sample_obd_csv,
            parsed_data=parsed_data,
            name="Test Chat"
        )

        assert chat is not None
        assert chat.name == "Test Chat"
        assert chat.user_id == self.user.id

    def test_get_user_chats(self, sample_obd_csv):
        """BR3.1: User views chat history."""
        from src.services.obd_parser import OBDParser
        parser = OBDParser()
        parsed_data = parser.parse_csv(sample_obd_csv)

        # Create multiple chats
        ChatService.create_chat(self.user.id, sample_obd_csv, parsed_data, "Chat 1")
        ChatService.create_chat(self.user.id, sample_obd_csv, parsed_data, "Chat 2")

        chats = ChatService.get_user_chats(self.user.id)

        assert len(chats) == 2

    def test_delete_chat(self, sample_obd_csv):
        """BR3.2: User deletes chat history."""
        from src.services.obd_parser import OBDParser
        parser = OBDParser()
        parsed_data = parser.parse_csv(sample_obd_csv)

        chat = ChatService.create_chat(self.user.id, sample_obd_csv, parsed_data, "To Delete")

        result = ChatService.delete_chat(chat.id, self.user.id)
        assert result is True

        # Verify chat is deleted
        chats = ChatService.get_user_chats(self.user.id)
        assert len(chats) == 0

    def test_rename_chat(self, sample_obd_csv):
        """BR3.3: User renames chat log."""
        from src.services.obd_parser import OBDParser
        parser = OBDParser()
        parsed_data = parser.parse_csv(sample_obd_csv)

        chat = ChatService.create_chat(self.user.id, sample_obd_csv, parsed_data, "Original Name")

        updated = ChatService.rename_chat(chat.id, self.user.id, "New Name")

        assert updated is not None
        assert updated.name == "New Name"

    def test_export_chat(self, sample_obd_csv):
        """BR3.4: User exports chat log."""
        from src.services.obd_parser import OBDParser
        parser = OBDParser()
        parsed_data = parser.parse_csv(sample_obd_csv)

        chat = ChatService.create_chat(self.user.id, sample_obd_csv, parsed_data, "Export Test")

        # Add some messages
        ChatService.add_message(chat.id, "user", "What is wrong with my car?")
        ChatService.add_message(chat.id, "assistant", "Your car appears to be in good condition.", "normal")

        # Export
        export_content = ChatService.export_chat(chat.id, self.user.id, "txt")

        assert export_content is not None
        assert "Export Test" in export_content
        assert "What is wrong with my car?" in export_content
        assert "InsightBot" in export_content

    def test_add_message(self, sample_obd_csv):
        """Test adding messages to chat."""
        from src.services.obd_parser import OBDParser
        parser = OBDParser()
        parsed_data = parser.parse_csv(sample_obd_csv)

        chat = ChatService.create_chat(self.user.id, sample_obd_csv, parsed_data, "Message Test")

        # Add user message
        user_msg = ChatService.add_message(chat.id, "user", "Hello")
        assert user_msg.role == "user"
        assert user_msg.content == "Hello"

        # Add assistant message with severity
        assistant_msg = ChatService.add_message(
            chat.id, "assistant", "Hi there!", severity="normal"
        )
        assert assistant_msg.role == "assistant"
        assert assistant_msg.severity == "normal"

    def test_get_chat_messages(self, sample_obd_csv):
        """Test retrieving chat messages."""
        from src.services.obd_parser import OBDParser
        parser = OBDParser()
        parsed_data = parser.parse_csv(sample_obd_csv)

        chat = ChatService.create_chat(self.user.id, sample_obd_csv, parsed_data, "Messages Test")

        ChatService.add_message(chat.id, "user", "Message 1")
        ChatService.add_message(chat.id, "assistant", "Response 1")
        ChatService.add_message(chat.id, "user", "Message 2")

        messages = ChatService.get_chat_messages(chat.id, self.user.id)

        assert len(messages) == 3
        assert messages[0].content == "Message 1"
        assert messages[1].content == "Response 1"

    def test_chat_authorization(self, sample_obd_csv):
        """Test that users can only access their own chats."""
        from src.services.obd_parser import OBDParser
        parser = OBDParser()
        parsed_data = parser.parse_csv(sample_obd_csv)

        # Create chat for first user
        chat = ChatService.create_chat(self.user.id, sample_obd_csv, parsed_data, "Private Chat")

        # Create second user
        other_user = AuthService.register("otheruser", "password123")

        # Other user should not be able to access the chat
        retrieved = ChatService.get_chat(chat.id, other_user.id)
        assert retrieved is None

        # Other user should not be able to delete the chat
        result = ChatService.delete_chat(chat.id, other_user.id)
        assert result is False

    def test_delete_multiple_chats(self, sample_obd_csv):
        """Test deleting multiple chats at once."""
        from src.services.obd_parser import OBDParser
        parser = OBDParser()
        parsed_data = parser.parse_csv(sample_obd_csv)

        chat1 = ChatService.create_chat(self.user.id, sample_obd_csv, parsed_data, "Chat 1")
        chat2 = ChatService.create_chat(self.user.id, sample_obd_csv, parsed_data, "Chat 2")
        chat3 = ChatService.create_chat(self.user.id, sample_obd_csv, parsed_data, "Chat 3")

        deleted = ChatService.delete_multiple_chats([chat1.id, chat2.id], self.user.id)

        assert deleted == 2

        remaining = ChatService.get_user_chats(self.user.id)
        assert len(remaining) == 1
        assert remaining[0].name == "Chat 3"
