"""
Core module for PrintOrderWeb.

Contains fundamental infrastructure components:
- exceptions: Custom exception hierarchy
- dll_manager: ConsumableClient DLL lifecycle management
- api_client: Thread-safe API client for blockchain operations
"""

from .exceptions import (
    PrintOrderWebError,
    DLLNotFoundError,
    ServiceUnavailableError,
    InventoryNotReadyError,
    JobSubmissionError,
    InsufficientBalanceError,
    BlockchainTimeoutError,
)
from .dll_manager import DLLManager
from .api_client import ConsumableAPIClient

__all__ = [
    "PrintOrderWebError",
    "DLLNotFoundError",
    "ServiceUnavailableError",
    "InventoryNotReadyError",
    "JobSubmissionError",
    "InsufficientBalanceError",
    "BlockchainTimeoutError",
    "DLLManager",
    "ConsumableAPIClient",
]
