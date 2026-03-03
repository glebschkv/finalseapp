#!/usr/bin/env python3
"""
OBD InsightBot - Main Application Entry Point

A conversational AI chatbot for vehicle diagnostics using IBM Granite.
"""

import sys
import os
import argparse
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="OBD InsightBot - Smart Vehicle Diagnostics"
    )
    parser.add_argument(
        "--teleport",
        metavar="SESSION_ID",
        help="Recover a previous session by its session ID, skipping login"
    )
    # Parse known args to avoid conflicts with Qt arguments
    args, remaining = parser.parse_known_args()
    return args, remaining


def main():
    """Main application entry point."""
    # Parse CLI arguments before anything else
    args, qt_args = parse_args()

    # Import after path setup
    from src.config.settings import get_settings
    from src.config.logging_config import setup_logging

    # Setup logging
    settings = get_settings()
    logger = setup_logging(settings.log_level)
    logger.info("Starting OBD InsightBot")

    if args.teleport:
        logger.info(f"Teleport session recovery requested: {args.teleport}")

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

    # Create application - pass remaining args for Qt
    app = QApplication([sys.argv[0]] + qt_args)
    app.setApplicationName("OBD InsightBot")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Group 18")

    # Create and show main window
    window = MainWindow()
    window.show()

    # Attempt teleport session recovery if requested
    if args.teleport:
        success = window.teleport_recover(args.teleport)
        if not success:
            logger.warning(f"Teleport session recovery failed for: {args.teleport}")

    logger.info("Application started successfully")

    # Run event loop
    exit_code = app.exec()

    logger.info(f"Application exiting with code {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
