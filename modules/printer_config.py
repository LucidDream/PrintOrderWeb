"""
Printer Configuration Module

Provides modular printer configuration management with support for:
- Default printer configurations
- API-based printer detection (future)
- Ink slot mapping and verification status
- Multi-language printer specifications
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class InkSlot:
    """Represents a single ink slot in the printer."""
    slot_number: int
    color_name: str  # e.g., "cyan", "light_cyan", "orange"
    color_hex: str   # e.g., "#00bcd4"
    verified: bool
    account_id: Optional[str] = None  # Links to inventory account
    capacity_ml: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for template rendering."""
        return {
            'slot_number': self.slot_number,
            'color_name': self.color_name,
            'color_hex': self.color_hex,
            'verified': self.verified,
            'account_id': self.account_id,
            'capacity_ml': self.capacity_ml,
        }


@dataclass
class PrinterConfig:
    """Represents a complete printer configuration."""
    model_name: str
    manufacturer: str
    model_code: str
    description: str
    ink_set_name: str
    total_slots: int
    slots: List[InkSlot]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for template rendering."""
        return {
            'model_name': self.model_name,
            'manufacturer': self.manufacturer,
            'model_code': self.model_code,
            'description': self.description,
            'ink_set_name': self.ink_set_name,
            'total_slots': self.total_slots,
            'slots': [slot.to_dict() for slot in self.slots],
            'verified_count': sum(1 for slot in self.slots if slot.verified),
            'unverified_count': sum(1 for slot in self.slots if not slot.verified),
        }


# Default printer configuration - Roland TrueVIS VG3-640
# All slots start UNVERIFIED - they will be verified by API data presence
DEFAULT_PRINTER = PrinterConfig(
    model_name="Roland TrueVIS VG3-640",
    manufacturer="Roland DG",
    model_code="VG3-640",
    description="64-inch Printer/Cutter",
    ink_set_name="8-Color TR2 Eco-Solvent Ink Set",
    total_slots=8,
    slots=[
        # Standard CMYK slots (1-4)
        # These are verified=False by default and will be set to True if API has data
        InkSlot(
            slot_number=1,
            color_name="cyan",
            color_hex="#00bcd4",
            verified=False,  # Updated by API
            account_id="cyan",
            capacity_ml=None  # Updated by API
        ),
        InkSlot(
            slot_number=2,
            color_name="magenta",
            color_hex="#e91e63",
            verified=False,  # Updated by API
            account_id="magenta",
            capacity_ml=None  # Updated by API
        ),
        InkSlot(
            slot_number=3,
            color_name="yellow",
            color_hex="#ffc107",
            verified=False,  # Updated by API
            account_id="yellow",
            capacity_ml=None  # Updated by API
        ),
        InkSlot(
            slot_number=4,
            color_name="black",
            color_hex="#212529",
            verified=False,  # Updated by API
            account_id="black",
            capacity_ml=None  # Updated by API
        ),
        # Extended gamut slots (5-8) - Roland VG3 configuration
        InkSlot(
            slot_number=5,
            color_name="light_cyan",
            color_hex="#80deea",
            verified=False,
            account_id="lt-cyan",  # Match blockchain naming
            capacity_ml=None
        ),
        InkSlot(
            slot_number=6,
            color_name="light_magenta",
            color_hex="#f48fb1",
            verified=False,
            account_id="lt-magenta",  # Match blockchain naming
            capacity_ml=None
        ),
        InkSlot(
            slot_number=7,
            color_name="orange",
            color_hex="#ff9800",
            verified=False,
            account_id="orange",  # Match blockchain naming
            capacity_ml=None
        ),
        InkSlot(
            slot_number=8,
            color_name="green",
            color_hex="#4caf50",
            verified=False,
            account_id="green",  # No matching ink in current inventory
            capacity_ml=None
        ),
    ]
)


class PrinterConfigManager:
    """
    Manages printer configuration with support for multiple sources.

    Priority order:
    1. API-detected printer (future implementation)
    2. User-configured printer (future implementation)
    3. Default printer (Epson SureColor P8000)
    """

    def __init__(self):
        """Initialize printer configuration manager."""
        self._current_config: Optional[PrinterConfig] = None
        self._api_config: Optional[PrinterConfig] = None
        logger.info("PrinterConfigManager initialized")

    def get_current_config(self) -> PrinterConfig:
        """
        Get the current active printer configuration.

        Returns:
            PrinterConfig: Active printer configuration
        """
        # Priority 1: API-detected printer (not yet implemented)
        if self._api_config:
            logger.debug("Using API-detected printer configuration")
            return self._api_config

        # Priority 2: User-configured printer (not yet implemented)
        if self._current_config:
            logger.debug("Using user-configured printer")
            return self._current_config

        # Priority 3: Default printer
        logger.debug("Using default printer configuration: Epson SureColor P8000")
        return DEFAULT_PRINTER

    def set_printer_from_api(self, api_data: Dict[str, Any]) -> None:
        """
        Configure printer from API data (future implementation).

        This method will be called when ConsumableClient API returns
        printer model information in the template structure.

        Args:
            api_data: API response containing printer information

        Example API structure (hypothetical):
            {
                "printerInfo": {
                    "model": "Epson SureColor P8000",
                    "manufacturer": "Epson",
                    "inkSlots": [...]
                }
            }
        """
        # TODO: Parse API data and create PrinterConfig
        # For now, this is a placeholder for future API integration
        logger.info(f"API printer detection not yet implemented. Data received: {api_data.keys()}")
        pass

    def update_slot_verification(
        self,
        inventory_accounts: Dict[str, Any]
    ) -> PrinterConfig:
        """
        Update slot verification status based on inventory data from API.

        A slot is VERIFIED if the API provides consumable data for that color.
        A slot is UNVERIFIED if the API does not have consumable data for that color.

        This ensures verification reflects actual API data presence, not hardcoded values.

        Args:
            inventory_accounts: Dictionary of toner_balances from API
                Format: {color: {"display": str, "available": float}}

        Returns:
            PrinterConfig: Updated printer configuration
        """
        config = self.get_current_config()

        # Update verification status for each slot based on API data presence
        for slot in config.slots:
            if slot.account_id:
                # Slot is VERIFIED only if API has data for this consumable
                if slot.account_id in inventory_accounts:
                    slot.verified = True
                    account = inventory_accounts[slot.account_id]
                    # Update slot data from API
                    slot.capacity_ml = account.get('available', slot.capacity_ml)
                    logger.info(
                        f"Slot {slot.slot_number} ({slot.color_name}): "
                        f"VERIFIED with {slot.capacity_ml:.1f} mL from API"
                    )
                else:
                    # API doesn't have this consumable - mark as unverified
                    slot.verified = False
                    slot.capacity_ml = None  # No data available
                    logger.info(
                        f"Slot {slot.slot_number} ({slot.color_name}): "
                        f"UNVERIFIED - no API data for this consumable"
                    )
            else:
                # Slot has no account_id - cannot verify
                slot.verified = False
                logger.debug(f"Slot {slot.slot_number}: No account_id, marked unverified")

        return config

    def get_slot_by_color(self, color: str) -> Optional[InkSlot]:
        """
        Get ink slot by color name.

        Args:
            color: Color name (e.g., "cyan", "light_cyan")

        Returns:
            InkSlot if found, None otherwise
        """
        config = self.get_current_config()
        for slot in config.slots:
            if slot.color_name.lower() == color.lower():
                return slot
        return None

    def get_verified_slots(self) -> List[InkSlot]:
        """Get list of verified ink slots."""
        config = self.get_current_config()
        return [slot for slot in config.slots if slot.verified]

    def get_unverified_slots(self) -> List[InkSlot]:
        """Get list of unverified ink slots."""
        config = self.get_current_config()
        return [slot for slot in config.slots if not slot.verified]


# Global printer config manager instance
printer_manager = PrinterConfigManager()


def get_printer_config() -> Dict[str, Any]:
    """
    Get current printer configuration as dictionary.

    This is the main entry point for templates and routes.

    Returns:
        Dict containing printer configuration
    """
    return printer_manager.get_current_config().to_dict()


def update_printer_from_inventory(inventory_accounts: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update printer configuration with inventory verification status.

    Args:
        inventory_accounts: Dictionary of inventory accounts

    Returns:
        Updated printer configuration dictionary
    """
    return printer_manager.update_slot_verification(inventory_accounts).to_dict()
