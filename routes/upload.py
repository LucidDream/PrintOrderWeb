"""
PDF upload route.

Handles file upload, validation, and PDF analysis.
Stores order in session and redirects to details.
"""

from datetime import datetime
from pathlib import Path

import bleach
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from logging_config import get_logger


# Module logger
logger = get_logger(__name__)

upload_bp = Blueprint("upload", __name__)

# Constants
ALLOWED_EXTENSIONS = {"pdf"}
MAX_FILENAME_LENGTH = 255
MAX_JOB_NAME_LENGTH = 200


def _allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _sanitize_text(text: str, max_length: int = None) -> str:
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


def _validate_file_size(content_length: int) -> tuple[bool, str]:
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


@upload_bp.route("/upload", methods=["GET", "POST"])
def upload():
    """
    Handle PDF file upload.

    GET: Display upload form
    POST: Process uploaded PDF, analyze, and redirect to details
    """
    if request.method == "POST":
        try:
            # Get and sanitize job name
            job_name = _sanitize_text(
                request.form.get("job_name", ""),
                max_length=MAX_JOB_NAME_LENGTH
            )
            pdf_file = request.files.get("pdf")

            # Validation: Job name required
            if not job_name:
                flash("Please provide a job name.", "error")
                return redirect(url_for("upload.upload"))

            # Validation: File required
            if not pdf_file or pdf_file.filename == "":
                flash("Please choose a PDF file to upload.", "error")
                return redirect(url_for("upload.upload"))

            # Validation: File type
            if not _allowed_file(pdf_file.filename):
                flash("Unsupported file type. Please upload a PDF document.", "error")
                return redirect(url_for("upload.upload"))

            # Validation: File size (check content length if available)
            if request.content_length:
                is_valid, error_msg = _validate_file_size(request.content_length)
                if not is_valid:
                    flash(error_msg, "error")
                    return redirect(url_for("upload.upload"))

            # Validation: Filename length
            if len(pdf_file.filename) > MAX_FILENAME_LENGTH:
                flash(f"Filename too long. Maximum {MAX_FILENAME_LENGTH} characters.", "error")
                return redirect(url_for("upload.upload"))

            # Get upload folder from config
            upload_folder = Path(current_app.config["UPLOAD_FOLDER"])

            # Save file with timestamp prefix
            timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            safe_name = secure_filename(pdf_file.filename)
            stored_name = f"{timestamp}_{safe_name}"
            stored_path = upload_folder / stored_name

            logger.info(f"Saving uploaded file: {stored_name}")
            pdf_file.save(stored_path)

            # Analyze PDF using the analyzer from app context
            pdf_analyzer = current_app.config.get("PDF_ANALYZER")
            if pdf_analyzer:
                logger.debug(f"Analyzing PDF: {stored_path}")
                analysis = pdf_analyzer.analyze(stored_path)
                logger.info(f"PDF analysis complete: {analysis.get('pages')} pages")
            else:
                # Fallback if analyzer not configured
                analysis = {"pages": 1, "width_mm": 210, "height_mm": 297}
                logger.warning("PDF analyzer not configured, using defaults")

            # Store in session (clear any previous order)
            order = session.setdefault("order", {})
            order.clear()
            order.update({
                "job_name": job_name,
                "uploaded_at": timestamp,
                "original_filename": safe_name,
                "stored_filename": stored_name,
                "stored_path": str(stored_path),
                "analysis": analysis,
            })
            session.modified = True

            flash("PDF uploaded successfully.", "success")
            return redirect(url_for("details.details"))

        except Exception as e:
            logger.error(f"Upload failed: {e}", exc_info=True)
            flash(f"Failed to upload file: {str(e)}", "error")
            return redirect(url_for("upload.upload"))

    # GET request - display upload form
    return render_template("upload.html", order=session.get("order"))
