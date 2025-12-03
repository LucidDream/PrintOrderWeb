"""
Job submission route.

Handles job submission to blockchain.
Creates a FROZEN order snapshot and spawns a job thread.
The job thread is COMPLETELY ISOLATED from inventory.
"""

from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    session,
    url_for,
)

from models.order import Order
from logging_config import get_logger


# Module logger
logger = get_logger(__name__)

submit_bp = Blueprint("submit", __name__)


@submit_bp.route("/submit", methods=["POST"])
def submit():
    """
    Submit job for processing in dedicated thread.

    CRITICAL ARCHITECTURE:
    1. Creates FrozenOrder (immutable snapshot) from session
    2. Spawns job thread via JobService
    3. Job thread creates its OWN API client (isolated from inventory!)
    4. Job thread fetches FRESH template from blockchain
    5. Job thread builds payload, submits, waits for confirmation
    6. Job thread stores result in JobResultStore
    7. Main thread polls status and retrieves result

    NO SHARED STATE between inventory and job submission.
    """
    order_dict = session.get("order")

    # Validation
    if not order_dict or "choices" not in order_dict:
        flash("Please complete job details before submitting.", "error")
        return redirect(url_for("details.details"))

    try:
        job_name = order_dict.get('job_name', 'Unknown Job')
        logger.info(f"Starting job submission for: {job_name}")

        # Get job service from app context
        job_service = current_app.config.get("JOB_SERVICE")
        if not job_service:
            flash("Job service unavailable. Please try again later.", "error")
            return redirect(url_for("review.review"))

        # STEP 1: Convert session dict to Order object
        order = Order.from_dict(order_dict)

        # STEP 2: Create FROZEN (immutable) snapshot
        # This is the ONLY data the job thread will have
        # It cannot be modified, ensuring complete isolation
        frozen_order = order.freeze()

        logger.info(f"Created frozen order: {frozen_order.job_name}")
        logger.debug(f"  Quantity: {frozen_order.quantity}")
        logger.debug(f"  Media: {frozen_order.media_type}")
        logger.debug(f"  Sheets: {frozen_order.sheets_required}")
        logger.debug(f"  Toner: {frozen_order.toner_usage}")

        # STEP 3: Submit to job service (spawns thread)
        # The job thread will:
        # - Create its OWN API client
        # - Fetch FRESH template
        # - Build payload from frozen_order
        # - Submit to blockchain
        # - Store result in JobResultStore
        job_id = job_service.submit_job(frozen_order)

        logger.info(f"Job submitted: {job_id}")

        # STEP 4: Store job ID in session for status polling
        session["job_id"] = job_id
        session["job_start_time"] = datetime.utcnow().isoformat()
        session.modified = True

        # Redirect to processing page for AJAX polling
        return redirect(url_for("submit.processing"))

    except Exception as e:
        logger.error(f"Failed to submit job: {e}", exc_info=True)
        flash(f"Failed to start job: {str(e)}", "error")

        # Store error in session
        order_dict["result"] = {
            "job_id": "error",
            "submitted_at": datetime.utcnow().isoformat(),
            "status": "failed",
            "ledger_entries": [],
            "estimated_cost": order_dict.get("estimate", {}).get("estimated_cost", 0),
            "transaction_success": False,
            "notes": f"Submission error: {str(e)}"
        }
        session.modified = True

        return redirect(url_for("confirmation.confirmation"))


@submit_bp.route("/processing", methods=["GET"])
def processing():
    """
    Display processing page with real-time progress updates.

    This page uses AJAX to poll job status and redirect when complete.
    """
    order = session.get("order")
    job_id = session.get("job_id")

    if not order or not job_id:
        flash("No active job found. Please submit a new order.", "warning")
        return redirect(url_for("upload.upload"))

    from flask import render_template
    return render_template("processing.html", order=order)
