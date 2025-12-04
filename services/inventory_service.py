"""
Inventory service with background refresh thread.

This service manages blockchain inventory data independently from job submission.
It runs a background thread that refreshes inventory every 30 seconds.

COMPLETE THREAD ISOLATION:
    - This service has its OWN ConsumableAPIClient instance
    - It does NOT share any state with job submission
    - Routes read inventory via get_snapshot() which returns immutable data

Thread Safety:
    - Background thread creates new InventorySnapshot on each refresh
    - Main thread reads current snapshot via atomic reference
    - No locks needed - Python's GIL + immutable data = thread-safe

Usage:
    # At app startup
    inventory_service = InventoryService(dll_manager)
    inventory_service.start()

    # In routes (main thread)
    snapshot = inventory_service.get_snapshot()
    if snapshot.is_stale:
        # Show warning, but still use data
        pass

    # At app shutdown
    inventory_service.stop()
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from core.dll_manager import DLLManager
from core.api_client import ConsumableAPIClient
from core.exceptions import InventoryNotReadyError
from models.inventory import InventorySnapshot
from logging_config import get_logger, set_thread_name


# Module logger
logger = get_logger(__name__)


class InventoryService:
    """
    Background service for inventory refresh.

    This service:
    1. Creates its OWN API client (complete isolation from job threads)
    2. Runs a background thread that fetches inventory every 30 seconds
    3. Stores snapshots as immutable objects for thread-safe reading
    4. Provides get_snapshot() for routes to access current inventory

    The service is completely independent from job submission.
    Job threads create their own API clients and fetch their own templates.

    Attributes:
        refresh_interval_seconds: Time between refreshes (default 30)
        is_running: Whether the background thread is active
    """

    def __init__(
        self,
        dll_manager: DLLManager,
        refresh_interval_seconds: float = 30.0
    ):
        """
        Initialize inventory service.

        Args:
            dll_manager: Initialized DLLManager with context handle
            refresh_interval_seconds: Seconds between inventory refreshes

        Raises:
            ValueError: If dll_manager is not initialized
        """
        if not dll_manager.is_initialized:
            raise ValueError("DLLManager must be initialized before creating InventoryService")

        self._dll_manager = dll_manager
        self._refresh_interval = refresh_interval_seconds

        # Thread control
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._is_running = False

        # Current inventory snapshot (atomic reference)
        # Start with empty snapshot so get_snapshot() never returns None
        self._current_snapshot: InventorySnapshot = InventorySnapshot.create_empty()

        # Track consecutive failures for logging
        self._consecutive_failures = 0

        logger.info(f"InventoryService initialized (refresh interval: {refresh_interval_seconds}s)")

    @property
    def is_running(self) -> bool:
        """Whether the background refresh thread is active."""
        return self._is_running

    @property
    def refresh_interval_seconds(self) -> float:
        """Time between inventory refreshes."""
        return self._refresh_interval

    def start(self) -> None:
        """
        Start the background refresh thread.

        The thread will immediately fetch inventory, then refresh every
        refresh_interval_seconds until stop() is called.

        Safe to call multiple times - only starts if not already running.
        """
        if self._is_running:
            logger.warning("InventoryService already running")
            return

        logger.info("Starting inventory refresh thread...")

        # Clear stop event in case of restart
        self._stop_event.clear()

        # Create and start background thread
        self._thread = threading.Thread(
            target=self._refresh_loop,
            name="Inventory",
            daemon=True  # Thread will exit when main process exits
        )
        self._is_running = True
        self._thread.start()

        logger.info("Inventory refresh thread started")

    def stop(self) -> None:
        """
        Stop the background refresh thread.

        Signals the thread to stop and waits for it to finish.
        Safe to call multiple times.
        """
        if not self._is_running:
            return

        logger.info("Stopping inventory refresh thread...")

        # Signal thread to stop
        self._stop_event.set()

        # Wait for thread to finish (with timeout)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

            if self._thread.is_alive():
                logger.warning("Inventory thread did not stop cleanly")

        self._is_running = False
        self._thread = None

        logger.info("Inventory refresh thread stopped")

    def get_snapshot(self) -> InventorySnapshot:
        """
        Get the current inventory snapshot.

        Returns an immutable snapshot that is safe to use from any thread.
        The snapshot may be stale if recent refreshes have failed.

        Returns:
            Current InventorySnapshot (never None)

        Note:
            Check snapshot.is_stale to determine if data is fresh.
            If is_stale is True, consider showing a warning to users.
        """
        return self._current_snapshot

    def get_snapshot_or_raise(self) -> InventorySnapshot:
        """
        Get current snapshot, raising if inventory isn't ready.

        Use this when fresh inventory data is required (e.g., job submission).

        Returns:
            Current InventorySnapshot

        Raises:
            InventoryNotReadyError: If snapshot is empty or very stale (>5 min)
        """
        snapshot = self._current_snapshot

        # Check if we have any data
        if not snapshot.toner_balances and not snapshot.media_options:
            raise InventoryNotReadyError(
                "Inventory not yet loaded. Please wait for initial fetch."
            )

        # Check if data is very stale (more than 5 minutes)
        if snapshot.age_seconds > 300:
            raise InventoryNotReadyError(
                f"Inventory data is {int(snapshot.age_seconds)}s old. "
                "Refresh may have failed - check service status."
            )

        return snapshot

    def force_refresh(self) -> bool:
        """
        Force an immediate inventory refresh.

        This runs in the calling thread, not the background thread.
        Use sparingly - prefer waiting for scheduled refresh.

        Returns:
            True if refresh succeeded, False otherwise
        """
        logger.info("Forcing inventory refresh...")
        return self._do_refresh()

    def _refresh_loop(self) -> None:
        """
        Background thread main loop.

        Fetches inventory immediately, then every refresh_interval_seconds.
        Runs until stop_event is set.
        """
        # Set thread name for logging
        set_thread_name("Inventory")

        logger.info("Inventory refresh loop starting")

        # Initial fetch
        self._do_refresh()

        # Refresh loop
        while not self._stop_event.is_set():
            # Wait for interval (or stop event)
            if self._stop_event.wait(timeout=self._refresh_interval):
                # Stop event was set
                break

            # Refresh inventory
            self._do_refresh()

        logger.info("Inventory refresh loop exiting")

    def _do_refresh(self) -> bool:
        """
        Perform a single inventory refresh.

        Creates a new API client for this fetch (thread owns the client),
        fetches fresh template, and creates new immutable snapshot.

        Returns:
            True if refresh succeeded, False otherwise
        """
        logger.debug("Refreshing inventory...")

        try:
            # Create API client for THIS thread
            # Each refresh gets a fresh client - complete isolation
            api_client = ConsumableAPIClient(
                context_handle=self._dll_manager.context_handle,
                library=self._dll_manager.library,
                logger=logger
            )

            # Fetch fresh template from blockchain
            template = api_client.new_job_template()

            # Create new immutable snapshot
            new_snapshot = InventorySnapshot.from_template(template)

            # Atomic reference swap (Python GIL makes this thread-safe)
            self._current_snapshot = new_snapshot

            # Reset failure counter on success
            if self._consecutive_failures > 0:
                logger.info(
                    f"Inventory refresh recovered after {self._consecutive_failures} failures"
                )
            self._consecutive_failures = 0

            # Log summary at DEBUG level to avoid filling logs every 30 seconds
            # Errors are still logged at WARNING/ERROR level
            logger.debug(
                f"Inventory refreshed: {len(new_snapshot.toner_balances)} toners, "
                f"{len(new_snapshot.media_options)} media options"
            )

            return True

        except Exception as e:
            self._consecutive_failures += 1

            # Log with increasing severity based on consecutive failures
            if self._consecutive_failures == 1:
                logger.warning(f"Inventory refresh failed: {e}")
            elif self._consecutive_failures <= 3:
                logger.error(f"Inventory refresh failed ({self._consecutive_failures} consecutive): {e}")
            else:
                # Only log every 5th failure after that to avoid spam
                if self._consecutive_failures % 5 == 0:
                    logger.error(
                        f"Inventory refresh still failing ({self._consecutive_failures} consecutive): {e}"
                    )

            return False
