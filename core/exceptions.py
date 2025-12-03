"""
Custom exceptions for PrintOrderWeb.

Exception Hierarchy:
    PrintOrderWebError (base)
    ├── DLLNotFoundError        - DLL file not found (startup failure)
    ├── ServiceUnavailableError - Backend service not running (startup failure)
    ├── InventoryNotReadyError  - Inventory not yet loaded (runtime, graceful)
    └── JobSubmissionError      - Job submission failed (runtime, graceful)
        ├── InsufficientBalanceError - Not enough consumables
        └── BlockchainTimeoutError   - Operation timed out

Usage:
    Startup errors (DLLNotFoundError, ServiceUnavailableError) cause app to fail fast.
    Runtime errors allow graceful handling with user-friendly messages.
"""

from typing import Optional, Dict, Any


class PrintOrderWebError(Exception):
    """
    Base exception for all PrintOrderWeb errors.

    All custom exceptions inherit from this class, allowing callers to catch
    all application-specific errors with a single except clause if needed.
    """

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Initialize the exception.

        Args:
            message: Human-readable error message
            details: Optional dictionary with additional context for debugging
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


# =============================================================================
# STARTUP ERRORS - Application will not start if these occur
# =============================================================================

class DLLNotFoundError(PrintOrderWebError):
    """
    ConsumableClient.dll was not found at the configured path.

    This is a FATAL error - the application cannot function without the DLL.
    The app should display a clear error message and exit.

    Typical causes:
    - DLL not installed
    - Incorrect CONSUMABLE_DLL_PATH in .env
    - Running on non-Windows platform
    """

    def __init__(self, dll_path: str):
        message = f"ConsumableClient.dll not found at: {dll_path}"
        details = {
            "dll_path": dll_path,
            "resolution": "Ensure ConsumableClient.dll is installed and CONSUMABLE_DLL_PATH is correct in .env"
        }
        super().__init__(message, details)
        self.dll_path = dll_path


class ServiceUnavailableError(PrintOrderWebError):
    """
    ConsumableLedger backend service is not running or not responding.

    This is a FATAL error - the application cannot connect to the blockchain
    without the backend service. The app should display a clear error and exit.

    Typical causes:
    - LDConsumables.SSS service not running
    - Network connectivity issues
    - Service crashed or unresponsive
    """

    def __init__(self, message: str = "ConsumableLedger service is not available"):
        details = {
            "service": "LDConsumables.SSS",
            "resolution": "Ensure the ConsumableLedger service is running"
        }
        super().__init__(message, details)


# =============================================================================
# RUNTIME ERRORS - Application continues, but operation fails gracefully
# =============================================================================

class InventoryNotReadyError(PrintOrderWebError):
    """
    Inventory data has not yet been loaded from the blockchain.

    This can occur when:
    - App just started and first refresh hasn't completed
    - Backend service became unavailable after startup
    - Network issues during refresh

    The UI should show a "loading" or "unavailable" state and retry.
    """

    def __init__(self, message: str = "Inventory not yet loaded"):
        details = {
            "resolution": "Wait for inventory refresh or check service connectivity"
        }
        super().__init__(message, details)


class JobSubmissionError(PrintOrderWebError):
    """
    Base class for job submission failures.

    Job submission can fail for various reasons - insufficient inventory,
    blockchain timeout, invalid payload, etc. Subclasses provide specific
    error types with appropriate user messages.
    """

    def __init__(
        self,
        message: str,
        job_id: Optional[str] = None,
        job_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if job_id:
            error_details["job_id"] = job_id
        if job_name:
            error_details["job_name"] = job_name
        super().__init__(message, error_details)
        self.job_id = job_id
        self.job_name = job_name


class InsufficientBalanceError(JobSubmissionError):
    """
    Not enough consumable balance to complete the job.

    This occurs when the estimated usage exceeds available inventory.
    The user should either reduce the job quantity or wait for
    consumables to be replenished.
    """

    def __init__(
        self,
        consumable_type: str,
        consumable_name: str,
        required: float,
        available: float,
        job_id: Optional[str] = None,
        job_name: Optional[str] = None
    ):
        message = (
            f"Insufficient {consumable_name}: "
            f"need {required:.1f}, only {available:.1f} available"
        )
        details = {
            "consumable_type": consumable_type,
            "consumable_name": consumable_name,
            "required": required,
            "available": available,
            "resolution": "Reduce job quantity or wait for consumable replenishment"
        }
        super().__init__(message, job_id, job_name, details)
        self.consumable_type = consumable_type
        self.consumable_name = consumable_name
        self.required = required
        self.available = available


class BlockchainTimeoutError(JobSubmissionError):
    """
    Blockchain operation timed out.

    This can occur during:
    - Job submission (ld3s_submit_job)
    - Status polling (ld3s_get_job_status)
    - Template fetching (ld3s_new_job)

    The blockchain may be busy or experiencing issues.
    The job may still complete - user should check status later.
    """

    def __init__(
        self,
        operation: str,
        timeout_seconds: float,
        job_id: Optional[str] = None,
        job_name: Optional[str] = None
    ):
        message = f"Blockchain {operation} timed out after {timeout_seconds:.1f}s"
        details = {
            "operation": operation,
            "timeout_seconds": timeout_seconds,
            "resolution": "The blockchain may be busy. Job might still complete - check status later."
        }
        super().__init__(message, job_id, job_name, details)
        self.operation = operation
        self.timeout_seconds = timeout_seconds
