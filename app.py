from __future__ import annotations

import os
import logging
import bleach
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

import threading
import atexit
from ctypes import cdll, c_void_p

from logging_config import setup_logging
from modules.api_client_threaded import ThreadSafeAPIClient, ConsumableClientAPIStub
from modules.estimator import JobEstimator
from modules.inventory_threaded import ThreadedInventoryService
from modules.job_processor import JobProcessor
from modules.pdf_analyzer import PDFAnalyzer
from modules.i18n import create_translation_filter, get_supported_languages, DEFAULT_LANGUAGE
from modules.printer_config import get_printer_config, update_printer_from_inventory
from modules.consumable_details import get_consumable_details
from modules.image_defaults import get_default_image


ALLOWED_EXTENSIONS = {"pdf"}
MAX_FILENAME_LENGTH = 255
MAX_JOB_NAME_LENGTH = 200
MAX_NOTES_LENGTH = 1000

# Global DLL context handle (initialized in main thread)
_dll_context_handle = None
_dll_lib = None
_dll_path = None
_inventory_service = None

# Thread-safe result storage for job threads
_job_results = {}
_job_results_lock = threading.Lock()

# Temporary background finalization poller (removable once CL returns sane expenditures)
_finalizer_queue = []
_finalizer_lock = threading.Lock()
_finalizer_stop = threading.Event()


def sanitize_text(text: str, max_length: int = None) -> str:
    """
    Sanitize user input text to prevent XSS and injection attacks.

    Args:
        text: Raw input text
        max_length: Optional maximum length to enforce

    Returns:
        Sanitized text safe for storage and display
    """
    if not text:
        return ""

    # Strip whitespace
    text = text.strip()

    # Bleach HTML tags and attributes
    text = bleach.clean(text, tags=[], strip=True)

    # Truncate if needed
    if max_length and len(text) > max_length:
        text = text[:max_length]

    return text


def validate_file_size(content_length: int) -> tuple[bool, str]:
    """
    Validate that the uploaded file size is within limits.

    Args:
        content_length: Size of the file in bytes

    Returns:
        Tuple of (is_valid, error_message)
    """
    max_size = 16 * 1024 * 1024  # 16 MB

    if content_length > max_size:
        max_mb = max_size / (1024 * 1024)
        actual_mb = content_length / (1024 * 1024)
        return False, f"File too large ({actual_mb:.1f} MB). Maximum size is {max_mb:.0f} MB."

    return True, ""


def create_app() -> Flask:
    """Factory to create and configure the Flask application."""
    load_dotenv()

    app = Flask(__name__)
    app.config.from_object("config.Config")

    # Configure comprehensive logging
    log_level = logging.DEBUG if app.config.get("DEBUG") else logging.INFO
    enable_file_logging = app.config.get("ENVIRONMENT") == "production"

    logger = setup_logging(
        app_name="print_order_web",
        log_level=log_level,
        enable_file_logging=enable_file_logging
    )

    # Set app logger to use our configured logger
    app.logger.handlers = logger.handlers
    app.logger.setLevel(log_level)

    app.logger.info(f"Starting Print Order Web in {app.config.get('ENVIRONMENT')} mode")

    upload_folder = Path(app.config["UPLOAD_FOLDER"])
    upload_folder.mkdir(parents=True, exist_ok=True)
    app.logger.debug(f"Upload folder: {upload_folder}")

    # CRITICAL: Initialize DLL context in MAIN THREAD
    global _dll_context_handle, _dll_path, _dll_lib, _inventory_service
    _dll_context_handle = _initialize_dll_context(app)

    # Create threaded inventory service
    _inventory_service = ThreadedInventoryService(
        context_handle=_dll_context_handle,
        library=_dll_lib,
        dll_path=app.config.get("CONSUMABLE_DLL_PATH", ""),
        logger=app.logger,
        cache_duration=30
    )

    # Start inventory background thread
    _inventory_service.start()
    app.logger.info("[Main Thread] ✓ Inventory service started")

    # Register cleanup on shutdown
    atexit.register(lambda: _cleanup_dll_context(app.logger))

    # Create simple services (no API dependency)
    pdf_analyzer = PDFAnalyzer()
    estimator = JobEstimator(_inventory_service)

    def allowed_file(filename: str) -> bool:
        return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

    def get_order() -> Dict[str, Any]:
        return session.setdefault("order", {})

    @app.route("/")
    def index() -> Any:
        """Redirect root to demo page (home page)."""
        return redirect(url_for("demo"))

    @app.route("/demo", methods=["GET"])
    def demo() -> Any:
        """
        Demo page showcasing authenticated ink verification UI.

        Displays printer configuration with ink slot verification status
        and blockchain-authenticated consumable inventory.
        """
        return render_template("demo.html")

    @app.route("/api/sidebar_refresh", methods=["GET"])
    def sidebar_refresh() -> Any:
        """
        API endpoint for refreshing sidebar data via AJAX.

        Returns the sidebar HTML partial with fresh inventory data.
        Called periodically by JavaScript to keep sidebar up-to-date.
        """
        try:
            # Force refresh to bypass cache and get latest data
            inventory = _inventory_service.get_inventory_snapshot(force_refresh=True)

            # Check if API is unavailable or returning stale data
            # Treat stale cache as API unavailable for display purposes
            if inventory.get("api_unavailable") or inventory.get("stale") or inventory.get("error"):
                app.logger.warning(f"API unavailable or stale data detected: {inventory.get('error', 'Unknown error')}")
                printer = get_printer_config()
                toner_details = {}
                media_details = {}
                unattached_consumables = []
                # Replace inventory with empty state - don't show stale data
                inventory = {
                    "error": inventory.get("error", "API unavailable"),
                    "api_unavailable": True,
                    "media_options": {},
                    "toner_balances": {},
                }
            else:
                # Update printer config with current inventory
                printer = update_printer_from_inventory(inventory.get("toner_balances", {}))

                # Extract consumable details
                toner_details = {}
                for color_id in inventory.get("toner_balances", {}).keys():
                    account = _inventory_service.get_full_account_data(color_id, "toner")
                    if account:
                        toner_details[color_id] = get_consumable_details("toner", account, inventory)

                media_details = {}
                for media_id in inventory.get("media_options", {}).keys():
                    account = _inventory_service.get_full_account_data(media_id, "media")
                    if account:
                        media_details[media_id] = get_consumable_details("media", account, inventory)

                unattached_consumables = _inventory_service.get_unattached_consumables(printer, inventory)

            # Render just the sidebar partial
            return render_template(
                "partials/authenticated_sidebar.html",
                printer=printer,
                inventory=inventory,
                toner_details=toner_details,
                media_details=media_details,
                unattached_consumables=unattached_consumables,
                default_images={
                    'toner': get_default_image('Toner'),
                    'media': get_default_image('Media'),
                }
            )
        except Exception as e:
            app.logger.error(f"Sidebar refresh failed: {e}", exc_info=True)
            # Return error state sidebar
            return render_template(
                "partials/authenticated_sidebar.html",
                printer=get_printer_config(),
                inventory={
                    "error": "Failed to refresh inventory",
                    "api_unavailable": True,
                    "media_options": {},
                    "toner_balances": {},
                },
                toner_details={},
                media_details={},
                unattached_consumables=[],
                default_images={
                    'toner': get_default_image('Toner'),
                    'media': get_default_image('Media'),
                }
            )

    @app.route("/upload", methods=["GET", "POST"])
    def upload() -> Any:
        if request.method == "POST":
            try:
                # Get and sanitize job name
                job_name = sanitize_text(
                    request.form.get("job_name", ""),
                    max_length=MAX_JOB_NAME_LENGTH
                )
                pdf_file = request.files.get("pdf")

                # Validation: Job name required
                if not job_name:
                    flash("Please provide a job name.", "error")
                    return redirect(url_for("upload"))

                # Validation: File required
                if not pdf_file or pdf_file.filename == "":
                    flash("Please choose a PDF file to upload.", "error")
                    return redirect(url_for("upload"))

                # Validation: File type
                if not allowed_file(pdf_file.filename):
                    flash("Unsupported file type. Please upload a PDF document.", "error")
                    return redirect(url_for("upload"))

                # Validation: File size (check content length if available)
                if request.content_length:
                    is_valid, error_msg = validate_file_size(request.content_length)
                    if not is_valid:
                        flash(error_msg, "error")
                        return redirect(url_for("upload"))

                # Validation: Filename length
                if len(pdf_file.filename) > MAX_FILENAME_LENGTH:
                    flash(f"Filename too long. Maximum {MAX_FILENAME_LENGTH} characters.", "error")
                    return redirect(url_for("upload"))

                # Save file
                timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
                safe_name = secure_filename(pdf_file.filename)
                stored_name = f"{timestamp}_{safe_name}"
                stored_path = upload_folder / stored_name

                app.logger.info(f"Saving uploaded file: {stored_name}")
                pdf_file.save(stored_path)

                # Analyze PDF
                app.logger.debug(f"Analyzing PDF: {stored_path}")
                analysis = pdf_analyzer.analyze(stored_path)
                app.logger.info(f"PDF analysis complete: {analysis.get('pages')} pages")

                # Store in session
                order = get_order()
                order.clear()
                order.update(
                    {
                        "job_name": job_name,
                        "uploaded_at": timestamp,
                        "original_filename": safe_name,
                        "stored_filename": stored_name,
                        "stored_path": str(stored_path),
                        "analysis": analysis,
                    }
                )
                session.modified = True

                flash("PDF uploaded successfully.", "success")
                return redirect(url_for("details"))

            except Exception as e:
                app.logger.error(f"Upload failed: {e}", exc_info=True)
                flash(f"Failed to upload file: {str(e)}", "error")
                return redirect(url_for("upload"))

        return render_template("upload.html", order=session.get("order"))

    @app.route("/details", methods=["GET", "POST"])
    def details() -> Any:
        order = session.get("order")
        if not order:
            flash("Please upload a PDF before filling in job details.", "warning")
            return redirect(url_for("upload"))

        # CRITICAL: Always force fresh inventory on POST (estimate generation)
        # This prevents using stale cached data when new consumables are added
        force_refresh = (request.method == "POST")

        # Fetch inventory with error handling
        app.logger.debug(f"Fetching inventory snapshot (force_refresh={force_refresh})")
        inventory = _inventory_service.get_inventory_snapshot(force_refresh=force_refresh)

        # Display warning if inventory fetch had issues
        if inventory.get("error"):
            flash(inventory["error"], "warning")
        if inventory.get("fallback"):
            flash("Inventory system unavailable. Job submission is currently disabled.", "error")

        if request.method == "POST":
            try:
                # Block submission if using fallback inventory
                if inventory.get("fallback"):
                    flash("Cannot submit job - inventory system is unavailable. Please try again later.", "error")
                    return redirect(url_for("details"))

                # Parse and validate quantity
                try:
                    quantity = int(request.form.get("quantity", "0"))
                except ValueError:
                    flash("Invalid quantity. Please enter a valid number.", "error")
                    return redirect(url_for("details"))

                if quantity <= 0:
                    flash("Quantity must be greater than zero.", "error")
                    return redirect(url_for("details"))

                if quantity > 10000:
                    flash("Quantity too large. Maximum is 10,000 copies.", "error")
                    return redirect(url_for("details"))

                # Get and validate selections
                color_mode = request.form.get("color_mode")
                media_type = request.form.get("media_type")
                turnaround = request.form.get("turnaround_time", "standard")
                quality = request.form.get("quality", "standard")

                # Validate quality parameter
                valid_qualities = ["draft", "standard", "high"]
                if quality not in valid_qualities:
                    app.logger.warning(f"Invalid quality value: {quality}, defaulting to standard")
                    quality = "standard"

                # Sanitize notes input
                notes = sanitize_text(
                    request.form.get("notes", ""),
                    max_length=MAX_NOTES_LENGTH
                )

                # Validation: Media type
                if media_type not in inventory["media_options"]:
                    flash("Selected media type is not available.", "error")
                    return redirect(url_for("details"))

                # Validation: Color mode
                if color_mode not in inventory["toner_profiles"]:
                    flash("Selected color mode is not supported.", "error")
                    return redirect(url_for("details"))

                # Validation: Media availability
                media_available = inventory["media_options"][media_type]["available"]
                sheets_needed = quantity * order.get("analysis", {}).get("pages", 1)
                if media_available < sheets_needed:
                    flash(
                        f"Insufficient media. Need {sheets_needed} sheets but only {media_available} available. "
                        f"Please reduce quantity to {media_available // order.get('analysis', {}).get('pages', 1)} or less.",
                        "error"
                    )
                    return redirect(url_for("details"))

                # Look up media display name for better UX
                media_display_name = inventory["media_options"].get(media_type, {}).get("display", media_type)

                # Create choices dict and add to order BEFORE calling estimator
                choices = {
                    "quantity": quantity,
                    "color_mode": color_mode,
                    "media_type": media_type,  # mintId for API submission
                    "media_display_name": media_display_name,  # Human-readable name for display
                    "turnaround_time": turnaround,
                    "quality": quality,  # Print quality setting
                    "notes": notes,
                }

                # Add choices to order so estimator can access them
                order["choices"] = choices

                # Generate estimate (now order has choices!)
                app.logger.debug(f"Generating estimate for {quantity} copies, {color_mode} mode")
                estimate = estimator.estimate(order, inventory)
                app.logger.debug(f"Estimate generated: {estimate}")
                app.logger.debug(f"Toner usage in estimate: {estimate.get('toner_usage', {})}")
                app.logger.debug(f"Sheets required in estimate: {estimate.get('sheets_required', 0)}")

                # Validation: Toner availability
                toner_balances = inventory["toner_balances"]
                toner_profiles = inventory["toner_profiles"]

                # Get the list of toner colors needed for this color mode
                if color_mode in toner_profiles:
                    required_colors = toner_profiles[color_mode]

                    # Check each required toner against estimate
                    for toner_name, required_ml in estimate.get("toner_usage", {}).items():
                        if toner_name in required_colors and toner_name in toner_balances:
                            available_ml = toner_balances[toner_name]["available"]
                            if required_ml > available_ml:
                                flash(
                                    f"Insufficient {toner_name} toner. Need {required_ml:.1f} mL but only {available_ml:.1f} mL available. "
                                    f"Please reduce quantity.",
                                    "error"
                                )
                                return redirect(url_for("details"))

                # Add estimate to order
                order["estimate"] = estimate
                session.modified = True

                app.logger.info(f"Order details saved: {quantity} copies, {color_mode}, {sheets_needed} sheets")
                app.logger.info(f"Estimate saved to session: sheets={estimate.get('sheets_required')}, toner={estimate.get('toner_usage')}")
                return redirect(url_for("review"))

            except Exception as e:
                app.logger.error(f"Error processing details form: {e}", exc_info=True)
                flash(f"Failed to process job details: {str(e)}", "error")
                return redirect(url_for("details"))

        return render_template(
            "details.html",
            order=order,
            inventory=inventory,
        )

    @app.route("/review", methods=["GET"])
    def review() -> Any:
        order = session.get("order")
        if not order or "choices" not in order:
            flash("Please complete job details before review.")
            return redirect(url_for("details"))

        return render_template("review.html", order=order)

    @app.route("/submit", methods=["POST"])
    def submit() -> Any:
        """
        Submit job for processing in dedicated thread.

        Spawns a new thread for this job submission, ensuring complete
        isolation from other jobs and the inventory service.
        """
        order = session.get("order")
        if not order or "choices" not in order:
            flash("Please complete job details before submitting.", "error")
            return redirect(url_for("details"))

        try:
            from uuid import uuid4
            from copy import deepcopy

            job_name = order.get('job_name', 'Unknown Job')
            app.logger.info(f"[Main Thread] Starting threaded job submission for: {job_name}")

            # Generate unique job ID
            job_id = str(uuid4())

            # Create deep copy of order for thread (prevents session contamination)
            order_copy = deepcopy(order)

            # Spawn dedicated thread for this job
            job_thread = threading.Thread(
                target=_job_submission_thread,
                args=(_dll_lib, _dll_context_handle, _dll_path, order_copy, job_id),
                name=f"JobSubmission-{job_name}",
                daemon=False  # Don't kill mid-transaction
            )
            job_thread.start()

            # Store job ID in session for status polling
            session["job_id"] = job_id
            session["job_start_time"] = datetime.utcnow().isoformat()
            session.modified = True

            app.logger.info(f"[Main Thread] ✓ Job thread spawned (ID: {job_id})")

            # Redirect to processing page for AJAX polling
            return redirect(url_for("processing"))

        except Exception as e:
            app.logger.error(f"[Main Thread] Failed to spawn job thread: {e}", exc_info=True)
            flash(f"Failed to start job: {str(e)}", "error")

            # Store error in session
            order["result"] = {
                "job_id": "error",
                "submitted_at": datetime.utcnow().isoformat(),
                "status": "failed",
                "ledger_entries": [],
                "estimated_cost": order.get("estimate", {}).get("estimated_cost", 0),
                "transaction_success": False,
                "notes": f"Thread spawn error: {str(e)}"
            }
            session.modified = True

            return redirect(url_for("confirmation"))

    @app.route("/processing", methods=["GET"])
    def processing() -> Any:
        """
        Display processing page with real-time progress updates.

        This page uses AJAX to poll job status and redirect when complete.
        """
        order = session.get("order")
        job_id = session.get("job_id")

        if not order or not job_id:
            flash("No active job found. Please submit a new order.", "warning")
            return redirect(url_for("upload"))

        return render_template("processing.html", order=order)

    @app.route("/status", methods=["GET"])
    def status() -> Dict[str, Any]:
        """
        AJAX endpoint to check job processing status.

        Reads from thread-safe result storage populated by job threads.
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
            # Check if result is ready (thread-safe read)
            with _job_results_lock:
                result = _job_results.get(job_id)

            if result:
                # Job thread has completed and stored result
                app.logger.info(f"[Main Thread] Job {job_id} completed: {result['status']}")
                app.logger.info(f"[Main Thread]   Retrieved result - Job ID: {result.get('job_id')}, Status: {result.get('status')}, Entries: {len(result.get('ledger_entries', []))}")
                app.logger.info(f"[Main Thread]   Current session order - Job name: {order.get('job_name')}, PDF: {order.get('stored_path')}")

                # Remove from results storage (job is done)
                with _job_results_lock:
                    _job_results.pop(job_id, None)

                # Store result in session
                order["result"] = result
                session.modified = True
                app.logger.info(f"[Main Thread] ✓ Result stored in session['order']['result']")

                # 2025-11-21: Do not force an immediate inventory refresh here.
                # Final ledger settlement is intentionally asynchronous; balances will update via the
                # background inventory thread when the chain finalizes. Forcing a refresh now would give
                # a false sense of completion while CL is still reporting 0 actualExpenditure.

                # Return submission acknowledgement (not final ledger status)
                status_label = result.get("status", "submitted")
                message = result.get("notes") or (
                    "Job submitted for blockchain processing. Balances will update after finalization."
                )
                is_error = (status_label == "failed") or (result.get("transaction_success") is False)
                return {
                    "status": status_label,
                    "progress": 100,
                    "message": message,
                    "complete": True,
                    "error": is_error,
                    "result": result
                }

            # Job still processing (thread hasn't stored result yet)
            return {
                "status": "processing",
                "progress": 25,
                "message": "Submitting job for blockchain processing...",
                "complete": False,
                "error": False
            }

        except Exception as e:
            app.logger.error(f"[Main Thread] Status check failed: {e}", exc_info=True)
            return {
                "status": "error",
                "progress": 0,
                "message": f"Status check error: {str(e)}",
                "complete": True,
                "error": True
            }, 500

    @app.route("/confirmation", methods=["GET"])
    def confirmation() -> Any:
        order = session.get("order")
        if not order or "result" not in order:
            flash("Submit an order to see the confirmation page.")
            return redirect(url_for("upload"))

        return render_template("confirmation.html", order=order)

    @app.route("/start-over", methods=["POST"])
    def start_over() -> Any:
        """
        Clear session and start a new order.

        Force cache refresh to ensure user sees latest consumables
        when starting a new order.
        """
        session.pop("order", None)

        # Force fresh inventory for next page load
        # This ensures user sees any newly added consumables
        _inventory_service.invalidate_cache()
        app.logger.info("Cache invalidated for new order")

        flash("Session cleared. Start a new order.")
        return redirect(url_for("upload"))

    @app.route("/health", methods=["GET"])
    def health() -> Dict[str, Any]:
        """Health check endpoint with API status."""
        health_status = {
            "status": "ok",
            "environment": app.config["ENVIRONMENT"],
            "api_mode": "enabled" if app.config.get("ENABLE_API_MODE") else "disabled",
            "checks": {}
        }

        # Check API connectivity
        try:
            if hasattr(api_client, 'is_initialized'):
                if api_client.is_initialized:
                    health_status["checks"]["api"] = "connected"
                else:
                    health_status["checks"]["api"] = "stub_mode"
            else:
                health_status["checks"]["api"] = "stub_mode"
        except Exception as e:
            health_status["checks"]["api"] = f"error: {str(e)}"
            health_status["status"] = "degraded"

        # Check upload directory
        if upload_folder.exists():
            health_status["checks"]["storage"] = "ok"
        else:
            health_status["checks"]["storage"] = "error: upload directory missing"
            health_status["status"] = "error"

        status_code = 200 if health_status["status"] == "ok" else 503
        return health_status, status_code

    # Global error handlers
    @app.errorhandler(RequestEntityTooLarge)
    def handle_file_too_large(e):
        """Handle file upload size limit exceeded."""
        app.logger.warning(f"File upload size limit exceeded: {e}")
        max_mb = app.config.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024) / (1024 * 1024)
        flash(f"File too large. Maximum upload size is {max_mb:.0f} MB.", "error")
        return redirect(url_for("upload"))

    @app.errorhandler(404)
    def handle_not_found(e):
        """Handle 404 errors."""
        app.logger.warning(f"404 error: {request.url}")
        flash("Page not found.", "warning")
        return redirect(url_for("upload"))

    @app.errorhandler(500)
    def handle_server_error(e):
        """Handle internal server errors."""
        app.logger.error(f"500 error: {e}", exc_info=True)
        flash("An unexpected error occurred. Please try again.", "error")
        return redirect(url_for("upload"))

    # Temporary background finalizer poller (remove once CL reports real expenditures)
    def _start_background_finalizer(app_logger: logging.Logger) -> None:
        """
        Start background polling for job finalization.

        2025-11-21: CL currently writes actualExpenditure=0 in final results. This poller is a
        stopgap intended to poke the status endpoint asynchronously and refresh inventory once
        CL starts reporting real spends. Safe to delete when CL fixes balance reporting.
        """
        def _poll_loop() -> None:
            app_logger.info("[BackgroundFinalizer] Started (temporary mitigation for CL zero-expenditure bug)")

            # Build API client once for this thread (shared DLL handle is thread-safe)
            try:
                api_client = (
                    ThreadSafeAPIClient(_dll_context_handle, _dll_lib, app_logger)
                    if _dll_context_handle
                    else ConsumableClientAPIStub(_dll_path, app_logger)
                )
            except Exception as e:
                app_logger.error(f"[BackgroundFinalizer] Failed to create API client: {e}")
                return

            while not _finalizer_stop.is_set():
                try:
                    # Snapshot queue to avoid holding lock during network calls
                    with _finalizer_lock:
                        queue_snapshot = list(_finalizer_queue)

                    for item in queue_snapshot:
                        job_id = item.get("job_id")
                        job_handle = item.get("job_handle")
                        order_snapshot = item.get("order_snapshot", {})

                        status = api_client.get_job_status(job_handle)
                        if not status or not status.get("final"):
                            continue

                        app_logger.info(
                            f"[BackgroundFinalizer] Final status detected (job_id={job_id}, handle={job_handle})"
                        )

                        try:
                            processor = JobProcessor(api_client, app_logger)
                            parsed = processor._parse_job_result(status, order_snapshot, job_handle)
                            app_logger.info(
                                f"[BackgroundFinalizer] Parsed final result: "
                                f"status={parsed.get('status')}, "
                                f"entries={len(parsed.get('ledger_entries', []))}, "
                                f"transaction_success={parsed.get('transaction_success')}"
                            )
                        except Exception as parse_exc:
                            app_logger.error(
                                f"[BackgroundFinalizer] Failed to parse final result for job_id={job_id}: {parse_exc}",
                                exc_info=True
                            )

                        # Trigger inventory refresh so any corrected balances become visible ASAP
                        try:
                            if _inventory_service:
                                _inventory_service.get_inventory_snapshot(force_refresh=True)
                                app_logger.info("[BackgroundFinalizer] Inventory refresh requested after final status")
                        except Exception as refresh_exc:
                            app_logger.error(
                                f"[BackgroundFinalizer] Inventory refresh failed after final status: {refresh_exc}",
                                exc_info=True
                            )

                        # Remove finalized job from queue
                        with _finalizer_lock:
                            _finalizer_queue[:] = [q for q in _finalizer_queue if q.get("job_id") != job_id]

                except Exception as loop_exc:
                    app_logger.error(f"[BackgroundFinalizer] Poll loop error: {loop_exc}", exc_info=True)

                time.sleep(5)  # avoid hammering CL

            app_logger.info("[BackgroundFinalizer] Stopped")

        if not hasattr(_start_background_finalizer, "_started"):
            _start_background_finalizer._started = True  # type: ignore[attr-defined]
            poll_thread = threading.Thread(
                target=_poll_loop,
                name="CL-BackgroundFinalizer",
                daemon=True
            )
            poll_thread.start()

    def _enqueue_for_background_finalization(job_id: str, job_handle: int, order_snapshot: Dict[str, Any]) -> None:
        """
        Queue a job handle for background finalization polling (temporary CL workaround).

        Args:
            job_id: Unique job identifier
            job_handle: Handle returned by CL submit call
            order_snapshot: Order data used for parsing results (best-effort)
        """
        with _finalizer_lock:
            _finalizer_queue.append({
                "job_id": job_id,
                "job_handle": job_handle,
                "order_snapshot": order_snapshot,
                "queued_at": datetime.utcnow().isoformat(),
            })
            app.logger.info(
                f"[BackgroundFinalizer] Queued job for async finalization polling (temporary CL fix): job_id={job_id}, handle={job_handle}"
            )

    # Thread-based job processing
    def _job_submission_thread(
        library_handle,
        context_handle: Optional[int],
        dll_path: str,
        order: Dict[str, Any],
        job_id: str
    ):
        """
        Job submission worker thread.

        This function runs in a dedicated thread for each job submission.
        It creates its own API client and job processor, ensuring complete
        isolation from other jobs and the inventory service.

        Thread Architecture:
            - Each job gets its own thread with own API client
            - NO deep copy needed - thread owns all data exclusively
            - Thread fetches fresh template (no sharing with inventory)
            - Thread builds payload, submits, polls status
            - Thread stores result in thread-safe storage
            - Thread exits when complete (automatic cleanup)

        Args:
            context_handle: DLL context from main thread (None for stub mode)
            dll_path: Path to ConsumableClient.dll
            order: Order dictionary (copied from session)
            job_id: Unique job identifier for result storage
        """
        from uuid import uuid4
        import json

        thread_id = threading.get_ident()
        thread_logger = logging.getLogger(f"JobThread-{thread_id}")

        # CRITICAL FIX: Configure thread logger with handlers from app logger
        # Without this, thread logs are silently discarded (logger has no handlers)
        if not thread_logger.handlers:
            app_logger = logging.getLogger("print_order_web")
            for handler in app_logger.handlers:
                thread_logger.addHandler(handler)
            thread_logger.setLevel(app_logger.level)
            thread_logger.propagate = False  # Prevent duplicate logs

        try:
            thread_logger.info("=" * 80)
            thread_logger.info(f"[Thread {thread_id}] JOB THREAD STARTED")
            thread_logger.info(f"[Thread {thread_id}] Job Name: {order.get('job_name')}")
            thread_logger.info(f"[Thread {thread_id}] Job ID: {job_id}")
            thread_logger.info(f"[Thread {thread_id}] PDF File: {order.get('stored_path', 'N/A')}")
            thread_logger.info(f"[Thread {thread_id}] Quantity: {order.get('choices', {}).get('quantity', 'N/A')}")
            thread_logger.info(f"[Thread {thread_id}] Estimate: sheets={order.get('estimate', {}).get('sheets_required')}, toner={order.get('estimate', {}).get('toner_usage')}")
            thread_logger.info("=" * 80)

            # Determine mode (stub vs real API)
            is_stub_mode = (context_handle is None)

            if is_stub_mode:
                # Stub mode: Simulate job completion
                thread_logger.info(f"[Thread {thread_id}] Running in STUB MODE")

                # Create stub API client for this thread
                api_client = ConsumableClientAPIStub(dll_path, thread_logger)

                # Simulate job with stub processor
                from modules.job_processor import JobProcessor
                job_processor = JobProcessor(api_client, thread_logger)
                result = job_processor._simulate_job(order)

                thread_logger.info(f"[Thread {thread_id}] ✓ Stub job completed")

            else:
                # Real API mode: Full blockchain submission
                thread_logger.info(f"[Thread {thread_id}] Running in REAL API MODE")

                # Step 1: Create API client for THIS thread
                if library_handle is None:
                    raise RuntimeError("Shared DLL handle is missing for real API mode")
                api_client = ThreadSafeAPIClient(context_handle, library_handle, thread_logger)
                thread_logger.info(f"[Thread {thread_id}] ✓ Thread-specific API client created")

                # Step 2: Create job processor for THIS thread
                from modules.job_processor import JobProcessor
                job_processor = JobProcessor(api_client, thread_logger)
                thread_logger.info(f"[Thread {thread_id}] Thread-specific job processor created")

                # Step 3: Fetch fresh template (THIS thread's data, no sharing!)
                template = api_client.new_job_template()
                thread_logger.info(f"[Thread {thread_id}] Fresh template fetched")

                # Step 4: Build payload (NO DEEP COPY NEEDED - thread owns this data!)
                job_payload = job_processor._build_job_payload(template, order)
                thread_logger.info(f"[Thread {thread_id}] Job payload built")
                
                

                # Log expenditures being submitted
                total_accounts = 0
                accounts_with_expenditure = 0
                for wallet in job_payload.get('inventoryParameters', {}).get('wallets', []):
                    for account in wallet.get('accounts', []):
                        total_accounts += 1
                        expenditure = account.get('currentExpenditure', 0)
                        if expenditure > 0:
                            accounts_with_expenditure += 1
                            mint_id = account.get('mintId', 'unknown')
                            thread_logger.debug(f"[Thread {thread_id}]     Account {mint_id[:8]}...: expenditure={expenditure}")

                thread_logger.info(f"[Thread {thread_id}]   Accounts with expenditure: {accounts_with_expenditure}/{total_accounts}")

                # Step 5: Submit job to blockchain
                job_handle = api_client.submit_job(job_payload)
                thread_logger.info(f"[Thread {thread_id}] ✓ Job submitted, handle={job_handle}")

                # 2025-11-21: Do NOT wait for final ledger results.
                # The ConsumableLedger currently returns zeroed actualExpenditure values during polling,
                # and the UX requirement is to avoid exposing blockchain waits to users.
                # Instead, take a single lightweight status peek (non-blocking) purely for logging/traceability,
                # then record an asynchronous "submitted" result so the UI can move forward immediately.
                initial_status = api_client.get_job_status(job_handle)
                if initial_status:
                    thread_logger.info(
                        f"[Thread {thread_id}] Initial status peek: "
                        f"status={initial_status.get('status')}, final={initial_status.get('final')}"
                    )
                else:
                    thread_logger.info(f"[Thread {thread_id}] Initial status peek returned no data (expected for async submit)")

                result = {
                    # Preserve the API-provided jobId when available; otherwise fall back to the thread job_id
                    "job_id": (initial_status or {}).get("jobId", job_id),
                    "job_handle": job_handle,
                    "submitted_at": datetime.utcnow().isoformat(),
                    "status": "submitted",
                    # Ledger entries intentionally omitted from user flow to hide blockchain details
                    "ledger_entries": [],
                    "estimated_cost": order.get("estimate", {}).get("estimated_cost", 0),
                    # Transaction success reflects submission acknowledgement, not final ledger state
                    "transaction_success": True,
                    "notes": (
                        "Job submitted for blockchain processing. Finalization continues asynchronously; "
                        "balances will update once the ledger settles."
                    ),
                }

                # Enqueue this handle for temporary background finalization polling.
                # This can be removed once CL returns correct actualExpenditure values.
                _enqueue_for_background_finalization(
                    job_id=job_id,
                    job_handle=job_handle,
                    order_snapshot=order
                )

            # Log parsed result details
            thread_logger.info(f"[Thread {thread_id}] Result parsed:")
            thread_logger.info(f"[Thread {thread_id}]   Status: {result.get('status')}")
            thread_logger.info(f"[Thread {thread_id}]   Transaction success: {result.get('transaction_success')}")
            thread_logger.info(f"[Thread {thread_id}]   Ledger entries: {len(result.get('ledger_entries', []))}")
            thread_logger.info(f"[Thread {thread_id}]   Job ID in result: {result.get('job_id')}")

            # Store result (thread-safe)
            with _job_results_lock:
                _job_results[job_id] = result
                thread_logger.info(f"[Thread {thread_id}] ✓ Result stored in _job_results[{job_id}]")

            thread_logger.info("=" * 80)
            thread_logger.info(f"[Thread {thread_id}] JOB THREAD COMPLETED: {result['status']}")
            thread_logger.info("=" * 80)

        except Exception as e:
            thread_logger.error(f"[Thread {thread_id}] Job thread failed: {e}", exc_info=True)

            # Store error result (thread-safe)
            error_result = {
                "job_id": job_id,
                "submitted_at": datetime.utcnow().isoformat(),
                "status": "failed",
                "ledger_entries": [],
                "estimated_cost": order.get("estimate", {}).get("estimated_cost", 0),
                "transaction_success": False,
                "notes": f"Thread error: {str(e)}"
            }

            with _job_results_lock:
                _job_results[job_id] = error_result

        finally:
            thread_logger.info(f"[Thread {thread_id}] Job thread exiting (cleanup complete)")

    # Language switching route
    @app.route("/set_language/<lang>", methods=["GET"])
    def set_language(lang: str) -> Any:
        """
        Switch application language.

        Args:
            lang: Language code (en, de)

        Returns:
            Redirect to previous page or upload page
        """
        if lang in get_supported_languages():
            session["language"] = lang
            session.modified = True
            app.logger.info(f"Language changed to: {lang}")
            flash(f"Language changed to {get_supported_languages()[lang]['name']}.", "success")
        else:
            flash(f"Unsupported language: {lang}", "error")

        # Redirect back to previous page or upload
        return redirect(request.referrer or url_for("upload"))

    # Context processors for templates
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
        """
        Inject printer configuration and consumable details into all templates.

        This MUST only inject data from the API. If API is unavailable:
        - Show empty/unavailable state
        - Do NOT inject hardcoded fake data
        - Let the template handle the unavailable state gracefully
        """
        try:
            # Get inventory from API - will return empty if unavailable
            inventory = _inventory_service.get_inventory_snapshot()

            # Check if API is unavailable, stale, or has errors
            # Treat stale cache as API unavailable for display purposes
            if inventory.get("api_unavailable") or inventory.get("stale") or inventory.get("error"):
                # API is unavailable or returning stale data - return empty state
                app.logger.warning(f"API unavailable or stale: {inventory.get('error', 'Unknown error')}")
                # Replace inventory with empty state - don't show stale data
                return {
                    "printer": get_printer_config(),  # Empty printer with all unverified
                    "inventory": {
                        "error": inventory.get("error", "API unavailable"),
                        "api_unavailable": True,
                        "media_options": {},
                        "toner_balances": {},
                    },
                    "toner_details": {},
                    "media_details": {},
                    "unattached_consumables": [],
                }

            # Update printer config with current inventory verification
            # Only slots with API data will be marked verified
            printer = update_printer_from_inventory(inventory.get("toner_balances", {}))

            # Extract consumable details for each toner from API
            toner_details = {}
            for color_id in inventory.get("toner_balances", {}).keys():
                account = _inventory_service.get_full_account_data(color_id, "toner")
                if account:
                    toner_details[color_id] = get_consumable_details("toner", account, inventory)

            # Extract consumable details for each media from API
            media_details = {}
            for media_id in inventory.get("media_options", {}).keys():
                account = _inventory_service.get_full_account_data(media_id, "media")
                if account:
                    media_details[media_id] = get_consumable_details("media", account, inventory)

            # Get unattached consumables (in inventory but not mapped to any printer slot)
            unattached_consumables = _inventory_service.get_unattached_consumables(printer, inventory)

            return {
                "printer": printer,
                "inventory": inventory,
                "toner_details": toner_details,
                "media_details": media_details,
                "unattached_consumables": unattached_consumables,
                "default_images": {
                    'toner': get_default_image('Toner'),
                    'media': get_default_image('Media'),
                }
            }
        except Exception as e:
            app.logger.error(f"Failed to inject printer config: {e}", exc_info=True)
            # Return empty state on error - no fake data
            return {
                "printer": get_printer_config(),  # Empty printer, all unverified
                "inventory": {
                    "error": "System error - unable to load inventory",
                    "api_unavailable": True,
                    "media_options": {},
                    "toner_balances": {},
                },
                "toner_details": {},
                "media_details": {},
                "unattached_consumables": [],
                "default_images": {
                    'toner': get_default_image('Toner'),
                    'media': get_default_image('Media'),
                }
            }

    # Kick off temporary background finalizer poller after all helpers are defined.
    # Remove this when CL returns correct actualExpenditure values in status responses.
    _start_background_finalizer(app.logger)

    return app


def _initialize_dll_context(app: Flask) -> Optional[int]:
    """
    Initialize ConsumableClient DLL context in main thread.

    CRITICAL: This must be called from the main thread only.
    The context handle is then passed to worker threads.

    Args:
        app: Flask application instance

    Returns:
        Context handle (int) from ld3s_open(), or None for stub mode
    """
    global _dll_path, _dll_lib

    enable_api = app.config.get("ENABLE_API_MODE", False)
    _dll_path = app.config.get("CONSUMABLE_DLL_PATH")

    if not enable_api:
        app.logger.info("API mode disabled - using stub mode")
        return None

    # Check if DLL exists
    dll_file = Path(_dll_path) if _dll_path else None
    if not dll_file or not dll_file.exists():
        app.logger.warning(
            f"ConsumableClient.dll not found at: {_dll_path}. "
            f"Falling back to stub mode."
        )
        return None

    # Initialize DLL in main thread
    try:
        app.logger.info(f"[Main Thread] Initializing DLL context: {_dll_path}")

        # Load DLL once and keep the handle alive for all threads
        _dll_lib = cdll.LoadLibrary(str(dll_file))

        # Setup ld3s_open function
        _dll_lib.ld3s_open.argtypes = []
        _dll_lib.ld3s_open.restype = c_void_p

        # Call ld3s_open in MAIN THREAD
        context = _dll_lib.ld3s_open()

        if not context:
            app.logger.error("[Main Thread] ld3s_open returned NULL - initialization failed")
            return None

        app.logger.info(f"[Main Thread] ✓ DLL context initialized: {context}")
        return context

    except Exception as e:
        app.logger.error(f"[Main Thread] Failed to initialize DLL context: {e}", exc_info=True)
        app.logger.warning("[Main Thread] Falling back to stub mode")
        return None


def _cleanup_dll_context(logger: logging.Logger):
    """
    Cleanup DLL context in main thread on shutdown.

    CRITICAL: This must be called from the main thread only.
    """
    global _dll_context_handle, _dll_path, _inventory_service

    # Stop inventory background thread
    if _inventory_service:
        logger.info("[Main Thread] Stopping inventory service...")
        _inventory_service.stop()

    # Stop temporary background finalizer poller
    _finalizer_stop.set()

    # Close DLL context
    if _dll_context_handle and _dll_lib:
        try:
            logger.info("[Main Thread] Closing DLL context...")

            # Setup ld3s_close function on the shared library
            _dll_lib.ld3s_close.argtypes = [c_void_p]
            _dll_lib.ld3s_close.restype = None

            # Call ld3s_close in MAIN THREAD
            _dll_lib.ld3s_close(c_void_p(_dll_context_handle))

            logger.info("[Main Thread] ✓ DLL context closed")
        except Exception as e:
            logger.error(f"[Main Thread] Error closing DLL context: {e}", exc_info=True)


if __name__ == "__main__":
    app = create_app()
    debug_mode = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(debug=debug_mode)




