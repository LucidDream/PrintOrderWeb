"""
Unit tests for the Inventory Service.

Tests both stub and real API template parsing.
"""

import json
import pytest
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock

from modules.inventory import InventoryService
from modules.api_client import ConsumableClientAPIStub


# Fixtures

@pytest.fixture
def stub_client():
    """Create a stub API client."""
    return ConsumableClientAPIStub()


@pytest.fixture
def inventory_service(stub_client):
    """Create an inventory service with stub client."""
    return InventoryService(stub_client)


@pytest.fixture
def real_template():
    """Load real template structure from Template.pdf.txt."""
    template_path = Path(__file__).parent.parent.parent / "Template.pdf.txt"
    if template_path.exists():
        with open(template_path, 'r', encoding='utf-8') as f:
            full_data = json.load(f)
            # Extract just the API reference part
            return full_data.get("apiTemplateReference", {})
    else:
        # Return a minimal real-style template for testing
        return {
            "inventoryParameters": {
                "wallets": [
                    {
                        "accounts": [
                            {
                                "estimatedBalance": 6000.0,
                                "mintId": "test-cyan-mint",
                                "metadata": {
                                    "metadata": {
                                        "uom": "Toner",
                                        "tokenDescription": {
                                            "projectData": {
                                                "Consumable Name": "Test Cyan Ink",
                                                "Color": "CYAN",
                                                "Unit of Measure for Spending": "mL"
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


@pytest.fixture
def mock_api_client_with_real_template(real_template):
    """Create a mock API client that returns real template structure."""
    mock_client = MagicMock()
    mock_client.new_job_template.return_value = real_template
    return mock_client


# Tests for Stub Template Parsing

class TestInventoryServiceWithStub:
    """Test inventory service with stub API client."""

    def test_initialization(self, stub_client):
        """Test service initializes correctly."""
        service = InventoryService(stub_client)
        assert service.api_client == stub_client
        assert service._cache is None
        assert service._cache_timestamp == 0
        assert service._cache_duration == 30

    def test_get_inventory_snapshot_stub(self, inventory_service):
        """Test getting inventory snapshot with stub client."""
        snapshot = inventory_service.get_inventory_snapshot()

        assert "media_options" in snapshot
        assert "toner_balances" in snapshot
        assert "toner_profiles" in snapshot
        assert "default_turnaround_options" in snapshot

        # Check media options
        assert len(snapshot["media_options"]) == 2  # std-matte, std-gloss from stub
        assert "std-matte" in snapshot["media_options"]
        assert snapshot["media_options"]["std-matte"]["display"] == "ProMatte A4"
        assert snapshot["media_options"]["std-matte"]["available"] == 1200

        # Check toner balances
        assert len(snapshot["toner_balances"]) == 4  # CMYK
        assert "cyan" in snapshot["toner_balances"]
        assert "magenta" in snapshot["toner_balances"]
        assert "yellow" in snapshot["toner_balances"]
        assert "black" in snapshot["toner_balances"]

        # Check toner profiles
        assert "full_color" in snapshot["toner_profiles"]
        assert snapshot["toner_profiles"]["full_color"] == ["cyan", "magenta", "yellow", "black"]
        assert snapshot["toner_profiles"]["mono"] == ["black"]

    def test_cache_functionality(self, inventory_service):
        """Test that caching works correctly."""
        # First call - should fetch fresh
        snapshot1 = inventory_service.get_inventory_snapshot()
        timestamp1 = inventory_service._cache_timestamp

        # Immediate second call - should use cache
        snapshot2 = inventory_service.get_inventory_snapshot()
        timestamp2 = inventory_service._cache_timestamp

        assert snapshot1 == snapshot2
        assert timestamp1 == timestamp2  # Cache timestamp shouldn't change

        # Wait and force refresh
        time.sleep(0.1)
        snapshot3 = inventory_service.get_inventory_snapshot(force_refresh=True)
        timestamp3 = inventory_service._cache_timestamp

        assert timestamp3 > timestamp1  # New timestamp

    def test_cache_expiration(self, inventory_service):
        """Test that cache expires after 30 seconds."""
        # Override cache duration for testing
        inventory_service._cache_duration = 0.1  # 100ms

        # First call
        snapshot1 = inventory_service.get_inventory_snapshot()
        timestamp1 = inventory_service._cache_timestamp

        # Wait for cache to expire
        time.sleep(0.15)

        # Second call should fetch fresh
        snapshot2 = inventory_service.get_inventory_snapshot()
        timestamp2 = inventory_service._cache_timestamp

        assert timestamp2 > timestamp1  # New timestamp

    def test_cache_invalidation(self, inventory_service):
        """Test cache can be manually invalidated."""
        # Populate cache
        snapshot1 = inventory_service.get_inventory_snapshot()
        assert inventory_service._cache is not None

        # Invalidate
        inventory_service.invalidate_cache()

        assert inventory_service._cache is None
        assert inventory_service._cache_timestamp == 0


# Tests for Real Template Parsing

class TestInventoryServiceWithRealTemplate:
    """Test inventory service with real API template structure."""

    def test_parse_real_template(self, mock_api_client_with_real_template):
        """Test parsing real blockchain template structure."""
        service = InventoryService(mock_api_client_with_real_template)
        snapshot = service.get_inventory_snapshot()

        assert "media_options" in snapshot
        assert "toner_balances" in snapshot

        # Should have parsed at least the test cyan ink
        # Note: actual counts depend on the real template fixture
        assert isinstance(snapshot["toner_balances"], dict)
        assert isinstance(snapshot["media_options"], dict)

    def test_parse_real_toner_account(self, inventory_service):
        """Test parsing a real toner account with nested structure."""
        account = {
            "estimatedBalance": 5000.0,
            "mintId": "test-mint-id",
            "metadata": {
                "metadata": {
                    "uom": "Toner",
                    "tokenDescription": {
                        "projectData": {
                            "Consumable Name": "Test Magenta Ink Bottle",
                            "Color": "MAGENTA",
                            "Unit of Measure for Spending": "mL"
                        }
                    }
                }
            }
        }

        result = inventory_service._parse_account(account)

        assert result["id"] == "magenta"
        assert result["type"] == "toner"
        assert result["display_name"] == "Test Magenta Ink Bottle"
        assert result["balance"] == 5000.0
        assert result["uom"] == "mL"
        assert result["color"] == "magenta"

    def test_parse_real_media_account(self, inventory_service):
        """Test parsing a real media account with nested structure."""
        account = {
            "estimatedBalance": 200.0,
            "mintId": "media-mint-abc123",
            "metadata": {
                "metadata": {
                    "uom": "Media",
                    "tokenDescription": {
                        "projectData": {
                            "Consumable Name": "ProMatte A4 Premium",
                            "Media Type": "MATTE",
                            "Unit of Measure": "sheets"
                        }
                    }
                }
            }
        }

        result = inventory_service._parse_account(account)

        assert result["id"] == "media-mint-abc123"
        assert result["type"] == "media"
        assert result["display_name"] == "ProMatte A4 Premium"
        assert result["balance"] == 200.0
        assert result["uom"] == "sheets"
        assert result["media_type"] == "matte"

    def test_parse_stub_account_fallback(self, inventory_service):
        """Test that stub account structure still works (backward compatibility)."""
        account = {
            "accountId": "cyan",
            "estimatedBalance": 4800.0,
            "metadata": {
                "uom": "ml",
                "displayName": "Cyan Ink (Stub)"
            }
        }

        result = inventory_service._parse_account(account)

        assert result["id"] == "cyan"
        assert result["type"] == "toner"
        assert result["display_name"] == "Cyan Ink (Stub)"
        assert result["balance"] == 4800.0
        assert result["uom"] == "ml"

    def test_parse_account_missing_data(self, inventory_service):
        """Test parsing account with missing/incomplete data."""
        account = {
            "estimatedBalance": 1000.0,
            "mintId": "incomplete-account",
            "metadata": {
                "metadata": {
                    "uom": "Toner",
                    "tokenDescription": {
                        "projectData": {}  # Empty project data
                    }
                }
            }
        }

        result = inventory_service._parse_account(account)

        # Should gracefully handle missing data
        assert result["type"] == "toner"
        assert result["balance"] == 1000.0
        assert result["display_name"] == "incomplete-account"  # Falls back to mintId

    def test_parse_account_unknown_type(self, inventory_service):
        """Test parsing account with unknown type."""
        account = {
            "estimatedBalance": 500.0,
            "mintId": "unknown-type",
            "metadata": {
                "metadata": {
                    "uom": "UnknownType",  # Not Toner or Media
                    "tokenDescription": {
                        "projectData": {
                            "Consumable Name": "Mystery Consumable"
                        }
                    }
                }
            }
        }

        result = inventory_service._parse_account(account)

        # Should default to toner for unknown types
        assert result["type"] == "toner"
        assert result["display_name"] == "Mystery Consumable"


# Integration Tests

class TestInventoryServiceIntegration:
    """Integration tests for inventory service."""

    def test_full_snapshot_with_real_template(self, real_template):
        """Test complete snapshot generation with real template."""
        mock_client = MagicMock()
        mock_client.new_job_template.return_value = real_template

        service = InventoryService(mock_client)
        snapshot = service.get_inventory_snapshot()

        # Verify structure
        assert "media_options" in snapshot
        assert "toner_balances" in snapshot
        assert "toner_profiles" in snapshot

        # Verify all toner colors are present (from real template)
        # Real template should have CMYK
        toner_colors = set(snapshot["toner_balances"].keys())
        expected_colors = {"cyan", "magenta", "yellow", "black"}

        # Check if all expected colors are present
        assert toner_colors.intersection(expected_colors), "Should have at least some CMYK colors"

        # Verify media options
        assert len(snapshot["media_options"]) > 0

    def test_cache_reduces_api_calls(self):
        """Test that caching reduces API calls."""
        mock_client = MagicMock()
        mock_client.new_job_template.return_value = {
            "inventoryParameters": {"wallets": []}
        }

        service = InventoryService(mock_client)

        # First call
        service.get_inventory_snapshot()
        assert mock_client.new_job_template.call_count == 1

        # Second call (should use cache)
        service.get_inventory_snapshot()
        assert mock_client.new_job_template.call_count == 1  # No additional call

        # Force refresh
        service.get_inventory_snapshot(force_refresh=True)
        assert mock_client.new_job_template.call_count == 2  # New call

    def test_inventory_service_with_no_client(self):
        """Test that service uses stub when no client provided."""
        service = InventoryService()

        assert isinstance(service.api_client, ConsumableClientAPIStub)

        # Should still work
        snapshot = service.get_inventory_snapshot()
        assert "media_options" in snapshot
        assert "toner_balances" in snapshot
