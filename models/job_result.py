"""
Job result data models.

These models represent the result of a job submission to the blockchain.
Used for communication between job threads and the main Flask thread.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, List, Optional


class JobStatus(Enum):
    """
    Status of a job submission.

    Lifecycle:
        PENDING -> SUBMITTED -> (COMPLETED | FAILED)
    """

    PENDING = "pending"
    """Job is waiting to be submitted."""

    SUBMITTED = "submitted"
    """Job has been submitted, awaiting blockchain confirmation."""

    COMPLETED = "completed"
    """Job completed successfully."""

    FAILED = "failed"
    """Job submission failed."""


@dataclass
class LedgerEntry:
    """
    A single ledger entry from a job result.

    Each consumable (toner color, media) gets its own ledger entry
    recording the amount used and the blockchain transaction.
    """

    account: str
    """Account identifier (color name for toner, mintId for media)."""

    amount: float
    """Amount consumed (mL for toner, sheets for media)."""

    unit: str
    """Unit of measurement ('ml' or 'sheets')."""

    tx_id: str = ""
    """Blockchain transaction ID (empty if not yet confirmed)."""

    success: bool = True
    """Whether this entry was successfully recorded."""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for session storage."""
        return {
            "account": self.account,
            "amount": self.amount,
            "unit": self.unit,
            "txId": self.tx_id,
            "success": self.success,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LedgerEntry":
        """Create from dictionary."""
        return cls(
            account=data.get("account", ""),
            amount=data.get("amount", 0.0),
            unit=data.get("unit", ""),
            tx_id=data.get("txId", data.get("tx_id", "")),
            success=data.get("success", True),
        )


@dataclass
class JobResult:
    """
    Result of a job submission.

    This is stored in the JobResultStore by job threads and retrieved
    by the main thread to update the session.

    Thread Safety:
        - Job thread WRITES to JobResultStore once when complete
        - Main thread READS from JobResultStore (removes on read)
        - No concurrent access to the same JobResult instance
    """

    job_id: str
    """Unique job identifier (UUID)."""

    submitted_at: datetime
    """When the job was submitted."""

    status: JobStatus
    """Current job status."""

    ledger_entries: List[LedgerEntry] = field(default_factory=list)
    """Ledger entries for each consumable."""

    estimated_cost: float = 0.0
    """Estimated cost from the order."""

    transaction_success: bool = False
    """Whether the blockchain transaction succeeded."""

    job_handle: Optional[int] = None
    """DLL job handle (for debugging)."""

    notes: str = ""
    """Additional notes or error messages."""

    @classmethod
    def create_submitted(
        cls,
        job_id: str,
        job_handle: int,
        estimated_cost: float = 0.0
    ) -> "JobResult":
        """
        Create a result for a job that has been submitted.

        Use this immediately after ld3s_submit_job returns.
        The job may still be processing on the blockchain.

        Args:
            job_id: Unique job identifier
            job_handle: Handle from submit_job()
            estimated_cost: Estimated cost from order

        Returns:
            JobResult in SUBMITTED status
        """
        return cls(
            job_id=job_id,
            submitted_at=datetime.now(timezone.utc),
            status=JobStatus.SUBMITTED,
            ledger_entries=[],
            estimated_cost=estimated_cost,
            transaction_success=True,  # Submission succeeded
            job_handle=job_handle,
            notes="Job submitted, awaiting blockchain confirmation.",
        )

    @classmethod
    def create_completed(
        cls,
        job_id: str,
        ledger_entries: List[LedgerEntry],
        estimated_cost: float = 0.0,
        job_handle: Optional[int] = None
    ) -> "JobResult":
        """
        Create a result for a completed job.

        Args:
            job_id: Unique job identifier
            ledger_entries: Ledger entries from blockchain
            estimated_cost: Estimated cost from order
            job_handle: Handle from submit_job()

        Returns:
            JobResult in COMPLETED status
        """
        return cls(
            job_id=job_id,
            submitted_at=datetime.now(timezone.utc),
            status=JobStatus.COMPLETED,
            ledger_entries=ledger_entries,
            estimated_cost=estimated_cost,
            transaction_success=True,
            job_handle=job_handle,
            notes="Job completed successfully.",
        )

    @classmethod
    def create_failed(
        cls,
        job_id: str,
        error_message: str,
        estimated_cost: float = 0.0,
        job_handle: Optional[int] = None
    ) -> "JobResult":
        """
        Create a result for a failed job.

        Args:
            job_id: Unique job identifier
            error_message: Description of the failure
            estimated_cost: Estimated cost from order
            job_handle: Handle from submit_job() (if available)

        Returns:
            JobResult in FAILED status
        """
        return cls(
            job_id=job_id,
            submitted_at=datetime.now(timezone.utc),
            status=JobStatus.FAILED,
            ledger_entries=[],
            estimated_cost=estimated_cost,
            transaction_success=False,
            job_handle=job_handle,
            notes=error_message,
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for session storage.

        This format is compatible with the existing template expectations.
        """
        return {
            "job_id": self.job_id,
            "submitted_at": self.submitted_at.isoformat(),
            "status": self.status.value,
            "ledger_entries": [e.to_dict() for e in self.ledger_entries],
            "estimated_cost": self.estimated_cost,
            "transaction_success": self.transaction_success,
            "job_handle": self.job_handle,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobResult":
        """Create from dictionary (e.g., from session)."""
        # Parse submitted_at
        submitted_at_str = data.get("submitted_at", "")
        if submitted_at_str:
            try:
                submitted_at = datetime.fromisoformat(submitted_at_str)
            except ValueError:
                submitted_at = datetime.now(timezone.utc)
        else:
            submitted_at = datetime.now(timezone.utc)

        # Parse status
        status_str = data.get("status", "pending")
        try:
            status = JobStatus(status_str)
        except ValueError:
            status = JobStatus.PENDING

        # Parse ledger entries
        entries_data = data.get("ledger_entries", [])
        ledger_entries = [LedgerEntry.from_dict(e) for e in entries_data]

        return cls(
            job_id=data.get("job_id", ""),
            submitted_at=submitted_at,
            status=status,
            ledger_entries=ledger_entries,
            estimated_cost=data.get("estimated_cost", 0.0),
            transaction_success=data.get("transaction_success", False),
            job_handle=data.get("job_handle"),
            notes=data.get("notes", ""),
        )
