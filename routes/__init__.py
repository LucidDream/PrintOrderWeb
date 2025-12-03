"""
Flask route blueprints for PrintOrderWeb.

This module contains all route handlers organized by functionality:
- main: Home and demo pages
- upload: PDF upload handling
- details: Job configuration
- review: Order review
- submit: Job submission
- confirmation: Results display
- api: AJAX endpoints (sidebar refresh, status polling)

Each blueprint is registered with the Flask app in create_app().
"""

from flask import Blueprint

from .main import main_bp
from .upload import upload_bp
from .details import details_bp
from .review import review_bp
from .submit import submit_bp
from .confirmation import confirmation_bp
from .api import api_bp

__all__ = [
    "main_bp",
    "upload_bp",
    "details_bp",
    "review_bp",
    "submit_bp",
    "confirmation_bp",
    "api_bp",
]


def register_blueprints(app):
    """
    Register all blueprints with the Flask app.

    Args:
        app: Flask application instance
    """
    app.register_blueprint(main_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(details_bp)
    app.register_blueprint(review_bp)
    app.register_blueprint(submit_bp)
    app.register_blueprint(confirmation_bp)
    app.register_blueprint(api_bp)
