"""
Tests for OBD-II Parser Service.
Tests BR2: New Chat Creation with Log Upload
"""

import pytest
from src.services.obd_parser import OBDParser, OBDParseError


class TestOBDParser:
    """Test suite for BR2: OBD-II Log Upload and Parsing."""

    def test_valid_csv_upload(self, obd_parser, sample_obd_csv):
        """BR2.1: Valid OBD-II CSV file is processed successfully."""
        is_valid, message = obd_parser.validate_file(sample_obd_csv)

        assert is_valid is True
        assert "Valid" in message

    def test_valid_csv_parsing(self, obd_parser, sample_obd_csv):
        """BR2.1: Valid OBD-II CSV file is parsed correctly."""
        result = obd_parser.parse_csv(sample_obd_csv)

        assert result is not None
        assert "metrics" in result
        assert "fault_codes" in result
        assert len(result["metrics"]) > 0

    def test_invalid_file_type_rejected(self, obd_parser, non_csv_file):
        """BR2.2: Non-CSV file is rejected."""
        is_valid, message = obd_parser.validate_file(non_csv_file)

        assert is_valid is False
        assert ".csv" in message.lower()

    def test_valid_csv_invalid_data_rejected(self, obd_parser, invalid_csv):
        """BR2.3: CSV without OBD-II data is rejected."""
        is_valid, message = obd_parser.validate_file(invalid_csv)

        assert is_valid is False
        assert "No valid OBD-II data" in message

    def test_nonexistent_file(self, obd_parser):
        """Test handling of non-existent file."""
        is_valid, message = obd_parser.validate_file("/nonexistent/file.csv")

        assert is_valid is False
        assert "does not exist" in message

    def test_metrics_extraction(self, obd_parser, sample_obd_csv):
        """Test that metrics are correctly extracted."""
        result = obd_parser.parse_csv(sample_obd_csv)
        metrics = result["metrics"]

        # Check expected metrics are present
        metric_names = [m["name"] for m in metrics]
        assert "engine_rpm" in metric_names
        assert "coolant_temp" in metric_names
        assert "vehicle_speed" in metric_names

    def test_fault_codes_extraction(self, obd_parser, sample_obd_csv):
        """Test that fault codes are correctly extracted."""
        result = obd_parser.parse_csv(sample_obd_csv)
        fault_codes = result["fault_codes"]

        assert len(fault_codes) > 0

        # Check P0300 is found
        codes = [f["code"] for f in fault_codes]
        assert "P0300" in codes

    def test_healthy_vehicle_no_faults(self, obd_parser, sample_healthy_obd_csv):
        """Test parsing of healthy vehicle data."""
        result = obd_parser.parse_csv(sample_healthy_obd_csv)

        assert len(result["fault_codes"]) == 0
        assert result["has_issues"] is False

    def test_critical_vehicle_detection(self, obd_parser, sample_critical_obd_csv):
        """Test detection of critical issues."""
        result = obd_parser.parse_csv(sample_critical_obd_csv)

        assert result["has_issues"] is True
        assert result["critical_count"] > 0

    def test_metric_status_classification(self, obd_parser):
        """Test metric status classification logic."""
        # Normal RPM
        status = obd_parser._classify_metric_status("engine_rpm", 2500)
        assert status == "normal"

        # Critical RPM (too low)
        status = obd_parser._classify_metric_status("engine_rpm", 100)
        assert status == "critical"

        # Warning coolant temp
        status = obd_parser._classify_metric_status("coolant_temp", 112)
        assert status == "warning"

        # Critical coolant temp
        status = obd_parser._classify_metric_status("coolant_temp", 125)
        assert status == "critical"

    def test_fault_code_info_retrieval(self, obd_parser):
        """Test fault code information retrieval."""
        # Known generic code
        fault = obd_parser.get_fault_code_info("P0300")
        assert fault is not None
        assert fault.code == "P0300"
        assert fault.severity == "critical"
        assert "misfire" in fault.description.lower()

        # Unknown code
        fault = obd_parser.get_fault_code_info("P9999")
        assert fault is not None
        assert fault.code == "P9999"

    def test_statistics_calculation(self, obd_parser, sample_obd_csv):
        """Test statistics are calculated correctly."""
        result = obd_parser.parse_csv(sample_obd_csv)
        stats = result["statistics"]

        assert "total_rows" in stats
        assert stats["total_rows"] == 10
        assert "metrics_count" in stats
        assert "metric_statistics" in stats


class TestOBDParserEdgeCases:
    """Edge case tests for OBD Parser."""

    def test_empty_csv(self, obd_parser, tmp_path):
        """Test handling of empty CSV."""
        empty_file = tmp_path / "empty.csv"
        empty_file.write_text("")

        is_valid, message = obd_parser.validate_file(str(empty_file))
        assert is_valid is False

    def test_csv_with_only_headers(self, obd_parser, tmp_path):
        """Test handling of CSV with only headers."""
        csv_file = tmp_path / "headers_only.csv"
        csv_file.write_text("engine_rpm,coolant_temp,vehicle_speed\n")

        is_valid, message = obd_parser.validate_file(str(csv_file))
        # Should be valid but with no data
        assert is_valid is True or "empty" in message.lower()

    def test_manufacturer_specific_fault_code(self, obd_parser):
        """Test handling of manufacturer-specific fault codes."""
        # P1xxx codes are manufacturer-specific
        fault = obd_parser.get_fault_code_info("P1234")

        assert fault is not None
        assert fault.is_generic is False
        assert "manufacturer" in fault.description.lower()
