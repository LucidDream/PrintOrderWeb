"""Thread-safe inventory service with background refresh."""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Any, List, Optional

from .api_client_threaded import ThreadSafeAPIClient, ConsumableClientAPIStub


class ThreadedInventoryService:
    """
    Inventory service that runs in a dedicated background thread.

    Architecture:
        - Background thread fetches templates every 30 seconds
        - Thread-safe cache with locks for concurrent access
        - Flask routes read from cache (fast, non-blocking)
        - Automatic refresh keeps sidebar up-to-date

    Thread Safety:
        - _cache and _raw_template protected by _cache_lock
        - Multiple threads can read from cache simultaneously
        - Only background thread writes to cache
    """

    def __init__(
        self,
        context_handle: Optional[int],
        library,
        dll_path: str,
        logger: Optional[logging.Logger] = None,
        cache_duration: int = 30
    ):
        """
        Initialize threaded inventory service.

        Args:
            context_handle: DLL context handle from main thread (None for stub mode)
            library: Shared ctypes.CDLL instance (None in stub mode)
            dll_path: Path to ConsumableClient.dll (for logging only)
            logger: Logger instance
            cache_duration: Seconds between cache refreshes (default 30)
        """
        self.context_handle = context_handle
        self.library = library
        self.dll_path = dll_path
        self.logger = logger or logging.getLogger(__name__)
        self.cache_duration = cache_duration

        # Thread-safe cache
        self._cache: Optional[Dict[str, Any]] = None
        self._raw_template: Optional[Dict[str, Any]] = None
        self._cache_lock = threading.Lock()
        self._last_error: Optional[str] = None

        # Background thread control
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False

        self.logger.info("ThreadedInventoryService initialized")

    def start(self):
        """Start background refresh thread."""
        if self._running:
            self.logger.warning("Inventory refresh thread already running")
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._refresh_loop,
            name="InventoryRefreshThread",
            daemon=True
        )
        self._thread.start()
        self.logger.info("✓ Inventory refresh thread started")

    def stop(self):
        """Stop background refresh thread gracefully."""
        if not self._running:
            return

        self.logger.info("Stopping inventory refresh thread...")
        self._running = False
        self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                self.logger.warning("Inventory thread did not stop within timeout")
            else:
                self.logger.info("✓ Inventory refresh thread stopped")

    def _refresh_loop(self):
        """
        Background thread loop - refreshes inventory every N seconds.

        This thread:
        1. Creates its own API client instance
        2. Fetches fresh template
        3. Parses inventory
        4. Updates cache (thread-safe)
        5. Waits N seconds
        6. Repeats until stop signal
        """
        thread_id = threading.get_ident()
        self.logger.info(f"[Thread {thread_id}] Inventory refresh loop started")

        # Perform initial fetch immediately
        self._perform_refresh(thread_id)

        # Continue with periodic refresh
        while not self._stop_event.is_set():
            # Wait for cache_duration or stop signal
            self._stop_event.wait(timeout=self.cache_duration)

            if self._stop_event.is_set():
                break

            # Refresh inventory
            self._perform_refresh(thread_id)

        self.logger.info(f"[Thread {thread_id}] Inventory refresh loop exited")

    def _perform_refresh(self, thread_id: int):
        """
        Perform single inventory refresh.

        Args:
            thread_id: Thread identifier for logging
        """
        try:
            # Create API client for THIS thread
            if self.context_handle is None:
                api_client = ConsumableClientAPIStub(self.dll_path, self.logger)
            else:
                if self.library is None:
                    raise RuntimeError("Library handle is required for real API mode")
                api_client = ThreadSafeAPIClient(
                    self.context_handle,
                    self.library,
                    self.logger
                )

            # Fetch fresh template
            self.logger.debug(f"[Thread {thread_id}] Fetching fresh inventory template")
            template = api_client.new_job_template()

            # Parse inventory
            inventory = self._parse_template(template)

            # Update cache (thread-safe)
            with self._cache_lock:
                self._cache = inventory
                self._raw_template = template
                self._last_error = None

            # Log summary
            media_count = len(inventory.get("media_options", {}))
            toner_count = len(inventory.get("toner_balances", {}))
            self.logger.info(f"[Thread {thread_id}] ✓ Inventory refreshed: {toner_count} toners, {media_count} media")

        except Exception as e:
            error_msg = f"Inventory refresh failed: {str(e)}"
            self.logger.error(f"[Thread {thread_id}] {error_msg}", exc_info=True)

            # Update error status (thread-safe)
            with self._cache_lock:
                self._last_error = error_msg
                # Keep existing cache (if any) - don't clear on error

    def get_inventory_snapshot(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get inventory snapshot from cache.

        Thread-safe: Multiple threads can call this simultaneously.

        Args:
            force_refresh: If True, triggers immediate refresh in current thread

        Returns:
            Inventory snapshot dictionary
        """
        if force_refresh:
            # Force immediate refresh in CURRENT thread (not background thread)
            thread_id = threading.get_ident()
            self.logger.info(f"[Thread {thread_id}] Force refresh requested")
            self._perform_refresh(thread_id)

        # Read from cache (thread-safe)
        with self._cache_lock:
            if not self._cache:
                # No cache available
                return {
                    "media_options": {},
                    "toner_balances": {},
                    "toner_profiles": {},
                    "default_turnaround_options": [],
                    "error": "Inventory not yet loaded. Please wait...",
                    "api_unavailable": True
                }

            # Check for errors
            if self._last_error:
                # Have cached data but last refresh failed
                cache_with_warning = self._cache.copy()
                cache_with_warning["error"] = "Using cached data - unable to connect to inventory system"
                cache_with_warning["stale"] = True
                return cache_with_warning

            # Return fresh cached data
            return self._cache.copy()

    def invalidate_cache(self) -> None:
        """
        Invalidate the inventory cache.

        Thread-safe: Can be called from any thread.
        """
        with self._cache_lock:
            self._cache = None
            self._raw_template = None
        self.logger.info("Inventory cache invalidated")

    def get_full_account_data(self, account_id: str, consumable_type: str) -> Optional[Dict[str, Any]]:
        """
        Get full account data including metadata.

        Thread-safe: Reads from cached raw template.

        Args:
            account_id: Account identifier (color name or mintId)
            consumable_type: "toner" or "media"

        Returns:
            Full account dictionary or None if not found
        """
        with self._cache_lock:
            if not self._raw_template:
                self.logger.warning("No raw template available")
                return None

            wallets = self._raw_template.get("inventoryParameters", {}).get("wallets", [])

        # Parse outside lock to avoid holding lock too long
        for wallet in wallets:
            for account in wallet.get("accounts", []):
                account_info = self._parse_account(account)
                if account_info["id"] == account_id and account_info["type"] == consumable_type:
                    return account

        return None

    def get_unattached_consumables(
        self,
        printer_config: Dict[str, Any],
        inventory_snapshot: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Get consumables in inventory not attached to printer slots.

        Args:
            printer_config: Printer configuration
            inventory_snapshot: Inventory snapshot

        Returns:
            List of unattached consumables
        """
        unattached = []

        # Get list of slot account IDs
        slot_account_ids = set()
        for slot in printer_config.get("slots", []):
            if slot.get("account_id"):
                slot_account_ids.add(slot["account_id"])

        # Check toner balances for unattached
        for toner_id, toner_data in inventory_snapshot.get("toner_balances", {}).items():
            if toner_id not in slot_account_ids:
                # Get full account for image URL
                full_account = self.get_full_account_data(toner_id, "toner")
                image_url = None
                if full_account:
                    metadata = full_account.get("metadata", {})
                    nested_metadata = metadata.get("metadata", {})
                    token_desc = nested_metadata.get("tokenDescription", {})
                    project_data = token_desc.get("projectData", {})
                    image_url = project_data.get("url")

                unattached.append({
                    "id": toner_id,
                    "display_name": toner_data.get("display", toner_id),
                    "balance": toner_data.get("available", 0),
                    "type": "toner",
                    "uom": "mL",
                    "image_url": image_url
                })

        return unattached

    def _parse_template(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse template into inventory snapshot.

        Args:
            template: Raw template from API

        Returns:
            Inventory snapshot dictionary
        """
        wallets = template.get("inventoryParameters", {}).get("wallets", [])

        media_options = {}
        toner_balances = {}

        for wallet in wallets:
            for account in wallet.get("accounts", []):
                account_info = self._parse_account(account)

                if account_info["type"] == "media":
                    media_options[account_info["id"]] = {
                        "display": account_info["display_name"],
                        "available": int(account_info["balance"]),
                    }
                elif account_info["type"] == "toner":
                    toner_balances[account_info["id"]] = {
                        "display": account_info["display_name"],
                        "available": float(account_info["balance"]),
                    }

        # Define color profiles
        toner_profiles = {
            "full_color": ["cyan", "magenta", "yellow", "black"],
            "mono": ["black"],
        }

        return {
            "media_options": media_options,
            "toner_balances": toner_balances,
            "toner_profiles": toner_profiles,
            "default_turnaround_options": ["standard", "rush", "economy"],
        }

    def _parse_account(self, account: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse account information from template.

        Supports both stub and real API structures.

        Args:
            account: Account dictionary

        Returns:
            Parsed account info with id, type, display_name, balance, uom
        """
        balance = account.get("estimatedBalance", 0)
        metadata = account.get("metadata", {})

        # Try real API structure first (deeply nested)
        nested_metadata = metadata.get("metadata", {})
        if nested_metadata:
            return self._parse_real_api_account(account, nested_metadata, balance)

        # Fall back to stub structure
        return self._parse_stub_account(account, metadata, balance)

    def _parse_real_api_account(
        self,
        account: Dict[str, Any],
        nested_metadata: Dict[str, Any],
        balance: float
    ) -> Dict[str, Any]:
        """Parse account from real API structure."""
        type_indicator = nested_metadata.get("uom", "").lower()
        token_desc = nested_metadata.get("tokenDescription", {})
        project_data = token_desc.get("projectData", {})
        display_name = project_data.get("Consumable Name", account.get("mintId", "Unknown"))

        if type_indicator == "toner":
            color = project_data.get("Color", "").lower()
            uom = project_data.get("Unit of Measure for Spending", "mL")
            return {
                "id": color,
                "type": "toner",
                "display_name": display_name,
                "balance": balance,
                "uom": uom,
                "color": color
            }
        elif type_indicator == "media":
            mint_id = account.get("mintId", "unknown")
            uom = project_data.get("Unit of Measure", "sheets")
            media_type = project_data.get("Media Type", "").lower()
            return {
                "id": mint_id,
                "type": "media",
                "display_name": display_name,
                "balance": balance,
                "uom": uom,
                "media_type": media_type
            }
        else:
            return {
                "id": account.get("mintId", "unknown"),
                "type": "toner",
                "display_name": display_name,
                "balance": balance,
                "uom": "mL"
            }

    def _parse_stub_account(
        self,
        account: Dict[str, Any],
        metadata: Dict[str, Any],
        balance: float
    ) -> Dict[str, Any]:
        """Parse account from stub structure."""
        display_name = metadata.get("displayName", account.get("accountId", "Unknown"))
        uom = metadata.get("uom", "")
        account_id = account.get("accountId", "unknown")

        if uom == "sheets":
            return {
                "id": account_id,
                "type": "media",
                "display_name": display_name,
                "balance": balance,
                "uom": uom
            }
        else:
            return {
                "id": account_id,
                "type": "toner",
                "display_name": display_name,
                "balance": balance,
                "uom": uom or "ml"
            }
