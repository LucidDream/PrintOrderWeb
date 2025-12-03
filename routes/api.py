"""
API routes (AJAX endpoints).

Handles:
- /api/sidebar_refresh - Refresh sidebar inventory display
- /status - Poll job processing status
- /health - Health check endpoint
"""

from flask import (
    Blueprint,
    current_app,
    render_template,
    session,
)

from models.job_result import JobStatus
from logging_config import get_logger


# Module logger
logger = get_logger(__name__)

api_bp = Blueprint("api", __name__)


@api_bp.route("/api/sidebar_refresh", methods=["GET"])
def sidebar_refresh():
    """
    API endpoint for refreshing sidebar data via AJAX.

    Returns the sidebar HTML partial with fresh inventory data.
    Called periodically by JavaScript to keep sidebar up-to-date.

    This uses the INVENTORY SERVICE's cached data (refreshed every 30s).
    It is COMPLETELY SEPARATE from job submission data.
    """
    try:
        inventory_service = current_app.config.get("INVENTORY_SERVICE")

        if not inventory_service:
            return _render_error_sidebar("Inventory service unavailable")

        # Get current snapshot (from background refresh thread)
        snapshot = inventory_service.get_snapshot()

        # Check if data is available
        if not snapshot.toner_balances and not snapshot.media_options:
            return _render_error_sidebar("Inventory not yet loaded")

        # Get helper modules
        printer_config_module = current_app.config.get("PRINTER_CONFIG_MODULE")
        consumable_details_module = current_app.config.get("CONSUMABLE_DETAILS_MODULE")
        image_defaults_module = current_app.config.get("IMAGE_DEFAULTS_MODULE")

        # Build toner dict with display names from raw_template
        toner_dict = {}
        for t in snapshot.toner_balances:
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

        # Build printer config
        if printer_config_module:
            printer = printer_config_module.update_printer_from_inventory(toner_dict)
        else:
            printer = {"slots": []}

        # Build media dict with display names
        media_dict = {}
        for m in snapshot.media_options:
            display_name = m.display_name
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

        # Build inventory dict for templates
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
        media_details = {}
        if consumable_details_module:
            for toner in snapshot.toner_balances:
                account = snapshot.get_full_account_data(toner.color, "toner")
                if account:
                    toner_details[toner.color] = consumable_details_module.get_consumable_details(
                        "toner", account, inventory
                    )

            for media in snapshot.media_options:
                account = snapshot.get_full_account_data(media.mint_id, "media")
                if account:
                    media_details[media.mint_id] = consumable_details_module.get_consumable_details(
                        "media", account, inventory
                    )

        # Get default images
        default_images = {
            'toner': '/static/images/default_toner.svg',
            'media': '/static/images/default_media.svg',
        }
        if image_defaults_module:
            default_images = {
                'toner': image_defaults_module.get_default_image('Toner'),
                'media': image_defaults_module.get_default_image('Media'),
            }

        # Render sidebar partial
        return render_template(
            "partials/authenticated_sidebar.html",
            printer=printer,
            inventory=inventory,
            toner_details=toner_details,
            media_details=media_details,
            unattached_consumables=[],
            default_images=default_images
        )

    except Exception as e:
        logger.error(f"Sidebar refresh failed: {e}", exc_info=True)
        return _render_error_sidebar(f"Refresh failed: {str(e)}")


@api_bp.route("/status", methods=["GET"])
def status():
    """
    AJAX endpoint to check job processing status.

    Reads from JobResultStore populated by job threads.
    Returns JSON with current progress and status information.
    """
    job_id = session.get("job_id")
    order = session.get("order")

    if not job_id or not order:
        return {
            "status": "error",
            "progress": 0,
            "message": "No active job found",
            "complete": True,
            "error": True
        }, 404

    try:
        job_service = current_app.config.get("JOB_SERVICE")

        if not job_service:
            return {
                "status": "error",
                "progress": 0,
                "message": "Job service unavailable",
                "complete": True,
                "error": True
            }, 500

        # Check if result is ready (from JobResultStore)
        result = job_service.get_result(job_id)

        if result:
            # Job thread has completed and stored result
            logger.info(f"Job {job_id[:8]} completed: {result.status.value}")

            # Convert JobResult to dict for session storage
            result_dict = result.to_dict()

            # Store result in session
            order["result"] = result_dict
            session.modified = True
            logger.info(f"Result stored in session")

            # Determine if error
            is_error = (
                result.status == JobStatus.FAILED or
                not result.transaction_success
            )

            return {
                "status": result.status.value,
                "progress": 100,
                "message": result.notes,
                "complete": True,
                "error": is_error,
                "result": result_dict
            }

        # Check if job is still processing
        if job_service.is_job_pending(job_id):
            return {
                "status": "processing",
                "progress": 50,
                "message": "Submitting job to blockchain...",
                "complete": False,
                "error": False
            }

        # Job not found in pending or results - might have expired
        return {
            "status": "unknown",
            "progress": 0,
            "message": "Job status unknown. Please try submitting again.",
            "complete": True,
            "error": True
        }

    except Exception as e:
        logger.error(f"Status check failed: {e}", exc_info=True)
        return {
            "status": "error",
            "progress": 0,
            "message": f"Status check error: {str(e)}",
            "complete": True,
            "error": True
        }, 500


@api_bp.route("/health", methods=["GET"])
def health():
    """Health check endpoint with service status."""
    health_status = {
        "status": "ok",
        "environment": current_app.config.get("ENVIRONMENT", "unknown"),
        "checks": {}
    }

    # Check DLL manager
    dll_manager = current_app.config.get("DLL_MANAGER")
    if dll_manager and dll_manager.is_initialized:
        health_status["checks"]["dll"] = "initialized"
    else:
        health_status["checks"]["dll"] = "not_initialized"
        health_status["status"] = "degraded"

    # Check inventory service
    inventory_service = current_app.config.get("INVENTORY_SERVICE")
    if inventory_service and inventory_service.is_running:
        snapshot = inventory_service.get_snapshot()
        if snapshot.is_stale:
            health_status["checks"]["inventory"] = "stale"
        else:
            health_status["checks"]["inventory"] = "ok"
    else:
        health_status["checks"]["inventory"] = "not_running"
        health_status["status"] = "degraded"

    # Check job service
    job_service = current_app.config.get("JOB_SERVICE")
    if job_service:
        health_status["checks"]["job_service"] = "ok"
    else:
        health_status["checks"]["job_service"] = "not_available"
        health_status["status"] = "degraded"

    status_code = 200 if health_status["status"] == "ok" else 503
    return health_status, status_code


def _render_error_sidebar(error_message: str):
    """Render sidebar with error state."""
    # Get proper printer config (with unverified_count and other required fields)
    printer_config_module = current_app.config.get("PRINTER_CONFIG_MODULE")
    if printer_config_module:
        printer = printer_config_module.get_printer_config()
    else:
        # Fallback with all required template fields
        printer = {
            "slots": [],
            "unverified_count": 0,
            "verified_count": 0,
            "total_slots": 0,
            "model_name": "Unknown",
            "description": "",
            "ink_set_name": "",
            "model_code": "",
        }

    image_defaults_module = current_app.config.get("IMAGE_DEFAULTS_MODULE")
    if image_defaults_module:
        default_images = {
            'toner': image_defaults_module.get_default_image('Toner'),
            'media': image_defaults_module.get_default_image('Media'),
        }
    else:
        default_images = {
            'toner': '/static/images/default_toner.svg',
            'media': '/static/images/default_media.svg',
        }

    return render_template(
        "partials/authenticated_sidebar.html",
        printer=printer,
        inventory={
            "error": error_message,
            "api_unavailable": True,
            "media_options": {},
            "toner_balances": {},
        },
        toner_details={},
        media_details={},
        unattached_consumables=[],
        default_images=default_images
    )


def _snapshot_to_template_dict(snapshot) -> dict:
    """Convert InventorySnapshot to template-compatible dict."""
    toner_balances = {}
    for toner in snapshot.toner_balances:
        toner_balances[toner.color] = {
            "available": toner.balance_ml,
            "mintId": toner.mint_id,
            "slot_number": toner.slot_number,
        }

    media_options = {}
    for media in snapshot.media_options:
        media_options[media.mint_id] = {
            "available": media.balance_sheets,
            "display": media.display_name,
        }

    return {
        "toner_balances": toner_balances,
        "media_options": media_options,
        "is_stale": snapshot.is_stale,
        "age_seconds": snapshot.age_seconds,
    }
