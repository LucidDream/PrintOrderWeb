"""
ConsumableClient DLL Test Application

Multi-threaded command-line test tool for diagnosing ConsumableClient.dll
via the Consumable Client API.

Usage:
    python test_cc.py
"""

import sys
import json
import threading
import time
from pathlib import Path
from ctypes import cdll, c_uint64, c_char_p, c_bool, c_void_p


class ConsumableClientTester:
    """Test harness for ConsumableClient DLL."""

    def __init__(self, dll_path: str):
        """
        Initialize tester with DLL path.

        Args:
            dll_path: Path to ConsumableClient.dll
        """
        self.dll_path = Path(dll_path).resolve()
        self.lib = None
        self.context: int | None = None

        # Result storage (thread-safe)
        self.job_results: dict[int, dict] = {}
        self.results_lock = threading.Lock()

    def print_status(self, message: str):
        print(f"[STATUS] {message}", flush=True)

    def print_error(self, message: str):
        print(f"[ERROR] {message}", file=sys.stderr, flush=True)

    def print_info(self, message: str):
        print(f"[INFO] {message}", flush=True)

    # ------------------------------------------------------------------
    # DLL / context setup
    # ------------------------------------------------------------------

    def load_dll(self) -> bool:
        """Load the ConsumableClient DLL if it is not already loaded."""
        if self.lib is not None:
            return True

        self.print_status(f"Loading DLL: {self.dll_path}")
        if not self.dll_path.exists():
            self.print_error(f"DLL not found: {self.dll_path}")
            return False

        try:
            self.lib = cdll.LoadLibrary(str(self.dll_path))
            self.print_status("DLL loaded successfully")
            return True
        except Exception as e:
            self.print_error(f"Failed to load DLL: {e}")
            return False

    def setup_function_signatures(self) -> bool:
        """Setup DLL function signatures for ctypes."""
        if self.lib is None:
            self.print_error("DLL is not loaded")
            return False

        self.print_status("Setting up function signatures")

        try:
            # API matches ConsumableClient.h
            self.lib.ld3s_open.argtypes = []
            self.lib.ld3s_open.restype = c_uint64

            self.lib.ld3s_close.argtypes = [c_uint64]
            self.lib.ld3s_close.restype = None

            self.lib.ld3s_new_job.argtypes = [c_uint64]
            self.lib.ld3s_new_job.restype = c_char_p

            self.lib.ld3s_submit_job.argtypes = [c_uint64, c_char_p]
            self.lib.ld3s_submit_job.restype = c_uint64

            self.lib.ld3s_get_job_status.argtypes = [c_uint64, c_uint64]
            self.lib.ld3s_get_job_status.restype = c_char_p

            self.lib.ld3s_cancel_job.argtypes = [c_uint64, c_uint64]
            self.lib.ld3s_cancel_job.restype = c_bool

            self.lib.ld3s_get_last_error.argtypes = [c_uint64]
            self.lib.ld3s_get_last_error.restype = c_char_p

            self.lib.ld3s_free.argtypes = [c_uint64, c_void_p]
            self.lib.ld3s_free.restype = None

            self.print_status("Function signatures configured")
            return True
        except Exception as e:
            self.print_error(f"Failed to setup function signatures: {e}")
            return False

    def initialize_context(self) -> bool:
        """
        Initialize DLL context by calling ld3s_open() once.

        Returns:
            True if successful, False otherwise
        """
        self.print_status("Initializing DLL context (ld3s_open once for the process)")

        if self.context:
            self.print_status(f"Context already initialized: {self.context}")
            return True

        if not self.load_dll():
            return False

        if not self.setup_function_signatures():
            return False

        try:
            ctx = self.lib.ld3s_open()
        except Exception as e:
            self.print_error(f"Failed to initialize context: {e}")
            return False

        if not ctx:
            self.print_error("ld3s_open() returned NULL/0 context")
            return False

        self.context = int(ctx)
        self.print_status(f"Context initialized successfully: {self.context}")
        return True

    def get_last_error(self) -> str:
        """
        Get last error message from DLL.

        The returned string is freed via ld3s_free().
        """
        try:
            if not self.context or self.lib is None:
                return ""

            ctx = c_uint64(self.context)
            error_ptr = self.lib.ld3s_get_last_error(ctx)
            if not error_ptr:
                return ""

            try:
                error_msg = error_ptr.decode("utf-8")
            finally:
                try:
                    self.lib.ld3s_free(ctx, error_ptr)
                except Exception:
                    pass

            return error_msg
        except Exception as e:
            return f"Failed to get error: {e}"

    def cleanup(self):
        """Cleanup DLL context."""
        if self.context:
            self.print_status("Cleaning up DLL context (calling ld3s_close)")
            try:
                if self.lib is not None:
                    self.lib.ld3s_close(c_uint64(self.context))
                self.print_status("Context closed successfully")
            except Exception as e:
                self.print_error(f"Failed to close context: {e}")
            finally:
                self.context = None

    # ------------------------------------------------------------------
    # Job execution
    # ------------------------------------------------------------------

    def job_processing_thread(self, thread_id: int, data_file: str):
        """
        Job processing thread.

        Loads job data from a JSON file, uses the shared API context to
        create and submit a job, polls for completion, and stores a
        summarized result.
        """
        thread_name = threading.current_thread().name
        self.print_status(f"[Thread {thread_id}/{thread_name}] Starting job processing thread")
        self.print_info(f"[Thread {thread_id}] Data file: {data_file}")

        if not self.context or self.lib is None:
            self.print_error(f"[Thread {thread_id}] Context is not initialized")
            return

        ctx = c_uint64(self.context)
        lib = self.lib

        try:
            # Fetch fresh template with current balances
            self.print_status(f"[Thread {thread_id}] Fetching fresh template with current balances...")
            template_ptr = lib.ld3s_new_job(ctx)
            if not template_ptr:
                self.print_error(f"[Thread {thread_id}] Failed to fetch template")
                return

            template_json = template_ptr.decode("utf-8")
            template = json.loads(template_json)
            lib.ld3s_free(ctx, template_ptr)

            job_parameters = template.get("jobParameters")
            if not job_parameters:
                self.print_error(f"[Thread {thread_id}] Template missing jobParameters")
                return

            self.print_info(
                f"[Thread {thread_id}]   Got jobParameters with jobID: "
                f"{job_parameters.get('jobID', 'N/A')}"
            )

            # Load expenditure data from file
            self.print_status(f"[Thread {thread_id}] Loading expenditure data from {data_file}")
            with open(data_file, "r", encoding="utf-8") as f:
                expenditure_data = json.load(f)

            job_name = expenditure_data.get("jobMetadata", {}).get("jobName", "Unknown")
            quantity = expenditure_data.get("jobMetadata", {}).get("quantity", 0)
            self.print_info(f"[Thread {thread_id}]   Job: '{job_name}', Quantity: {quantity}")

            # Apply expenditures from file onto fresh template accounts
            expenditure_count = 0
            for exp_wallet in expenditure_data.get("inventoryParameters", {}).get("wallets", []):
                exp_pubkey = exp_wallet.get("publicKey")
                for exp_account in exp_wallet.get("accounts", []):
                    exp_mintid = exp_account.get("mintId")
                    exp_value = exp_account.get("currentExpenditure", 0)

                    if exp_value > 0:
                        for tmpl_wallet in template.get("inventoryParameters", {}).get("wallets", []):
                            if tmpl_wallet.get("publicKey") == exp_pubkey:
                                for tmpl_account in tmpl_wallet.get("accounts", []):
                                    if tmpl_account.get("mintId") == exp_mintid:
                                        tmpl_account["currentExpenditure"] = exp_value
                                        expenditure_count += 1
                                        break

            self.print_info(
                f"[Thread {thread_id}]   Applied {expenditure_count} expenditure(s) to fresh template"
            )

            # Copy job metadata into template payload
            template["jobMetadata"] = expenditure_data.get("jobMetadata", {})

            # Log final payload expenditures
            self.print_status(
                f"[Thread {thread_id}] DEBUG: Checking expenditures in payload before submission:"
            )
            for wallet_idx, wallet in enumerate(
                template.get("inventoryParameters", {}).get("wallets", [])
            ):
                for acc_idx, account in enumerate(wallet.get("accounts", [])):
                    exp_value = account.get("currentExpenditure", 0)
                    balance = account.get("estimatedBalance", 0)
                    mintid = account.get("mintId", "unknown")[:20]
                    self.print_info(
                        f"[Thread {thread_id}]   Wallet {wallet_idx}, Account {acc_idx}: "
                        f"mintId={mintid}..., estimatedBalance={balance}, "
                        f"currentExpenditure={exp_value}"
                    )

            # Submit job
            self.print_status(f"[Thread {thread_id}] Submitting job to DLL...")
            job_json = json.dumps(template).encode("utf-8")
            job_handle = lib.ld3s_submit_job(ctx, job_json)

            if not job_handle:
                self.print_error(f"[Thread {thread_id}] ld3s_submit_job() returned NULL handle")
                # Get last error and free it
                try:
                    err_ptr = lib.ld3s_get_last_error(ctx)
                except Exception:
                    err_ptr = None

                if err_ptr:
                    try:
                        err_msg = err_ptr.decode("utf-8")
                        self.print_error(f"[Thread {thread_id}] DLL Error: {err_msg}")
                    finally:
                        try:
                            lib.ld3s_free(ctx, err_ptr)
                        except Exception:
                            pass
                return

            self.print_status(f"[Thread {thread_id}] Job submitted successfully, handle={job_handle}")

            # Poll for completion
            polling_interval = 0.25
            timeout = 60
            start_time = time.time()
            poll_count = 0
            self.print_status(f"[Thread {thread_id}] Polling for job completion...")

            while True:
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    self.print_error(f"[Thread {thread_id}] Job timed out after {timeout}s")
                    # Optional: we could call ld3s_cancel_job here
                    break

                status_ptr = lib.ld3s_get_job_status(ctx, c_uint64(job_handle))
                poll_count += 1

                if status_ptr:
                    status_json = status_ptr.decode("utf-8")
                    status = json.loads(status_json)
                    lib.ld3s_free(ctx, status_ptr)

                    is_final = status.get("final", False)
                    if is_final:
                        # Log and persist raw JSON
                        self.print_status(
                            f"[Thread {thread_id}] ========== RAW JSON FROM DLL =========="
                        )
                        self.print_info(f"[Thread {thread_id}] Job Handle: {job_handle}")
                        self.print_info(
                            f"[Thread {thread_id}] JSON Length: {len(status_json)} chars"
                        )

                        import os

                        script_dir = os.path.dirname(__file__)
                        raw_json_file = os.path.join(
                            script_dir, f"dll_response_thread{thread_id}_handle{job_handle}.json"
                        )
                        with open(raw_json_file, "w", encoding="utf-8") as f:
                            f.write(status_json)
                        self.print_info(
                            f"[Thread {thread_id}] Saved raw JSON to: {raw_json_file}"
                        )

                        try:
                            pretty_json = json.dumps(status, indent=2)
                            preview = (
                                pretty_json[:1000] + "..."
                                if len(pretty_json) > 1000
                                else pretty_json
                            )
                            self.print_info(
                                f"[Thread {thread_id}] JSON Preview:\n{preview}"
                            )
                        except Exception:
                            pass

                        self.print_status(
                            f"[Thread {thread_id}] =========================================="
                        )
                        self.print_status(
                            f"[Thread {thread_id}] Job completed after {poll_count} polls "
                            f"({elapsed:.2f}s)"
                        )

                        # Parse result
                        transaction_success = status.get("transactionSuccess", False)
                        status_str = status.get("status", "")

                        if status_str != "ready":
                            self.print_error(
                                f"[Thread {thread_id}] Job finalized with status='{status_str}' "
                                f"(transactionSuccess={transaction_success})"
                            )
                            transaction_success = False

                        results = status.get("results", [])
                        if isinstance(results, dict) and "results" in results:
                            results = results["results"]

                        transaction_count = 0
                        total_expenditure = {"media": 0.0, "toner": 0.0}

                        for wallet in results if isinstance(results, list) else []:
                            for account in wallet.get("accounts", []):
                                actual_exp = account.get("actualExpenditure", 0)
                                if actual_exp > 0:
                                    transaction_count += 1
                                    uom = (
                                        account.get("metadata", {})
                                        .get("metadata", {})
                                        .get("uom", "")
                                    )
                                    if uom == "Media":
                                        total_expenditure["media"] += actual_exp
                                    elif uom == "Toner":
                                        total_expenditure["toner"] += actual_exp

                        result = {
                            "thread_id": thread_id,
                            "job_name": job_name,
                            "quantity": quantity,
                            "job_handle": job_handle,
                            "transaction_success": transaction_success,
                            "transaction_count": transaction_count,
                            "media_expenditure": total_expenditure["media"],
                            "toner_expenditure": total_expenditure["toner"],
                            "status": status,
                        }

                        with self.results_lock:
                            self.job_results[thread_id] = result

                        self.print_status(f"[Thread {thread_id}] Result stored")
                        self.print_info(
                            f"[Thread {thread_id}]   Transactions: {transaction_count}"
                        )
                        self.print_info(
                            f"[Thread {thread_id}]   Media: "
                            f"{total_expenditure['media']:.2f}, Toner: "
                            f"{total_expenditure['toner']:.4f}"
                        )
                        break
                    else:
                        if poll_count % 10 == 0:
                            self.print_status(
                                f"[Thread {thread_id}] Still processing... ({poll_count} polls)"
                            )

                time.sleep(polling_interval)

            self.print_status(f"[Thread {thread_id}] Job processing thread completed")

        except Exception as e:
            self.print_error(f"[Thread {thread_id}] Thread failed: {e}")
            import traceback

            traceback.print_exc()

    # ------------------------------------------------------------------
    # Test harness entry points
    # ------------------------------------------------------------------

    def run_threading_test(self, data_files: list[str]) -> bool:
        """
        Run threading test with job processing threads.

        Args:
            data_files: List of data file paths.
        """
        num_threads = len(data_files)
        print("=" * 80)
        print(f"ConsumableClient DLL Job Submission Test ({num_threads} job(s))")
        print("=" * 80)

        if not self.initialize_context():
            error_msg = self.get_last_error()
            if error_msg:
                self.print_error(f"DLL error: {error_msg}")
            return False

        self.print_status("DLL context ready, spawning job thread(s)...")
        print("-" * 80)

        threads: list[threading.Thread] = []
        for i, data_file in enumerate(data_files):
            thread = threading.Thread(
                target=self.job_processing_thread,
                args=(i + 1, data_file),
                name=f"JobThread-{i + 1}",
                daemon=False,
            )
            threads.append(thread)
            thread.start()
            self.print_status(f"[Main Thread] Spawned thread {i + 1} with {data_file}")
            time.sleep(0.5)

        self.print_status(f"[Main Thread] Waiting for {num_threads} thread(s) to complete...")
        for i, thread in enumerate(threads):
            thread.join()
            self.print_status(f"[Main Thread] Thread {i + 1} joined")

        print("-" * 80)
        self.print_status("All job threads completed")
        print("=" * 80)

        self.report_results()
        return True

    def report_results(self):
        """Report all job results in a formatted table."""
        print("\n" + "=" * 80)
        print("JOB RESULTS SUMMARY")
        print("=" * 80)

        with self.results_lock:
            if not self.job_results:
                self.print_error("No results available")
                return

            print(
                f"{'Thread':<8} {'Handle':<8} {'Job Name':<15} "
                f"{'Qty':<5} {'Media':<10} {'Toner':<10} {'Txns':<6} {'Success':<8}"
            )
            print("-" * 80)

            for thread_id in sorted(self.job_results.keys()):
                result = self.job_results[thread_id]
                print(
                    f"{result['thread_id']:<8} "
                    f"{result['job_handle']:<8} "
                    f"{result['job_name']:<15} "
                    f"{result['quantity']:<5} "
                    f"{result['media_expenditure']:<10.2f} "
                    f"{result['toner_expenditure']:<10.4f} "
                    f"{result['transaction_count']:<6} "
                    f"{'YES' if result['transaction_success'] else 'NO':<8}"
                )

        print("=" * 80)

    def run_initialization_test(self) -> bool:
        """
        Run complete initialization test.

        Returns:
            True if all steps successful, False otherwise
        """
        print("=" * 80)
        print("ConsumableClient DLL Initialization Test")
        print("=" * 80)

        if not self.load_dll():
            return False

        if not self.setup_function_signatures():
            return False

        if not self.initialize_context():
            error_msg = self.get_last_error()
            if error_msg:
                self.print_error(f"DLL error: {error_msg}")
            return False

        print("=" * 80)
        self.print_status("Initialization test PASSED")
        print("=" * 80)
        return True


def main():
    """Main entry point."""

    script_dir = Path(__file__).parent
    dll_path = script_dir.parent.parent / "CCAPIv2.0.0.2" / "ConsumableClient.dll"

    print(f"\nDLL Path: {dll_path}")
    print(f"DLL Exists: {dll_path.exists()}\n")

    tester = ConsumableClientTester(str(dll_path))

    try:
        script_dir = Path(__file__).parent
        data_files = [
            str(script_dir / "data.json"),
            str(script_dir / "data2.json"),
            str(script_dir / "data3.json"),
        ]

        success = tester.run_threading_test(data_files)
        tester.cleanup()
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Test interrupted by user")
        tester.cleanup()
        sys.exit(2)

    except Exception as e:
        print(f"\n[EXCEPTION] Unexpected error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        tester.cleanup()
        sys.exit(3)


if __name__ == "__main__":
    main()

