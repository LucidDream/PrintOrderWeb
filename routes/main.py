"""
Main routes (home, demo).

Simple landing pages and redirects.
"""

from flask import Blueprint, redirect, render_template, url_for

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Redirect root to demo page (home page)."""
    return redirect(url_for("main.demo"))


@main_bp.route("/demo", methods=["GET"])
def demo():
    """
    Demo page showcasing authenticated ink verification UI.

    Displays printer configuration with ink slot verification status
    and blockchain-authenticated consumable inventory.
    """
    return render_template("demo.html")
