"""
Thread-safe ConsumableClient API wrapper.

This module provides a clean, thread-safe wrapper for the ConsumableClient DLL.
Each worker thread should create its own ConsumableAPIClient instance using the
shared DLL context handle from DLLManager.

THREAD SAFETY:
    - Each thread creates its own ConsumableAPIClient instance
    - All instances share the same DLL context handle (thread-safe by DLL design)
    - Each API call returns independent data (no shared state between calls)

NO STUB MODE:
    This is production-only code. There is no stub/mock implementation.
    If you need to test without the DLL, mock at the DLLManager level.

Usage:
    # Worker thread creates its own client
    api_client = ConsumableAPIClient(
        dll_manager.context_handle,
        dll_manager.library,
        logger
    )

    # Fetch fresh template (thread's own copy)
    template = api_client.new_job_template()

    # Submit job
    handle = api_client.submit_job(payload)

    # Poll status
    status = api_client.get_job_status(handle)

    # Or wait for completion
    final_status = api_client.wait_for_job_completion(handle, timeout_seconds=60)
"""

from __future__ import annotations

import json
import logging
import threading
import time
from ctypes import c_void_p, c_char_p, c_uint64
from typing import Dict, Any, Optional

from .exceptions import BlockchainTimeoutError, JobSubmissionError


class ConsumableAPIClient:
    """
    Thread-safe wrapper for ConsumableClient API.

    Each thread should create its own instance of this class.
    All instances share the DLL context handle, which is thread-safe by design.

    This class provides methods for:
    - Fetching job templates (inventory data)
    - Submitting jobs to the blockchain
    - Polling job status
    - Waiting for job completion

    Thread Safety Guarantees:
    - new_job_template(): Returns independent data per call
    - submit_job(): Thread-safe, returns unique handle
    - get_job_status(): Thread-safe, non-blocking
    - wait_for_job_completion(): Runs in calling thread

    Attributes:
        thread_id: ID of the thread that owns this client
    """

    def __init__(
        self,
        context_handle: int,
        library,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize thread-safe API client.

        Args:
            context_handle: DLL context from DLLManager.context_handle
            library: Shared ctypes.CDLL from DLLManager.library
            logger: Logger instance (creates default if not provided)

        Raises:
            ValueError: If context_handle or library is None
        """
        if context_handle is None:
            raise ValueError("context_handle is required - DLL must be initialized")
        if library is None:
            raise ValueError("library is required - DLL must be loaded")

        # Store context as ctypes pointer
        self._context = c_void_p(context_handle)
        self._lib = library
        self._logger = logger or logging.getLogger("core.api_client")
        self._thread_id = threading.get_ident()

        # Configure DLL function signatures
        self._setup_functions()

        self._logger.debug(f"[Thread {self._thread_id}] ConsumableAPIClient initialized")

    @property
    def thread_id(self) -> int:
        """ID of the thread that owns this client."""
        return self._thread_id

    def _setup_functions(self) -> None:
        """
        Configure DLL function signatures.

        This is idempotent - safe to call multiple times on the shared library.
        Sets up argument types and return types for all API functions.
        """
        # ld3s_new_job - fetch template from blockchain
        # Returns: JSON string (char*) with inventory and job parameters
        self._lib.ld3s_new_job.argtypes = [c_void_p]
        self._lib.ld3s_new_job.restype = c_char_p

        # ld3s_submit_job - submit job payload to blockchain
        # Returns: Job handle (uint64) for status polling
        self._lib.ld3s_submit_job.argtypes = [c_void_p, c_char_p]
        self._lib.ld3s_submit_job.restype = c_uint64

        # ld3s_get_job_status - poll job status
        # Returns: JSON string (char*) with status info, or NULL if not ready
        self._lib.ld3s_get_job_status.argtypes = [c_void_p, c_uint64]
        self._lib.ld3s_get_job_status.restype = c_char_p

        # ld3s_free - free memory allocated by DLL
        # MUST be called for all returned char* pointers
        self._lib.ld3s_free.argtypes = [c_void_p, c_void_p]
        self._lib.ld3s_free.restype = None

        # ld3s_get_last_error - get error message for failed calls
        self._lib.ld3s_get_last_error.argtypes = [c_void_p]
        self._lib.ld3s_get_last_error.restype = c_char_p

    def new_job_template(self) -> Dict[str, Any]:
        """
        Fetch fresh job template from blockchain.

        This returns a template containing:
        - inventoryParameters: Current inventory (toner/media accounts with balances)
        - jobParameters: Job configuration parameters

        Each call returns independent data - templates are not shared between threads.

        Returns:
            Dictionary with inventoryParameters and jobParameters

        Raises:
            RuntimeError: If API call fails or response is invalid
        """
        self._logger.debug(f"[Thread {self._thread_id}] Fetching job template...")

        # Call DLL function
        result_ptr = self._lib.ld3s_new_job(self._context)

        if not result_ptr:
            error = self._get_last_error()
            self._logger.error(f"[Thread {self._thread_id}] ld3s_new_job failed: {error}")
            raise RuntimeError(f"Failed to fetch job template: {error}")

        try:
            # Parse JSON response
            json_str = result_ptr.decode('utf-8')
            template = json.loads(json_str)

            # Log summary (not full template - it's huge)
            # Use DEBUG level to avoid filling logs during 30-second inventory refreshes
            # Job submission still logs important events at INFO level
            wallets = template.get("inventoryParameters", {}).get("wallets", [])
            account_count = sum(len(w.get("accounts", [])) for w in wallets)
            self._logger.debug(
                f"[Thread {self._thread_id}] Template fetched: {account_count} accounts"
            )

            return template

        except UnicodeDecodeError as e:
            self._logger.error(f"[Thread {self._thread_id}] Failed to decode template: {e}")
            raise RuntimeError(f"Failed to decode template response: {e}")

        except json.JSONDecodeError as e:
            self._logger.error(f"[Thread {self._thread_id}] Invalid JSON in template: {e}")
            raise RuntimeError(f"Invalid JSON in template response: {e}")

        finally:
            # IMPORTANT: Free memory allocated by DLL
            self._lib.ld3s_free(self._context, result_ptr)

    def submit_job(self, payload: Dict[str, Any]) -> int:
        """
        Submit job to blockchain.

        The payload should contain:
        - inventoryParameters: With currentExpenditure values set for consumables
        - jobParameters: Job configuration

        Args:
            payload: Job payload dictionary

        Returns:
            Job handle (uint64) for status polling

        Raises:
            JobSubmissionError: If submission fails
        """
        self._logger.debug(f"[Thread {self._thread_id}] Submitting job...")

        # Serialize payload to JSON
        try:
            payload_json = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        except (TypeError, ValueError) as e:
            self._logger.error(f"[Thread {self._thread_id}] Failed to serialize payload: {e}")
            raise JobSubmissionError(f"Failed to serialize job payload: {e}")

        # Call DLL function
        job_handle = self._lib.ld3s_submit_job(self._context, payload_json)

        if not job_handle:
            error = self._get_last_error()
            self._logger.error(f"[Thread {self._thread_id}] ld3s_submit_job failed: {error}")
            raise JobSubmissionError(f"Job submission failed: {error}")

        self._logger.info(f"[Thread {self._thread_id}] Job submitted: handle={job_handle}")
        return job_handle

    def get_job_status(self, job_handle: int) -> Optional[Dict[str, Any]]:
        """
        Get job status from blockchain (non-blocking).

        This is a lightweight status check. Returns None if status is not
        yet available (job still processing).

        Args:
            job_handle: Job handle from submit_job()

        Returns:
            Status dictionary if available, None if still processing

        The status dictionary typically contains:
            - final: bool - True if job is complete
            - status: str - Status string (e.g., "completed", "failed")
            - jobId: str - Job identifier
            - transactionSuccess: bool - True if transaction succeeded
            - results: list - Result details for each consumable
        """
        self._logger.debug(f"[Thread {self._thread_id}] Checking status for handle {job_handle}")

        # Call DLL function
        result_ptr = self._lib.ld3s_get_job_status(self._context, c_uint64(job_handle))

        if not result_ptr:
            # No status available yet - job still processing
            return None

        try:
            # Parse JSON response
            json_str = result_ptr.decode('utf-8')
            status = json.loads(json_str)

            is_final = status.get("final", False)
            status_str = status.get("status", "unknown")
            self._logger.debug(
                f"[Thread {self._thread_id}] Status: {status_str}, final={is_final}"
            )

            return status

        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            self._logger.error(f"[Thread {self._thread_id}] Failed to parse status: {e}")
            return None

        finally:
            # IMPORTANT: Free memory allocated by DLL
            self._lib.ld3s_free(self._context, result_ptr)

    def wait_for_job_completion(
        self,
        job_handle: int,
        timeout_seconds: float = 60.0,
        polling_interval_ms: int = 250
    ) -> Dict[str, Any]:
        """
        Poll job status until completion or timeout.

        This is a blocking call that runs in the calling thread.
        It repeatedly calls get_job_status() until the job is complete.

        Args:
            job_handle: Job handle from submit_job()
            timeout_seconds: Maximum seconds to wait (default 60)
            polling_interval_ms: Milliseconds between polls (default 250)

        Returns:
            Final job status dictionary

        Raises:
            BlockchainTimeoutError: If timeout occurs before completion
        """
        self._logger.info(
            f"[Thread {self._thread_id}] Waiting for job {job_handle} "
            f"(timeout={timeout_seconds}s, poll_interval={polling_interval_ms}ms)"
        )

        start_time = time.time()
        polling_interval_sec = polling_interval_ms / 1000.0

        while True:
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                self._logger.error(
                    f"[Thread {self._thread_id}] Job {job_handle} timed out after {elapsed:.1f}s"
                )
                raise BlockchainTimeoutError(
                    operation="wait_for_completion",
                    timeout_seconds=timeout_seconds
                )

            # Poll status
            status = self.get_job_status(job_handle)

            if status:
                is_final = status.get("final", False)

                if is_final:
                    self._logger.info(
                        f"[Thread {self._thread_id}] Job {job_handle} completed after {elapsed:.1f}s"
                    )
                    return status

            # Wait before next poll
            time.sleep(polling_interval_sec)

    def _get_last_error(self) -> str:
        """
        Get last error message from DLL.

        Called after a DLL function returns an error indicator (NULL or 0).

        Returns:
            Error message string, or "Unknown error" if not available
        """
        error_ptr = self._lib.ld3s_get_last_error(self._context)

        if error_ptr:
            try:
                error_msg = error_ptr.decode('utf-8')
                return error_msg
            except UnicodeDecodeError:
                return "Unknown error (failed to decode error message)"
            finally:
                # Free memory
                self._lib.ld3s_free(self._context, error_ptr)

        return "Unknown error"
