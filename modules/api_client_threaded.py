"""Thread-safe ConsumableClient API wrapper for multi-threaded operations."""

from __future__ import annotations

import json
import logging
import threading
import time
from ctypes import c_void_p, c_char_p, c_uint64
from typing import Dict, Any, Optional
from uuid import uuid4


class ThreadSafeAPIClient:
    """
    Thread-safe wrapper for ConsumableClient API v2.0.0.1.

    Each instance operates on the shared DLL context (initialized in main thread)
    but maintains its own thread-local state. Safe for concurrent use across
    multiple threads.

    Architecture:
        - Main thread calls ld3s_open() once at startup
        - Worker threads create ThreadSafeAPIClient instances
        - Each instance uses the shared context handle
        - All operations (new_job, submit, status) are thread-safe
        - Main thread calls ld3s_close() on shutdown

    Usage:
        # Main thread initializes context and loads the DLL once
        context_handle = ld3s_open()
        library = cdll.LoadLibrary("ConsumableClient.dll")

        # Worker thread creates its own client using the shared DLL handle
        api_client = ThreadSafeAPIClient(context_handle, library, logger)
        template = api_client.new_job_template()
        handle = api_client.submit_job(payload)
        status = api_client.wait_for_job_completion(handle)
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
            context_handle: DLL context from ld3s_open() (called in main thread)
            library: Shared ctypes.CDLL instance (loaded in main thread)
            logger: Logger instance (optional)
        """
        if library is None:
            raise ValueError("library handle is required for ThreadSafeAPIClient")

        self.context = c_void_p(context_handle)
        self.lib = library
        self.logger = logger or logging.getLogger(__name__)
        self.thread_id = threading.get_ident()

        # Configure function signatures once per client (idempotent on shared lib)
        self._setup_functions()
        self.logger.info(f"[Thread {self.thread_id}] ThreadSafeAPIClient initialized with shared DLL")

    def _setup_functions(self):
        """Setup DLL function signatures (all thread-safe operations)."""
        # ld3s_new_job - fetch template
        self.lib.ld3s_new_job.argtypes = [c_void_p]
        self.lib.ld3s_new_job.restype = c_char_p

        # ld3s_submit_job - submit job, returns handle
        self.lib.ld3s_submit_job.argtypes = [c_void_p, c_char_p]
        self.lib.ld3s_submit_job.restype = c_uint64

        # ld3s_get_job_status - poll status
        self.lib.ld3s_get_job_status.argtypes = [c_void_p, c_uint64]
        self.lib.ld3s_get_job_status.restype = c_char_p

        # ld3s_free - free memory
        self.lib.ld3s_free.argtypes = [c_void_p, c_void_p]
        self.lib.ld3s_free.restype = None

        # ld3s_get_last_error - error reporting
        self.lib.ld3s_get_last_error.argtypes = [c_void_p]
        self.lib.ld3s_get_last_error.restype = c_char_p

    def new_job_template(self) -> Dict[str, Any]:
        """
        Fetch fresh job template from blockchain.

        Thread-safe: Multiple threads can call this simultaneously.
        Each call returns independent data.

        Returns:
            Job template dictionary with inventoryParameters and jobParameters

        Raises:
            RuntimeError: If API call fails
        """
        self.logger.debug(f"[Thread {self.thread_id}] Fetching job template")

        result_ptr = self.lib.ld3s_new_job(self.context)
        if not result_ptr:
            error = self._get_last_error()
            self.logger.error(f"[Thread {self.thread_id}] new_job failed: {error}")
            raise RuntimeError(f"new_job failed: {error}")

        try:
            json_str = result_ptr.decode('utf-8')
            template = json.loads(json_str)
            self.logger.info(f"[Thread {self.thread_id}] Template fetched successfully")
            return template
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            self.logger.error(f"[Thread {self.thread_id}] Failed to parse template: {e}")
            raise RuntimeError(f"Failed to parse template: {e}")
        finally:
            # Free memory
            self.lib.ld3s_free(self.context, result_ptr)

    def submit_job(self, payload: Dict[str, Any]) -> int:
        """
        Submit job to blockchain.

        Thread-safe: Multiple threads can submit jobs simultaneously.

        Args:
            payload: Job payload dictionary

        Returns:
            Job handle (uint64) for status polling

        Raises:
            RuntimeError: If submission fails
        """
        self.logger.debug(f"[Thread {self.thread_id}] Submitting job")

        try:
            payload_json = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        except (TypeError, ValueError) as e:
            self.logger.error(f"[Thread {self.thread_id}] Failed to serialize payload: {e}")
            raise RuntimeError(f"Failed to serialize payload: {e}")

        job_handle = self.lib.ld3s_submit_job(self.context, payload_json)

        if not job_handle:
            error = self._get_last_error()
            self.logger.error(f"[Thread {self.thread_id}] submit_job failed: {error}")
            raise RuntimeError(f"submit_job failed: {error}")

        self.logger.info(f"[Thread {self.thread_id}] Job submitted successfully, handle={job_handle}")
        return job_handle

    def get_job_status(self, job_handle: int) -> Optional[Dict[str, Any]]:
        """
        Get job status from blockchain.

        Thread-safe: Multiple threads can poll status simultaneously.

        Args:
            job_handle: Job handle from submit_job()

        Returns:
            Status dictionary or None if not ready
        """
        self.logger.debug(f"[Thread {self.thread_id}] Checking status for handle {job_handle}")

        result_ptr = self.lib.ld3s_get_job_status(self.context, c_uint64(job_handle))
        if not result_ptr:
            # No status available yet (not an error)
            return None

        try:
            json_str = result_ptr.decode('utf-8')
            status = json.loads(json_str)
            return status
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            self.logger.error(f"[Thread {self.thread_id}] Failed to parse status: {e}")
            return None
        finally:
            # Free memory
            self.lib.ld3s_free(self.context, result_ptr)

    def wait_for_job_completion(
        self,
        job_handle: int,
        polling_interval_ms: int = 250,
        timeout_seconds: int = 60
    ) -> Dict[str, Any]:
        """
        Poll job status until completion or timeout.

        Thread-safe: Runs in the calling thread.

        Args:
            job_handle: Job handle from submit_job()
            polling_interval_ms: Milliseconds between polls (default 250)
            timeout_seconds: Maximum seconds to wait (default 60)

        Returns:
            Final job status dictionary

        Raises:
            RuntimeError: If timeout occurs
        """
        self.logger.debug(f"[Thread {self.thread_id}] Polling job {job_handle}, timeout={timeout_seconds}s")

        start_time = time.time()
        polling_interval_sec = polling_interval_ms / 1000.0

        while True:
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                self.logger.error(f"[Thread {self.thread_id}] Job {job_handle} timed out after {timeout_seconds}s")
                raise RuntimeError(f"Job polling timed out after {timeout_seconds} seconds")

            # Poll status
            status = self.get_job_status(job_handle)

            if status:
                is_final = status.get("final", False)

                if is_final:
                    self.logger.info(f"[Thread {self.thread_id}] Job {job_handle} completed")
                    return status
                else:
                    self.logger.debug(f"[Thread {self.thread_id}] Job {job_handle} still processing...")

            # Wait before next poll
            time.sleep(polling_interval_sec)

    def _get_last_error(self) -> str:
        """
        Get last error message from DLL.

        Returns:
            Error message string
        """
        error_ptr = self.lib.ld3s_get_last_error(self.context)
        if error_ptr:
            try:
                error_msg = error_ptr.decode('utf-8')
                return error_msg
            except UnicodeDecodeError:
                return "Unknown error (decode failed)"
            finally:
                self.lib.ld3s_free(self.context, error_ptr)
        return "Unknown error"


class ConsumableClientAPIStub:
    """
    Stub implementation for development/testing without real DLL.

    Returns empty inventory and simulates successful job submission.
    Thread-safe for use in multi-threaded environment.
    """

    def __init__(self, dll_path: str = None, logger: Optional[logging.Logger] = None):
        """Initialize stub client."""
        self.dll_path = dll_path
        self.logger = logger or logging.getLogger(__name__)
        self.thread_id = threading.get_ident()
        self.logger.info(f"[Thread {self.thread_id}] Stub API client initialized (no real DLL)")

    def new_job_template(self) -> Dict[str, Any]:
        """Return empty template (stub mode)."""
        self.logger.debug(f"[Thread {self.thread_id}] Stub: Returning empty template")
        return {
            "inventoryParameters": {
                "wallets": []
            },
            "jobParameters": {
                "jobID": f"STUB-{uuid4().hex[:8]}",
                "status": "ready",
                "timestamp": time.time()
            }
        }

    def submit_job(self, payload: Dict[str, Any]) -> int:
        """Return fake job handle (stub mode)."""
        fake_handle = int(time.time() * 1000) % (2**32)
        self.logger.info(f"[Thread {self.thread_id}] Stub: Returning fake handle {fake_handle}")
        return fake_handle

    def get_job_status(self, job_handle: int) -> Dict[str, Any]:
        """Return immediate success status (stub mode)."""
        return {
            "final": True,
            "jobID": f"STUB-{job_handle}",
            "status": "completed",
            "transactionSuccess": True,
            "results": []
        }

    def wait_for_job_completion(
        self,
        job_handle: int,
        polling_interval_ms: int = 250,
        timeout_seconds: int = 60
    ) -> Dict[str, Any]:
        """Return immediate success (stub mode)."""
        self.logger.debug(f"[Thread {self.thread_id}] Stub: Immediate completion")
        return self.get_job_status(job_handle)
