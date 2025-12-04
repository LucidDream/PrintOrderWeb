"""
PrintOrderWeb - Flask Application Entry Point.

This is a slim app factory that:
1. Initializes DLL context (fail-fast, no stub mode)
2. Starts inventory service (separate thread)
3. Creates job service (thread-per-job)
4. Registers route blueprints
5. Sets up error handlers and context processors

ARCHITECTURE:
    Main Thread
    ├── DLL initialization (ld3s_open)
    ├── Flask request handling
    └── Cleanup on shutdown (ld3s_close)

    Inventory Thread (background)
    └── 30-second refresh loop with OWN API client

    Job Threads (one per submission)
    └── Each with OWN API client, FRESH template

NO SHARED STATE between inventory and job submission.
Each thread creates its own API client for complete isolation.
"""

from __future__ import annotations

import atexit
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, session
from werkzeug.exceptions import RequestEntityTooLarge

from logging_config import setup_logging, get_logger
from core.dll_manager import DLLManager
from core.exceptions import DLLNotFoundError, ServiceUnavailableError
from services.inventory_service import InventoryService
from services.job_service import JobService
from routes import register_blueprints
from modules.i18n import create_translation_filter, get_supported_languages, DEFAULT_LANGUAGE
from modules.printer_config import get_printer_config, update_printer_from_inventory
from modules.image_defaults import get_default_image


# Module logger (configured after setup_logging)
logger = get_logger(__name__)


def _get_base_path() -> Path:
    """
    Get the base path for the application.

    In PyInstaller bundle: Returns the directory containing the executable
    In development: Returns the directory containing app.py
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent


def create_app() -> Flask:
    """
    Application factory - creates and configures Flask app.

    FAIL-FAST: If DLL cannot be loaded, app will not start.
    There is NO stub mode - the blockchain API is required.

    Returns:
        Configured Flask application

    Raises:
        DLLNotFoundError: If ConsumableClient.dll not found
        ServiceUnavailableError: If DLL initialization fails
    """
    # Load .env from base path (next to executable in production)
    # Use override=True so .env file always takes precedence over shell environment
    base_path = _get_base_path()
    env_file = base_path / '.env'
    if env_file.exists():
        load_dotenv(env_file, override=True)
    else:
        load_dotenv(override=True)  # Default behavior

    # Create Flask app
    app = Flask(__name__)
    app.config.from_object("config.Config")

    # Configure logging
    log_level = logging.DEBUG if app.config.get("DEBUG") else logging.INFO
    enable_file_logging = app.config.get("ENVIRONMENT") == "production"

    root_logger = setup_logging(
        app_name="print_order_web",
        log_level=log_level,
        enable_file_logging=enable_file_logging
    )

    # Set Flask's logger to use our configured logger
    app.logger.handlers = root_logger.handlers
    app.logger.setLevel(log_level)

    logger.info(f"Starting PrintOrderWeb in {app.config.get('ENVIRONMENT')} mode")

    # Ensure upload folder exists
    upload_folder = Path(app.config["UPLOAD_FOLDER"])
    upload_folder.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # CORE INITIALIZATION (FAIL-FAST)
    # =========================================================================

    # Initialize DLL manager (main thread only)
    dll_path = app.config.get("CONSUMABLE_DLL_PATH")
    dll_manager = DLLManager(dll_path)

    try:
        dll_manager.initialize()
        logger.info("DLL context initialized successfully")
    except (DLLNotFoundError, ServiceUnavailableError) as e:
        logger.error(f"FATAL: Cannot start application - {e}")
        raise

    # Store in app config for access by routes
    app.config["DLL_MANAGER"] = dll_manager

    # =========================================================================
    # SERVICES INITIALIZATION
    # =========================================================================

    # Create inventory service (starts background thread)
    inventory_service = InventoryService(dll_manager, refresh_interval_seconds=30.0)
    inventory_service.start()
    app.config["INVENTORY_SERVICE"] = inventory_service
    logger.info("Inventory service started")

    # Create job service (manages job threads)
    job_service = JobService(dll_manager)
    app.config["JOB_SERVICE"] = job_service
    logger.info("Job service initialized")

    # =========================================================================
    # HELPER MODULES
    # =========================================================================

    # PDF analyzer
    from modules.pdf_analyzer import PDFAnalyzer
    app.config["PDF_ANALYZER"] = PDFAnalyzer()

    # Estimator
    from modules.estimator import JobEstimator
    # Note: JobEstimator needs inventory, but we'll adapt it
    app.config["ESTIMATOR"] = JobEstimator(inventory_service)

    # Printer config and image defaults modules (for sidebar)
    import modules.printer_config as printer_config_module
    import modules.consumable_details as consumable_details_module
    import modules.image_defaults as image_defaults_module
    app.config["PRINTER_CONFIG_MODULE"] = printer_config_module
    app.config["CONSUMABLE_DETAILS_MODULE"] = consumable_details_module
    app.config["IMAGE_DEFAULTS_MODULE"] = image_defaults_module

    # =========================================================================
    # CLEANUP REGISTRATION
    # =========================================================================

    def cleanup():
        """Cleanup on application shutdown."""
        logger.info("Shutting down...")

        # Stop inventory service
        if inventory_service:
            inventory_service.stop()

        # Wait for job threads
        if job_service:
            job_service.shutdown()

        # Close DLL context
        if dll_manager:
            dll_manager.cleanup()

        logger.info("Shutdown complete")

    atexit.register(cleanup)

    # =========================================================================
    # REGISTER BLUEPRINTS
    # =========================================================================

    register_blueprints(app)

    # =========================================================================
    # CONTEXT PROCESSORS
    # =========================================================================

    @app.context_processor
    def inject_i18n():
        """Inject translation function into all templates."""
        current_lang = session.get("language", DEFAULT_LANGUAGE)
        return {
            "_": create_translation_filter(current_lang),
            "current_language": current_lang,
            "supported_languages": get_supported_languages(),
        }

    @app.context_processor
    def inject_printer_config():
        """Inject printer configuration into all templates."""
        from modules.consumable_details import get_consumable_details

        try:
            snapshot = inventory_service.get_snapshot()

            if not snapshot.toner_balances and not snapshot.media_options:
                return _empty_printer_context()

            # Build toner dict with display names from raw template
            toner_dict = {}
            for t in snapshot.toner_balances:
                # Get display name from raw_template (projectData.Consumable Name)
                display_name = t.color.title()  # Default fallback
                account = snapshot.get_full_account_data(t.color, "toner")
                if account:
                    outer_meta = account.get("metadata", {})
                    inner_meta = outer_meta.get("metadata", {})
                    token_desc = inner_meta.get("tokenDescription", {})
                    project_data = token_desc.get("projectData", {})
                    display_name = project_data.get("Consumable Name", display_name)

                toner_dict[t.color] = {
                    "available": t.balance_ml,
                    "mintId": t.mint_id,
                    "display": display_name,
                }

            printer = update_printer_from_inventory(toner_dict)

            # Build media dict with display names
            media_dict = {}
            for m in snapshot.media_options:
                # Get display name from raw_template
                display_name = m.display_name  # Default from snapshot
                account = snapshot.get_full_account_data(m.mint_id, "media")
                if account:
                    outer_meta = account.get("metadata", {})
                    inner_meta = outer_meta.get("metadata", {})
                    token_desc = inner_meta.get("tokenDescription", {})
                    project_data = token_desc.get("projectData", {})
                    display_name = project_data.get("Consumable Name", display_name)

                media_dict[m.mint_id] = {
                    "available": m.balance_sheets,
                    "display": display_name,
                }

            # Build inventory dict (for compatibility with existing code)
            inventory = {
                "toner_balances": toner_dict,
                "media_options": media_dict,
                "is_stale": snapshot.is_stale,
                "toner_profiles": {
                    "full_color": ["cyan", "magenta", "yellow", "black"],
                    "mono": ["black"],
                },
                "default_turnaround_options": ["standard", "rush", "economy"],
            }

            # Extract consumable details from raw_template for sidebar display
            toner_details = {}
            for toner in snapshot.toner_balances:
                account = snapshot.get_full_account_data(toner.color, "toner")
                if account:
                    toner_details[toner.color] = get_consumable_details("toner", account, inventory)

            media_details = {}
            for media in snapshot.media_options:
                account = snapshot.get_full_account_data(media.mint_id, "media")
                if account:
                    media_details[media.mint_id] = get_consumable_details("media", account, inventory)

            return {
                "printer": printer,
                "inventory": inventory,
                "toner_details": toner_details,
                "media_details": media_details,
                "unattached_consumables": [],
                "default_images": {
                    'toner': get_default_image('Toner'),
                    'media': get_default_image('Media'),
                }
            }

        except Exception as e:
            logger.error(f"Failed to inject printer config: {e}")
            return _empty_printer_context()

    def _empty_printer_context():
        """Return empty printer context for error cases."""
        return {
            "printer": get_printer_config(),
            "inventory": {"error": "Unavailable", "toner_balances": {}, "media_options": {}},
            "toner_details": {},
            "media_details": {},
            "unattached_consumables": [],
            "default_images": {
                'toner': get_default_image('Toner'),
                'media': get_default_image('Media'),
            }
        }

    # =========================================================================
    # ERROR HANDLERS
    # =========================================================================

    @app.errorhandler(RequestEntityTooLarge)
    def handle_file_too_large(e):
        from flask import flash, redirect, url_for
        max_mb = app.config.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024) / (1024 * 1024)
        flash(f"File too large. Maximum upload size is {max_mb:.0f} MB.", "error")
        return redirect(url_for("upload.upload"))

    @app.errorhandler(404)
    def handle_not_found(e):
        from flask import flash, redirect, url_for
        flash("Page not found.", "warning")
        return redirect(url_for("upload.upload"))

    @app.errorhandler(500)
    def handle_server_error(e):
        from flask import flash, redirect, url_for
        logger.error(f"500 error: {e}", exc_info=True)
        flash("An unexpected error occurred. Please try again.", "error")
        return redirect(url_for("upload.upload"))

    # =========================================================================
    # LANGUAGE ROUTE
    # =========================================================================

    @app.route("/set_language/<lang>", methods=["GET"])
    def set_language(lang: str):
        from flask import flash, redirect, request, url_for
        if lang in get_supported_languages():
            session["language"] = lang
            session.modified = True
            flash(f"Language changed to {get_supported_languages()[lang]['name']}.", "success")
        else:
            flash(f"Unsupported language: {lang}", "error")
        return redirect(request.referrer or url_for("upload.upload"))

    logger.info("Application initialized successfully")
    return app


if __name__ == "__main__":
    app = create_app()
    debug_mode = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(debug=debug_mode)
