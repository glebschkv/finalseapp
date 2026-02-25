"""
Health check utilities for OBD InsightBot.
Provides system status monitoring and diagnostics.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import os
import sys
import platform
from pathlib import Path

from ..config.settings import get_settings
from ..config.logging_config import get_logger

logger = get_logger(__name__)


class HealthStatus(Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health status of a single component."""
    name: str
    status: HealthStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "checked_at": self.checked_at.isoformat()
        }


@dataclass
class SystemHealth:
    """Overall system health status."""
    status: HealthStatus
    components: List[ComponentHealth]
    version: str = "1.0.0"
    uptime: Optional[float] = None
    checked_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "version": self.version,
            "uptime": self.uptime,
            "checked_at": self.checked_at.isoformat(),
            "components": [c.to_dict() for c in self.components]
        }


class HealthChecker:
    """
    Health checker for monitoring system components.

    Checks:
    - Database connectivity
    - AI backend availability (local model or watsonx.ai)
    - Disk space
    - Configuration validity
    - Required dependencies
    """

    def __init__(self):
        self.settings = get_settings()
        self._start_time = datetime.utcnow()

    def check_all(self) -> SystemHealth:
        """
        Perform all health checks.

        Returns:
            SystemHealth object with overall status and component details
        """
        components = [
            self.check_database(),
            self.check_ai_backend(),
            self.check_disk_space(),
            self.check_configuration(),
            self.check_dependencies(),
        ]

        # Determine overall status
        if any(c.status == HealthStatus.UNHEALTHY for c in components):
            overall = HealthStatus.UNHEALTHY
        elif any(c.status == HealthStatus.DEGRADED for c in components):
            overall = HealthStatus.DEGRADED
        elif all(c.status == HealthStatus.HEALTHY for c in components):
            overall = HealthStatus.HEALTHY
        else:
            overall = HealthStatus.UNKNOWN

        uptime = (datetime.utcnow() - self._start_time).total_seconds()

        return SystemHealth(
            status=overall,
            components=components,
            uptime=uptime
        )

    def check_database(self) -> ComponentHealth:
        """Check database connectivity and integrity."""
        try:
            from ..models.base import get_engine, DatabaseSession

            # Try to connect
            engine = get_engine()
            with DatabaseSession() as session:
                # Simple query to verify connection
                session.execute("SELECT 1")

            db_path = Path(self.settings.database_path)
            db_size = db_path.stat().st_size if db_path.exists() else 0

            return ComponentHealth(
                name="database",
                status=HealthStatus.HEALTHY,
                message="Database is accessible",
                details={
                    "path": str(db_path),
                    "size_bytes": db_size,
                    "exists": db_path.exists()
                }
            )

        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Database error: {str(e)}",
                details={"error": str(e)}
            )

    def check_ai_backend(self) -> ComponentHealth:
        """Check AI backend availability."""
        try:
            # Check Ollama server
            ollama_url = self.settings.ollama_url
            ollama_model = self.settings.ollama_model

            try:
                import requests
                response = requests.get(f"{ollama_url}/api/tags", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    model_base = ollama_model.split(":")[0]
                    model_found = any(model_base in m for m in models)

                    if model_found:
                        return ComponentHealth(
                            name="ai_backend",
                            status=HealthStatus.HEALTHY,
                            message=f"Ollama running with model '{ollama_model}'",
                            details={
                                "backend": "ollama",
                                "url": ollama_url,
                                "model": ollama_model,
                                "available_models": models,
                            }
                        )
                    else:
                        return ComponentHealth(
                            name="ai_backend",
                            status=HealthStatus.DEGRADED,
                            message=f"Ollama running but model '{ollama_model}' not found",
                            details={
                                "backend": "ollama",
                                "url": ollama_url,
                                "model": ollama_model,
                                "available_models": models,
                                "fix": f"ollama pull {ollama_model}"
                            }
                        )
            except ImportError:
                logger.info("requests library not installed")
            except Exception as e:
                logger.info(f"Ollama not available: {e}")

            # Check watsonx.ai configuration
            is_valid, errors = self.settings.validate()
            if is_valid:
                return ComponentHealth(
                    name="ai_backend",
                    status=HealthStatus.HEALTHY,
                    message="watsonx.ai is configured",
                    details={
                        "backend": "watsonx.ai",
                        "model": self.settings.granite_chat_model
                    }
                )

            # Neither available - degraded mode with mock
            return ComponentHealth(
                name="ai_backend",
                status=HealthStatus.DEGRADED,
                message="Running in mock mode (no AI backend)",
                details={
                    "backend": "mock",
                    "ollama_error": f"Ollama not reachable at {ollama_url}",
                    "watsonx_errors": errors
                }
            )

        except Exception as e:
            logger.error(f"AI backend health check failed: {e}")
            return ComponentHealth(
                name="ai_backend",
                status=HealthStatus.UNKNOWN,
                message=f"Could not check AI backend: {str(e)}",
                details={"error": str(e)}
            )

    def check_disk_space(self) -> ComponentHealth:
        """Check available disk space."""
        try:
            import shutil

            # Check disk space for data directory
            data_dir = Path(self.settings.database_path).parent
            data_dir.mkdir(parents=True, exist_ok=True)

            total, used, free = shutil.disk_usage(data_dir)

            # Convert to GB
            free_gb = free / (1024 ** 3)
            total_gb = total / (1024 ** 3)
            used_percent = (used / total) * 100

            if free_gb < 0.5:  # Less than 500MB
                status = HealthStatus.UNHEALTHY
                message = f"Critical: Only {free_gb:.2f} GB free"
            elif free_gb < 2:  # Less than 2GB
                status = HealthStatus.DEGRADED
                message = f"Warning: Only {free_gb:.2f} GB free"
            else:
                status = HealthStatus.HEALTHY
                message = f"{free_gb:.2f} GB available"

            return ComponentHealth(
                name="disk_space",
                status=status,
                message=message,
                details={
                    "total_gb": round(total_gb, 2),
                    "free_gb": round(free_gb, 2),
                    "used_percent": round(used_percent, 1),
                    "path": str(data_dir)
                }
            )

        except Exception as e:
            logger.error(f"Disk space check failed: {e}")
            return ComponentHealth(
                name="disk_space",
                status=HealthStatus.UNKNOWN,
                message=f"Could not check disk space: {str(e)}",
                details={"error": str(e)}
            )

    def check_configuration(self) -> ComponentHealth:
        """Check configuration validity."""
        try:
            issues = []
            warnings = []

            # Check database path
            db_path = Path(self.settings.database_path)
            if not db_path.parent.exists():
                warnings.append("Database directory does not exist (will be created)")

            # Check log level
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if self.settings.log_level.upper() not in valid_levels:
                issues.append(f"Invalid log level: {self.settings.log_level}")

            # Check generation parameters
            if not 0 <= self.settings.temperature <= 2:
                issues.append(f"Temperature out of range: {self.settings.temperature}")
            if not 0 <= self.settings.top_p <= 1:
                issues.append(f"Top-p out of range: {self.settings.top_p}")
            if self.settings.max_new_tokens <= 0:
                issues.append(f"Invalid max_new_tokens: {self.settings.max_new_tokens}")

            if issues:
                return ComponentHealth(
                    name="configuration",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Configuration issues: {', '.join(issues)}",
                    details={"issues": issues, "warnings": warnings}
                )
            elif warnings:
                return ComponentHealth(
                    name="configuration",
                    status=HealthStatus.DEGRADED,
                    message=f"Configuration warnings: {', '.join(warnings)}",
                    details={"warnings": warnings}
                )
            else:
                return ComponentHealth(
                    name="configuration",
                    status=HealthStatus.HEALTHY,
                    message="Configuration is valid",
                    details={
                        "log_level": self.settings.log_level,
                        "debug_mode": self.settings.app_debug
                    }
                )

        except Exception as e:
            logger.error(f"Configuration check failed: {e}")
            return ComponentHealth(
                name="configuration",
                status=HealthStatus.UNKNOWN,
                message=f"Could not validate configuration: {str(e)}",
                details={"error": str(e)}
            )

    def check_dependencies(self) -> ComponentHealth:
        """Check required dependencies are available."""
        required = {
            "sqlalchemy": "Database ORM",
            "pandas": "Data processing",
            "bcrypt": "Password hashing",
        }

        optional = {
            "PyQt6": "GUI framework",
            "langchain": "LLM framework",
            "chromadb": "Vector database",
        }

        missing_required = []
        missing_optional = []
        installed = {}

        for package, description in required.items():
            try:
                module = __import__(package)
                version = getattr(module, "__version__", "unknown")
                installed[package] = version
            except ImportError:
                missing_required.append(f"{package} ({description})")

        for package, description in optional.items():
            try:
                module = __import__(package.replace("-", "_").lower())
                version = getattr(module, "__version__", "unknown")
                installed[package] = version
            except ImportError:
                missing_optional.append(f"{package} ({description})")

        if missing_required:
            return ComponentHealth(
                name="dependencies",
                status=HealthStatus.UNHEALTHY,
                message=f"Missing required packages: {', '.join(missing_required)}",
                details={
                    "installed": installed,
                    "missing_required": missing_required,
                    "missing_optional": missing_optional
                }
            )
        elif missing_optional:
            return ComponentHealth(
                name="dependencies",
                status=HealthStatus.DEGRADED,
                message=f"Missing optional packages: {', '.join(missing_optional)}",
                details={
                    "installed": installed,
                    "missing_optional": missing_optional
                }
            )
        else:
            return ComponentHealth(
                name="dependencies",
                status=HealthStatus.HEALTHY,
                message="All dependencies installed",
                details={"installed": installed}
            )


def get_system_info() -> Dict[str, Any]:
    """
    Get system information for diagnostics.

    Returns:
        Dictionary with system information
    """
    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "os": platform.system(),
        "os_version": platform.version(),
    }


def run_health_check() -> Dict[str, Any]:
    """
    Run a complete health check and return results.

    Returns:
        Dictionary with health check results
    """
    checker = HealthChecker()
    health = checker.check_all()

    return {
        "health": health.to_dict(),
        "system_info": get_system_info()
    }
