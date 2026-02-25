"""
Helper utility functions.
"""

from datetime import datetime
from typing import Optional
import re
import os


def format_timestamp(dt: Optional[datetime], format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format a datetime object as a string.

    Args:
        dt: Datetime to format
        format_str: Format string

    Returns:
        Formatted string or "N/A" if dt is None
    """
    if dt is None:
        return "N/A"
    return dt.strftime(format_str)


def format_relative_time(dt: Optional[datetime]) -> str:
    """
    Format a datetime as relative time (e.g., "2 hours ago").

    Args:
        dt: Datetime to format

    Returns:
        Relative time string
    """
    if dt is None:
        return "Unknown"

    now = datetime.utcnow()
    diff = now - dt

    seconds = diff.total_seconds()

    if seconds < 60:
        return "Just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"
    else:
        return dt.strftime("%Y-%m-%d")


def truncate_text(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to append if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def safe_filename(filename: str, max_length: int = 100) -> str:
    """
    Convert a string to a safe filename.

    Args:
        filename: Original filename
        max_length: Maximum length

    Returns:
        Safe filename
    """
    # Remove invalid characters
    safe = re.sub(r'[<>:"/\\|?*]', '', filename)

    # Replace spaces with underscores
    safe = safe.replace(' ', '_')

    # Truncate if necessary
    if len(safe) > max_length:
        safe = safe[:max_length]

    return safe


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def get_severity_emoji(severity: str) -> str:
    """
    Get emoji for severity level.

    Args:
        severity: Severity level

    Returns:
        Emoji string
    """
    emojis = {
        "critical": "🔴",
        "warning": "🟡",
        "normal": "🟢",
        "info": "🔵"
    }
    return emojis.get(severity.lower(), "⚪")


def sanitize_html(text: str) -> str:
    """
    Sanitize text for safe HTML display.

    Args:
        text: Text to sanitize

    Returns:
        Sanitized text
    """
    replacements = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#x27;",
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text


def parse_fault_code_category(code: str) -> str:
    """
    Parse the category from a fault code.

    Args:
        code: Fault code (e.g., "P0300")

    Returns:
        Category name
    """
    if not code:
        return "Unknown"

    prefix = code[0].upper()
    categories = {
        "P": "Powertrain",
        "C": "Chassis",
        "B": "Body",
        "U": "Network"
    }
    return categories.get(prefix, "Unknown")


def is_generic_fault_code(code: str) -> bool:
    """
    Check if a fault code is generic (not manufacturer-specific).

    Args:
        code: Fault code to check

    Returns:
        True if generic
    """
    if len(code) < 2:
        return False

    # Generic codes have 0, 2, or 3 as the second character
    return code[1] in ["0", "2", "3"]
