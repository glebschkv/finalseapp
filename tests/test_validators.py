"""
Tests for input validation and sanitization utilities.
"""

import pytest
import time

from src.utils.validators import Validators, InputSanitizer, RateLimiter


class TestInputSanitizer:
    """Tests for InputSanitizer class."""

    def test_sanitize_string_basic(self):
        """Test basic string sanitization."""
        result = InputSanitizer.sanitize_string("  hello world  ")
        assert result == "hello world"

    def test_sanitize_string_max_length(self):
        """Test string truncation to max length."""
        long_string = "a" * 1500
        result = InputSanitizer.sanitize_string(long_string, max_length=1000)
        assert len(result) == 1000

    def test_sanitize_string_removes_null_bytes(self):
        """Test null byte removal."""
        dirty = "hello\x00world"
        result = InputSanitizer.sanitize_string(dirty)
        assert "\x00" not in result

    def test_sanitize_string_removes_control_chars(self):
        """Test control character removal."""
        dirty = "hello\x01\x02\x03world"
        result = InputSanitizer.sanitize_string(dirty)
        assert "\x01" not in result
        assert "\x02" not in result

    def test_sanitize_string_preserves_newlines(self):
        """Test newlines are preserved."""
        text = "hello\nworld"
        result = InputSanitizer.sanitize_string(text)
        assert "\n" in result

    def test_sanitize_string_empty(self):
        """Test empty string handling."""
        assert InputSanitizer.sanitize_string("") == ""
        assert InputSanitizer.sanitize_string(None) == ""

    def test_sanitize_html(self):
        """Test HTML escaping."""
        dirty = "<script>alert('xss')</script>"
        result = InputSanitizer.sanitize_html(dirty)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_sanitize_html_empty(self):
        """Test empty HTML handling."""
        assert InputSanitizer.sanitize_html("") == ""
        assert InputSanitizer.sanitize_html(None) == ""

    def test_sanitize_filename(self):
        """Test filename sanitization."""
        dirty = "../../../etc/passwd"
        result = InputSanitizer.sanitize_filename(dirty)
        assert "/" not in result
        assert "\\" not in result

    def test_sanitize_filename_removes_path_separators(self):
        """Test path separator removal."""
        result = InputSanitizer.sanitize_filename("path/to\\file.txt")
        assert "/" not in result
        assert "\\" not in result

    def test_sanitize_filename_strips_dots(self):
        """Test leading/trailing dots are stripped."""
        result = InputSanitizer.sanitize_filename("..filename..")
        assert not result.startswith(".")
        assert not result.endswith(".")

    def test_sanitize_filename_empty(self):
        """Test empty filename handling."""
        assert InputSanitizer.sanitize_filename("") == ""

    def test_sanitize_path_valid(self):
        """Test valid path sanitization."""
        result = InputSanitizer.sanitize_path("/home/user/file.txt")
        assert result is not None

    def test_sanitize_path_traversal_attempt(self):
        """Test path traversal detection."""
        result = InputSanitizer.sanitize_path("../../../etc/passwd")
        # Should resolve the path
        assert result is not None  # The resolved path won't contain literal ..

    def test_sanitize_path_empty(self):
        """Test empty path handling."""
        assert InputSanitizer.sanitize_path("") is None
        assert InputSanitizer.sanitize_path(None) is None


class TestValidators:
    """Tests for Validators class."""

    def test_validate_username_valid(self):
        """Test valid username."""
        is_valid, msg = Validators.validate_username("john_doe123")
        assert is_valid is True
        assert msg == ""

    def test_validate_username_too_short(self):
        """Test username too short."""
        is_valid, msg = Validators.validate_username("ab")
        assert is_valid is False
        assert "3 characters" in msg

    def test_validate_username_too_long(self):
        """Test username too long."""
        is_valid, msg = Validators.validate_username("a" * 51)
        assert is_valid is False
        assert "50 characters" in msg

    def test_validate_username_invalid_chars(self):
        """Test username with invalid characters."""
        is_valid, msg = Validators.validate_username("user@name!")
        assert is_valid is False
        assert "letters, numbers, and underscores" in msg

    def test_validate_username_empty(self):
        """Test empty username."""
        is_valid, msg = Validators.validate_username("")
        assert is_valid is False

    def test_validate_password_valid(self):
        """Test valid password."""
        is_valid, msg = Validators.validate_password("secure123")
        assert is_valid is True

    def test_validate_password_too_short(self):
        """Test password too short."""
        is_valid, msg = Validators.validate_password("12345")
        assert is_valid is False
        assert "6 characters" in msg

    def test_validate_password_too_long(self):
        """Test password too long."""
        is_valid, msg = Validators.validate_password("a" * 129)
        assert is_valid is False
        assert "128 characters" in msg

    def test_validate_password_empty(self):
        """Test empty password."""
        is_valid, msg = Validators.validate_password("")
        assert is_valid is False

    def test_validate_passwords_match(self):
        """Test matching passwords."""
        is_valid, msg = Validators.validate_passwords_match("password", "password")
        assert is_valid is True

    def test_validate_passwords_no_match(self):
        """Test non-matching passwords."""
        is_valid, msg = Validators.validate_passwords_match("password1", "password2")
        assert is_valid is False
        assert "do not match" in msg

    def test_validate_file_path_valid(self, tmp_path):
        """Test valid file path."""
        test_file = tmp_path / "test.csv"
        test_file.write_text("content")

        is_valid, msg = Validators.validate_file_path(str(test_file))
        assert is_valid is True

    def test_validate_file_path_not_exists(self):
        """Test non-existent file path."""
        is_valid, msg = Validators.validate_file_path("/nonexistent/file.csv")
        assert is_valid is False
        assert "does not exist" in msg

    def test_validate_file_path_wrong_extension(self, tmp_path):
        """Test file with wrong extension."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        is_valid, msg = Validators.validate_file_path(str(test_file), ".csv")
        assert is_valid is False
        assert ".csv" in msg

    def test_validate_file_path_empty(self):
        """Test empty file path."""
        is_valid, msg = Validators.validate_file_path("")
        assert is_valid is False
        assert "required" in msg

    def test_validate_chat_name_valid(self):
        """Test valid chat name."""
        is_valid, msg = Validators.validate_chat_name("My Vehicle Diagnostic")
        assert is_valid is True

    def test_validate_chat_name_too_long(self):
        """Test chat name too long."""
        is_valid, msg = Validators.validate_chat_name("a" * 101)
        assert is_valid is False
        assert "100 characters" in msg

    def test_validate_chat_name_invalid_chars(self):
        """Test chat name with invalid characters."""
        is_valid, msg = Validators.validate_chat_name("name<script>")
        assert is_valid is False
        assert "invalid characters" in msg

    def test_validate_obd_fault_code_valid(self):
        """Test valid fault codes."""
        test_codes = ["P0300", "C0035", "B1000", "U0100"]
        for code in test_codes:
            is_valid, msg = Validators.validate_obd_fault_code(code)
            assert is_valid is True, f"Code {code} should be valid"

    def test_validate_obd_fault_code_invalid(self):
        """Test invalid fault codes."""
        test_codes = ["X0300", "P030", "P03000", "12345"]
        for code in test_codes:
            is_valid, msg = Validators.validate_obd_fault_code(code)
            assert is_valid is False, f"Code {code} should be invalid"

    def test_validate_email_valid(self):
        """Test valid email."""
        is_valid, msg = Validators.validate_email("user@example.com")
        assert is_valid is True

    def test_validate_email_optional(self):
        """Test email is optional (empty is valid)."""
        is_valid, msg = Validators.validate_email("")
        assert is_valid is True

    def test_validate_email_invalid(self):
        """Test invalid email."""
        is_valid, msg = Validators.validate_email("not-an-email")
        assert is_valid is False

    def test_validate_message_content_valid(self):
        """Test valid message content."""
        is_valid, msg = Validators.validate_message_content("What is my vehicle status?")
        assert is_valid is True

    def test_validate_message_content_empty(self):
        """Test empty message content."""
        is_valid, msg = Validators.validate_message_content("")
        assert is_valid is False
        assert "empty" in msg

    def test_validate_message_content_too_long(self):
        """Test message content too long."""
        is_valid, msg = Validators.validate_message_content("a" * 10001)
        assert is_valid is False
        assert "10,000" in msg

    def test_validate_message_content_script_tag(self):
        """Test message with script tag."""
        is_valid, msg = Validators.validate_message_content("<script>alert('xss')</script>")
        assert is_valid is False
        assert "unsafe" in msg

    def test_validate_positive_integer_valid(self):
        """Test valid positive integer."""
        is_valid, msg = Validators.validate_positive_integer(5)
        assert is_valid is True

    def test_validate_positive_integer_zero(self):
        """Test zero is invalid."""
        is_valid, msg = Validators.validate_positive_integer(0)
        assert is_valid is False
        assert "positive" in msg

    def test_validate_positive_integer_negative(self):
        """Test negative number is invalid."""
        is_valid, msg = Validators.validate_positive_integer(-5)
        assert is_valid is False

    def test_validate_positive_integer_string(self):
        """Test string number is valid."""
        is_valid, msg = Validators.validate_positive_integer("5")
        assert is_valid is True

    def test_validate_positive_integer_invalid_string(self):
        """Test invalid string."""
        is_valid, msg = Validators.validate_positive_integer("abc")
        assert is_valid is False
        assert "valid number" in msg


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_rate_limiter_initialization(self):
        """Test rate limiter initializes correctly."""
        limiter = RateLimiter(max_attempts=5, window_seconds=300)
        assert limiter.max_attempts == 5
        assert limiter.window_seconds == 300

    def test_not_rate_limited_initially(self):
        """Test key is not rate limited initially."""
        limiter = RateLimiter(max_attempts=3, window_seconds=60)
        assert limiter.is_rate_limited("user1") is False

    def test_rate_limited_after_max_attempts(self):
        """Test key is rate limited after max attempts."""
        limiter = RateLimiter(max_attempts=3, window_seconds=60)

        for _ in range(3):
            limiter.record_attempt("user1")

        assert limiter.is_rate_limited("user1") is True

    def test_different_keys_independent(self):
        """Test different keys are tracked independently."""
        limiter = RateLimiter(max_attempts=3, window_seconds=60)

        for _ in range(3):
            limiter.record_attempt("user1")

        assert limiter.is_rate_limited("user1") is True
        assert limiter.is_rate_limited("user2") is False

    def test_reset_clears_attempts(self):
        """Test reset clears attempts for a key."""
        limiter = RateLimiter(max_attempts=3, window_seconds=60)

        for _ in range(3):
            limiter.record_attempt("user1")

        limiter.reset("user1")
        assert limiter.is_rate_limited("user1") is False

    def test_attempts_expire_after_window(self):
        """Test attempts expire after the time window."""
        limiter = RateLimiter(max_attempts=3, window_seconds=1)  # 1 second window

        for _ in range(3):
            limiter.record_attempt("user1")

        assert limiter.is_rate_limited("user1") is True

        # Wait for window to expire
        time.sleep(1.1)

        assert limiter.is_rate_limited("user1") is False

    def test_get_remaining_lockout_time(self):
        """Test getting remaining lockout time."""
        limiter = RateLimiter(max_attempts=3, window_seconds=60)

        for _ in range(3):
            limiter.record_attempt("user1")

        remaining = limiter.get_remaining_lockout_time("user1")
        assert remaining > 0
        assert remaining <= 60

    def test_get_remaining_lockout_time_no_attempts(self):
        """Test remaining time is 0 when not rate limited."""
        limiter = RateLimiter(max_attempts=3, window_seconds=60)
        assert limiter.get_remaining_lockout_time("user1") == 0

    def test_cleanup_old_entries(self):
        """Test old entries are cleaned up."""
        limiter = RateLimiter(max_attempts=3, window_seconds=1)

        limiter.record_attempt("user1")
        limiter.record_attempt("user1")

        # Wait for window to expire
        time.sleep(1.1)

        # Trigger cleanup by checking rate limit
        limiter.is_rate_limited("user1")

        # Attempts should be cleared
        assert "user1" not in limiter._attempts or len(limiter._attempts.get("user1", [])) == 0
