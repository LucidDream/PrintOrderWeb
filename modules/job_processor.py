"""Job processor for submitting print jobs to blockchain via ConsumableClient API."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Union, Optional
from uuid import uuid4

from .api_client_threaded import ThreadSafeAPIClient, ConsumableClientAPIStub


class JobProcessorStub:
    """Creates a fake ledger response so the UI can complete the flow."""

    def process(self, order: Dict[str, Any]) -> Dict[str, Any]:
        estimate = order.get("estimate", {})
        choices = order.get("choices", {})

        ledger_entries = []
        for color, usage in estimate.get("toner_usage", {}).items():
            ledger_entries.append(
                {
                    "account": color,
                    "amount": usage,
                    "unit": "ml",
                }
            )

        ledger_entries.append(
            {
                "account": choices.get("media_type", "unknown-media"),
                "amount": estimate.get("sheets_required", 0),
                "unit": "sheets",
            }
        )

        return {
            "job_id": str(uuid4()),
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "status": "simulated",
            "ledger_entries": ledger_entries,
            "estimated_cost": estimate.get("estimated_cost", 0),
            "notes": "Replace JobProcessorStub with ConsumableClient-backed implementation on Windows.",
        }


class JobProcessor:
    """
    Job processor for building payloads and parsing results.

    Thread-Per-Job Architecture:
        - Each job thread creates its own JobProcessor instance
        - Processor builds payload from thread-owned template
        - NO deep copy needed - thread owns all data exclusively
        - Processor parses final results from blockchain

    Responsibilities:
        - Build job payload (apply expenditures to template)
        - Parse job results (extract transaction IDs)
        - Simulate jobs in stub mode

    Note: Job submission and status polling are handled by the
    job thread in app.py, not by this processor.
    """

    def __init__(
        self,
        api_client: Union[ThreadSafeAPIClient, ConsumableClientAPIStub],
        logger: Optional[logging.Logger] = None
    ) -> None:
        """
        Initialize the job processor.

        Args:
            api_client: ConsumableClient API wrapper (real or stub)
            logger: Logger instance for tracking operations
        """
        self.api_client = api_client
        self.logger = logger or logging.getLogger(__name__)
        self._fallback_to_stub = isinstance(api_client, ConsumableClientAPIStub)

    def process(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a print job order (stub mode only).

        In thread-per-job architecture, this method is only used for stub mode.
        Real API mode is handled directly by the job thread in app.py.

        Args:
            order: Order dictionary with choices and estimates

        Returns:
            Simulated job result
        """
        self.logger.info("Processing job in stub mode")
        return self._simulate_job(order)

    def _simulate_job(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulate job processing (stub mode).

        Args:
            order: Order dictionary

        Returns:
            Simulated job result
        """
        estimate = order.get("estimate", {})
        choices = order.get("choices", {})

        ledger_entries = []
        for color, usage in estimate.get("toner_usage", {}).items():
            ledger_entries.append(
                {
                    "account": color,
                    "amount": usage,
                    "unit": "ml",
                    "txId": f"simulated-tx-{color}",
                    "success": True
                }
            )

        ledger_entries.append(
            {
                "account": choices.get("media_type", "unknown-media"),
                "amount": estimate.get("sheets_required", 0),
                "unit": "sheets",
                "txId": f"simulated-tx-media",
                "success": True
            }
        )

        return {
            "job_id": str(uuid4()),
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "status": "simulated",
            "ledger_entries": ledger_entries,
            "estimated_cost": estimate.get("estimated_cost", 0),
            "transaction_success": True,
            "notes": "Simulated job - enable API mode for real blockchain submission",
        }

    def _build_job_payload(self, template: Dict[str, Any], order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build job payload by applying expenditures to template.

        Thread-safe: Each thread owns its template exclusively.

        Args:
            template: Job template from blockchain (thread-owned)
            order: Order with estimates and choices

        Returns:
            Job payload with expenditures applied
        """
        estimate = order.get("estimate", {})
        choices = order.get("choices", {})

        # Extract expenditure data
        toner_usage = estimate.get("toner_usage", {})
        sheets_required = estimate.get("sheets_required", 0)
        media_type = choices.get("media_type")

        self.logger.debug(f"Building payload: toner={toner_usage}, media={sheets_required} sheets")

        # Apply expenditures to accounts
        wallets = template.get("inventoryParameters", {}).get("wallets", [])

        for wallet in wallets:
            for account in wallet.get("accounts", []):
                account_info = self._identify_account(account)

                if account_info["type"] == "toner":
                    # Apply toner expenditure by color
                    color = account_info["id"]
                    if color in toner_usage:
                        account["currentExpenditure"] = float(toner_usage[color])
                        self.logger.debug(f"Applied {color} toner: {toner_usage[color]} mL")
                    else:
                        account["currentExpenditure"] = 0.0

                elif account_info["type"] == "media":
                    # Match by mintId
                    account_mint_id = account.get("mintId")
                    if account_mint_id == media_type:
                        account["currentExpenditure"] = float(sheets_required)
                        self.logger.debug(f"Applied media: {sheets_required} sheets")
                    else:
                        account["currentExpenditure"] = 0.0

                else:
                    account["currentExpenditure"] = 0.0

                # CC-Test guidance: strip display-only balances to avoid ledger validation issues
                if "estimatedBalance" in account:
                    account.pop("estimatedBalance", None)

        # Log payload summary
        expenditure_count = sum(
            1 for wallet in wallets
            for account in wallet.get("accounts", [])
            if account.get("currentExpenditure", 0) > 0
        )
        self.logger.debug(f"Payload built with {expenditure_count} expenditures")

        return template

    def _identify_account(self, account: Dict[str, Any]) -> Dict[str, str]:
        """
        Identify account type and ID (matches inventory service logic).

        Args:
            account: Account from template

        Returns:
            Dict with type and id
        """
        metadata = account.get("metadata", {})
        nested_metadata = metadata.get("metadata", {})

        if nested_metadata:
            # Real API structure
            type_indicator = nested_metadata.get("uom", "").lower()
            token_desc = nested_metadata.get("tokenDescription", {})
            project_data = token_desc.get("projectData", {})

            if type_indicator == "toner":
                color = project_data.get("Color", "").lower()
                return {"type": "toner", "id": color}
            elif type_indicator == "media":
                return {"type": "media", "id": account.get("mintId", "")}
            else:
                return {"type": "unknown", "id": account.get("mintId", "")}
        else:
            # Stub structure
            uom = metadata.get("uom", "")
            if uom == "sheets":
                return {"type": "media", "id": account.get("accountId", "")}
            else:
                return {"type": "toner", "id": account.get("accountId", "")}

    def _parse_job_result(
        self,
        status: Dict[str, Any],
        order: Dict[str, Any],
        job_handle: int
    ) -> Dict[str, Any]:
        """
        Parse final job status into result format.

        Args:
            status: Final status from API
            order: Original order
            job_handle: Job handle

        Returns:
            Formatted job result
        """
        import json

        # Extract transaction results from API v2 "results" structure
        results = status.get("results", [])

        # Handle JSON string results
        if isinstance(results, str):
            try:
                results = json.loads(results)
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse results JSON: {e}")
                results = []

        # Handle nested dict structure
        if isinstance(results, dict):
            if "results" in results:
                results = results["results"]
            else:
                results = [results]

        # Parse ledger entries
        ledger_entries = []
        for result_wallet in results:
            accounts = result_wallet.get("accounts", [])

            for account in accounts:
                actual_expenditure = account.get("actualExpenditure", 0)
                if actual_expenditure == 0:
                    continue

                # Extract account metadata
                metadata = account.get("metadata", {})
                nested_metadata = metadata.get("metadata", {})
                token_desc = nested_metadata.get("tokenDescription", {})
                project_data = token_desc.get("projectData", {})

                # Build ledger entry
                account_name = project_data.get("Consumable Name", "Unknown")
                uom = nested_metadata.get("uom", "")
                unit = "mL" if uom == "Toner" else "sheets" if uom == "Media" else "units"
                mint_id = account.get("mintId", account.get("mintAddress", "unknown"))

                ledger_entries.append({
                    "account": account_name,
                    "amount": actual_expenditure,
                    "unit": unit,
                    "txId": mint_id,
                    "success": True
                })

        # Evaluate success based on CC-Test rules
        api_status = status.get("status")
        transaction_success = status.get("transactionSuccess", False)
        api_ready = api_status == "ready"
        has_transactions = bool(ledger_entries)

        if api_ready and transaction_success and has_transactions:
            self.logger.info(f"Parsed {len(ledger_entries)} transactions from job result")
        else:
            self.logger.warning(
                "Job result incomplete: "
                f"api_status={api_status}, transaction_success={transaction_success}, "
                f"ledger_entries={len(ledger_entries)}"
            )
            # Treat missing transactions or non-ready status as failure
            transaction_success = False

        job_status = "completed" if transaction_success else "failed"

        # Parse error message
        raw_notes = status.get("notes", "")
        if transaction_success:
            notes = "Job processed successfully"
        else:
            notes_lower = raw_notes.lower()
            if any(keyword in notes_lower for keyword in ["insufficient", "balance", "not enough", "depleted"]):
                notes = (
                    "Insufficient inventory to complete this job. "
                    "One or more consumables (toner or media) have been depleted. "
                    "Please check current inventory levels and reduce quantity if needed."
                )
            elif "timeout" in notes_lower or "timed out" in notes_lower:
                notes = "Job submission timed out. The blockchain may be busy. Please try again."
            elif raw_notes:
                notes = f"Job processing failed: {raw_notes}"
            else:
                notes = "Job processing failed. Please check inventory and try again."

        return {
            "job_id": status.get("jobId", str(uuid4())),
            "job_handle": job_handle,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "status": job_status,
            "ledger_entries": ledger_entries,
            "estimated_cost": order.get("estimate", {}).get("estimated_cost", 0),
            "transaction_success": transaction_success,
            "notes": notes
        }
