"""
Inventory data models.

These models represent point-in-time snapshots of blockchain inventory.
Used by the inventory service for caching and by routes for display.

Thread Safety:
    - InventorySnapshot is a frozen dataclass (immutable)
    - Safe to read from any thread without locks
    - New snapshots replace old ones atomically
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# Reverse geocoder for converting coordinates to location names
try:
    import reverse_geocoder as rg
    REVERSE_GEOCODER_AVAILABLE = True
except ImportError:
    REVERSE_GEOCODER_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LocationData:
    """
    Geographic location data for a consumable.

    Optional field - may or may not be present on any given account.
    Used to track where consumables were registered/created.
    """

    latitude: float
    """North/South coordinate."""

    longitude: float
    """East/West coordinate."""

    accuracy: str
    """Precision level (e.g., 'city', 'gps')."""

    timestamp: str
    """ISO 8601 timestamp when location was recorded."""

    # Reverse-geocoded display fields
    city: str = ""
    """City name (e.g., 'Nashville')."""

    region: str = ""
    """Region/state code (e.g., 'TN')."""

    country: str = ""
    """Country code ISO 3166-1 alpha-2 (e.g., 'US')."""

    @property
    def display_name(self) -> str:
        """Formatted location string for UI display (e.g., 'Nashville, TN, US')."""
        if self.city and self.region and self.country:
            return f"{self.city}, {self.region}, {self.country}"
        elif self.city and self.country:
            return f"{self.city}, {self.country}"
        elif self.country:
            return self.country
        return ""

    @property
    def recorded_date(self) -> str:
        """Formatted date string from timestamp (e.g., 'Dec 7, 2025')."""
        try:
            dt = datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
            return dt.strftime("%b %d, %Y")
        except (ValueError, AttributeError):
            return self.timestamp

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for template rendering."""
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "accuracy": self.accuracy,
            "timestamp": self.timestamp,
            "city": self.city,
            "region": self.region,
            "country": self.country,
            "display_name": self.display_name,
            "recorded_date": self.recorded_date,
        }

    @classmethod
    def from_api_data(cls, location_data: Dict[str, Any]) -> "LocationData":
        """
        Create LocationData from API response, with reverse geocoding.

        Args:
            location_data: The locationData dict from account.metadata

        Returns:
            LocationData with geocoded city/region/country if available
        """
        latitude = location_data.get("latitude", 0.0)
        longitude = location_data.get("longitude", 0.0)
        accuracy = location_data.get("accuracy", "")
        timestamp = location_data.get("timestamp", "")

        # Attempt reverse geocoding
        city = ""
        region = ""
        country = ""

        if REVERSE_GEOCODER_AVAILABLE and latitude and longitude:
            try:
                results = rg.search([(latitude, longitude)], verbose=False)
                if results and len(results) > 0:
                    result = results[0]
                    city = result.get("name", "")
                    region = result.get("admin1", "")  # State/province code
                    country = result.get("cc", "")  # ISO 3166-1 alpha-2
            except Exception as e:
                logger.warning(f"Reverse geocoding failed for ({latitude}, {longitude}): {e}")

        return cls(
            latitude=latitude,
            longitude=longitude,
            accuracy=accuracy,
            timestamp=timestamp,
            city=city,
            region=region,
            country=country,
        )


@dataclass(frozen=True)
class TonerBalance:
    """
    A single toner color balance from blockchain.

    Immutable snapshot of one toner account's state.
    """

    color: str
    """Color name (lowercase, e.g., 'cyan', 'magenta')."""

    balance_ml: float
    """Current balance in milliliters."""

    mint_id: str
    """Blockchain mint ID for this toner."""

    slot_number: Optional[int] = None
    """Printer slot number (1-8 for Roland TrueVIS)."""

    # Extended metadata (optional, for display)
    manufacturer: str = ""
    """Toner manufacturer name."""

    product_name: str = ""
    """Product/model name."""

    price: float = 0.0
    """Price per unit."""

    tax_rate: float = 0.0
    """Tax rate percentage."""

    location: Optional[LocationData] = None
    """Geographic location data (optional - may not be present)."""

    @property
    def has_location(self) -> bool:
        """Whether this toner has location data."""
        return self.location is not None and bool(self.location.display_name)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for template rendering."""
        result = {
            "color": self.color,
            "balance_ml": self.balance_ml,
            "mintId": self.mint_id,
            "slot_number": self.slot_number,
            "manufacturer": self.manufacturer,
            "product_name": self.product_name,
            "price": self.price,
            "tax_rate": self.tax_rate,
            "has_location": self.has_location,
        }
        if self.location:
            result["location"] = self.location.to_dict()
        return result


@dataclass(frozen=True)
class MediaOption:
    """
    A single media type from blockchain inventory.

    Immutable snapshot of one media account's state.
    """

    mint_id: str
    """Blockchain mint ID (used for matching)."""

    display_name: str
    """Human-readable name for UI display."""

    balance_sheets: float
    """Current balance in sheets."""

    width_mm: float = 0.0
    """Media width in millimeters."""

    height_mm: float = 0.0
    """Media height in millimeters."""

    # Extended metadata (optional)
    manufacturer: str = ""
    """Media manufacturer name."""

    product_name: str = ""
    """Product/model name."""

    price: float = 0.0
    """Price per sheet."""

    tax_rate: float = 0.0
    """Tax rate percentage."""

    location: Optional[LocationData] = None
    """Geographic location data (optional - may not be present)."""

    @property
    def has_location(self) -> bool:
        """Whether this media has location data."""
        return self.location is not None and bool(self.location.display_name)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for template rendering."""
        result = {
            "mintId": self.mint_id,
            "display_name": self.display_name,
            "balance_sheets": self.balance_sheets,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "manufacturer": self.manufacturer,
            "product_name": self.product_name,
            "price": self.price,
            "tax_rate": self.tax_rate,
            "has_location": self.has_location,
        }
        if self.location:
            result["location"] = self.location.to_dict()
        return result


@dataclass(frozen=True)
class InventorySnapshot:
    """
    Point-in-time snapshot of blockchain inventory.

    This is a FROZEN dataclass - completely immutable after creation.
    The inventory service creates new snapshots on each refresh.
    Routes read snapshots without any locking concerns.

    Thread Safety:
        - Inventory thread creates new InventorySnapshot on refresh
        - Main thread reads current snapshot via atomic reference swap
        - No locks needed - immutable data guarantees consistency

    Usage:
        # In inventory service (creates new snapshot)
        snapshot = InventorySnapshot.from_template(template_data)

        # In routes (reads current snapshot)
        snapshot = inventory_service.get_snapshot()
        for toner in snapshot.toner_balances:
            print(f"{toner.color}: {toner.balance_ml} mL")
    """

    fetched_at: datetime
    """When this snapshot was fetched from blockchain."""

    toner_balances: tuple[TonerBalance, ...]
    """Immutable tuple of toner balances (use tuple for frozen dataclass)."""

    media_options: tuple[MediaOption, ...]
    """Immutable tuple of media options."""

    raw_template: Dict[str, Any] = field(default_factory=dict)
    """Raw template data from API (for job submission)."""

    @property
    def age_seconds(self) -> float:
        """How old this snapshot is in seconds."""
        now = datetime.now(timezone.utc)
        return (now - self.fetched_at).total_seconds()

    @property
    def is_stale(self) -> bool:
        """Whether this snapshot is older than 60 seconds."""
        return self.age_seconds > 60.0

    def get_toner_by_color(self, color: str) -> Optional[TonerBalance]:
        """
        Find toner balance by color name.

        Args:
            color: Color name (case-insensitive)

        Returns:
            TonerBalance if found, None otherwise
        """
        color_lower = color.lower()
        for toner in self.toner_balances:
            if toner.color.lower() == color_lower:
                return toner
        return None

    def get_media_by_mint_id(self, mint_id: str) -> Optional[MediaOption]:
        """
        Find media option by mint ID.

        Args:
            mint_id: Blockchain mint ID

        Returns:
            MediaOption if found, None otherwise
        """
        for media in self.media_options:
            if media.mint_id == mint_id:
                return media
        return None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for session storage or API response.

        Note: raw_template is excluded (too large for session).
        """
        return {
            "fetched_at": self.fetched_at.isoformat(),
            "toner_balances": [t.to_dict() for t in self.toner_balances],
            "media_options": [m.to_dict() for m in self.media_options],
            "age_seconds": self.age_seconds,
            "is_stale": self.is_stale,
        }

    @classmethod
    def from_template(cls, template: Dict[str, Any]) -> "InventorySnapshot":
        """
        Create snapshot from blockchain template response.

        This parses the deeply nested template structure and extracts
        toner and media accounts into clean, typed objects.

        Args:
            template: Raw template from ld3s_new_job()

        Returns:
            InventorySnapshot with parsed data
        """
        toner_list: List[TonerBalance] = []
        media_list: List[MediaOption] = []

        # Navigate the nested structure
        inventory_params = template.get("inventoryParameters", {})
        wallets = inventory_params.get("wallets", [])

        for wallet in wallets:
            accounts = wallet.get("accounts", [])

            for account in accounts:
                # Extract common fields
                mint_id = account.get("mintId", "")
                balance = account.get("estimatedBalance", 0.0)

                # Navigate nested metadata
                outer_meta = account.get("metadata", {})
                price = float(outer_meta.get("price", 0))
                tax = float(outer_meta.get("tax", 0))

                # Extract optional location data (at same level as nested metadata)
                location_data_raw = outer_meta.get("locationData")
                location = None
                if location_data_raw:
                    location = LocationData.from_api_data(location_data_raw)

                inner_meta = outer_meta.get("metadata", {})
                uom = inner_meta.get("uom", "")

                token_desc = inner_meta.get("tokenDescription", {})
                project_data = token_desc.get("projectData", {})

                # Determine if toner or media based on UOM
                if uom == "Toner":
                    # Extract toner-specific fields
                    color = project_data.get("Color", "").lower()
                    manufacturer = project_data.get("Manufacturer", "")
                    # Try "Consumable Name" first (real API), then "ProductName"
                    product_name = project_data.get("Consumable Name") or project_data.get("ProductName", "")

                    # Try to get slot number from project data
                    slot_str = project_data.get("SlotNumber", "")
                    slot_number = int(slot_str) if slot_str.isdigit() else None

                    toner = TonerBalance(
                        color=color,
                        balance_ml=balance,
                        mint_id=mint_id,
                        slot_number=slot_number,
                        manufacturer=manufacturer,
                        product_name=product_name,
                        price=price,
                        tax_rate=tax,
                        location=location,
                    )
                    toner_list.append(toner)

                elif uom == "Media":
                    # Extract media-specific fields
                    # Try "Consumable Name" first (real API), then "ProductName", fallback to mint_id
                    display_name = project_data.get("Consumable Name") or project_data.get("ProductName") or mint_id
                    manufacturer = project_data.get("Manufacturer", "")
                    width = float(project_data.get("Width", 0))
                    height = float(project_data.get("Height", 0))

                    media = MediaOption(
                        mint_id=mint_id,
                        display_name=display_name,
                        balance_sheets=balance,
                        width_mm=width,
                        height_mm=height,
                        manufacturer=manufacturer,
                        product_name=display_name,
                        price=price,
                        tax_rate=tax,
                        location=location,
                    )
                    media_list.append(media)

        return cls(
            fetched_at=datetime.now(timezone.utc),
            toner_balances=tuple(toner_list),
            media_options=tuple(media_list),
            raw_template=template,
        )

    def get_full_account_data(self, account_id: str, consumable_type: str) -> Optional[Dict[str, Any]]:
        """
        Get full account data from raw_template for a specific consumable.

        This is needed for extracting detailed metadata for sidebar display.
        The account_id can be a color name (for toner) or mint_id (for media).

        Args:
            account_id: Color name (e.g., 'cyan') for toner, or mint_id for media
            consumable_type: 'toner' or 'media'

        Returns:
            Full account dict from raw_template if found, None otherwise
        """
        if not self.raw_template:
            return None

        inventory_params = self.raw_template.get("inventoryParameters", {})
        wallets = inventory_params.get("wallets", [])

        for wallet in wallets:
            accounts = wallet.get("accounts", [])

            for account in accounts:
                # Navigate to UOM to determine type
                outer_meta = account.get("metadata", {})
                inner_meta = outer_meta.get("metadata", {})
                uom = inner_meta.get("uom", "")

                if consumable_type == "toner" and uom == "Toner":
                    # Match by color
                    token_desc = inner_meta.get("tokenDescription", {})
                    project_data = token_desc.get("projectData", {})
                    color = project_data.get("Color", "").lower()

                    if color == account_id.lower():
                        return account

                elif consumable_type == "media" and uom == "Media":
                    # Match by mint_id
                    mint_id = account.get("mintId", "")
                    if mint_id == account_id:
                        return account

        return None

    @classmethod
    def create_empty(cls) -> "InventorySnapshot":
        """
        Create an empty snapshot (for initialization before first fetch).

        This is marked as stale immediately so routes know data isn't ready.
        """
        # Create with old timestamp so is_stale returns True
        old_time = datetime(2000, 1, 1, tzinfo=timezone.utc)
        return cls(
            fetched_at=old_time,
            toner_balances=(),
            media_options=(),
            raw_template={},
        )
