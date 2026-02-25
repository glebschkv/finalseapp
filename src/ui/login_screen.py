"""
Login and Registration Screen.
Implements BR1: Account Management
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QMessageBox, QStackedWidget
)
from PyQt6.QtCore import Qt, pyqtSignal

from .styles import Styles
from ..services.auth_service import AuthService, AuthenticationError, RateLimitError
from ..utils.validators import Validators


_PRIMARY_BTN_STYLE = """
    QPushButton {
        min-height: 52px;
        font-size: 15px;
        font-weight: 700;
        border-radius: 14px;
        background-color: #6366F1;
        color: #FFFFFF;
        border: none;
        letter-spacing: 0.3px;
    }
    QPushButton:hover { background-color: #4F46E5; }
    QPushButton:pressed { background-color: #4338CA; }
    QPushButton:disabled { background-color: #C7D2FE; color: #6366F1; }
"""

_SECONDARY_BTN_STYLE = """
    QPushButton {
        background-color: #F8FAFC;
        color: #475569;
        border: 1.5px solid #CBD5E1;
        min-height: 52px;
        font-size: 15px;
        font-weight: 600;
        border-radius: 14px;
    }
    QPushButton:hover {
        background-color: #F1F5F9;
        border-color: #94A3B8;
        color: #0F172A;
    }
    QPushButton:pressed { background-color: #E2E8F0; }
    QPushButton:disabled {
        background-color: #F8FAFC;
        color: #CBD5E1;
        border-color: #E2E8F0;
    }
"""


class PasswordField(QWidget):
    """Password input field with show/hide toggle."""

    def __init__(self, placeholder: str = "Enter your password", parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Password input
        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.input)

        # Toggle button overlaid on right side
        self.toggle_btn = QPushButton("Show")
        self.toggle_btn.setFixedSize(52, 32)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #6366F1;
                border: none;
                font-size: 12px;
                font-weight: 600;
                padding: 0;
            }
            QPushButton:hover {
                color: #4F46E5;
            }
        """)
        self.toggle_btn.clicked.connect(self._toggle_visibility)
        layout.addWidget(self.toggle_btn)

    def _toggle_visibility(self):
        """Toggle password visibility."""
        if self.input.echoMode() == QLineEdit.EchoMode.Password:
            self.input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_btn.setText("Hide")
        else:
            self.input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_btn.setText("Show")

    def text(self):
        return self.input.text()

    def clear(self):
        self.input.clear()
        self.input.setEchoMode(QLineEdit.EchoMode.Password)
        self.toggle_btn.setText("Show")


class LoginScreen(QWidget):
    """
    Login and registration screen widget.

    Implements:
    - BR1.1: User creates an account
    - BR1.2: User logs-in to their account
    """

    # Signals
    login_successful = pyqtSignal(object, str)  # (User, session_token)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        """Initialize the UI components."""
        # Dark gradient background
        self.setObjectName("loginBg")
        self.setStyleSheet("""
            QWidget#loginBg {
                background: qlineargradient(x1:0, y1:0, x2:0.7, y2:1,
                    stop:0 #0F172A, stop:0.4 #1E1B4B, stop:1 #0F172A);
            }
        """ + Styles.LOGIN_STYLE)

        # Main layout - centered
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.setSpacing(0)

        # Brand icon
        brand_icon = QLabel("\u25C6")
        brand_icon.setObjectName("brandIcon")
        brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(brand_icon)

        main_layout.addSpacing(12)

        # Title
        title = QLabel("InsightBot")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)

        main_layout.addSpacing(6)

        # Subtitle
        subtitle = QLabel("Smart Vehicle Diagnostics")
        subtitle.setObjectName("subtitleLabel")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(subtitle)

        main_layout.addSpacing(36)

        # White card container
        card = QFrame()
        card.setObjectName("loginCard")
        card.setFixedWidth(420)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(0)
        card_layout.setContentsMargins(36, 36, 36, 36)

        # Stacked widget for login/register forms
        self.stacked_widget = QStackedWidget()

        # Login form
        self.login_form = self._create_login_form()
        self.stacked_widget.addWidget(self.login_form)

        # Register form
        self.register_form = self._create_register_form()
        self.stacked_widget.addWidget(self.register_form)

        card_layout.addWidget(self.stacked_widget)

        # Center the card
        card_wrapper = QHBoxLayout()
        card_wrapper.addStretch()
        card_wrapper.addWidget(card)
        card_wrapper.addStretch()
        main_layout.addLayout(card_wrapper)

        main_layout.addSpacing(32)

        # Footer
        footer = QLabel("Powered by IBM Granite AI")
        footer.setObjectName("footerLabel")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(footer)

    def _create_login_form(self) -> QWidget:
        """Create the login form."""
        form = QWidget()
        form.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(form)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Card header
        header = QLabel("Welcome back")
        header.setObjectName("cardTitle")
        layout.addWidget(header)

        layout.addSpacing(4)

        sub = QLabel("Sign in to your account to continue")
        sub.setObjectName("cardSubtitle")
        layout.addWidget(sub)

        layout.addSpacing(28)

        # Username label + field
        username_label = QLabel("Username")
        username_label.setObjectName("inputLabel")
        layout.addWidget(username_label)
        layout.addSpacing(6)

        self.login_username = QLineEdit()
        self.login_username.setPlaceholderText("Enter your username")
        layout.addWidget(self.login_username)

        layout.addSpacing(16)

        # Password label + field
        password_label = QLabel("Password")
        password_label.setObjectName("inputLabel")
        layout.addWidget(password_label)
        layout.addSpacing(6)

        self.login_password_field = PasswordField("Enter your password")
        layout.addWidget(self.login_password_field)

        # Error label
        self.login_error = QLabel()
        self.login_error.setObjectName("errorLabel")
        self.login_error.setWordWrap(True)
        self.login_error.hide()
        layout.addSpacing(8)
        layout.addWidget(self.login_error)

        layout.addSpacing(24)

        # Login button
        self.login_btn = QPushButton("Sign In")
        self.login_btn.setObjectName("primaryButton")
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_btn.setStyleSheet(_PRIMARY_BTN_STYLE)
        self.login_btn.clicked.connect(self._handle_login)
        layout.addWidget(self.login_btn)

        layout.addSpacing(16)

        # Divider
        divider_layout = QHBoxLayout()
        divider_layout.setSpacing(16)
        divider_left = QFrame()
        divider_left.setObjectName("dividerLine")
        divider_left.setFixedHeight(1)
        divider_layout.addWidget(divider_left)
        or_label = QLabel("or")
        or_label.setObjectName("dividerText")
        divider_layout.addWidget(or_label)
        divider_right = QFrame()
        divider_right.setObjectName("dividerLine")
        divider_right.setFixedHeight(1)
        divider_layout.addWidget(divider_right)
        layout.addLayout(divider_layout)

        layout.addSpacing(16)

        # Register link
        register_btn = QPushButton("Create Account")
        register_btn.setObjectName("secondaryButton")
        register_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        register_btn.setStyleSheet(_SECONDARY_BTN_STYLE)
        register_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        layout.addWidget(register_btn)

        # Enter key handling
        self.login_password_field.input.returnPressed.connect(self._handle_login)

        return form

    def _create_register_form(self) -> QWidget:
        """Create the registration form."""
        form = QWidget()
        form.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(form)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Card header
        header = QLabel("Create account")
        header.setObjectName("cardTitle")
        layout.addWidget(header)

        layout.addSpacing(4)

        sub = QLabel("Get started with vehicle diagnostics")
        sub.setObjectName("cardSubtitle")
        layout.addWidget(sub)

        layout.addSpacing(28)

        # Username label + field
        username_label = QLabel("Username")
        username_label.setObjectName("inputLabel")
        layout.addWidget(username_label)
        layout.addSpacing(6)

        self.register_username = QLineEdit()
        self.register_username.setPlaceholderText("Choose a username")
        layout.addWidget(self.register_username)

        layout.addSpacing(16)

        # Password label + field
        password_label = QLabel("Password")
        password_label.setObjectName("inputLabel")
        layout.addWidget(password_label)
        layout.addSpacing(6)

        self.register_password_field = PasswordField("Create a password")
        layout.addWidget(self.register_password_field)

        layout.addSpacing(16)

        # Confirm password label + field
        confirm_label = QLabel("Confirm Password")
        confirm_label.setObjectName("inputLabel")
        layout.addWidget(confirm_label)
        layout.addSpacing(6)

        self.register_confirm_field = PasswordField("Confirm your password")
        layout.addWidget(self.register_confirm_field)

        # Error label
        self.register_error = QLabel()
        self.register_error.setObjectName("errorLabel")
        self.register_error.setWordWrap(True)
        self.register_error.hide()
        layout.addSpacing(8)
        layout.addWidget(self.register_error)

        layout.addSpacing(24)

        # Register button
        self.register_btn = QPushButton("Create Account")
        self.register_btn.setObjectName("primaryButton")
        self.register_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.register_btn.setStyleSheet(_PRIMARY_BTN_STYLE)
        self.register_btn.clicked.connect(self._handle_register)
        layout.addWidget(self.register_btn)

        layout.addSpacing(16)

        # Back to login
        back_btn = QPushButton("Back to Sign In")
        back_btn.setObjectName("secondaryButton")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet(_SECONDARY_BTN_STYLE)
        back_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        layout.addWidget(back_btn)

        return form

    def _set_login_loading(self, loading: bool):
        """Set login form loading state."""
        self.login_btn.setEnabled(not loading)
        self.login_username.setEnabled(not loading)
        self.login_password_field.input.setEnabled(not loading)
        self.login_btn.setText("Signing in..." if loading else "Sign In")

    def _set_register_loading(self, loading: bool):
        """Set register form loading state."""
        self.register_btn.setEnabled(not loading)
        self.register_username.setEnabled(not loading)
        self.register_password_field.input.setEnabled(not loading)
        self.register_confirm_field.input.setEnabled(not loading)
        self.register_btn.setText("Creating account..." if loading else "Create Account")

    def _handle_login(self):
        """Handle login attempt (BR1.2)."""
        username = self.login_username.text().strip()
        password = self.login_password_field.text()

        # Validate
        valid, error = Validators.validate_username(username)
        if not valid:
            self._show_login_error(error)
            return

        self._set_login_loading(True)

        try:
            user, token = AuthService.login(username, password)
            self.login_error.hide()
            self._set_login_loading(False)
            self.login_successful.emit(user, token)
        except (AuthenticationError, RateLimitError) as e:
            self._set_login_loading(False)
            self._show_login_error(str(e))

    def _handle_register(self):
        """Handle registration attempt (BR1.1)."""
        username = self.register_username.text().strip()
        password = self.register_password_field.text()
        confirm = self.register_confirm_field.text()

        # Validate username
        valid, error = Validators.validate_username(username)
        if not valid:
            self._show_register_error(error)
            return

        # Validate password
        valid, error = Validators.validate_password(password)
        if not valid:
            self._show_register_error(error)
            return

        # Validate passwords match
        valid, error = Validators.validate_passwords_match(password, confirm)
        if not valid:
            self._show_register_error(error)
            return

        self._set_register_loading(True)

        try:
            user = AuthService.register(username, password)
            self.register_error.hide()
            self._set_register_loading(False)

            # Show success and switch to login
            QMessageBox.information(
                self,
                "Account Created",
                f"Account '{username}' created successfully!\nPlease sign in."
            )

            # Clear fields and switch to login
            self.register_username.clear()
            self.register_password_field.clear()
            self.register_confirm_field.clear()
            self.login_username.setText(username)
            self.stacked_widget.setCurrentIndex(0)

        except (AuthenticationError, RateLimitError) as e:
            self._set_register_loading(False)
            self._show_register_error(str(e))

    def _show_login_error(self, message: str):
        """Display login error message."""
        self.login_error.setText(message)
        self.login_error.show()

    def _show_register_error(self, message: str):
        """Display registration error message."""
        self.register_error.setText(message)
        self.register_error.show()

    def reset(self):
        """Reset the form fields."""
        self.login_username.clear()
        self.login_password_field.clear()
        self.login_error.hide()
        self.register_username.clear()
        self.register_password_field.clear()
        self.register_confirm_field.clear()
        self.register_error.hide()
        self.stacked_widget.setCurrentIndex(0)
