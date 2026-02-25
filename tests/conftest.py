"""
Pytest fixtures and configuration.
"""

import pytest
import tempfile
import os
from pathlib import Path

# Add project root to path
import sys
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _reset_database_state():
    """Reset the global database state (engine, session factory, and settings)."""
    import src.models.base as base_module
    import src.config.settings as settings_module

    # Reset database engine and session factory
    if base_module._engine is not None:
        base_module._engine.dispose()
        base_module._engine = None
    base_module._SessionFactory = None

    # Reset settings singleton so it re-reads DATABASE_PATH
    settings_module._settings = None


@pytest.fixture(scope="function")
def test_db(tmp_path):
    """Create a temporary database for testing (function-scoped for isolation)."""
    db_path = os.path.join(str(tmp_path), "test.db")
    os.environ["DATABASE_PATH"] = db_path

    # Reset any existing database state
    _reset_database_state()

    yield db_path

    # Cleanup: reset database state to release file handles
    _reset_database_state()


@pytest.fixture
def sample_obd_csv(tmp_path):
    """Create a sample OBD-II CSV file for testing."""
    csv_content = """timestamp,engine_rpm,coolant_temp,vehicle_speed,throttle_position,engine_load,fault_codes
2024-01-01 10:00:00,850,92,0,15,25,
2024-01-01 10:00:01,900,93,0,16,26,
2024-01-01 10:00:02,2500,94,45,35,55,
2024-01-01 10:00:03,2800,95,55,40,60,
2024-01-01 10:00:04,3000,96,65,45,65,P0300
2024-01-01 10:00:05,3200,97,70,48,68,P0300
2024-01-01 10:00:06,2000,95,50,30,50,
2024-01-01 10:00:07,1500,94,35,25,40,
2024-01-01 10:00:08,900,93,0,15,25,
2024-01-01 10:00:09,850,92,0,14,24,
"""
    csv_file = tmp_path / "sample_obd.csv"
    csv_file.write_text(csv_content)
    return str(csv_file)


@pytest.fixture
def sample_healthy_obd_csv(tmp_path):
    """Create a healthy OBD-II CSV file (no faults)."""
    csv_content = """timestamp,engine_rpm,coolant_temp,vehicle_speed,throttle_position,engine_load
2024-01-01 10:00:00,850,92,0,15,25
2024-01-01 10:00:01,900,93,0,16,26
2024-01-01 10:00:02,2500,94,45,35,55
2024-01-01 10:00:03,2800,95,55,40,60
2024-01-01 10:00:04,3000,96,65,45,65
"""
    csv_file = tmp_path / "healthy_obd.csv"
    csv_file.write_text(csv_content)
    return str(csv_file)


@pytest.fixture
def sample_critical_obd_csv(tmp_path):
    """Create an OBD-II CSV with critical issues."""
    csv_content = """timestamp,engine_rpm,coolant_temp,vehicle_speed,throttle_position,engine_load,fault_codes
2024-01-01 10:00:00,200,130,0,15,95,P0300
2024-01-01 10:00:01,150,135,0,16,96,P0300 P0118
2024-01-01 10:00:02,100,140,0,35,97,P0300 P0118 P0120
"""
    csv_file = tmp_path / "critical_obd.csv"
    csv_file.write_text(csv_content)
    return str(csv_file)


@pytest.fixture
def invalid_csv(tmp_path):
    """Create an invalid CSV file."""
    csv_file = tmp_path / "invalid.csv"
    csv_file.write_text("this,is,not,obd,data\n1,2,3,4,5")
    return str(csv_file)


@pytest.fixture
def non_csv_file(tmp_path):
    """Create a non-CSV file."""
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("This is not a CSV file")
    return str(txt_file)


def _reset_auth_state():
    """Reset AuthService state including rate limiters."""
    from src.services.auth_service import AuthService
    AuthService._sessions.clear()
    AuthService._login_limiter._attempts.clear()
    AuthService._register_limiter._attempts.clear()


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """Reset rate limiters before and after each test."""
    _reset_auth_state()
    yield
    _reset_auth_state()


@pytest.fixture
def auth_service():
    """Get AuthService with clean state."""
    from src.services.auth_service import AuthService
    _reset_auth_state()
    return AuthService


@pytest.fixture
def obd_parser():
    """Get OBDParser instance."""
    from src.services.obd_parser import OBDParser
    return OBDParser()


@pytest.fixture
def severity_classifier():
    """Get SeverityClassifier instance."""
    from src.services.severity_classifier import SeverityClassifier
    return SeverityClassifier()
