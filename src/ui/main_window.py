"""
Main Application Window.
Coordinates login and chat screens.
"""

from PyQt6.QtWidgets import QMainWindow, QStackedWidget, QMessageBox, QStatusBar, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent

from .styles import Styles
from .login_screen import LoginScreen
from .chat_screen import ChatScreen
from ..models.base import init_database
from ..models.user import User
from ..services.granite_client import GraniteClient
from ..config.logging_config import get_logger

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """
    Main application window.
    Manages navigation between login and chat screens.
    """

    def __init__(self):
        super().__init__()
        self.current_user = None
        self.session_token = None

        # Initialize database
        init_database()

        self.setup_ui()
        self._setup_status_bar()

    def setup_ui(self):
        """Set up the main window UI."""
        self.setWindowTitle("OBD InsightBot - Vehicle Diagnostics")
        self.setMinimumSize(1200, 800)
        self.setStyleSheet(Styles.MAIN_STYLE)

        # Stacked widget for screen navigation
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # Login screen
        self.login_screen = LoginScreen()
        self.login_screen.login_successful.connect(self._on_login_success)
        self.stack.addWidget(self.login_screen)

        # Chat screen placeholder (created on login)
        self.chat_screen = None

        logger.info("Main window initialized")

    def _setup_status_bar(self):
        """Set up the status bar with connection info."""
        status_bar = QStatusBar()
        status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #0F172A;
                color: #94A3B8;
                font-size: 12px;
                padding: 2px 8px;
                border-top: 1px solid #1E293B;
            }
            QStatusBar QLabel {
                color: #94A3B8;
                padding: 0 8px;
            }
        """)
        self.setStatusBar(status_bar)

        # AI status indicator
        self._ai_status_label = QLabel()
        status_bar.addPermanentWidget(self._ai_status_label)

        # Update AI status
        self._update_ai_status()

    def _update_ai_status(self):
        """Update the AI backend status in the status bar."""
        try:
            client = GraniteClient(enable_cache=False)
            info = client.get_model_info()
            backend = info.get("backend", "unknown")

            if backend == "ollama":
                model = info.get("model", "unknown")
                self._ai_status_label.setText(f"AI: {model} (Ollama)")
                self._ai_status_label.setStyleSheet("color: #4ADE80; padding: 0 8px;")
            else:
                self._ai_status_label.setText("AI: Demo Mode")
                self._ai_status_label.setStyleSheet("color: #FBBF24; padding: 0 8px;")
        except Exception:
            self._ai_status_label.setText("AI: Unknown")
            self._ai_status_label.setStyleSheet("color: #94A3B8; padding: 0 8px;")

    def _on_login_success(self, user: User, token: str):
        """Handle successful login."""
        logger.info(f"User logged in: {user.username}")

        self.current_user = user
        self.session_token = token

        # Create chat screen
        if self.chat_screen:
            self.stack.removeWidget(self.chat_screen)
            self.chat_screen.deleteLater()

        self.chat_screen = ChatScreen(user, token)
        self.chat_screen.logout_requested.connect(self._on_logout)
        self.stack.addWidget(self.chat_screen)

        # Switch to chat screen
        self.stack.setCurrentWidget(self.chat_screen)

        # Update status bar
        self._update_ai_status()

    def _on_logout(self):
        """Handle logout."""
        logger.info(f"User logged out: {self.current_user.username if self.current_user else 'Unknown'}")

        self.current_user = None
        self.session_token = None

        # Reset login screen
        self.login_screen.reset()

        # Switch to login screen
        self.stack.setCurrentWidget(self.login_screen)

        # Clean up chat screen
        if self.chat_screen:
            self.stack.removeWidget(self.chat_screen)
            self.chat_screen.deleteLater()
            self.chat_screen = None

    def closeEvent(self, event: QCloseEvent):
        """Handle window close event with confirmation if AI is active."""
        # Check if there's an active AI worker
        if (self.chat_screen and
                hasattr(self.chat_screen, '_active_worker') and
                self.chat_screen._active_worker and
                self.chat_screen._active_worker.isRunning()):
            reply = QMessageBox.question(
                self,
                "Close Application",
                "An AI response is still being generated.\nAre you sure you want to close?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            # Cancel the worker
            self.chat_screen._cleanup_worker()

        # Logout if user is logged in
        if self.session_token:
            from ..services.auth_service import AuthService
            AuthService.logout(self.session_token)

        logger.info("Application closing")
        event.accept()
