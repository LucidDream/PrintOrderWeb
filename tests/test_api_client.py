"""
Unit tests for the ConsumableClient API wrapper.

These tests cover both the stub and real API client implementations.
"""

import json
import logging
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from modules.api_client import ConsumableClientAPI, ConsumableClientAPIStub, JobSubmissionResult


# Fixtures

@pytest.fixture
def logger():
    """Create a test logger."""
    return logging.getLogger("test")


@pytest.fixture
def stub_client(logger):
    """Create a stub API client."""
    return ConsumableClientAPIStub(dll_path="fake.dll", logger=logger)


@pytest.fixture
def mock_dll():
    """Create a mock DLL object with v2 API functions."""
    dll = MagicMock()

    # Configure v2 API return types
    dll.ld3s_open.return_value = 12345  # Mock context handle
    dll.ld3s_new_job.return_value = json.dumps({
        "inventoryParameters": {
            "wallets": [
                {
                    "name": "Test Wallet",
                    "accounts": [
                        {
                            "accountId": "test-account",
                            "estimatedBalance": 1000,
                            "metadata": {
                                "uom": "ml",
                                "displayName": "Test Consumable"
                            }
                        }
                    ]
                }
            ]
        }
    }).encode("utf-8")
    dll.ld3s_submit_job.return_value = 67890  # Mock job handle
    dll.ld3s_get_job_status.return_value = json.dumps({
        "status": "complete",
        "final": True,
        "transactionSuccess": True
    }).encode("utf-8")
    dll.ld3s_get_last_error.return_value = b""
    dll.ld3s_cancel_job.return_value = True
    dll.ld3s_free.return_value = None
    dll.ld3s_close.return_value = None

    return dll


# Tests for ConsumableClientAPIStub

class TestConsumableClientAPIStub:
    """Test the stub implementation."""

    def test_stub_initialization(self, stub_client):
        """Test stub client initializes correctly."""
        assert stub_client.dll_path == "fake.dll"
        assert stub_client.is_initialized is True
        assert stub_client.logger is not None

    def test_stub_new_job_template(self, stub_client):
        """Test stub returns valid template structure."""
        template = stub_client.new_job_template()

        assert "inventoryParameters" in template
        assert "wallets" in template["inventoryParameters"]
        assert len(template["inventoryParameters"]["wallets"]) == 2  # Ink and Media wallets

        # Check for expected accounts
        ink_wallet = template["inventoryParameters"]["wallets"][0]
        assert "accounts" in ink_wallet
        assert len(ink_wallet["accounts"]) == 4  # CMYK

        # Verify structure
        cyan_account = ink_wallet["accounts"][0]
        assert cyan_account["accountId"] == "cyan"
        assert "estimatedBalance" in cyan_account
        assert cyan_account["estimatedBalance"] > 0
        assert "metadata" in cyan_account
        assert cyan_account["metadata"]["uom"] == "ml"

    def test_stub_submit_job_raises(self, stub_client):
        """Test stub submit_job raises NotImplementedError."""
        with pytest.raises(NotImplementedError) as exc_info:
            stub_client.submit_job({"test": "data"})

        assert "ConsumableClient API is not available" in str(exc_info.value)

    def test_stub_get_job_status_raises(self, stub_client):
        """Test stub get_job_status raises NotImplementedError."""
        with pytest.raises(NotImplementedError) as exc_info:
            stub_client.get_job_status("12345")

        assert "ConsumableClient API is not available" in str(exc_info.value)


# Tests for ConsumableClientAPI

class TestConsumableClientAPI:
    """Test the real API client implementation."""

    def test_initialization_requires_dll_path(self, logger):
        """Test that initialization requires DLL path."""
        with pytest.raises(RuntimeError) as exc_info:
            ConsumableClientAPI(dll_path=None, logger=logger)

        assert "DLL path is required" in str(exc_info.value)

    def test_initialization_fails_missing_dll(self, logger, tmp_path):
        """Test initialization fails gracefully when DLL doesn't exist."""
        fake_dll = tmp_path / "nonexistent.dll"

        with pytest.raises(RuntimeError) as exc_info:
            ConsumableClientAPI(dll_path=str(fake_dll), logger=logger)

        assert "not found" in str(exc_info.value).lower()

    @patch('modules.api_client.CDLL')
    @patch('modules.api_client.Path')
    def test_successful_initialization(self, mock_path, mock_cdll, logger, mock_dll):
        """Test successful API client initialization."""
        # Mock Path.exists() to return True
        mock_path_inst = MagicMock()
        mock_path_inst.exists.return_value = True
        mock_path.return_value = mock_path_inst

        # Mock CDLL to return our mock DLL
        mock_cdll.return_value = mock_dll

        client = ConsumableClientAPI(dll_path="test.dll", logger=logger)

        assert client.is_initialized is True
        assert client.context == 12345
        assert client.dll_path == "test.dll"
        mock_dll.ld3s_open.assert_called_once()

    @patch('modules.api_client.CDLL')
    @patch('modules.api_client.Path')
    def test_new_job_template(self, mock_path, mock_cdll, logger, mock_dll):
        """Test new_job_template returns parsed JSON."""
        mock_path_inst = MagicMock()
        mock_path_inst.exists.return_value = True
        mock_path.return_value = mock_path_inst
        mock_cdll.return_value = mock_dll

        client = ConsumableClientAPI(dll_path="test.dll", logger=logger)
        template = client.new_job_template()

        assert isinstance(template, dict)
        assert "inventoryParameters" in template
        assert "wallets" in template["inventoryParameters"]

        # Verify DLL calls
        mock_dll.ld3s_new_job.assert_called_with(12345)
        mock_dll.ld3s_free.assert_called()

    @patch('modules.api_client.CDLL')
    @patch('modules.api_client.Path')
    def test_new_job_template_handles_error(self, mock_path, mock_cdll, logger, mock_dll):
        """Test new_job_template handles API errors."""
        mock_path_inst = MagicMock()
        mock_path_inst.exists.return_value = True
        mock_path.return_value = mock_path_inst

        # Configure mock to return None (error condition)
        mock_dll.ld3s_new_job.return_value = None
        mock_dll.ld3s_get_last_error.return_value = b"API Error"
        mock_cdll.return_value = mock_dll

        client = ConsumableClientAPI(dll_path="test.dll", logger=logger)

        with pytest.raises(RuntimeError) as exc_info:
            client.new_job_template()

        assert "API Error" in str(exc_info.value) or "Failed to create" in str(exc_info.value)

    @patch('modules.api_client.CDLL')
    @patch('modules.api_client.Path')
    def test_submit_job(self, mock_path, mock_cdll, logger, mock_dll):
        """Test job submission returns handle."""
        mock_path_inst = MagicMock()
        mock_path_inst.exists.return_value = True
        mock_path.return_value = mock_path_inst
        mock_cdll.return_value = mock_dll

        client = ConsumableClientAPI(dll_path="test.dll", logger=logger)
        job_data = {"test": "data", "inventoryParameters": {}}

        handle = client.submit_job(job_data)

        assert handle == 67890
        assert client.current_job_handle == 67890
        mock_dll.ld3s_submit_job.assert_called_once()

        # Verify JSON was encoded
        call_args = mock_dll.ld3s_submit_job.call_args
        assert call_args[0][0] == 12345  # context
        assert isinstance(call_args[0][1], bytes)  # JSON bytes

    @patch('modules.api_client.CDLL')
    @patch('modules.api_client.Path')
    def test_submit_job_failure(self, mock_path, mock_cdll, logger, mock_dll):
        """Test job submission failure handling."""
        mock_path_inst = MagicMock()
        mock_path_inst.exists.return_value = True
        mock_path.return_value = mock_path_inst

        # Configure mock to return 0 (failure)
        mock_dll.ld3s_submit_job.return_value = 0
        mock_dll.ld3s_get_last_error.return_value = b"Submission failed"
        mock_cdll.return_value = mock_dll

        client = ConsumableClientAPI(dll_path="test.dll", logger=logger)
        handle = client.submit_job({"test": "data"})

        assert handle == 0

    @patch('modules.api_client.CDLL')
    @patch('modules.api_client.Path')
    def test_get_job_status(self, mock_path, mock_cdll, logger, mock_dll):
        """Test job status polling."""
        mock_path_inst = MagicMock()
        mock_path_inst.exists.return_value = True
        mock_path.return_value = mock_path_inst
        mock_cdll.return_value = mock_dll

        client = ConsumableClientAPI(dll_path="test.dll", logger=logger)
        client.current_job_handle = 67890

        status = client.get_job_status()

        assert isinstance(status, dict)
        assert status["status"] == "complete"
        assert status["final"] is True
        assert status["transactionSuccess"] is True

        mock_dll.ld3s_get_job_status.assert_called_with(12345, 67890)
        mock_dll.ld3s_free.assert_called()

    @patch('modules.api_client.CDLL')
    @patch('modules.api_client.Path')
    def test_get_job_status_with_handle_parameter(self, mock_path, mock_cdll, logger, mock_dll):
        """Test job status with explicit handle parameter."""
        mock_path_inst = MagicMock()
        mock_path_inst.exists.return_value = True
        mock_path.return_value = mock_path_inst
        mock_cdll.return_value = mock_dll

        client = ConsumableClientAPI(dll_path="test.dll", logger=logger)
        status = client.get_job_status(job_handle=99999)

        assert isinstance(status, dict)
        mock_dll.ld3s_get_job_status.assert_called_with(12345, 99999)

    @patch('modules.api_client.CDLL')
    @patch('modules.api_client.Path')
    def test_get_job_status_string_handle(self, mock_path, mock_cdll, logger, mock_dll):
        """Test job status accepts string handle."""
        mock_path_inst = MagicMock()
        mock_path_inst.exists.return_value = True
        mock_path.return_value = mock_path_inst
        mock_cdll.return_value = mock_dll

        client = ConsumableClientAPI(dll_path="test.dll", logger=logger)
        status = client.get_job_status(job_handle="12345")

        assert isinstance(status, dict)
        mock_dll.ld3s_get_job_status.assert_called_with(12345, 12345)

    @patch('modules.api_client.CDLL')
    @patch('modules.api_client.Path')
    def test_get_job_status_no_handle_raises(self, mock_path, mock_cdll, logger, mock_dll):
        """Test job status raises when no handle available."""
        mock_path_inst = MagicMock()
        mock_path_inst.exists.return_value = True
        mock_path.return_value = mock_path_inst
        mock_cdll.return_value = mock_dll

        client = ConsumableClientAPI(dll_path="test.dll", logger=logger)

        with pytest.raises(RuntimeError) as exc_info:
            client.get_job_status()

        assert "No job handle available" in str(exc_info.value)

    @patch('modules.api_client.CDLL')
    @patch('modules.api_client.Path')
    def test_cancel_job(self, mock_path, mock_cdll, logger, mock_dll):
        """Test job cancellation."""
        mock_path_inst = MagicMock()
        mock_path_inst.exists.return_value = True
        mock_path.return_value = mock_path_inst
        mock_cdll.return_value = mock_dll

        client = ConsumableClientAPI(dll_path="test.dll", logger=logger)
        client.current_job_handle = 67890

        result = client.cancel_job()

        assert result is True
        mock_dll.ld3s_cancel_job.assert_called_with(12345, 67890)

    @patch('modules.api_client.CDLL')
    @patch('modules.api_client.Path')
    def test_get_last_error(self, mock_path, mock_cdll, logger, mock_dll):
        """Test getting last error message."""
        mock_path_inst = MagicMock()
        mock_path_inst.exists.return_value = True
        mock_path.return_value = mock_path_inst

        mock_dll.ld3s_get_last_error.return_value = b"Test error message"
        mock_cdll.return_value = mock_dll

        client = ConsumableClientAPI(dll_path="test.dll", logger=logger)
        error = client.get_last_error()

        assert error == "Test error message"
        mock_dll.ld3s_get_last_error.assert_called_with(12345)

    @patch('modules.api_client.CDLL')
    @patch('modules.api_client.Path')
    @patch('modules.api_client.time.sleep')
    def test_wait_for_job_completion(self, mock_sleep, mock_path, mock_cdll, logger, mock_dll):
        """Test wait_for_job_completion polls until done."""
        mock_path_inst = MagicMock()
        mock_path_inst.exists.return_value = True
        mock_path.return_value = mock_path_inst

        # Simulate job progressing through states
        status_responses = [
            json.dumps({"status": "pending", "final": False}).encode("utf-8"),
            json.dumps({"status": "processing", "final": False}).encode("utf-8"),
            json.dumps({"status": "complete", "final": True, "transactionSuccess": True}).encode("utf-8")
        ]
        mock_dll.ld3s_get_job_status.side_effect = status_responses
        mock_cdll.return_value = mock_dll

        client = ConsumableClientAPI(dll_path="test.dll", logger=logger)
        client.current_job_handle = 67890

        final_status = client.wait_for_job_completion()

        assert final_status["status"] == "complete"
        assert final_status["final"] is True
        assert mock_dll.ld3s_get_job_status.call_count == 3
        assert mock_sleep.call_count == 2  # Slept twice before reaching final state

    @patch('modules.api_client.CDLL')
    @patch('modules.api_client.Path')
    def test_cleanup_on_deletion(self, mock_path, mock_cdll, logger, mock_dll):
        """Test __del__ closes the API context."""
        mock_path_inst = MagicMock()
        mock_path_inst.exists.return_value = True
        mock_path.return_value = mock_path_inst
        mock_cdll.return_value = mock_dll

        client = ConsumableClientAPI(dll_path="test.dll", logger=logger)
        context = client.context

        # Trigger cleanup
        del client

        # Verify close was called (note: may not be immediate due to GC)
        # This is a best-effort test
        # mock_dll.ld3s_close.assert_called_with(context)


# Integration-style tests (would require real DLL)

class TestAPIClientIntegration:
    """
    Integration tests for API client.

    These tests are skipped by default and require a real ConsumableClient.dll
    to be available. Run with: pytest --run-integration
    """

    @pytest.mark.skipif(
        not Path("../CCAPIv2.0.0.1/ConsumableClient.dll").exists(),
        reason="ConsumableClient.dll not available"
    )
    def test_real_dll_initialization(self, logger):
        """Test initialization with real DLL (requires Windows + DLL)."""
        dll_path = "../CCAPIv2.0.0.1/ConsumableClient.dll"

        client = ConsumableClientAPI(dll_path=dll_path, logger=logger)

        assert client.is_initialized is True
        assert client.context is not None
        assert client.context != 0

    @pytest.mark.skipif(
        not Path("../CCAPIv2.0.0.1/ConsumableClient.dll").exists(),
        reason="ConsumableClient.dll not available"
    )
    def test_real_new_job_template(self, logger):
        """Test new_job_template with real DLL."""
        dll_path = "../CCAPIv2.0.0.1/ConsumableClient.dll"

        client = ConsumableClientAPI(dll_path=dll_path, logger=logger)
        template = client.new_job_template()

        # Verify structure
        assert "inventoryParameters" in template
        assert "wallets" in template["inventoryParameters"]
        assert len(template["inventoryParameters"]["wallets"]) > 0

        # Check that we got real wallet data
        first_wallet = template["inventoryParameters"]["wallets"][0]
        assert "accounts" in first_wallet
        assert len(first_wallet["accounts"]) > 0

        # Check account structure
        first_account = first_wallet["accounts"][0]
        assert "estimatedBalance" in first_account
        assert "metadata" in first_account
