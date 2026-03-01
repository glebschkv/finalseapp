#!/usr/bin/env python3
"""
OBD InsightBot - Main Application Entry Point

A conversational AI chatbot for vehicle diagnostics using IBM Granite.
"""

import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    """Main application entry point."""
    # Import after path setup
    from src.config.settings import get_settings
    from src.config.logging_config import setup_logging

    # Setup logging
    settings = get_settings()
    logger = setup_logging(settings.log_level)
    logger.info("Starting OBD InsightBot")

    # Pre-load the Whisper speech model BEFORE PyQt6's QApplication is
    # created.  CTranslate2 (used by faster-whisper) crashes with a
    # native segfault if it initialises after Qt's native libraries are
    # loaded on Windows.  Loading it first avoids the conflict entirely.
    from src.services.voice_service import VoiceService
    VoiceService.preload_model()

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from src.ui.main_window import MainWindow

    # Validate configuration
    is_valid, errors = settings.validate()
    if not is_valid:
        logger.warning(f"Configuration warnings: {errors}")

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("OBD InsightBot")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Group 18")

    # Create and show main window
    window = MainWindow()
    window.show()

    logger.info("Application started successfully")

    # Run event loop
    exit_code = app.exec()

    logger.info(f"Application exiting with code {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
