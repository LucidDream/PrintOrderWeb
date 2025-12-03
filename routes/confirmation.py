"""
Confirmation route.

Displays job result after completion.
"""

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    session,
    url_for,
)

from logging_config import get_logger


# Module logger
logger = get_logger(__name__)

confirmation_bp = Blueprint("confirmation", __name__)


@confirmation_bp.route("/confirmation", methods=["GET"])
def confirmation():
    """
    Display job confirmation page.

    Shows result of job submission (success or failure).
    """
    order = session.get("order")

    if not order or "result" not in order:
        flash("Submit an order to see the confirmation page.", "warning")
        return redirect(url_for("upload.upload"))

    return render_template("confirmation.html", order=order)


@confirmation_bp.route("/start-over", methods=["POST"])
def start_over():
    """
    Clear session and start a new order.

    Force cache refresh to ensure user sees latest consumables
    when starting a new order.
    """
    # Clear order from session
    session.pop("order", None)
    session.pop("job_id", None)
    session.pop("job_start_time", None)

    # Force inventory refresh (if available)
    inventory_service = current_app.config.get("INVENTORY_SERVICE")
    if inventory_service:
        inventory_service.force_refresh()
        logger.info("Inventory refresh triggered for new order")

    flash("Session cleared. Start a new order.", "success")
    return redirect(url_for("upload.upload"))
