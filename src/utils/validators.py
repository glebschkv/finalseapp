"""
Input validation utilities.
Enhanced with security features and comprehensive validation.
"""

import re
import html
from typing import Tuple, Optional
from pathlib import Path


class InputSanitizer:
    """Sanitization utilities for user input."""

    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """
        Sanitize a string input to prevent injection attacks.

        Args:
            value: Input string to sanitize
            max_length: Maximum allowed length

        Returns:
            Sanitized string
        """
        if not value:
            return ""

        # Truncate to max length
        value = value[:max_length]

        # Remove null bytes and control characters (except newline, tab)
        value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)

        # Normalize unicode
        import unicodedata
        value = unicodedata.normalize('NFKC', value)

        return value.strip()

    @staticmethod
    def sanitize_html(value: str) -> str:
        """
        Escape HTML entities to prevent XSS.

        Args:
            value: Input string

        Returns:
            HTML-escaped string
        """
        return html.escape(value) if value else ""

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize a filename to prevent path traversal.

        Args:
            filename: Input filename

        Returns:
            Sanitized filename
        """
        if not filename:
            return ""

        # Remove path separators and null bytes
        filename = re.sub(r'[/\\:\x00]', '', filename)

        # Remove leading/trailing dots and spaces
        filename = filename.strip('. ')

        # Limit length
        return filename[:255]

    @staticmethod
    def sanitize_path(path: str) -> Optional[str]:
        """
        Sanitize and validate a file path.

        Args:
            path: Input path

        Returns:
            Resolved absolute path or None if invalid
        """
        if not path:
            return None

        try:
            resolved = Path(path).resolve()
            # Check for path traversal attempts
            if '..' in str(resolved):
                return None
            return str(resolved)
        except (ValueError, OSError):
            return None


class Validators:
    """Collection of validation functions with enhanced security."""

    @staticmethod
    def validate_username(username: str) -> Tuple[bool, str]:
        """
        Validate username format.

        Args:
            username: Username to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not username:
            return False, "Username is required"

        if len(username) < 3:
            return False, "Username must be at least 3 characters"

        if len(username) > 50:
            return False, "Username must be at most 50 characters"

        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            return False, "Username can only contain letters, numbers, and underscores"

        return True, ""

    @staticmethod
    def validate_password(password: str) -> Tuple[bool, str]:
        """
        Validate password strength.

        Args:
            password: Password to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not password:
            return False, "Password is required"

        if len(password) < 6:
            return False, "Password must be at least 6 characters"

        if len(password) > 128:
            return False, "Password must be at most 128 characters"

        return True, ""

    @staticmethod
    def validate_passwords_match(password: str, confirm: str) -> Tuple[bool, str]:
        """
        Validate that passwords match.

        Args:
            password: Primary password
            confirm: Confirmation password

        Returns:
            Tuple of (is_valid, error_message)
        """
        if password != confirm:
            return False, "Passwords do not match"

        return True, ""

    @staticmethod
    def validate_file_path(file_path: str, expected_extension: str = ".csv") -> Tuple[bool, str]:
        """
        Validate a file path.

        Args:
            file_path: Path to validate
            expected_extension: Expected file extension

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not file_path:
            return False, "File path is required"

        path = Path(file_path)

        if not path.exists():
            return False, "File does not exist"

        if not path.is_file():
            return False, "Path is not a file"

        if expected_extension and path.suffix.lower() != expected_extension.lower():
            return False, f"File must be a {expected_extension} file"

        return True, ""

    @staticmethod
    def validate_chat_name(name: str) -> Tuple[bool, str]:
        """
        Validate chat name.

        Args:
            name: Chat name to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not name:
            return False, "Chat name is required"

        if len(name) > 100:
            return False, "Chat name must be at most 100 characters"

        # Check for invalid characters
        if re.search(r'[<>:"/\\|?*]', name):
            return False, "Chat name contains invalid characters"

        return True, ""

    @staticmethod
    def validate_obd_fault_code(code: str) -> Tuple[bool, str]:
        """
        Validate OBD-II fault code format.

        Args:
            code: Fault code to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not code:
            return False, "Fault code is required"

        # OBD-II codes are in format: PXXXX, CXXXX, BXXXX, or UXXXX
        pattern = r'^[PCBU][0-9]{4}$'

        if not re.match(pattern, code.upper()):
            return False, "Invalid fault code format. Expected format: P0123, C0123, B0123, or U0123"

        return True, ""

    @staticmethod
    def validate_email(email: str) -> Tuple[bool, str]:
        """
        Validate email format (optional field).

        Args:
            email: Email to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not email:
            return True, ""  # Email is optional

        # Basic email pattern
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        if len(email) > 254:
            return False, "Email must be at most 254 characters"

        if not re.match(pattern, email):
            return False, "Invalid email format"

        return True, ""

    @staticmethod
    def validate_message_content(content: str) -> Tuple[bool, str]:
        """
        Validate chat message content.

        Args:
            content: Message content to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not content:
            return False, "Message cannot be empty"

        if len(content) > 10000:
            return False, "Message is too long (maximum 10,000 characters)"

        # Check for potentially malicious content
        suspicious_patterns = [
            r'<script[^>]*>',  # Script tags
            r'javascript:',    # JavaScript URLs
            r'data:text/html', # Data URLs
        ]

        for pattern in suspicious_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return False, "Message contains potentially unsafe content"

        return True, ""

    @staticmethod
    def validate_csv_content(content: str) -> Tuple[bool, str]:
        """
        Validate CSV content structure.

        Args:
            content: CSV content string

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not content:
            return False, "CSV content is empty"

        lines = content.strip().split('\n')
        if len(lines) < 2:
            return False, "CSV must have at least a header and one data row"

        # Check header
        header = lines[0].lower()
        obd_keywords = ['rpm', 'temp', 'speed', 'throttle', 'load', 'fault', 'engine', 'coolant']

        if not any(kw in header for kw in obd_keywords):
            return False, "CSV does not appear to contain OBD-II data"

        return True, ""

    @staticmethod
    def validate_positive_integer(value: any, name: str = "Value") -> Tuple[bool, str]:
        """
        Validate that a value is a positive integer.

        Args:
            value: Value to validate
            name: Name for error message

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            int_val = int(value)
            if int_val <= 0:
                return False, f"{name} must be a positive number"
            return True, ""
        except (TypeError, ValueError):
            return False, f"{name} must be a valid number"


class RateLimiter:
    """Simple in-memory rate limiter for preventing brute force attacks."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 300):
        """
        Initialize rate limiter.

        Args:
            max_attempts: Maximum attempts allowed in the time window
            window_seconds: Time window in seconds (default: 5 minutes)
        """
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict = {}  # {key: [(timestamp, count)]}

    def is_rate_limited(self, key: str) -> bool:
        """
        Check if a key is rate limited.

        Args:
            key: Identifier (e.g., username, IP address)

        Returns:
            True if rate limited, False otherwise
        """
        import time
        current_time = time.time()

        # Clean up old entries
        self._cleanup(current_time)

        if key not in self._attempts:
            return False

        attempts = self._attempts[key]
        recent_attempts = sum(
            1 for t in attempts
            if current_time - t < self.window_seconds
        )

        return recent_attempts >= self.max_attempts

    def record_attempt(self, key: str) -> None:
        """
        Record an attempt for a key.

        Args:
            key: Identifier (e.g., username, IP address)
        """
        import time
        current_time = time.time()

        if key not in self._attempts:
            self._attempts[key] = []

        self._attempts[key].append(current_time)

    def reset(self, key: str) -> None:
        """
        Reset attempts for a key (e.g., after successful login).

        Args:
            key: Identifier to reset
        """
        if key in self._attempts:
            del self._attempts[key]

    def _cleanup(self, current_time: float) -> None:
        """Remove expired entries."""
        keys_to_remove = []

        for key, attempts in self._attempts.items():
            # Keep only recent attempts
            self._attempts[key] = [
                t for t in attempts
                if current_time - t < self.window_seconds
            ]

            # Mark empty entries for removal
            if not self._attempts[key]:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._attempts[key]

    def get_remaining_lockout_time(self, key: str) -> int:
        """
        Get remaining lockout time in seconds.

        Args:
            key: Identifier

        Returns:
            Seconds until rate limit expires, or 0 if not limited
        """
        import time

        if key not in self._attempts or not self._attempts[key]:
            return 0

        oldest_attempt = min(self._attempts[key])
        remaining = self.window_seconds - (time.time() - oldest_attempt)

        return max(0, int(remaining))
