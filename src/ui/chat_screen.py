"""
Main Chat Screen.
Implements BR2, BR3, BR4, BR5, BR8
"""

from typing import Optional
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QFrame, QListWidget, QListWidgetItem,
    QFileDialog, QMessageBox, QScrollArea,
    QMenu, QInputDialog, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer, QEvent
from PyQt6.QtGui import QShortcut, QKeySequence

from .styles import Styles, SeverityStyles
from ..models.user import User
from ..models.chat import Chat, Message
from ..services.chat_service import ChatService
from ..services.obd_parser import OBDParser, OBDParseError
from ..services.granite_client import GraniteClient
from ..services.rag_pipeline import RAGPipeline
from ..config.logging_config import get_logger

logger = get_logger(__name__)


class ThinkingIndicator(QFrame):
    """Animated thinking indicator shown when AI is processing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.dots = 0
        self.setup_ui()
        self.setup_animation()

    def setup_ui(self):
        """Set up the thinking indicator UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        # Thinking text with animated dots
        self.thinking_label = QLabel("Thinking")
        self.thinking_label.setStyleSheet("""
            color: #64748B;
            font-size: 14px;
            font-weight: 500;
        """)
        layout.addWidget(self.thinking_label)
        layout.addStretch()

        # Style the frame
        self.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-left: 3px solid #6366F1;
                border-radius: 12px;
            }
        """)

    def setup_animation(self):
        """Set up the dot animation timer."""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate_dots)
        self.timer.start(500)  # Update every 500ms

    def _animate_dots(self):
        """Animate the thinking dots."""
        self.dots = (self.dots + 1) % 4
        dots_text = "." * self.dots
        self.thinking_label.setText(f"Thinking{dots_text}")

    def stop(self):
        """Stop the animation."""
        self.timer.stop()


class MessageWidget(QFrame):
    """Widget for displaying a single message with severity styling (BR8)."""

    def __init__(self, message: dict, parent=None):
        super().__init__(parent)
        self.message = message
        self.setup_ui()

    def setup_ui(self):
        """Set up the message widget UI."""
        role = self.message.get("role", "assistant")
        content = self.message.get("content", "")
        severity = self.message.get("severity", "normal")
        timestamp = self.message.get("timestamp")

        # Main horizontal layout with avatar
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Avatar
        avatar = QLabel("AI" if role == "assistant" else "U")
        avatar.setFixedSize(34, 34)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if role == "assistant":
            avatar.setStyleSheet("""
                background-color: #EEF2FF;
                color: #6366F1;
                border-radius: 17px;
                font-size: 11px;
                font-weight: 700;
            """)
        else:
            avatar.setStyleSheet("""
                background-color: #0F172A;
                color: #FFFFFF;
                border-radius: 17px;
                font-size: 12px;
                font-weight: 600;
            """)
        main_layout.addWidget(avatar)

        # Content container
        content_frame = QFrame()
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)

        # Header row with name, severity badge, and timestamp
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        # Role name
        role_name = "InsightBot" if role == "assistant" else "You"
        name_label = QLabel(role_name)
        name_label.setStyleSheet("""
            font-weight: 600;
            color: #0F172A;
            font-size: 13px;
            background-color: transparent;
        """)
        header_layout.addWidget(name_label)

        # Severity badge for assistant messages (non-normal)
        if role == "assistant" and severity and severity.lower() != "normal":
            style = SeverityStyles.get(severity)
            severity_badge = QLabel(style['name'])
            severity_badge.setStyleSheet(f"""
                background-color: {style['badge_bg']};
                color: {style['badge_text']};
                border-radius: 10px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 600;
            """)
            severity_badge.setFixedHeight(20)
            header_layout.addWidget(severity_badge)

        # Timestamp
        time_str = ""
        if timestamp:
            try:
                if isinstance(timestamp, str):
                    dt = datetime.fromisoformat(timestamp)
                elif isinstance(timestamp, datetime):
                    dt = timestamp
                else:
                    dt = None
                if dt:
                    time_str = dt.strftime("%-I:%M %p") if hasattr(dt, 'strftime') else ""
            except (ValueError, OSError):
                pass
        if not time_str:
            time_str = datetime.now().strftime("%-I:%M %p")

        time_label = QLabel(time_str)
        time_label.setStyleSheet("""
            color: #94A3B8;
            font-size: 11px;
            font-weight: 400;
            background-color: transparent;
        """)
        header_layout.addWidget(time_label)

        header_layout.addStretch()

        # Copy button for assistant messages
        if role == "assistant":
            self._copy_btn = QPushButton("Copy")
            self._copy_btn.setFixedHeight(22)
            self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._copy_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #94A3B8;
                    border: 1px solid #E2E8F0;
                    border-radius: 6px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #F1F5F9;
                    color: #475569;
                    border-color: #CBD5E1;
                }
                QPushButton:pressed {
                    background-color: #E2E8F0;
                    color: #0F172A;
                    border-color: #94A3B8;
                }
            """)
            self._copy_btn.clicked.connect(lambda: self._copy_content(content))
            header_layout.addWidget(self._copy_btn)

        content_layout.addLayout(header_layout)

        # Message content bubble
        bubble = QFrame()
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(14, 14, 14, 14)
        bubble_layout.setSpacing(0)

        # Apply styling based on role and severity
        if role == "assistant":
            style = SeverityStyles.get(severity)
            bubble.setStyleSheet(f"""
                QFrame {{
                    background-color: {style['background']};
                    border-left: 3px solid {style['border']};
                    border-radius: 12px;
                }}
            """)
        else:
            bubble.setStyleSheet("""
                QFrame {
                    background-color: #EEF2FF;
                    border-radius: 12px;
                }
            """)

        # Content text
        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content_label.setStyleSheet("""
            color: #0F172A;
            background-color: transparent;
            font-size: 14px;
        """)
        bubble_layout.addWidget(content_label)

        content_layout.addWidget(bubble)
        main_layout.addWidget(content_frame, stretch=1)

        # Transparent frame background
        self.setStyleSheet("QFrame { background-color: transparent; }")

    def _copy_content(self, text: str):
        """Copy message content to clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        self._copy_btn.setText("Copied!")
        QTimer.singleShot(1500, lambda: self._copy_btn.setText("Copy"))


class ChatWorker(QThread):
    """Worker thread for processing chat queries."""

    response_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, rag_pipeline: RAGPipeline, query: str, chat_id: int, context: dict):
        super().__init__()
        self.rag_pipeline = rag_pipeline
        self.query = query
        self.chat_id = chat_id
        self.context = context
        self._cancelled = False

    def run(self):
        """Process the query in background."""
        try:
            if self._cancelled:
                return
            response = self.rag_pipeline.query(
                self.query,
                self.chat_id,
                self.context
            )
            if not self._cancelled:
                self.response_ready.emit({
                    "response": response.response,
                    "severity": response.severity
                })
        except Exception as e:
            if not self._cancelled:
                logger.error(f"Chat worker error: {e}")
                self.error_occurred.emit(str(e))

    def cancel(self):
        """Mark this worker as cancelled."""
        self._cancelled = True


class ChatScreen(QWidget):
    """
    Main chat interface.

    Implements:
    - BR2: File upload and chat creation
    - BR3: Chat history management
    - BR4: Vehicle status queries
    - BR5: Fault code explanation
    - BR8: Severity color coding
    """

    logout_requested = pyqtSignal()

    def __init__(self, user: User, session_token: str, parent=None):
        super().__init__(parent)
        self.user = user
        self.session_token = session_token
        self.current_chat: Optional[Chat] = None
        self.current_context: dict = {}
        self._active_worker: Optional[ChatWorker] = None

        # Initialize services
        self.obd_parser = OBDParser()
        self.granite_client = GraniteClient()
        self.rag_pipeline = RAGPipeline(self.granite_client)

        self.setup_ui()
        self._setup_shortcuts()
        self.load_chat_history()

    def setup_ui(self):
        """Set up the chat screen UI."""
        self.setStyleSheet(Styles.CHAT_STYLE)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar)

        # Main chat area
        chat_area = self._create_chat_area()
        main_layout.addWidget(chat_area, stretch=1)

    def _setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        # Ctrl+N: New chat
        new_chat_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        new_chat_shortcut.activated.connect(self._create_new_chat)

        # Escape: Cancel active AI response
        cancel_shortcut = QShortcut(QKeySequence("Escape"), self)
        cancel_shortcut.activated.connect(self._cancel_response)

    def _cancel_response(self):
        """Cancel the active AI response."""
        if self._active_worker and self._active_worker.isRunning():
            self._active_worker.cancel()
            self._hide_loading()
            self._add_message_widget({
                "role": "assistant",
                "content": "Response cancelled.",
                "severity": "normal"
            })

    def _create_sidebar(self) -> QFrame:
        """Create the sidebar with chat history."""
        sidebar = QFrame()
        sidebar.setObjectName("sidebarFrame")
        sidebar.setFixedWidth(280)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(16)

        # Header with app title
        header = QHBoxLayout()
        header.setSpacing(10)

        title = QLabel("InsightBot")
        title.setObjectName("sidebarTitle")
        header.addWidget(title)
        header.addStretch()

        # Settings/Logout button
        logout_btn = QPushButton("Settings")
        logout_btn.setObjectName("logoutButton")
        logout_btn.setFixedSize(72, 32)
        logout_btn.setToolTip("Settings & Logout")
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.clicked.connect(self._show_settings_menu)
        header.addWidget(logout_btn)
        layout.addLayout(header)

        # User label
        user_label = QLabel(f"@{self.user.username}")
        user_label.setObjectName("usernameLabel")
        layout.addWidget(user_label)

        # Spacer
        layout.addSpacing(8)

        # New chat button
        new_chat_btn = QPushButton("+  New Chat")
        new_chat_btn.setObjectName("newChatButton")
        new_chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_chat_btn.clicked.connect(self._create_new_chat)
        layout.addWidget(new_chat_btn)

        # Spacer
        layout.addSpacing(8)

        # Chat history section header
        history_label = QLabel("RECENT CHATS")
        history_label.setObjectName("historyLabel")
        layout.addWidget(history_label)

        # Chat history list
        self.chat_list = QListWidget()
        self.chat_list.setObjectName("chatList")
        self.chat_list.itemClicked.connect(self._on_chat_selected)
        self.chat_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.chat_list.customContextMenuRequested.connect(self._show_chat_context_menu)
        layout.addWidget(self.chat_list, stretch=1)

        return sidebar

    def _create_chat_area(self) -> QFrame:
        """Create the main chat area."""
        chat_frame = QFrame()
        chat_frame.setObjectName("chatFrame")
        layout = QVBoxLayout(chat_frame)
        layout.setContentsMargins(32, 24, 32, 20)
        layout.setSpacing(16)

        # Chat header
        self.chat_header = QLabel("Welcome to InsightBot")
        self.chat_header.setObjectName("chatHeader")
        self.chat_header.setStyleSheet("background: transparent;")
        layout.addWidget(self.chat_header)

        # Messages scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.messages_container = QWidget()
        self.messages_container.setStyleSheet("background: transparent;")
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.messages_layout.setSpacing(12)
        self.messages_layout.setContentsMargins(4, 12, 4, 12)
        self.scroll_area.setWidget(self.messages_container)
        layout.addWidget(self.scroll_area, stretch=1)

        # Welcome message
        self._show_welcome_message()

        # Input area - premium pill shape
        self.input_frame = QFrame()
        self.input_frame.setObjectName("inputFrame")
        self._input_frame_base_style = """
            QFrame#inputFrame {
                background-color: #FFFFFF;
                border-radius: 28px;
                border: 2px solid %s;
            }
        """
        self.input_frame.setStyleSheet(self._input_frame_base_style % "#E2E8F0")
        input_layout = QHBoxLayout(self.input_frame)
        input_layout.setContentsMargins(22, 10, 10, 10)
        input_layout.setSpacing(12)
        input_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Text input with auto-resize
        self.message_input = QTextEdit()
        self.message_input.setObjectName("messageInput")
        self.message_input.setPlaceholderText("Create a new chat to start messaging")
        self.message_input.setMinimumHeight(36)
        self.message_input.setMaximumHeight(120)
        self.message_input.setEnabled(False)
        self.message_input.setStyleSheet("""
            QTextEdit {
                border: none;
                background-color: transparent;
                padding: 8px 4px;
                font-size: 14px;
                color: #0F172A;
            }
            QTextEdit:focus {
                border: none;
                padding: 8px 4px;
            }
            QTextEdit:hover {
                border: none;
            }
            QTextEdit:disabled {
                background-color: transparent;
                color: #94A3B8;
            }
        """)
        self.message_input.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.message_input.textChanged.connect(self._adjust_input_height)
        self.message_input.installEventFilter(self)
        input_layout.addWidget(self.message_input, stretch=1)

        # Send button with arrow icon
        self.send_btn = QPushButton("\u27A4")
        self.send_btn.setObjectName("sendButton")
        self.send_btn.setFixedSize(48, 48)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.clicked.connect(self._send_message)
        self.send_btn.setEnabled(False)
        input_layout.addWidget(self.send_btn)

        layout.addWidget(self.input_frame)

        # Keyboard hint
        hint_label = QLabel("Enter to send  |  Shift+Enter for new line  |  Ctrl+N new chat")
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_label.setStyleSheet("""
            color: #CBD5E1;
            font-size: 11px;
            background-color: transparent;
            padding: 4px 0;
        """)
        layout.addWidget(hint_label)

        return chat_frame

    def _show_welcome_message(self):
        """Show initial welcome message - premium design."""
        # Container widget
        welcome_container = QWidget()
        welcome_container.setStyleSheet("background: transparent;")
        welcome_layout = QVBoxLayout(welcome_container)
        welcome_layout.setContentsMargins(40, 80, 40, 40)
        welcome_layout.setSpacing(0)
        welcome_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Brand accent
        accent = QLabel("\u25C6")
        accent.setAlignment(Qt.AlignmentFlag.AlignCenter)
        accent.setStyleSheet("""
            color: #6366F1;
            font-size: 28px;
            background: transparent;
        """)
        welcome_layout.addWidget(accent)

        welcome_layout.addSpacing(12)

        # Title
        title = QLabel("InsightBot")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            color: #0F172A;
            font-size: 36px;
            font-weight: 700;
            letter-spacing: -1px;
            background: transparent;
        """)
        welcome_layout.addWidget(title)

        welcome_layout.addSpacing(8)

        # Subtitle
        subtitle = QLabel("Your intelligent vehicle diagnostics assistant")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("""
            color: #64748B;
            font-size: 15px;
            font-weight: 400;
            background: transparent;
        """)
        welcome_layout.addWidget(subtitle)

        welcome_layout.addSpacing(48)

        # Steps card
        steps_card = QFrame()
        steps_card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 20px;
            }
        """)
        steps_card.setFixedWidth(420)
        steps_layout = QVBoxLayout(steps_card)
        steps_layout.setContentsMargins(32, 28, 32, 28)
        steps_layout.setSpacing(0)

        # Steps header
        steps_header = QLabel("GET STARTED")
        steps_header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        steps_header.setStyleSheet("""
            color: #94A3B8;
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 1.5px;
            background: transparent;
        """)
        steps_layout.addWidget(steps_header)

        steps_layout.addSpacing(20)

        # Steps as numbered list
        steps = [
            ("+ New Chat", "Create a new diagnostic session"),
            ("Upload CSV", "Add your OBD-II log file"),
            ("Ask Away", "Query anything about your vehicle")
        ]
        for i, (label, desc) in enumerate(steps, 1):
            step_row = QHBoxLayout()
            step_row.setSpacing(14)

            # Step number circle
            num_label = QLabel(str(i))
            num_label.setFixedSize(30, 30)
            num_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            num_label.setStyleSheet("""
                background-color: #EEF2FF;
                color: #6366F1;
                border-radius: 15px;
                font-size: 13px;
                font-weight: 700;
            """)
            step_row.addWidget(num_label)

            # Step text
            text_layout = QVBoxLayout()
            text_layout.setSpacing(2)

            title_label = QLabel(label)
            title_label.setStyleSheet("""
                color: #0F172A;
                font-size: 14px;
                font-weight: 600;
                background: transparent;
            """)
            text_layout.addWidget(title_label)

            desc_label = QLabel(desc)
            desc_label.setStyleSheet("""
                color: #64748B;
                font-size: 13px;
                background: transparent;
            """)
            text_layout.addWidget(desc_label)

            step_row.addLayout(text_layout)
            step_row.addStretch()
            steps_layout.addLayout(step_row)

            if i < len(steps):
                steps_layout.addSpacing(16)

        # Center the card
        card_container = QHBoxLayout()
        card_container.addStretch()
        card_container.addWidget(steps_card)
        card_container.addStretch()
        welcome_layout.addLayout(card_container)

        welcome_layout.addSpacing(32)

        # Start New Chat CTA button
        cta_container = QHBoxLayout()
        cta_container.addStretch()
        cta_btn = QPushButton("+  Start New Chat")
        cta_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cta_btn.setStyleSheet("""
            QPushButton {
                background-color: #6366F1;
                color: #FFFFFF;
                border-radius: 14px;
                padding: 14px 32px;
                font-size: 15px;
                font-weight: 700;
                border: none;
            }
            QPushButton:hover {
                background-color: #4F46E5;
            }
            QPushButton:pressed {
                background-color: #4338CA;
            }
        """)
        cta_btn.clicked.connect(self._create_new_chat)
        cta_container.addWidget(cta_btn)
        cta_container.addStretch()
        welcome_layout.addLayout(cta_container)

        welcome_layout.addSpacing(32)

        # Footer
        footer = QLabel("Powered by IBM Granite AI")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("""
            color: #CBD5E1;
            font-size: 12px;
            background: transparent;
        """)
        welcome_layout.addWidget(footer)

        welcome_layout.addStretch()
        self.messages_layout.addWidget(welcome_container)

    def load_chat_history(self):
        """Load user's chat history (BR3.1)."""
        self.chat_list.clear()
        chats = ChatService.get_user_chats(self.user.id)

        for chat in chats:
            # Truncate long names for sidebar
            display_name = chat.name
            if len(display_name) > 28:
                display_name = display_name[:25] + "..."
            item = QListWidgetItem(display_name)
            item.setData(Qt.ItemDataRole.UserRole, chat.id)
            item.setToolTip(chat.name)

            # Add severity indicator based on fault codes
            fault_codes = chat.fault_codes or []
            has_critical = any(
                f.get("severity") == "critical" for f in fault_codes
            )
            has_warning = any(
                f.get("severity") == "warning" for f in fault_codes
            )
            if has_critical:
                item.setForeground(Qt.GlobalColor.red)
            elif has_warning:
                item.setForeground(Qt.GlobalColor.yellow)

            self.chat_list.addItem(item)

    def _create_new_chat(self):
        """Create a new chat with file upload (BR2)."""
        # Open file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select OBD-II Log File",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )

        if not file_path:
            return

        # Validate and parse file
        try:
            is_valid, message = self.obd_parser.validate_file(file_path)

            if not is_valid:
                QMessageBox.warning(self, "Invalid File", message)
                return

            # Parse the file
            parsed_data = self.obd_parser.parse_csv(file_path)

            # Create chat
            chat = ChatService.create_chat(
                user_id=self.user.id,
                obd_log_path=file_path,
                parsed_data=parsed_data,
                name=f"Vehicle Diagnostic - {file_path.split('/')[-1]}"
            )

            # Index data for RAG
            self.rag_pipeline.index_obd_data(parsed_data, chat.id)

            # Refresh chat list and open new chat
            self.load_chat_history()
            self._load_chat(chat.id)

            # Show initial summary
            self._generate_initial_summary(parsed_data)

        except OBDParseError as e:
            QMessageBox.critical(self, "Parse Error", str(e))
        except Exception as e:
            logger.error(f"Error creating chat: {e}")
            QMessageBox.critical(self, "Error", f"Failed to create chat: {str(e)}")

    def _on_chat_selected(self, item: QListWidgetItem):
        """Handle chat selection from list."""
        chat_id = item.data(Qt.ItemDataRole.UserRole)
        self._load_chat(chat_id)

    def _load_chat(self, chat_id: int):
        """Load a chat and display its messages."""
        # Cancel any active worker before switching chats
        self._cleanup_worker()

        try:
            chat = ChatService.get_chat(chat_id, self.user.id)
            if not chat:
                logger.warning(f"Chat {chat_id} not found or access denied")
                QMessageBox.warning(self, "Error", "Could not load the selected chat.")
                return

            self.current_chat = chat
            self.current_context = {
                "metrics": chat.parsed_metrics or [],
                "fault_codes": chat.fault_codes or []
            }

            # Update header
            self.chat_header.setText(chat.name)

            # Clear messages
            self._clear_messages()

            # Load messages with error handling
            try:
                messages = ChatService.get_chat_messages(chat_id, self.user.id)
                for msg in messages:
                    try:
                        self._add_message_widget(msg.to_dict())
                    except Exception as e:
                        logger.error(f"Error displaying message {msg.id}: {e}")
            except Exception as e:
                logger.error(f"Error loading messages for chat {chat_id}: {e}")

            # Enable input
            self.message_input.setEnabled(True)
            self.message_input.setPlaceholderText("Ask about your vehicle...")
            self.send_btn.setEnabled(True)

            # Re-index data for RAG if needed (with error handling)
            try:
                if chat.parsed_metrics:
                    self.rag_pipeline.index_obd_data({
                        "metrics": chat.parsed_metrics,
                        "fault_codes": chat.fault_codes or [],
                        "statistics": {}
                    }, chat_id)
            except Exception as e:
                logger.error(f"Error indexing RAG data for chat {chat_id}: {e}")

        except Exception as e:
            logger.error(f"Error loading chat {chat_id}: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load chat: {str(e)}")

    def _clear_messages(self):
        """Clear all messages from the display."""
        while self.messages_layout.count():
            item = self.messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_message_widget(self, message: dict):
        """Add a message widget to the display."""
        widget = MessageWidget(message)
        self.messages_layout.addWidget(widget)

        # Scroll to bottom after layout update
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        """Scroll messages to bottom."""
        try:
            scrollbar = self.scroll_area.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            logger.debug(f"Could not scroll to bottom: {e}")

    def _adjust_input_height(self):
        """Adjust input height based on content."""
        doc_height = self.message_input.document().size().height()
        new_height = min(max(36, int(doc_height) + 12), 120)
        self.message_input.setFixedHeight(new_height)

    def eventFilter(self, obj, event):
        """Handle Enter key and input frame focus highlight."""
        if obj == self.message_input:
            if event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
                    if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                        self._send_message()
                        return True
            elif event.type() == QEvent.Type.FocusIn:
                self.input_frame.setStyleSheet(self._input_frame_base_style % "#6366F1")
            elif event.type() == QEvent.Type.FocusOut:
                self.input_frame.setStyleSheet(self._input_frame_base_style % "#E2E8F0")
        return super().eventFilter(obj, event)

    def _cleanup_worker(self):
        """Cancel and clean up the active worker thread."""
        if self._active_worker and self._active_worker.isRunning():
            self._active_worker.cancel()
            self._active_worker.response_ready.disconnect()
            self._active_worker.error_occurred.disconnect()
            self._active_worker = None
            self._hide_loading()

    def _send_message(self):
        """Send a message and get response (BR4, BR5)."""
        if not self.current_chat:
            return

        text = self.message_input.toPlainText().strip()
        if not text:
            return

        # Don't allow sending while worker is active
        if self._active_worker and self._active_worker.isRunning():
            return

        # Clear input
        self.message_input.clear()

        try:
            # Add user message
            user_msg = ChatService.add_message(
                self.current_chat.id,
                "user",
                text
            )
            self._add_message_widget(user_msg.to_dict())

            # Show loading indicator
            self._show_loading()

            # Process query in background
            self._active_worker = ChatWorker(
                self.rag_pipeline,
                text,
                self.current_chat.id,
                self.current_context
            )
            self._active_worker.response_ready.connect(self._on_response_ready)
            self._active_worker.error_occurred.connect(self._on_response_error)
            self._active_worker.start()

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self._hide_loading()
            self._add_message_widget({
                "role": "assistant",
                "content": "Sorry, there was an error processing your message. Please try again.",
                "severity": "warning"
            })

    def _show_loading(self):
        """Show loading indicator with thinking animation."""
        self.send_btn.setEnabled(False)
        self.message_input.setEnabled(False)

        # Add thinking indicator
        self.thinking_indicator = ThinkingIndicator()
        self.messages_layout.addWidget(self.thinking_indicator)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _hide_loading(self):
        """Hide loading indicator."""
        self.send_btn.setEnabled(True)
        self.message_input.setEnabled(True)
        self.message_input.setFocus()

        # Remove thinking indicator
        if hasattr(self, 'thinking_indicator') and self.thinking_indicator:
            self.thinking_indicator.stop()
            self.thinking_indicator.deleteLater()
            self.thinking_indicator = None

    def _on_response_ready(self, response: dict):
        """Handle response from worker."""
        self._hide_loading()
        self._active_worker = None

        # Guard against chat being deleted while waiting for response
        if not self.current_chat:
            return

        # Add assistant message
        msg = ChatService.add_message(
            self.current_chat.id,
            "assistant",
            response["response"],
            severity=response["severity"]
        )
        self._add_message_widget(msg.to_dict())

    def _on_response_error(self, error: str):
        """Handle error from worker."""
        self._hide_loading()
        self._active_worker = None

        # Provide actionable error messages
        if "Connection" in error or "connect" in error.lower():
            user_msg = (
                "Could not connect to the AI backend. "
                "Make sure Ollama is running: ollama serve"
            )
        elif "timeout" in error.lower():
            user_msg = (
                "The AI request timed out. This can happen with complex queries. "
                "Please try a simpler question or check that Ollama is running."
            )
        else:
            user_msg = f"I encountered an error: {error}\n\nPlease try again."

        self._add_message_widget({
            "role": "assistant",
            "content": user_msg,
            "severity": "warning"
        })

    def _generate_initial_summary(self, parsed_data: dict):
        """Generate initial vehicle summary after upload."""
        # Add system message about the upload
        metrics_count = len(parsed_data.get("metrics", []))
        fault_count = len(parsed_data.get("fault_codes", []))
        has_issues = parsed_data.get("has_issues", False)

        summary = f"I've analyzed your OBD-II log file and found:\n\n"
        summary += f"  {metrics_count} vehicle metrics\n"
        summary += f"  {fault_count} fault codes\n\n"

        if has_issues:
            summary += "Some readings need your attention. Ask me for a detailed summary!"
        else:
            summary += "Your vehicle appears to be in good condition!"

        self._add_message_widget({
            "role": "assistant",
            "content": summary,
            "severity": "warning" if has_issues else "normal"
        })

    def _show_chat_context_menu(self, position):
        """Show context menu for chat list (BR3.2, BR3.3, BR3.4)."""
        item = self.chat_list.itemAt(position)
        if not item:
            return

        chat_id = item.data(Qt.ItemDataRole.UserRole)

        menu = QMenu(self)

        # Rename action (BR3.3)
        rename_action = menu.addAction("Rename")
        rename_action.triggered.connect(lambda: self._rename_chat(chat_id, item))

        # Export action (BR3.4)
        export_action = menu.addAction("Export to .txt")
        export_action.triggered.connect(lambda: self._export_chat(chat_id))

        # Copy all messages
        copy_all_action = menu.addAction("Copy All Messages")
        copy_all_action.triggered.connect(lambda: self._copy_all_messages(chat_id))

        menu.addSeparator()

        # Delete action (BR3.2) - styled as destructive
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(lambda: self._delete_chat(chat_id))

        # Apply red styling to the delete action's menu widget
        for action in menu.actions():
            widget = menu.widgetForAction(action)
            if action == delete_action and widget:
                widget.setStyleSheet("color: #DC2626;")

        menu.exec(self.chat_list.mapToGlobal(position))

    def _rename_chat(self, chat_id: int, item: QListWidgetItem):
        """Rename a chat (BR3.3)."""
        new_name, ok = QInputDialog.getText(
            self, "Rename Chat", "Enter new name:",
            text=item.text()
        )

        if ok and new_name:
            ChatService.rename_chat(chat_id, self.user.id, new_name)
            item.setText(new_name)

            if self.current_chat and self.current_chat.id == chat_id:
                self.chat_header.setText(new_name)

    def _export_chat(self, chat_id: int):
        """Export chat to file (BR3.4) with error handling."""
        try:
            content = ChatService.export_chat(chat_id, self.user.id, "txt")

            if not content:
                QMessageBox.warning(self, "Export Failed", "Could not export chat.")
                return

            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export Chat", "chat_export.txt", "Text Files (*.txt)"
            )

            if file_path:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                QMessageBox.information(self, "Export Complete", f"Chat exported to {file_path}")

        except PermissionError:
            QMessageBox.critical(
                self, "Export Failed",
                "Permission denied. Try saving to a different location."
            )
        except OSError as e:
            QMessageBox.critical(
                self, "Export Failed",
                f"Could not write file: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Export error: {e}")
            QMessageBox.critical(
                self, "Export Failed",
                f"An unexpected error occurred: {str(e)}"
            )

    def _copy_all_messages(self, chat_id: int):
        """Copy all messages from a chat to clipboard."""
        try:
            content = ChatService.export_chat(chat_id, self.user.id, "txt")
            if content:
                clipboard = QApplication.clipboard()
                clipboard.setText(content)
                # Brief visual feedback would be nice but a message box is too intrusive
        except Exception as e:
            logger.error(f"Error copying messages: {e}")

    def _delete_chat(self, chat_id: int):
        """Delete a chat (BR3.2) with confirmation."""
        reply = QMessageBox.question(
            self, "Delete Chat",
            "Are you sure you want to delete this chat?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Cancel active worker if it's for this chat
            if self.current_chat and self.current_chat.id == chat_id:
                self._cleanup_worker()

            ChatService.delete_chat(chat_id, self.user.id)
            self.load_chat_history()

            if self.current_chat and self.current_chat.id == chat_id:
                self.current_chat = None
                self._clear_messages()
                self._show_welcome_message()
                self.chat_header.setText("Welcome to OBD InsightBot")
                self.message_input.setEnabled(False)
                self.message_input.setPlaceholderText("Create a new chat to start messaging")
                self.send_btn.setEnabled(False)

    def _show_settings_menu(self):
        """Show settings/logout menu."""
        menu = QMenu(self)

        # Model info
        model_info = self.granite_client.get_model_info()
        backend = model_info.get("backend", "unknown")
        if backend == "ollama":
            model_name = model_info.get("model", "unknown")
            status_action = menu.addAction(f"AI: {model_name} (Ollama)")
            status_action.setEnabled(False)
        elif backend == "mock":
            status_action = menu.addAction("AI: Demo Mode")
            status_action.setEnabled(False)

        menu.addSeparator()

        logout_action = menu.addAction("Logout")
        logout_action.triggered.connect(self._logout)

        # Get button position
        btn = self.sender()
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _logout(self):
        """Handle logout (BR1.3)."""
        self._cleanup_worker()
        from ..services.auth_service import AuthService
        AuthService.logout(self.session_token)
        self.logout_requested.emit()
