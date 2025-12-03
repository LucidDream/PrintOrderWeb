"""
Order data models.

These models represent a user's print order as it flows through the
application: upload -> details -> review -> submit.

Thread Safety:
    - Regular Order class for session storage (mutable)
    - Use Order.freeze() to create immutable snapshot for job submission
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, Any, Optional
from copy import deepcopy


@dataclass
class OrderChoices:
    """
    User's choices for a print job.

    Captured on the /details page and stored in session.
    """

    quantity: int
    """Number of copies to print."""

    color_mode: str
    """Color profile (e.g., 'cmyk', 'full_color')."""

    media_type: str
    """Media mintId for blockchain lookup."""

    media_display_name: str
    """Human-readable media name for display."""

    turnaround_time: str = "standard"
    """Turnaround priority: 'rush', 'standard', 'economy'."""

    quality: str = "standard"
    """Print quality: 'draft', 'standard', 'high'."""

    notes: str = ""
    """Optional notes from user."""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for session storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrderChoices":
        """Create from dictionary (e.g., from session)."""
        return cls(
            quantity=data.get("quantity", 0),
            color_mode=data.get("color_mode", ""),
            media_type=data.get("media_type", ""),
            media_display_name=data.get("media_display_name", ""),
            turnaround_time=data.get("turnaround_time", "standard"),
            quality=data.get("quality", "standard"),
            notes=data.get("notes", ""),
        )


@dataclass
class OrderEstimate:
    """
    Estimated resource usage for a print job.

    Calculated by the estimator based on PDF analysis and user choices.
    """

    sheets_required: int
    """Total sheets of media needed."""

    toner_usage: Dict[str, float]
    """Toner usage by color name (e.g., {'cyan': 12.5, 'magenta': 8.2})."""

    estimated_cost: float = 0.0
    """Estimated cost in local currency."""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for session storage."""
        return {
            "sheets_required": self.sheets_required,
            "toner_usage": dict(self.toner_usage),
            "estimated_cost": self.estimated_cost,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrderEstimate":
        """Create from dictionary (e.g., from session)."""
        return cls(
            sheets_required=data.get("sheets_required", 0),
            toner_usage=dict(data.get("toner_usage", {})),
            estimated_cost=data.get("estimated_cost", 0.0),
        )


@dataclass
class Order:
    """
    A print order representing a user's job request.

    Lifecycle:
        1. Created on /upload with PDF file info
        2. Updated on /details with user choices
        3. Updated on /details with estimate
        4. Frozen for job submission thread
        5. Updated on completion with result

    This is a mutable class for easy session management.
    Use freeze() to create an immutable snapshot for job threads.
    """

    # PDF info (set on upload)
    job_name: str = ""
    """User-provided job name."""

    original_filename: str = ""
    """Original PDF filename."""

    stored_filename: str = ""
    """Unique filename on disk (with timestamp prefix)."""

    stored_path: str = ""
    """Full path to stored PDF file."""

    uploaded_at: str = ""
    """ISO timestamp of upload."""

    # PDF analysis (set on upload)
    pages: int = 0
    """Number of pages in PDF."""

    width_mm: float = 0.0
    """Page width in millimeters."""

    height_mm: float = 0.0
    """Page height in millimeters."""

    # User choices (set on details)
    choices: Optional[OrderChoices] = None
    """User's print choices (quantity, media, quality, etc.)."""

    # Estimate (set on details)
    estimate: Optional[OrderEstimate] = None
    """Calculated resource estimate."""

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for session storage.

        This format matches what Flask session expects.
        """
        data = {
            "job_name": self.job_name,
            "original_filename": self.original_filename,
            "stored_filename": self.stored_filename,
            "stored_path": self.stored_path,
            "uploaded_at": self.uploaded_at,
            "analysis": {
                "pages": self.pages,
                "width_mm": self.width_mm,
                "height_mm": self.height_mm,
            },
        }

        if self.choices:
            data["choices"] = self.choices.to_dict()

        if self.estimate:
            data["estimate"] = self.estimate.to_dict()

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Order":
        """
        Create Order from dictionary (e.g., from session).

        Args:
            data: Dictionary from session['order']

        Returns:
            Order instance
        """
        analysis = data.get("analysis", {})

        order = cls(
            job_name=data.get("job_name", ""),
            original_filename=data.get("original_filename", ""),
            stored_filename=data.get("stored_filename", ""),
            stored_path=data.get("stored_path", ""),
            uploaded_at=data.get("uploaded_at", ""),
            pages=analysis.get("pages", 0),
            width_mm=analysis.get("width_mm", 0.0),
            height_mm=analysis.get("height_mm", 0.0),
        )

        # Parse choices if present
        if "choices" in data:
            order.choices = OrderChoices.from_dict(data["choices"])

        # Parse estimate if present
        if "estimate" in data:
            order.estimate = OrderEstimate.from_dict(data["estimate"])

        return order

    def freeze(self) -> "FrozenOrder":
        """
        Create an immutable snapshot of this order.

        Use this when passing order data to job submission threads.
        The frozen order cannot be modified, ensuring thread safety.

        Returns:
            FrozenOrder instance (immutable)
        """
        return FrozenOrder(
            job_name=self.job_name,
            original_filename=self.original_filename,
            stored_filename=self.stored_filename,
            stored_path=self.stored_path,
            uploaded_at=self.uploaded_at,
            pages=self.pages,
            width_mm=self.width_mm,
            height_mm=self.height_mm,
            choices=deepcopy(self.choices.to_dict()) if self.choices else {},
            estimate=deepcopy(self.estimate.to_dict()) if self.estimate else {},
        )


@dataclass(frozen=True)
class FrozenOrder:
    """
    Immutable snapshot of an order for job submission.

    This is a FROZEN dataclass - all attributes are read-only after creation.
    Pass this to job submission threads to ensure they cannot modify the order.

    The job thread owns this data exclusively and can safely read from it
    without any risk of race conditions with the main thread.
    """

    job_name: str
    original_filename: str
    stored_filename: str
    stored_path: str
    uploaded_at: str
    pages: int
    width_mm: float
    height_mm: float
    choices: Dict[str, Any] = field(default_factory=dict)
    estimate: Dict[str, Any] = field(default_factory=dict)

    @property
    def quantity(self) -> int:
        """Number of copies from choices."""
        return self.choices.get("quantity", 0)

    @property
    def color_mode(self) -> str:
        """Color mode from choices."""
        return self.choices.get("color_mode", "")

    @property
    def media_type(self) -> str:
        """Media mintId from choices."""
        return self.choices.get("media_type", "")

    @property
    def quality(self) -> str:
        """Print quality from choices."""
        return self.choices.get("quality", "standard")

    @property
    def toner_usage(self) -> Dict[str, float]:
        """Toner usage from estimate."""
        return self.estimate.get("toner_usage", {})

    @property
    def sheets_required(self) -> int:
        """Sheets required from estimate."""
        return self.estimate.get("sheets_required", 0)
