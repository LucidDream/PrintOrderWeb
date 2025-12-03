"""
Job submission service with thread-per-job architecture.

This service handles job submission to the blockchain in background threads.
Each job gets its own thread and its own API client - complete isolation.

COMPLETE THREAD ISOLATION:
    - Each job thread creates its OWN ConsumableAPIClient
    - Job threads do NOT share API clients with inventory service
    - Job threads do NOT share state with each other
    - JobResultStore is the ONLY communication channel back to main thread

Thread Safety:
    - FrozenOrder is immutable - safe to pass to job thread
    - JobResult is created by job thread, consumed by main thread
    - JobResultStore uses threading.Lock for thread-safe access

Flow:
    1. Main thread creates FrozenOrder (immutable snapshot)
    2. Main thread calls job_service.submit_job(frozen_order)
    3. Job thread starts with its OWN API client
    4. Job thread fetches FRESH template (not cached inventory!)
    5. Job thread builds payload, submits to blockchain
    6. Job thread stores JobResult in JobResultStore
    7. Main thread polls job_service.get_result(job_id)

Usage:
    # At app startup
    job_service = JobService(dll_manager)

    # On job submission (main thread)
    frozen_order = order.freeze()
    job_id = job_service.submit_job(frozen_order)

    # Polling (main thread)
    result = job_service.get_result(job_id)
    if result:
        if result.status == JobStatus.COMPLETED:
            # Success!
        elif result.status == JobStatus.FAILED:
            # Show error

    # At app shutdown
    job_service.shutdown()
"""

from __future__ import annotations

import threading
import uuid
from typing import Dict, Optional

from core.dll_manager import DLLManager
from core.api_client import ConsumableAPIClient
from core.exceptions import JobSubmissionError
from models.order import FrozenOrder
from models.job_result import JobResult, JobStatus, LedgerEntry
from logging_config import get_logger, get_job_logger, set_thread_name


# Module logger
logger = get_logger(__name__)


class JobResultStore:
    """
    Thread-safe storage for job results.

    This is the ONLY communication channel between job threads and main thread.
    Job threads WRITE results here, main thread READS (and removes) results.

    Thread Safety:
        - Uses threading.Lock for all operations
        - Results are stored by job_id
        - get_result() removes the result (consume-once pattern)

    Usage:
        # Job thread writes
        store.put_result(job_result)

        # Main thread reads (removes on read)
        result = store.get_result(job_id)
        if result:
            # Process result
    """

    def __init__(self):
        """Initialize empty result store."""
        self._results: Dict[str, JobResult] = {}
        self._lock = threading.Lock()

    def put_result(self, result: JobResult) -> None:
        """
        Store a job result (called by job thread).

        Args:
            result: JobResult to store
        """
        with self._lock:
            self._results[result.job_id] = result
            logger.debug(f"Stored result for job {result.job_id[:8]}")

    def get_result(self, job_id: str) -> Optional[JobResult]:
        """
        Get and remove a job result (called by main thread).

        This is a consume-once operation - the result is removed after reading.
        Returns None if no result is available yet.

        Args:
            job_id: UUID of the job

        Returns:
            JobResult if available, None otherwise
        """
        with self._lock:
            result = self._results.pop(job_id, None)
            if result:
                logger.debug(f"Retrieved result for job {job_id[:8]}")
            return result

    def peek_result(self, job_id: str) -> Optional[JobResult]:
        """
        Check if a result exists without removing it.

        Use this for status checks without consuming the result.

        Args:
            job_id: UUID of the job

        Returns:
            JobResult if available, None otherwise
        """
        with self._lock:
            return self._results.get(job_id)

    def clear(self) -> int:
        """
        Remove all stored results.

        Returns:
            Number of results removed
        """
        with self._lock:
            count = len(self._results)
            self._results.clear()
            logger.info(f"Cleared {count} job results from store")
            return count


class JobService:
    """
    Service for submitting jobs to the blockchain.

    Creates one thread per job submission. Each thread:
    1. Creates its own ConsumableAPIClient (isolation from inventory)
    2. Fetches a FRESH template from blockchain (not cached!)
    3. Builds the job payload with consumption data
    4. Submits to blockchain and waits for confirmation
    5. Stores result in JobResultStore

    This is completely separate from InventoryService.
    The inventory data shown in the sidebar is NOT used for job submission.

    Attributes:
        result_store: JobResultStore for reading job results
    """

    def __init__(self, dll_manager: DLLManager):
        """
        Initialize job service.

        Args:
            dll_manager: Initialized DLLManager with context handle

        Raises:
            ValueError: If dll_manager is not initialized
        """
        if not dll_manager.is_initialized:
            raise ValueError("DLLManager must be initialized before creating JobService")

        self._dll_manager = dll_manager
        self._result_store = JobResultStore()

        # Track active job threads for cleanup
        self._active_threads: Dict[str, threading.Thread] = {}
        self._threads_lock = threading.Lock()

        logger.info("JobService initialized")

    @property
    def result_store(self) -> JobResultStore:
        """Access the job result store for reading results."""
        return self._result_store

    def submit_job(
        self,
        frozen_order: FrozenOrder,
        job_id: Optional[str] = None,
        timeout_seconds: float = 60.0
    ) -> str:
        """
        Submit a job for background processing.

        Creates a new thread that will:
        1. Create its own API client
        2. Fetch fresh template from blockchain
        3. Build and submit the job payload
        4. Store result in result_store

        Args:
            frozen_order: Immutable order snapshot
            job_id: Optional job ID (generated if not provided)
            timeout_seconds: Blockchain confirmation timeout

        Returns:
            job_id (UUID string)

        Note:
            This returns immediately. Poll result_store.get_result(job_id)
            to check for completion.
        """
        # Generate job ID if not provided
        if job_id is None:
            job_id = str(uuid.uuid4())

        logger.info(f"Submitting job {job_id[:8]} for '{frozen_order.job_name}'")

        # Create job thread
        thread = threading.Thread(
            target=self._job_thread_main,
            args=(job_id, frozen_order, timeout_seconds),
            name=f"Job-{job_id[:8]}",
            daemon=True
        )

        # Track thread
        with self._threads_lock:
            self._active_threads[job_id] = thread

        # Start thread
        thread.start()

        return job_id

    def get_result(self, job_id: str) -> Optional[JobResult]:
        """
        Get job result (consumes on read).

        Args:
            job_id: UUID of the job

        Returns:
            JobResult if complete, None if still processing
        """
        return self._result_store.get_result(job_id)

    def is_job_pending(self, job_id: str) -> bool:
        """
        Check if a job is still being processed.

        Args:
            job_id: UUID of the job

        Returns:
            True if job thread is still running
        """
        with self._threads_lock:
            thread = self._active_threads.get(job_id)
            return thread is not None and thread.is_alive()

    def shutdown(self, timeout_per_thread: float = 5.0) -> None:
        """
        Wait for all active job threads to complete.

        Call this during application shutdown.

        Args:
            timeout_per_thread: Max seconds to wait per thread
        """
        with self._threads_lock:
            active = list(self._active_threads.items())

        if not active:
            logger.info("No active job threads to wait for")
            return

        logger.info(f"Waiting for {len(active)} job threads to complete...")

        for job_id, thread in active:
            if thread.is_alive():
                thread.join(timeout=timeout_per_thread)
                if thread.is_alive():
                    logger.warning(f"Job thread {job_id[:8]} did not complete in time")

        logger.info("Job service shutdown complete")

    def _job_thread_main(
        self,
        job_id: str,
        frozen_order: FrozenOrder,
        timeout_seconds: float
    ) -> None:
        """
        Main function for job submission thread.

        This runs in its own thread with complete isolation:
        - Own API client (not shared with inventory)
        - Fresh template from blockchain (not cached)
        - Independent lifecycle

        Args:
            job_id: UUID for this job
            frozen_order: Immutable order data
            timeout_seconds: Blockchain timeout
        """
        # Set thread name for logging
        set_thread_name(f"Job-{job_id[:8]}")
        job_logger = get_job_logger(job_id)

        job_logger.info(f"Job thread starting for '{frozen_order.job_name}'")

        try:
            # =================================================================
            # STEP 1: Create OWN API client (complete isolation)
            # =================================================================
            job_logger.debug("Creating API client for this thread...")
            api_client = ConsumableAPIClient(
                context_handle=self._dll_manager.context_handle,
                library=self._dll_manager.library,
                logger=job_logger
            )

            # =================================================================
            # STEP 2: Fetch FRESH template (NOT cached inventory!)
            # =================================================================
            job_logger.info("Fetching fresh template from blockchain...")
            template = api_client.new_job_template()

            # =================================================================
            # STEP 3: Build job payload with consumption data
            # =================================================================
            job_logger.info("Building job payload...")
            payload = self._build_payload(template, frozen_order, job_logger)

            # =================================================================
            # STEP 4: Submit to blockchain
            # =================================================================
            job_logger.info("Submitting job to blockchain...")
            job_handle = api_client.submit_job(payload)

            job_logger.info(f"Job submitted, handle={job_handle}, waiting for confirmation...")

            # =================================================================
            # STEP 5: Wait for blockchain confirmation
            # =================================================================
            status = api_client.wait_for_job_completion(
                job_handle,
                timeout_seconds=timeout_seconds
            )

            # =================================================================
            # STEP 6: Parse result and store
            # =================================================================
            job_logger.info("Parsing job result...")
            result = self._parse_result(job_id, status, frozen_order, job_handle)

            job_logger.info(f"Job completed: status={result.status.value}")

        except Exception as e:
            job_logger.error(f"Job failed: {e}")

            # Create failed result
            result = JobResult.create_failed(
                job_id=job_id,
                error_message=str(e),
                estimated_cost=frozen_order.estimate.get("estimated_cost", 0.0)
            )

        finally:
            # Store result for main thread to retrieve
            self._result_store.put_result(result)

            # Remove from active threads
            with self._threads_lock:
                self._active_threads.pop(job_id, None)

            job_logger.info("Job thread exiting")

    def _build_payload(
        self,
        template: Dict,
        frozen_order: FrozenOrder,
        job_logger
    ) -> Dict:
        """
        Build job payload from template and order.

        Sets currentExpenditure values for each consumable based on
        the order's estimated usage.

        Args:
            template: Fresh template from blockchain
            frozen_order: Order with consumption estimates
            job_logger: Logger for this job

        Returns:
            Modified template ready for submission
        """
        # Get estimates from frozen order
        toner_usage = frozen_order.toner_usage  # Dict[color, mL]
        sheets_required = frozen_order.sheets_required
        media_mint_id = frozen_order.media_type

        job_logger.debug(f"Building payload: toner={toner_usage}, sheets={sheets_required}")

        # Navigate to accounts
        inventory_params = template.get("inventoryParameters", {})
        wallets = inventory_params.get("wallets", [])

        toner_matches = 0
        media_matches = 0

        for wallet in wallets:
            accounts = wallet.get("accounts", [])

            for account in accounts:
                mint_id = account.get("mintId", "")

                # Navigate to UOM to determine type
                outer_meta = account.get("metadata", {})
                inner_meta = outer_meta.get("metadata", {})
                uom = inner_meta.get("uom", "")

                if uom == "Toner":
                    # Match by color
                    token_desc = inner_meta.get("tokenDescription", {})
                    project_data = token_desc.get("projectData", {})
                    color = project_data.get("Color", "").lower()

                    if color in toner_usage:
                        usage = toner_usage[color]
                        account["currentExpenditure"] = usage
                        toner_matches += 1
                        job_logger.debug(f"Set {color} toner expenditure: {usage} mL")

                elif uom == "Media":
                    # Match by mintId
                    if mint_id == media_mint_id:
                        account["currentExpenditure"] = sheets_required
                        media_matches += 1
                        job_logger.debug(f"Set media expenditure: {sheets_required} sheets")

        job_logger.info(f"Payload built: {toner_matches} toner matches, {media_matches} media matches")

        return template

    def _parse_result(
        self,
        job_id: str,
        status: Dict,
        frozen_order: FrozenOrder,
        job_handle: int
    ) -> JobResult:
        """
        Parse blockchain status into JobResult.

        Args:
            job_id: UUID of the job
            status: Status dict from blockchain
            frozen_order: Original order
            job_handle: DLL job handle

        Returns:
            JobResult with parsed data
        """
        job_logger = get_job_logger(job_id)
        # Note: Don't log full status - it's huge and contains Unicode chars that fail on Windows console

        # Check for transaction success - DLL may use "transactionSuccess" or just "final"
        tx_success = status.get("transactionSuccess", status.get("final", False))
        status_str = status.get("status", "unknown")
        job_logger.debug(f"Parsed: tx_success={tx_success}, status_str={status_str}")

        # Parse ledger entries from results
        # DLL returns nested structure: results = {jobID: ..., results: [{accounts: [...], publicKey: ...}, ...]}
        ledger_entries = []
        results_data = status.get("results", {})

        # Handle both dict (DLL format) and list (legacy format)
        if isinstance(results_data, dict):
            # DLL format: results is a dict with nested 'results' list of wallets
            wallet_results = results_data.get("results", [])
            job_logger.debug(f"DLL results format: {len(wallet_results)} wallets")

            for wallet in wallet_results:
                if not isinstance(wallet, dict):
                    continue

                accounts = wallet.get("accounts", [])
                for account in accounts:
                    if not isinstance(account, dict):
                        continue

                    # Extract account info
                    actual_exp = account.get("actualExpenditure", 0.0)
                    balance = account.get("balance", 0.0)
                    mint_id = account.get("mintId", "")

                    # Get UOM from nested metadata
                    metadata = account.get("metadata", {})
                    inner_meta = metadata.get("metadata", {})
                    uom = inner_meta.get("uom", "")
                    name = inner_meta.get("name", "")

                    entry = LedgerEntry(
                        account=mint_id or name,
                        amount=actual_exp,
                        unit=uom,
                        tx_id=results_data.get("jobID", ""),
                        success=True
                    )
                    ledger_entries.append(entry)
                    job_logger.debug(f"Ledger entry: {name} ({uom}): {actual_exp}")

        elif isinstance(results_data, list):
            # Legacy format: results is a flat list
            for r in results_data:
                if isinstance(r, dict):
                    entry = LedgerEntry(
                        account=r.get("account", ""),
                        amount=r.get("amount", 0.0),
                        unit=r.get("unit", ""),
                        tx_id=r.get("txId", ""),
                        success=r.get("success", True)
                    )
                    ledger_entries.append(entry)

        job_logger.info(f"Parsed {len(ledger_entries)} ledger entries")

        estimated_cost = frozen_order.estimate.get("estimated_cost", 0.0)

        # DLL returns "ready" when job is done, "completed" is our internal status
        # Accept both "ready" and "completed" as success states
        if tx_success and status_str in ("completed", "ready"):
            return JobResult.create_completed(
                job_id=job_id,
                ledger_entries=ledger_entries,
                estimated_cost=estimated_cost,
                job_handle=job_handle
            )
        else:
            error_msg = status.get("error", f"Job failed with status: {status_str}")
            return JobResult.create_failed(
                job_id=job_id,
                error_message=error_msg,
                estimated_cost=estimated_cost,
                job_handle=job_handle
            )
