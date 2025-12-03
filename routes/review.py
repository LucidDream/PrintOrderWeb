"""
Order review route.

Displays order summary before submission.
"""

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    session,
    url_for,
)


review_bp = Blueprint("review", __name__)


@review_bp.route("/review", methods=["GET"])
def review():
    """
    Display order review page.

    Shows all order details and estimate before submission.
    """
    order = session.get("order")

    # Ensure we have complete order data
    if not order or "choices" not in order:
        flash("Please complete job details before review.", "warning")
        return redirect(url_for("details.details"))

    return render_template("review.html", order=order)
