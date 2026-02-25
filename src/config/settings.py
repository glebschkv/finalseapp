"""
Application settings and configuration management.
Loads configuration from environment variables and .env file.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Tuple, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class Settings:
    """Application configuration settings."""

    # Ollama Configuration (Local AI)
    ollama_url: str = field(
        default_factory=lambda: os.getenv("OLLAMA_URL", "http://localhost:11434")
    )
    ollama_model: str = field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL", "granite3.3:2b")
    )

    # IBM watsonx.ai Configuration (Cloud - Optional fallback)
    watsonx_url: str = field(
        default_factory=lambda: os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
    )
    watsonx_api_key: str = field(
        default_factory=lambda: os.getenv("WATSONX_API_KEY", "")
    )
    watsonx_project_id: str = field(
        default_factory=lambda: os.getenv("WATSONX_PROJECT_ID", "")
    )

    # IBM Watson Speech Services
    watson_speech_api_key: str = field(
        default_factory=lambda: os.getenv("WATSON_SPEECH_API_KEY", "")
    )
    watson_speech_url: str = field(
        default_factory=lambda: os.getenv(
            "WATSON_SPEECH_URL",
            "https://api.us-south.speech-to-text.watson.cloud.ibm.com"
        )
    )

    # Model IDs (for watsonx.ai cloud fallback)
    granite_chat_model: str = "ibm/granite-3-8b-instruct"
    granite_embedding_model: str = "ibm/granite-embedding-107m-multilingual"

    # Generation Parameters
    max_new_tokens: int = 1024
    temperature: float = 0.7
    top_p: float = 0.9
    repetition_penalty: float = 1.1
    decoding_method: str = "greedy"

    # Application Settings
    app_debug: bool = field(
        default_factory=lambda: os.getenv("APP_DEBUG", "false").lower() == "true"
    )
    log_level: str = field(
        default_factory=lambda: os.getenv("APP_LOG_LEVEL", "INFO")
    )

    # Database
    database_path: str = field(
        default_factory=lambda: os.getenv("DATABASE_PATH", "./data/obd_insightbot.db")
    )

    # Paths
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent)
    data_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent / "data")

    # Voice Settings
    silence_threshold_seconds: float = 3.0
    wake_word: str = "Hey InsightBot"

    def __post_init__(self):
        """Ensure data directory exists."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Ensure database directory exists
        db_path = Path(self.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def generation_params(self) -> dict:
        """Get generation parameters for Granite model."""
        return {
            "decoding_method": self.decoding_method,
            "max_new_tokens": self.max_new_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "repetition_penalty": self.repetition_penalty
        }

    def validate(self) -> Tuple[bool, List[str]]:
        """Validate required settings are configured."""
        errors = []

        if not self.watsonx_api_key:
            errors.append("WATSONX_API_KEY is not configured")
        if not self.watsonx_project_id:
            errors.append("WATSONX_PROJECT_ID is not configured")

        return len(errors) == 0, errors


# Singleton instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the application settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
