"""
Tests for Severity Classification.
Tests BR8: Danger Level Categorization
"""

import pytest
from src.services.severity_classifier import SeverityClassifier


class TestSeverityClassifier:
    """Test suite for BR8: Danger Level Categorization."""

    def test_critical_response_classification(self, severity_classifier):
        """BR8.1: Critical information is categorised as critical."""
        response = """
        CRITICAL WARNING: Your vehicle has a severe engine misfire.
        Stop driving immediately and have it towed to a mechanic.
        This is a safety risk that could cause engine damage.
        """

        severity = severity_classifier._check_response_severity(response)
        assert severity == "critical"

    def test_warning_response_classification(self, severity_classifier):
        """BR8.2: Warning information is categorised as potential danger."""
        response = """
        Your coolant temperature is slightly elevated.
        You should monitor this closely and schedule a service appointment soon.
        This issue needs attention but is not immediately dangerous.
        """

        severity = severity_classifier._check_response_severity(response)
        assert severity == "warning"

    def test_normal_response_classification(self, severity_classifier):
        """BR8.3: Normal information is categorised as harmless."""
        response = """
        Your vehicle is in good condition. All readings are within normal range.
        The engine is functioning properly and no issues were detected.
        Keep up with regular maintenance and you should be fine.
        """

        severity = severity_classifier._check_response_severity(response)
        assert severity == "normal"

    def test_metrics_severity_critical(self, severity_classifier):
        """Test severity classification from critical metrics."""
        metrics = [
            {"name": "engine_rpm", "status": "critical"},
            {"name": "coolant_temp", "status": "normal"},
        ]

        severity = severity_classifier._check_metrics_severity(metrics)
        assert severity == "critical"

    def test_metrics_severity_warning(self, severity_classifier):
        """Test severity classification from warning metrics."""
        metrics = [
            {"name": "engine_rpm", "status": "normal"},
            {"name": "coolant_temp", "status": "warning"},
        ]

        severity = severity_classifier._check_metrics_severity(metrics)
        assert severity == "warning"

    def test_metrics_severity_normal(self, severity_classifier):
        """Test severity classification from normal metrics."""
        metrics = [
            {"name": "engine_rpm", "status": "normal"},
            {"name": "coolant_temp", "status": "normal"},
        ]

        severity = severity_classifier._check_metrics_severity(metrics)
        assert severity == "normal"

    def test_fault_code_severity_critical(self, severity_classifier):
        """Test severity classification from critical fault codes."""
        fault_codes = [
            {"code": "P0300", "severity": "critical"},  # Misfire
        ]

        severity = severity_classifier._check_fault_code_severity(fault_codes)
        assert severity == "critical"

    def test_fault_code_severity_warning(self, severity_classifier):
        """Test severity classification from warning fault codes."""
        fault_codes = [
            {"code": "P0420", "severity": "warning"},  # Catalyst efficiency
        ]

        severity = severity_classifier._check_fault_code_severity(fault_codes)
        assert severity == "warning"

    def test_combined_severity_critical_wins(self, severity_classifier):
        """Test that critical severity takes precedence."""
        response = "Your vehicle needs attention soon."
        metrics = [{"name": "engine_rpm", "status": "critical"}]
        fault_codes = [{"code": "P0420", "severity": "warning"}]

        severity = severity_classifier.classify(response, metrics, fault_codes)
        assert severity == "critical"

    def test_combined_severity_warning(self, severity_classifier):
        """Test combined warning severity."""
        response = "Your vehicle is generally okay."
        metrics = [{"name": "engine_rpm", "status": "warning"}]
        fault_codes = []

        severity = severity_classifier.classify(response, metrics, fault_codes)
        assert severity == "warning"

    def test_severity_color_scheme(self, severity_classifier):
        """Test color scheme retrieval."""
        critical_colors = severity_classifier.get_severity_color("critical")
        assert critical_colors["icon"] == "🔴"
        assert critical_colors["background"] == "#FEF2F2"

        warning_colors = severity_classifier.get_severity_color("warning")
        assert warning_colors["icon"] == "🟡"

        normal_colors = severity_classifier.get_severity_color("normal")
        assert normal_colors["icon"] == "🟢"

    def test_severity_badge_format(self, severity_classifier):
        """Test severity badge formatting."""
        badge = severity_classifier.format_severity_badge("critical")
        assert "🔴" in badge
        assert "Critical" in badge

    def test_severity_recommendation(self, severity_classifier):
        """Test severity-based recommendations."""
        critical_rec = severity_classifier.get_severity_recommendation("critical")
        assert "immediate" in critical_rec.lower()

        warning_rec = severity_classifier.get_severity_recommendation("warning")
        assert "schedule" in warning_rec.lower() or "soon" in warning_rec.lower()

        normal_rec = severity_classifier.get_severity_recommendation("normal")
        assert "good" in normal_rec.lower()
