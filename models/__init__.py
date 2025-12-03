"""
Data models for PrintOrderWeb.

This module contains immutable dataclasses for:
- Order: User's print order (uploaded file, choices, estimate)
- JobSubmission: Frozen snapshot for job thread submission
- JobResult: Result from blockchain job submission
- InventorySnapshot: Point-in-time inventory state

All dataclasses are designed for thread safety:
- JobSubmission is frozen (immutable) for safe passing to threads
- InventorySnapshot is frozen for thread-safe cache reads
"""

from .order import Order, OrderChoices, OrderEstimate
from .job_result import JobResult, LedgerEntry, JobStatus
from .inventory import InventorySnapshot, TonerBalance, MediaOption

__all__ = [
    # Order models
    "Order",
    "OrderChoices",
    "OrderEstimate",
    # Job models
    "JobResult",
    "LedgerEntry",
    "JobStatus",
    # Inventory models
    "InventorySnapshot",
    "TonerBalance",
    "MediaOption",
]
