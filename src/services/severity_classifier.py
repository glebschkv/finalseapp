"""
Severity Classification Service.
Implements BR8: Danger Level Categorization
"""

from typing import List, Dict, Any
import re

from ..config.logging_config import get_logger

logger = get_logger(__name__)


class SeverityClassifier:
    """
    Classifier for determining response severity levels.

    Implements BR8:
    - BR8.1: Information categorised as critical (red)
    - BR8.2: Information categorised as potential danger (amber)
    - BR8.3: Information categorised as harmless (green)
    """

    # Keywords indicating critical severity
    CRITICAL_KEYWORDS = [
        "immediate", "immediately", "stop driving", "dangerous", "critical",
        "severe", "emergency", "safety risk", "do not drive", "tow",
        "pull over", "serious damage", "engine damage", "unsafe",
        "risk of", "fire", "overheat", "overheating", "failure imminent"
    ]

    # Keywords indicating warning severity
    WARNING_KEYWORDS = [
        "attention", "monitor", "soon", "potential", "recommend",
        "check", "abnormal", "unusual", "service", "maintenance",
        "should be", "may cause", "could lead", "inspect", "schedule",
        "not normal", "elevated", "low", "high", "outside range",
        "concern", "issue", "problem"
    ]

    # Keywords indicating normal/positive status
    NORMAL_KEYWORDS = [
        "normal", "healthy", "good", "optimal", "within range",
        "no issues", "no problems", "functioning properly", "working correctly",
        "satisfactory", "acceptable", "fine", "okay", "no concern",
        "no fault", "no error"
    ]

    # Fault code severity mappings
    CRITICAL_FAULT_PREFIXES = [
        "P03",  # Misfire codes
        "P0118", "P0120", "P0122", "P0123",  # Critical sensor failures
    ]

    WARNING_FAULT_PREFIXES = [
        "P01", "P02",  # Fuel/air and ignition
        "P04", "P05", "P07",  # Emissions, speed, transmission
    ]

    def classify(
        self,
        response: str,
        metrics: List[Dict[str, Any]] = None,
        fault_codes: List[Dict[str, Any]] = None
    ) -> str:
        """
        Classify the severity of a response.

        Args:
            response: The generated response text
            metrics: List of parsed metrics with status
            fault_codes: List of fault codes with severity

        Returns:
            Severity level: 'critical', 'warning', or 'normal'
        """
        metrics = metrics or []
        fault_codes = fault_codes or []

        # Check metrics for severity
        metric_severity = self._check_metrics_severity(metrics)
        if metric_severity == "critical":
            return "critical"

        # Check fault codes for severity
        fault_severity = self._check_fault_code_severity(fault_codes)
        if fault_severity == "critical":
            return "critical"

        # Check response content for severity indicators
        response_severity = self._check_response_severity(response)

        # Combine severities (take the most severe)
        severities = [metric_severity, fault_severity, response_severity]

        if "critical" in severities:
            return "critical"
        elif "warning" in severities:
            return "warning"
        else:
            return "normal"

    def classify_message(self, content: str) -> str:
        """
        Classify severity of a single message content.

        Args:
            content: Message text to classify

        Returns:
            Severity level: 'critical', 'warning', or 'normal'
        """
        return self._check_response_severity(content)

    def _check_metrics_severity(self, metrics: List[Dict[str, Any]]) -> str:
        """Check metrics for severity indicators."""
        has_critical = False
        has_warning = False

        for metric in metrics:
            status = metric.get("status", "normal").lower()
            if status == "critical":
                has_critical = True
            elif status == "warning":
                has_warning = True

        if has_critical:
            return "critical"
        elif has_warning:
            return "warning"
        return "normal"

    def _check_fault_code_severity(self, fault_codes: List[Dict[str, Any]]) -> str:
        """Check fault codes for severity indicators."""
        has_critical = False
        has_warning = False

        for fault in fault_codes:
            # Check explicit severity
            severity = fault.get("severity", "").lower()
            if severity == "critical":
                has_critical = True
            elif severity == "warning":
                has_warning = True

            # Check code patterns
            code = fault.get("code", "").upper()
            for prefix in self.CRITICAL_FAULT_PREFIXES:
                if code.startswith(prefix):
                    has_critical = True
                    break

            if not has_critical:
                for prefix in self.WARNING_FAULT_PREFIXES:
                    if code.startswith(prefix):
                        has_warning = True
                        break

        if has_critical:
            return "critical"
        elif has_warning:
            return "warning"
        return "normal"

    def _check_response_severity(self, response: str) -> str:
        """Check response text for severity indicators."""
        response_lower = response.lower()

        # Negation patterns to check before counting critical keywords
        negation_patterns = [
            "not ", "no ", "isn't ", "aren't ", "wasn't ", "weren't ",
            "don't ", "doesn't ", "didn't ", "won't ", "wouldn't ",
            "can't ", "cannot ", "couldn't ", "shouldn't "
        ]

        # Count keyword matches, excluding negated critical keywords
        critical_count = 0
        for kw in self.CRITICAL_KEYWORDS:
            if kw in response_lower:
                # Check if keyword is negated
                kw_pos = response_lower.find(kw)
                is_negated = False
                # Check for negation within 20 characters before the keyword
                check_start = max(0, kw_pos - 20)
                prefix = response_lower[check_start:kw_pos]
                for neg in negation_patterns:
                    if neg in prefix:
                        is_negated = True
                        break
                if not is_negated:
                    critical_count += 1

        warning_count = sum(1 for kw in self.WARNING_KEYWORDS if kw in response_lower)
        normal_count = sum(1 for kw in self.NORMAL_KEYWORDS if kw in response_lower)

        # Apply scoring with thresholds
        if critical_count >= 2:
            return "critical"
        elif critical_count >= 1 and warning_count >= 2 and normal_count < 2:
            return "critical"
        elif normal_count >= 3 and normal_count > warning_count:
            # Strong normal signal overrides mild warnings
            return "normal"
        elif warning_count >= 3 or (warning_count >= 2 and normal_count < warning_count):
            return "warning"
        elif normal_count > warning_count:
            return "normal"
        elif warning_count >= 2:
            return "warning"
        else:
            return "normal"

    def get_severity_color(self, severity: str) -> Dict[str, str]:
        """
        Get color scheme for a severity level.

        Args:
            severity: Severity level

        Returns:
            Dictionary with color information
        """
        colors = {
            "critical": {
                "background": "#FEF2F2",
                "border": "#F87171",
                "text": "#B91C1C",
                "icon": "🔴",
                "name": "Critical"
            },
            "warning": {
                "background": "#FFFBEB",
                "border": "#FBBF24",
                "text": "#B45309",
                "icon": "🟡",
                "name": "Warning"
            },
            "normal": {
                "background": "#F0FDF4",
                "border": "#4ADE80",
                "text": "#15803D",
                "icon": "🟢",
                "name": "Normal"
            }
        }
        return colors.get(severity.lower(), colors["normal"])

    def format_severity_badge(self, severity: str) -> str:
        """
        Format severity as a display badge.

        Args:
            severity: Severity level

        Returns:
            Formatted badge string
        """
        colors = self.get_severity_color(severity)
        return f"{colors['icon']} {colors['name']}"

    def get_severity_recommendation(self, severity: str) -> str:
        """
        Get a general recommendation based on severity.

        Args:
            severity: Severity level

        Returns:
            Recommendation string
        """
        recommendations = {
            "critical": "⚠️ IMMEDIATE ACTION REQUIRED: Please address these issues before continuing to drive. Consider having your vehicle towed to a mechanic if necessary.",
            "warning": "⚡ ATTENTION NEEDED: Schedule a service appointment soon to address these issues and prevent potential problems.",
            "normal": "✅ ALL GOOD: Your vehicle appears to be in good condition. Continue with regular maintenance."
        }
        return recommendations.get(severity.lower(), recommendations["normal"])
