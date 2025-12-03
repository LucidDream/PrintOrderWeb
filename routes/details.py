"""
Job details route.

Handles job configuration: quantity, media, quality, etc.
Generates consumption estimates and validates against inventory.
"""

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

from logging_config import get_logger


# Module logger
logger = get_logger(__name__)

details_bp = Blueprint("details", __name__)

# Constants
MAX_NOTES_LENGTH = 1000
MAX_QUANTITY = 10000


def _sanitize_text(text: str, max_length: int = None) -> str:
    """Sanitize user input text."""
    if not text:
        return ""
    text = text.strip()
    text = bleach.clean(text, tags=[], strip=True)
    if max_length and len(text) > max_length:
        text = text[:max_length]
    return text


@details_bp.route("/details", methods=["GET", "POST"])
def details():
    """
    Handle job configuration.

    GET: Display job details form with current inventory
    POST: Validate choices, generate estimate, redirect to review
    """
    order = session.get("order")
    if not order:
        flash("Please upload a PDF before filling in job details.", "warning")
        return redirect(url_for("upload.upload"))

    # Get services from app context
    inventory_service = current_app.config.get("INVENTORY_SERVICE")
    estimator = current_app.config.get("ESTIMATOR")

    if not inventory_service:
        flash("Inventory service unavailable. Please try again later.", "error")
        return redirect(url_for("upload.upload"))

    # Get inventory snapshot (for display)
    # Note: This is from the SIDEBAR inventory thread, completely separate from job submission
    snapshot = inventory_service.get_snapshot()

    # Check if inventory is ready
    if snapshot.is_stale:
        flash("Inventory data may be outdated. Please verify availability.", "warning")

    # Convert snapshot to template-compatible format
    # (maintains compatibility with existing templates)
    inventory = _snapshot_to_inventory_dict(snapshot)

    if request.method == "POST":
        try:
            # Block submission if no inventory data
            if not snapshot.toner_balances and not snapshot.media_options:
                flash("Cannot proceed - inventory system is unavailable.", "error")
                return redirect(url_for("details.details"))

            # Parse and validate quantity
            try:
                quantity = int(request.form.get("quantity", "0"))
            except ValueError:
                flash("Invalid quantity. Please enter a valid number.", "error")
                return redirect(url_for("details.details"))

            if quantity <= 0:
                flash("Quantity must be greater than zero.", "error")
                return redirect(url_for("details.details"))

            if quantity > MAX_QUANTITY:
                flash(f"Quantity too large. Maximum is {MAX_QUANTITY} copies.", "error")
                return redirect(url_for("details.details"))

            # Get and validate selections
            color_mode = request.form.get("color_mode")
            media_type = request.form.get("media_type")
            turnaround = request.form.get("turnaround_time", "standard")
            quality = request.form.get("quality", "standard")

            # Validate quality parameter
            valid_qualities = ["draft", "standard", "high"]
            if quality not in valid_qualities:
                logger.warning(f"Invalid quality value: {quality}, defaulting to standard")
                quality = "standard"

            # Sanitize notes input
            notes = _sanitize_text(
                request.form.get("notes", ""),
                max_length=MAX_NOTES_LENGTH
            )

            # Validation: Media type exists
            media_option = snapshot.get_media_by_mint_id(media_type)
            if not media_option:
                flash("Selected media type is not available.", "error")
                return redirect(url_for("details.details"))

            # Validation: Media availability
            pages = order.get("analysis", {}).get("pages", 1)
            sheets_needed = quantity * pages
            if media_option.balance_sheets < sheets_needed:
                max_qty = int(media_option.balance_sheets // pages)
                flash(
                    f"Insufficient media. Need {sheets_needed} sheets but only "
                    f"{media_option.balance_sheets:.0f} available. "
                    f"Please reduce quantity to {max_qty} or less.",
                    "error"
                )
                return redirect(url_for("details.details"))

            # Get accurate display name from raw_template
            media_display_name = media_option.display_name  # Default from model
            account = snapshot.get_full_account_data(media_type, "media")
            if account:
                outer_meta = account.get("metadata", {})
                inner_meta = outer_meta.get("metadata", {})
                token_desc = inner_meta.get("tokenDescription", {})
                project_data = token_desc.get("projectData", {})
                media_display_name = project_data.get("Consumable Name") or media_display_name

            # Create choices dict
            choices = {
                "quantity": quantity,
                "color_mode": color_mode,
                "media_type": media_type,
                "media_display_name": media_display_name,
                "turnaround_time": turnaround,
                "quality": quality,
                "notes": notes,
            }

            # Add choices to order so estimator can access them
            order["choices"] = choices

            # Generate estimate
            if estimator:
                logger.debug(f"Generating estimate for {quantity} copies, {color_mode} mode")
                estimate = estimator.estimate(order, inventory)
                logger.debug(f"Estimate generated: {estimate}")

                # Validation: Toner availability
                for color, required_ml in estimate.get("toner_usage", {}).items():
                    toner = snapshot.get_toner_by_color(color)
                    if toner and toner.balance_ml < required_ml:
                        flash(
                            f"Insufficient {color} toner. Need {required_ml:.1f} mL "
                            f"but only {toner.balance_ml:.1f} mL available.",
                            "error"
                        )
                        return redirect(url_for("details.details"))

                order["estimate"] = estimate
            else:
                # Fallback estimate
                order["estimate"] = {
                    "sheets_required": sheets_needed,
                    "toner_usage": {},
                    "estimated_cost": 0.0,
                }

            session.modified = True

            logger.info(f"Order details saved: {quantity} copies, {color_mode}, {sheets_needed} sheets")
            return redirect(url_for("review.review"))

        except Exception as e:
            logger.error(f"Error processing details form: {e}", exc_info=True)
            flash(f"Failed to process job details: {str(e)}", "error")
            return redirect(url_for("details.details"))

    # GET request - display details form
    return render_template(
        "details.html",
        order=order,
        inventory=inventory,
    )


def _snapshot_to_inventory_dict(snapshot) -> dict:
    """
    Convert InventorySnapshot to dictionary format for templates.

    This maintains compatibility with existing Jinja2 templates.
    """
    # Build toner balances dict
    toner_balances = {}
    for toner in snapshot.toner_balances:
        toner_balances[toner.color] = {
            "available": toner.balance_ml,
            "mintId": toner.mint_id,
            "slot_number": toner.slot_number,
        }

    # Build media options dict with display names from raw_template
    media_options = {}
    for media in snapshot.media_options:
        # Get display name from raw_template for accurate display
        display_name = media.display_name  # Default from model
        account = snapshot.get_full_account_data(media.mint_id, "media")
        if account:
            outer_meta = account.get("metadata", {})
            inner_meta = outer_meta.get("metadata", {})
            token_desc = inner_meta.get("tokenDescription", {})
            project_data = token_desc.get("projectData", {})
            # Try "Consumable Name" first (real API), then use model's display_name
            display_name = project_data.get("Consumable Name") or display_name

        media_options[media.mint_id] = {
            "available": media.balance_sheets,
            "display": display_name,
            "width_mm": media.width_mm,
            "height_mm": media.height_mm,
        }

    # Build toner profiles (which toners each color mode uses)
    # Default CMYK profiles
    toner_profiles = {
        "cmyk": ["cyan", "magenta", "yellow", "black"],
        "full_color": ["cyan", "magenta", "yellow", "black"],
    }

    return {
        "toner_balances": toner_balances,
        "media_options": media_options,
        "toner_profiles": toner_profiles,
        "default_turnaround_options": ["standard", "rush", "economy"],
        "is_stale": snapshot.is_stale,
        "age_seconds": snapshot.age_seconds,
    }
