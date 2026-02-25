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
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt

    from src.config.settings import get_settings
    from src.config.logging_config import setup_logging
    from src.ui.main_window import MainWindow

    # Setup logging
    settings = get_settings()
    logger = setup_logging(settings.log_level)
    logger.info("Starting OBD InsightBot")

    # Validate configuration
    is_valid, errors = settings.validate()
    if not is_valid:
        logger.warning(f"Configuration warnings: {errors}")
        logger.info("Running in demo mode - some features may be limited")

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
