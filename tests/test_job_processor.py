"""
Unit tests for the Job Processor.

Tests both stub and real API job submission workflows.
"""

import json
import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from modules.job_processor import JobProcessor, JobProcessorStub
from modules.api_client import ConsumableClientAPIStub


# Fixtures

@pytest.fixture
def stub_client():
    """Create a stub API client."""
    return ConsumableClientAPIStub()


@pytest.fixture
def mock_api_client():
    """Create a mock API client for real mode testing."""
    mock_client = MagicMock()
    mock_client.new_job_template.return_value = {
        "inventoryParameters": {
            "wallets": [
                {
                    "accounts": [
                        {
                            "estimatedBalance": 5000.0,
                            "mintId": "cyan-mint-id",
                            "metadata": {
                                "metadata": {
                                    "uom": "Toner",
                                    "tokenDescription": {
                                        "projectData": {
                                            "Consumable Name": "Cyan Ink",
                                            "Color": "CYAN",
                                            "Unit of Measure for Spending": "mL"
                                        }
                                    }
                                }
                            }
                        },
                        {
                            "estimatedBalance": 200.0,
                            "mintId": "media-mint-abc",
                            "metadata": {
                                "metadata": {
                                    "uom": "Media",
                                    "tokenDescription": {
                                        "projectData": {
                                            "Consumable Name": "ProMatte A4",
                                            "Media Type": "MATTE",
                                            "Unit of Measure": "sheets"
                                        }
                                    }
                                }
                            }
                        }
                    ]
                }
            ]
        }
    }
    mock_client.submit_job.return_value = 12345  # Job handle
    # Real API v2 format with results structure
    mock_client.wait_for_job_completion.return_value = {
        "jobId": "blockchain-job-123",
        "transactionSuccess": True,
        "results": [
            {
                "publicKey": "mock-pubkey-123",
                "accounts": [
                    {
                        "actualExpenditure": 15.5,
                        "balance": 5000.0,
                        "mintId": "sig-abc123",
                        "metadata": {
                            "metadata": {
                                "uom": "Toner",
                                "tokenDescription": {
                                    "projectData": {
                                        "Consumable Name": "Cyan Ink"
                                    }
                                }
                            }
                        }
                    },
                    {
                        "actualExpenditure": 10,
                        "balance": 1000,
                        "mintId": "sig-def456",
                        "metadata": {
                            "metadata": {
                                "uom": "Media",
                                "tokenDescription": {
                                    "projectData": {
                                        "Consumable Name": "ProMatte A4"
                                    }
                                }
                            }
                        }
                    }
                ]
            }
        ],
        "notes": "Job completed successfully"
    }
    return mock_client


@pytest.fixture
def sample_order():
    """Create a sample order for testing."""
    return {
        "job_name": "Test Print Job",
        "analysis": {
            "pages": 5,
            "color_pages": 5,
            "bw_pages": 0
        },
        "choices": {
            "quantity": 2,
            "color_mode": "full_color",
            "media_type": "media-mint-abc",
            "turnaround_time": "standard",
            "notes": "Test order"
        },
        "estimate": {
            "toner_usage": {
                "cyan": 15.5,
                "magenta": 12.3,
                "yellow": 8.7,
                "black": 5.2
            },
            "sheets_required": 10,
            "estimated_cost": 25.50
        }
    }


# Tests for JobProcessorStub

class TestJobProcessorStub:
    """Test the stub job processor."""

    def test_stub_initialization(self):
        """Test stub processor initializes correctly."""
        processor = JobProcessorStub()
        assert processor is not None

    def test_stub_process(self, sample_order):
        """Test stub processor returns expected result format."""
        processor = JobProcessorStub()
        result = processor.process(sample_order)

        # Verify result structure
        assert "job_id" in result
        assert "submitted_at" in result
        assert "status" in result
        assert "ledger_entries" in result
        assert "estimated_cost" in result

        # Verify status
        assert result["status"] == "simulated"
        assert result["estimated_cost"] == 25.50

        # Verify ledger entries
        assert len(result["ledger_entries"]) == 5  # 4 toner + 1 media

        # Check toner entries
        toner_entries = [e for e in result["ledger_entries"] if e["unit"] == "ml"]
        assert len(toner_entries) == 4

        # Check media entry
        media_entries = [e for e in result["ledger_entries"] if e["unit"] == "sheets"]
        assert len(media_entries) == 1
        assert media_entries[0]["amount"] == 10


# Tests for JobProcessor with Stub Client

class TestJobProcessorWithStubClient:
    """Test job processor when given a stub client."""

    def test_initialization_with_stub(self, stub_client):
        """Test processor initializes correctly with stub client."""
        processor = JobProcessor(stub_client)
        assert processor.api_client == stub_client
        assert processor._fallback_to_stub is True

    def test_process_falls_back_to_stub(self, stub_client, sample_order):
        """Test processor uses stub mode when given stub client."""
        processor = JobProcessor(stub_client)
        result = processor.process(sample_order)

        # Should return simulated result
        assert result["status"] == "simulated"
        assert result["transaction_success"] is True


# Tests for JobProcessor with Real API Client

class TestJobProcessorWithRealClient:
    """Test job processor with real API client (mocked)."""

    def test_initialization_with_real_client(self, mock_api_client):
        """Test processor initializes correctly with real client."""
        processor = JobProcessor(mock_api_client)
        assert processor.api_client == mock_api_client
        assert processor._fallback_to_stub is False

    def test_real_job_submission_workflow(self, mock_api_client, sample_order):
        """Test complete real job submission workflow."""
        processor = JobProcessor(mock_api_client)
        result = processor.process(sample_order)

        # Verify API calls
        assert mock_api_client.new_job_template.called
        assert mock_api_client.submit_job.called
        assert mock_api_client.wait_for_job_completion.called

        # Verify result structure
        assert result["status"] == "completed"
        assert result["transaction_success"] is True
        assert result["job_handle"] == 12345
        assert len(result["ledger_entries"]) == 2

        # Verify ledger entries
        for entry in result["ledger_entries"]:
            assert "account" in entry
            assert "amount" in entry
            assert "unit" in entry
            assert "txId" in entry
            assert "success" in entry
            assert entry["success"] is True

    def test_job_submission_with_error(self, mock_api_client, sample_order):
        """Test job submission handles errors gracefully."""
        # Configure mock to raise exception
        mock_api_client.submit_job.side_effect = RuntimeError("Blockchain unavailable")

        processor = JobProcessor(mock_api_client)
        result = processor.process(sample_order)

        # Should return error result
        assert result["status"] == "failed"
        assert result["transaction_success"] is False
        assert "error" in result["notes"].lower()


# Tests for _build_job_payload

class TestBuildJobPayload:
    """Test job payload building logic."""

    def test_build_payload_applies_toner_expenditures(self, mock_api_client, sample_order):
        """Test that toner expenditures are correctly applied to accounts."""
        processor = JobProcessor(mock_api_client)
        template = mock_api_client.new_job_template()

        payload = processor._build_job_payload(template, sample_order)

        # Find cyan account
        cyan_account = None
        for wallet in payload["inventoryParameters"]["wallets"]:
            for account in wallet["accounts"]:
                account_info = processor._identify_account(account)
                if account_info["type"] == "toner" and account_info["id"] == "cyan":
                    cyan_account = account
                    break

        assert cyan_account is not None
        assert cyan_account["currentExpenditure"] == 15.5

    def test_build_payload_applies_media_expenditures(self, mock_api_client, sample_order):
        """Test that media expenditures are correctly applied to accounts."""
        processor = JobProcessor(mock_api_client)
        template = mock_api_client.new_job_template()

        payload = processor._build_job_payload(template, sample_order)

        # Find media account
        media_account = None
        for wallet in payload["inventoryParameters"]["wallets"]:
            for account in wallet["accounts"]:
                if account.get("mintId") == "media-mint-abc":
                    media_account = account
                    break

        assert media_account is not None
        assert media_account["currentExpenditure"] == 10

    def test_build_payload_adds_job_metadata(self, mock_api_client, sample_order):
        """Test that job metadata is added to payload."""
        processor = JobProcessor(mock_api_client)
        template = mock_api_client.new_job_template()

        payload = processor._build_job_payload(template, sample_order)

        # Verify job metadata
        assert "jobMetadata" in payload
        metadata = payload["jobMetadata"]

        assert metadata["jobName"] == "Test Print Job"
        assert metadata["quantity"] == 2
        assert metadata["colorMode"] == "full_color"
        assert metadata["turnaroundTime"] == "standard"
        assert metadata["pdfPages"] == 5
        assert metadata["estimatedCost"] == 25.50


# Tests for _identify_account

class TestIdentifyAccount:
    """Test account identification logic."""

    def test_identify_toner_account_real_api(self, mock_api_client):
        """Test identifying toner account from real API structure."""
        processor = JobProcessor(mock_api_client)

        account = {
            "mintId": "cyan-mint",
            "metadata": {
                "metadata": {
                    "uom": "Toner",
                    "tokenDescription": {
                        "projectData": {
                            "Color": "CYAN"
                        }
                    }
                }
            }
        }

        result = processor._identify_account(account)

        assert result["type"] == "toner"
        assert result["id"] == "cyan"

    def test_identify_media_account_real_api(self, mock_api_client):
        """Test identifying media account from real API structure."""
        processor = JobProcessor(mock_api_client)

        account = {
            "mintId": "media-abc123",
            "metadata": {
                "metadata": {
                    "uom": "Media",
                    "tokenDescription": {
                        "projectData": {
                            "Media Type": "MATTE"
                        }
                    }
                }
            }
        }

        result = processor._identify_account(account)

        assert result["type"] == "media"
        assert result["id"] == "media-abc123"

    def test_identify_account_stub_structure(self, mock_api_client):
        """Test identifying account from stub structure."""
        processor = JobProcessor(mock_api_client)

        # Stub toner account
        toner_account = {
            "accountId": "magenta",
            "metadata": {
                "uom": "ml"
            }
        }

        result = processor._identify_account(toner_account)
        assert result["type"] == "toner"
        assert result["id"] == "magenta"

        # Stub media account
        media_account = {
            "accountId": "std-matte",
            "metadata": {
                "uom": "sheets"
            }
        }

        result = processor._identify_account(media_account)
        assert result["type"] == "media"
        assert result["id"] == "std-matte"


# Tests for _parse_job_result

class TestParseJobResult:
    """Test job result parsing logic."""

    def test_parse_successful_result(self, mock_api_client, sample_order):
        """Test parsing successful job result (real API v2 format)."""
        processor = JobProcessor(mock_api_client)

        # Real API v2 format with results structure
        status = {
            "jobId": "job-123",
            "transactionSuccess": True,
            "results": [
                {
                    "publicKey": "test-pubkey-123",
                    "accounts": [
                        {
                            "actualExpenditure": 15.5,
                            "balance": 5000.0,
                            "mintId": "sig-abc",
                            "metadata": {
                                "metadata": {
                                    "uom": "Toner",
                                    "tokenDescription": {
                                        "projectData": {
                                            "Consumable Name": "Cyan Ink"
                                        }
                                    }
                                }
                            }
                        }
                    ]
                }
            ],
            "notes": "Success"
        }

        result = processor._parse_job_result(status, sample_order, job_handle=12345)

        assert result["job_id"] == "job-123"
        assert result["job_handle"] == 12345
        assert result["status"] == "completed"
        assert result["transaction_success"] is True
        assert len(result["ledger_entries"]) == 1
        assert result["ledger_entries"][0]["account"] == "Cyan Ink"
        assert result["ledger_entries"][0]["amount"] == 15.5

    def test_parse_failed_result(self, mock_api_client, sample_order):
        """Test parsing failed job result (real API v2 format)."""
        processor = JobProcessor(mock_api_client)

        # Real API v2 format - failed transactions typically return empty results
        status = {
            "jobId": "job-456",
            "transactionSuccess": False,
            "results": [],  # Empty when failed
            "notes": "Insufficient balance"
        }

        result = processor._parse_job_result(status, sample_order, job_handle=67890)

        assert result["status"] == "failed"
        assert result["transaction_success"] is False
        # Check that error message was enhanced for user-friendliness
        assert "Insufficient inventory" in result["notes"]
        assert "depleted" in result["notes"]


# Integration Tests

class TestJobProcessorIntegration:
    """Integration tests for job processor."""

    def test_end_to_end_stub_mode(self, stub_client, sample_order):
        """Test complete workflow in stub mode."""
        processor = JobProcessor(stub_client)
        result = processor.process(sample_order)

        # Verify complete result structure
        assert result["job_id"] is not None
        assert result["status"] == "simulated"
        assert result["transaction_success"] is True
        assert len(result["ledger_entries"]) > 0
        assert result["estimated_cost"] == sample_order["estimate"]["estimated_cost"]

    def test_end_to_end_real_mode(self, mock_api_client, sample_order):
        """Test complete workflow in real API mode."""
        processor = JobProcessor(mock_api_client)
        result = processor.process(sample_order)

        # Verify API was called in correct order
        call_order = [
            call[0] for call in mock_api_client.method_calls
        ]

        # Should be: new_job_template, submit_job, wait_for_job_completion
        assert 'new_job_template' in call_order[0]
        assert 'submit_job' in call_order[1]
        assert 'wait_for_job_completion' in call_order[2]

        # Verify result
        assert result["status"] == "completed"
        assert result["transaction_success"] is True
        assert result["job_handle"] == 12345

    def test_graceful_degradation_on_api_failure(self, mock_api_client, sample_order):
        """Test that processor handles API failures gracefully."""
        # Configure mock to fail template fetch
        mock_api_client.new_job_template.side_effect = Exception("Network error")

        processor = JobProcessor(mock_api_client)
        result = processor.process(sample_order)

        # Should return error result, not crash
        assert result["status"] == "failed"
        assert result["transaction_success"] is False
        assert "error" in result["notes"].lower()
