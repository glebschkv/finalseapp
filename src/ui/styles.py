"""
UI Styles and Themes for OBD InsightBot.
Premium design system with modern, high-end aesthetics.
Implements BR8: Severity color coding.
"""


class SeverityStyles:
    """Severity-based color schemes for BR8."""

    CRITICAL = {
        "background": "#FEF2F2",
        "border": "#F87171",
        "text": "#B91C1C",
        "badge_bg": "#DC2626",
        "badge_text": "#FFFFFF",
        "name": "Critical"
    }

    WARNING = {
        "background": "#FFFBEB",
        "border": "#FBBF24",
        "text": "#B45309",
        "badge_bg": "#D97706",
        "badge_text": "#FFFFFF",
        "name": "Warning"
    }

    NORMAL = {
        "background": "#F0FDF4",
        "border": "#4ADE80",
        "text": "#15803D",
        "badge_bg": "#16A34A",
        "badge_text": "#FFFFFF",
        "name": "Normal"
    }

    @classmethod
    def get(cls, severity: str) -> dict:
        """Get style dict for a severity level."""
        styles = {
            "critical": cls.CRITICAL,
            "warning": cls.WARNING,
            "normal": cls.NORMAL
        }
        if not severity:
            return cls.NORMAL
        return styles.get(severity.lower(), cls.NORMAL)


class Styles:
    """Application-wide styles - Premium Design System."""

    # ═══════════════════════════════════════════════════════════════
    # COLOR PALETTE
    # ═══════════════════════════════════════════════════════════════

    # Primary Accent (Indigo-Violet)
    ACCENT = "#6366F1"
    ACCENT_DARK = "#4F46E5"
    ACCENT_DARKER = "#4338CA"
    ACCENT_LIGHT = "#818CF8"
    ACCENT_SUBTLE = "#EEF2FF"

    # Neutral Colors (Slate-based)
    BG_PRIMARY = "#F8FAFC"
    BG_SECONDARY = "#F1F5F9"
    SURFACE = "#FFFFFF"
    SURFACE_MUTED = "#F1F5F9"

    # Text Colors
    TEXT_PRIMARY = "#0F172A"
    TEXT_SECONDARY = "#475569"
    TEXT_MUTED = "#94A3B8"
    TEXT_DISABLED = "#CBD5E1"

    # Border Colors
    BORDER = "#E2E8F0"
    BORDER_LIGHT = "#F1F5F9"
    BORDER_FOCUS = "#6366F1"

    # Sidebar Colors
    SIDEBAR_BG = "#0F172A"
    SIDEBAR_BG_DARK = "#020617"
    SIDEBAR_TEXT = "#F8FAFC"
    SIDEBAR_TEXT_MUTED = "#94A3B8"
    SIDEBAR_HOVER = "rgba(255, 255, 255, 0.06)"
    SIDEBAR_SELECTED = "rgba(99, 102, 241, 0.2)"

    # Status Colors
    ERROR = "#EF4444"
    SUCCESS = "#10B981"
    WARNING = "#F59E0B"

    # ═══════════════════════════════════════════════════════════════
    # MAIN APPLICATION STYLE
    # ═══════════════════════════════════════════════════════════════

    MAIN_STYLE = """
    /* ─── BASE ─── */

    QMainWindow {
        background-color: #F8FAFC;
    }

    QWidget {
        font-family: 'Inter', 'SF Pro Display', -apple-system, 'Segoe UI', system-ui, sans-serif;
        font-size: 14px;
        color: #0F172A;
    }

    /* ─── BUTTONS ─── */

    QPushButton {
        background-color: #6366F1;
        color: #FFFFFF;
        border: none;
        padding: 10px 20px;
        border-radius: 10px;
        font-weight: 600;
        font-size: 14px;
    }

    QPushButton:hover {
        background-color: #4F46E5;
    }

    QPushButton:pressed {
        background-color: #4338CA;
    }

    QPushButton:disabled {
        background-color: #E2E8F0;
        color: #94A3B8;
    }

    /* ─── TEXT INPUTS ─── */

    QLineEdit {
        padding: 12px 16px;
        border: 1.5px solid #E2E8F0;
        border-radius: 12px;
        background-color: #FFFFFF;
        color: #0F172A;
        font-size: 14px;
        selection-background-color: #6366F1;
        selection-color: white;
    }

    QLineEdit:hover {
        border-color: #CBD5E1;
    }

    QLineEdit:focus {
        border-color: #6366F1;
        border-width: 2px;
        padding: 11px 15px;
    }

    QLineEdit::placeholder {
        color: #94A3B8;
    }

    QTextEdit {
        padding: 12px 16px;
        border: 1.5px solid #E2E8F0;
        border-radius: 12px;
        background-color: #FFFFFF;
        color: #0F172A;
        font-size: 14px;
        selection-background-color: #6366F1;
        selection-color: white;
    }

    QTextEdit:hover {
        border-color: #CBD5E1;
    }

    QTextEdit:focus {
        border-color: #6366F1;
        border-width: 2px;
        padding: 11px 15px;
    }

    /* ─── LABELS ─── */

    QLabel {
        color: #0F172A;
        background-color: transparent;
    }

    /* ─── LIST WIDGETS ─── */

    QListWidget {
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        background-color: #FFFFFF;
        color: #0F172A;
        outline: none;
        padding: 4px;
    }

    QListWidget::item {
        padding: 12px 16px;
        border-radius: 8px;
        margin: 2px 4px;
        color: #0F172A;
        background-color: transparent;
    }

    QListWidget::item:selected {
        background-color: #EEF2FF;
        color: #4F46E5;
    }

    QListWidget::item:hover:!selected {
        background-color: #F1F5F9;
        color: #0F172A;
    }

    /* ─── SCROLLBARS ─── */

    QScrollArea {
        border: none;
        background-color: transparent;
    }

    QScrollBar:vertical {
        background-color: transparent;
        width: 6px;
        border-radius: 3px;
        margin: 4px 2px;
    }

    QScrollBar::handle:vertical {
        background-color: #CBD5E1;
        border-radius: 3px;
        min-height: 40px;
    }

    QScrollBar::handle:vertical:hover {
        background-color: #94A3B8;
    }

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {
        height: 0px;
    }

    QScrollBar:horizontal {
        background-color: transparent;
        height: 6px;
        border-radius: 3px;
        margin: 2px 4px;
    }

    QScrollBar::handle:horizontal {
        background-color: #CBD5E1;
        border-radius: 3px;
        min-width: 40px;
    }

    QScrollBar::handle:horizontal:hover {
        background-color: #94A3B8;
    }

    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {
        width: 0px;
    }

    /* ─── DIALOGS ─── */

    QMessageBox {
        background-color: #FFFFFF;
    }

    QMessageBox QLabel {
        color: #0F172A;
        font-size: 14px;
    }

    QMessageBox QPushButton {
        min-width: 100px;
        padding: 10px 24px;
        border-radius: 10px;
    }

    QDialog {
        background-color: #F8FAFC;
    }

    /* ─── MENUS ─── */

    QMenu {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 6px;
    }

    QMenu::item {
        padding: 10px 20px;
        border-radius: 8px;
        color: #0F172A;
        background-color: transparent;
        margin: 2px;
        font-size: 13px;
    }

    QMenu::item:selected {
        background-color: #F1F5F9;
        color: #0F172A;
    }

    QMenu::separator {
        height: 1px;
        background-color: #E2E8F0;
        margin: 6px 12px;
    }

    QInputDialog {
        background-color: #FFFFFF;
    }

    QInputDialog QLineEdit {
        min-width: 300px;
    }

    /* ─── TOOLTIPS ─── */

    QToolTip {
        background-color: #0F172A;
        color: #F8FAFC;
        border: none;
        border-radius: 8px;
        padding: 8px 14px;
        font-size: 13px;
    }
    """

    # ═══════════════════════════════════════════════════════════════
    # LOGIN SCREEN STYLE
    # ═══════════════════════════════════════════════════════════════

    LOGIN_STYLE = """
    QFrame#loginCard {
        background-color: #FFFFFF;
        border-radius: 24px;
        border: 1px solid rgba(255, 255, 255, 0.12);
    }

    QLabel#titleLabel {
        font-size: 38px;
        font-weight: 700;
        color: #FFFFFF;
        letter-spacing: -1px;
        background: transparent;
    }

    QLabel#subtitleLabel {
        font-size: 15px;
        color: rgba(255, 255, 255, 0.55);
        font-weight: 400;
        background: transparent;
    }

    QLabel#brandIcon {
        color: #818CF8;
        font-size: 36px;
        background: transparent;
    }

    QLabel#cardTitle {
        font-size: 22px;
        font-weight: 700;
        color: #0F172A;
        letter-spacing: -0.5px;
        background: transparent;
    }

    QLabel#cardSubtitle {
        font-size: 14px;
        color: #64748B;
        font-weight: 400;
        background: transparent;
    }

    QLabel#errorLabel {
        color: #DC2626;
        font-size: 13px;
        font-weight: 500;
        padding: 10px 14px;
        background-color: #FEF2F2;
        border-radius: 10px;
        border: 1px solid #FECACA;
    }

    QLabel#inputLabel {
        font-size: 13px;
        font-weight: 600;
        color: #374151;
        background: transparent;
    }

    QLineEdit {
        min-height: 48px;
        font-size: 14px;
        border-radius: 12px;
        border: 1.5px solid #E2E8F0;
        padding: 0 16px;
        background-color: #F8FAFC;
        color: #0F172A;
    }

    QLineEdit:hover {
        border-color: #CBD5E1;
        background-color: #FFFFFF;
    }

    QLineEdit:focus {
        border: 2px solid #6366F1;
        padding: 0 15px;
        background-color: #FFFFFF;
    }

    QPushButton#primaryButton {
        min-height: 52px;
        font-size: 15px;
        font-weight: 700;
        border-radius: 14px;
        background-color: #6366F1;
        color: #FFFFFF;
        border: none;
        letter-spacing: 0.3px;
    }

    QPushButton#primaryButton:hover {
        background-color: #4F46E5;
    }

    QPushButton#primaryButton:pressed {
        background-color: #4338CA;
    }

    QPushButton#primaryButton:disabled {
        background-color: #C7D2FE;
        color: #6366F1;
    }

    QPushButton#secondaryButton {
        background-color: #F8FAFC;
        color: #475569;
        border: 1.5px solid #CBD5E1;
        min-height: 52px;
        font-size: 15px;
        font-weight: 600;
        border-radius: 14px;
    }

    QPushButton#secondaryButton:hover {
        background-color: #F1F5F9;
        border-color: #94A3B8;
        color: #0F172A;
    }

    QPushButton#secondaryButton:pressed {
        background-color: #E2E8F0;
    }

    QPushButton#secondaryButton:disabled {
        background-color: #F8FAFC;
        color: #CBD5E1;
        border-color: #E2E8F0;
    }

    QLabel#dividerText {
        color: #94A3B8;
        font-size: 12px;
        font-weight: 500;
        background: transparent;
    }

    QFrame#dividerLine {
        background-color: #E2E8F0;
    }

    QLabel#footerLabel {
        color: rgba(255, 255, 255, 0.3);
        font-size: 12px;
        background: transparent;
    }
    """

    # ═══════════════════════════════════════════════════════════════
    # CHAT SCREEN STYLE
    # ═══════════════════════════════════════════════════════════════

    CHAT_STYLE = """
    /* ─── MAIN FRAME ─── */

    QFrame#chatFrame {
        background-color: #F8FAFC;
        border: none;
    }

    /* ─── SIDEBAR ─── */

    QFrame#sidebarFrame {
        background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #0F172A, stop:1 #1E1B4B);
        border-radius: 0px;
    }

    QLabel#sidebarTitle {
        color: #F8FAFC;
        font-size: 18px;
        font-weight: 700;
        letter-spacing: -0.3px;
    }

    QLabel#usernameLabel {
        color: #94A3B8;
        font-size: 13px;
        font-weight: 400;
    }

    QLabel#historyLabel {
        color: #64748B;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 1px;
        text-transform: uppercase;
    }

    /* ─── CHAT LIST ─── */

    QListWidget#chatList {
        background-color: transparent;
        border: none;
        outline: none;
        padding: 0px;
    }

    QListWidget#chatList::item {
        padding: 12px 14px;
        border-radius: 10px;
        color: #94A3B8;
        background-color: transparent;
        margin: 2px 4px;
        font-size: 13px;
        border-left: 3px solid transparent;
    }

    QListWidget#chatList::item:selected {
        background-color: rgba(99, 102, 241, 0.15);
        color: #FFFFFF;
        border-left: 3px solid #818CF8;
    }

    QListWidget#chatList::item:hover:!selected {
        background-color: rgba(255, 255, 255, 0.06);
        color: #E2E8F0;
    }

    /* ─── NEW CHAT BUTTON ─── */

    QPushButton#newChatButton {
        background-color: #6366F1;
        color: #FFFFFF;
        border-radius: 14px;
        padding: 14px 16px;
        font-size: 14px;
        font-weight: 700;
        border: none;
    }

    QPushButton#newChatButton:hover {
        background-color: #4F46E5;
    }

    QPushButton#newChatButton:pressed {
        background-color: #4338CA;
    }

    /* ─── SETTINGS/LOGOUT BUTTON ─── */

    QPushButton#logoutButton {
        background-color: rgba(255, 255, 255, 0.08);
        color: #E2E8F0;
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 10px;
        padding: 6px;
        font-size: 13px;
        font-weight: 500;
    }

    QPushButton#logoutButton:hover {
        background-color: rgba(255, 255, 255, 0.15);
        color: #FFFFFF;
        border-color: rgba(255, 255, 255, 0.2);
    }

    QPushButton#logoutButton:pressed {
        background-color: rgba(255, 255, 255, 0.06);
    }

    /* ─── CHAT HEADER ─── */

    QLabel#chatHeader {
        color: #0F172A;
        font-size: 18px;
        font-weight: 700;
        letter-spacing: -0.3px;
    }

    /* ─── MESSAGE INPUT ─── */

    QTextEdit#messageInput {
        border: none;
        border-radius: 0px;
        padding: 8px 4px;
        font-size: 14px;
        background-color: transparent;
        color: #0F172A;
        selection-background-color: #6366F1;
        selection-color: white;
    }

    QTextEdit#messageInput:hover {
        border: none;
    }

    QTextEdit#messageInput:focus {
        border: none;
        padding: 8px 4px;
    }

    QTextEdit#messageInput:disabled {
        background-color: transparent;
        color: #94A3B8;
        border: none;
    }

    /* ─── SEND BUTTON ─── */

    QPushButton#sendButton {
        background-color: #6366F1;
        border-radius: 14px;
        min-width: 48px;
        max-width: 48px;
        min-height: 48px;
        max-height: 48px;
        font-size: 18px;
        border: none;
        color: #FFFFFF;
        font-weight: bold;
    }

    QPushButton#sendButton:hover {
        background-color: #4F46E5;
    }

    QPushButton#sendButton:pressed {
        background-color: #4338CA;
    }

    QPushButton#sendButton:disabled {
        background-color: #E2E8F0;
        color: #94A3B8;
    }

    /* ─── SIDEBAR SCROLLBAR ─── */

    QListWidget#chatList QScrollBar:vertical {
        background-color: transparent;
        width: 6px;
        border-radius: 3px;
        margin: 4px 2px;
    }

    QListWidget#chatList QScrollBar::handle:vertical {
        background-color: rgba(255, 255, 255, 0.15);
        border-radius: 3px;
        min-height: 40px;
    }

    QListWidget#chatList QScrollBar::handle:vertical:hover {
        background-color: rgba(255, 255, 255, 0.25);
    }

    QListWidget#chatList QScrollBar::add-line:vertical,
    QListWidget#chatList QScrollBar::sub-line:vertical {
        height: 0px;
    }

    """

    # ═══════════════════════════════════════════════════════════════
    # MESSAGE BUBBLE STYLES
    # ═══════════════════════════════════════════════════════════════

    USER_MESSAGE_STYLE = """
    QFrame {
        background-color: #EEF2FF;
        border-radius: 12px;
        border: none;
        padding: 0px;
        margin: 0px;
    }
    QLabel {
        color: #0F172A;
        background-color: transparent;
    }
    """

    ASSISTANT_MESSAGE_STYLE = """
    QFrame {
        background-color: #FFFFFF;
        border-radius: 12px;
        border: 1px solid #E2E8F0;
        padding: 0px;
        margin: 0px;
    }
    QLabel {
        color: #0F172A;
        background-color: transparent;
    }
    """

    ERROR_MESSAGE_STYLE = """
    QFrame {
        background-color: #FEF2F2;
        border-left: 3px solid #F87171;
        border-radius: 12px;
        padding: 0px;
        margin: 0px;
    }
    QLabel {
        color: #B91C1C;
        background-color: transparent;
    }
    """

    WARNING_MESSAGE_STYLE = """
    QFrame {
        background-color: #FFFBEB;
        border-left: 3px solid #FBBF24;
        border-radius: 12px;
        padding: 0px;
        margin: 0px;
    }
    QLabel {
        color: #B45309;
        background-color: transparent;
    }
    """

    @classmethod
    def get_message_style(cls, severity: str) -> str:
        """Get message style based on severity (BR8)."""
        colors = SeverityStyles.get(severity)
        return f"""
        QFrame {{
            background-color: {colors['background']};
            border-left: 3px solid {colors['border']};
            border-radius: 12px;
            padding: 0px;
            margin: 0px;
        }}
        QLabel {{
            color: #0F172A;
            background-color: transparent;
        }}
        """

    @classmethod
    def get_severity_badge_style(cls, severity: str) -> str:
        """Get severity badge style (pill-shaped badge)."""
        colors = SeverityStyles.get(severity)
        return f"""
        QLabel {{
            background-color: {colors['badge_bg']};
            color: {colors['badge_text']};
            border-radius: 10px;
            padding: 4px 10px;
            font-size: 11px;
            font-weight: 600;
        }}
        """

    @classmethod
    def get_severity_indicator(cls, severity: str) -> str:
        """Get severity indicator HTML."""
        colors = SeverityStyles.get(severity)
        return f"""
        <span style="
            background-color: {colors['badge_bg']};
            color: {colors['badge_text']};
            padding: 3px 10px;
            border-radius: 10px;
            font-size: 11px;
            font-weight: 600;
        ">{colors['name']}</span>
        """
