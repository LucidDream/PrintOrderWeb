"""
Configuration for PrintOrderWeb.

NO STUB MODE - the blockchain API is required.
Application will fail-fast if DLL cannot be loaded.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file early so environment variables are available for Config class
# This must happen before the Config class is defined
load_dotenv(override=True)

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

    # ==========================================================================
    # Estimator Configuration (for demos/testing)
    # ==========================================================================
    # These values control how toner usage is estimated for print jobs.
    # Increase these values to consume more ink during demonstrations.
    #
    # BASE_TONER_ML_PER_SHEET: mL of toner per sheet at 100% page coverage
    #   Default: 0.15 (industry standard)
    #   Demo suggestion: 0.50 - 1.0 for higher consumption
    #
    # PAGE_COVERAGE_PERCENT: Percentage of page assumed to be covered in ink
    #   Default: 10 (10% - industry standard for text documents)
    #   Demo suggestion: 30 - 50 for higher consumption
    #
    # Formula: toner_ml = sheets × (coverage/100) × base_ml × quality_modifier
    # ==========================================================================
    ESTIMATOR_BASE_TONER_ML = float(
        os.environ.get("ESTIMATOR_BASE_TONER_ML", "0.15")
    )
    ESTIMATOR_PAGE_COVERAGE_PERCENT = float(
        os.environ.get("ESTIMATOR_PAGE_COVERAGE_PERCENT", "10")
    )


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
