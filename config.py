"""
Configuration for PrintOrderWeb.

NO STUB MODE - the blockchain API is required.
Application will fail-fast if DLL cannot be loaded.
"""

import os
from pathlib import Path


# Base directory (where this file lives)
BASE_DIR = Path(__file__).resolve().parent


class Config:
    """Default configuration for the Flask application."""

    # Flask settings
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")
    UPLOAD_FOLDER = os.environ.get(
        "UPLOAD_FOLDER", str(BASE_DIR / "static" / "uploads")
    )
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB uploads
    SESSION_COOKIE_NAME = "print_order_session"
    ENVIRONMENT = os.environ.get("FLASK_ENV", "development")

    # ConsumableClient DLL path
    # Production builds should have DLL in _internal/ folder
    # Development can point to external location
    CONSUMABLE_DLL_PATH = os.environ.get(
        "CONSUMABLE_DLL_PATH",
        str(BASE_DIR.parent / "CCAPIv2.0.0.2" / "ConsumableClient.dll")
    )

    # Debug mode
    DEBUG = os.environ.get("FLASK_DEBUG", "1") == "1"


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    """Testing configuration."""
    DEBUG = False
    TESTING = True
