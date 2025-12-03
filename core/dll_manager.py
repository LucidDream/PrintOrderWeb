"""
ConsumableClient DLL lifecycle management.

This module handles loading the ConsumableClient.dll and managing the
DLL context handle. The context is initialized once in the main thread
at application startup and closed on shutdown.

THREAD SAFETY:
    - initialize() must be called from main thread only
    - cleanup() must be called from main thread only
    - context_handle and library properties are read-only and thread-safe
    - Worker threads use these properties to create their own API clients

FAIL FAST BEHAVIOR:
    - If DLL file not found: raises DLLNotFoundError
    - If ld3s_open() fails: raises ServiceUnavailableError
    - NO stub mode fallback - application will not start without working DLL

Usage:
    # At application startup (main thread)
    dll_manager = DLLManager(Path("ConsumableClient.dll"))
    dll_manager.initialize()

    # Worker threads access shared resources
    api_client = ConsumableAPIClient(
        dll_manager.context_handle,
        dll_manager.library,
        logger
    )

    # At application shutdown (main thread)
    dll_manager.cleanup()
"""

from __future__ import annotations

import logging
from ctypes import cdll, c_void_p
from pathlib import Path
from typing import Optional

from .exceptions import DLLNotFoundError, ServiceUnavailableError


class DLLManager:
    """
    Manages ConsumableClient.dll lifecycle.

    This class is responsible for:
    1. Loading the DLL at application startup
    2. Calling ld3s_open() to initialize the context
    3. Providing read-only access to the context handle for worker threads
    4. Calling ld3s_close() at application shutdown

    The DLL context handle is an integer that represents the connection
    to the ConsumableLedger backend service. All API calls require this
    context handle.

    Attributes:
        dll_path: Path to ConsumableClient.dll
        is_initialized: True if DLL context is active
        context_handle: Integer context handle (read-only after init)
        library: ctypes.CDLL instance (read-only after init)
    """

    def __init__(self, dll_path: str | Path, logger: Optional[logging.Logger] = None):
        """
        Initialize DLL manager.

        Args:
            dll_path: Path to ConsumableClient.dll (string or Path object)
            logger: Logger instance (optional, creates default if not provided)

        Note:
            This does NOT load the DLL - call initialize() to do that.
        """
        # Accept both str and Path
        self._dll_path = Path(dll_path) if isinstance(dll_path, str) else dll_path
        self._logger = logger or logging.getLogger("core.dll_manager")
        self._library = None
        self._context_handle: Optional[int] = None
        self._is_initialized = False

    @property
    def dll_path(self) -> Path:
        """Path to the DLL file."""
        return self._dll_path

    @property
    def is_initialized(self) -> bool:
        """True if DLL is loaded and context is active."""
        return self._is_initialized

    @property
    def context_handle(self) -> int:
        """
        DLL context handle for API calls.

        This is the integer value returned by ld3s_open().
        Worker threads pass this to ConsumableAPIClient.

        Raises:
            RuntimeError: If DLL not initialized
        """
        if not self._is_initialized or self._context_handle is None:
            raise RuntimeError("DLL not initialized - call initialize() first")
        return self._context_handle

    @property
    def library(self):
        """
        ctypes.CDLL instance for API calls.

        Worker threads pass this to ConsumableAPIClient.

        Raises:
            RuntimeError: If DLL not initialized
        """
        if not self._is_initialized or self._library is None:
            raise RuntimeError("DLL not initialized - call initialize() first")
        return self._library

    def initialize(self) -> int:
        """
        Load DLL and initialize context.

        MUST be called from the main thread only.
        FAILS FAST if DLL not found or service unavailable.

        Returns:
            Context handle (integer) for API calls

        Raises:
            DLLNotFoundError: If DLL file does not exist
            ServiceUnavailableError: If ld3s_open() fails
            RuntimeError: If called when already initialized
        """
        if self._is_initialized:
            raise RuntimeError("DLL already initialized")

        self._logger.info(f"[MainThread] Initializing DLL: {self._dll_path}")

        # FAIL FAST: DLL must exist
        if not self._dll_path.exists():
            self._logger.critical(f"[MainThread] DLL not found: {self._dll_path}")
            raise DLLNotFoundError(str(self._dll_path))

        # Load the DLL
        try:
            self._library = cdll.LoadLibrary(str(self._dll_path))
            self._logger.info(f"[MainThread] DLL loaded successfully")
        except OSError as e:
            self._logger.critical(f"[MainThread] Failed to load DLL: {e}")
            raise ServiceUnavailableError(f"Failed to load DLL: {e}")

        # Setup ld3s_open function signature
        self._library.ld3s_open.argtypes = []
        self._library.ld3s_open.restype = c_void_p

        # Setup ld3s_close function signature
        self._library.ld3s_close.argtypes = [c_void_p]
        self._library.ld3s_close.restype = None

        # Call ld3s_open to get context handle
        self._logger.info("[MainThread] Calling ld3s_open()...")
        context = self._library.ld3s_open()

        # FAIL FAST: Context must be valid
        if not context:
            self._logger.critical("[MainThread] ld3s_open() returned NULL")
            self._logger.critical("[MainThread] Is the ConsumableLedger service running?")
            raise ServiceUnavailableError(
                "ld3s_open() returned NULL - ConsumableLedger service is not running"
            )

        self._context_handle = context
        self._is_initialized = True

        self._logger.info(f"[MainThread] DLL context initialized: {context}")
        return context

    def cleanup(self) -> None:
        """
        Close DLL context and release resources.

        MUST be called from the main thread only.
        Safe to call multiple times (idempotent).
        """
        if not self._is_initialized:
            self._logger.debug("[MainThread] DLL not initialized, nothing to clean up")
            return

        if self._context_handle and self._library:
            try:
                self._logger.info("[MainThread] Calling ld3s_close()...")
                self._library.ld3s_close(c_void_p(self._context_handle))
                self._logger.info("[MainThread] DLL context closed successfully")
            except Exception as e:
                self._logger.error(f"[MainThread] Error closing DLL context: {e}")

        self._context_handle = None
        self._is_initialized = False

    def __enter__(self) -> "DLLManager":
        """Context manager entry - initialize DLL."""
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - cleanup DLL."""
        self.cleanup()
