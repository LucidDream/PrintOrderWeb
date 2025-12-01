"""
Consumable Details Module

Determines which metadata fields to display in the "Show Details" section
for each consumable. Extracts real data from inventory and presents it
in a user-friendly format.

This module is designed to be easily extended with AI-based field selection
in the future.
"""

from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class DetailField:
    """Represents a single detail field to display."""

    def __init__(
        self,
        key: str,
        label: str,
        value: Any,
        format_type: str = "text",
        priority: int = 0
    ):
        """
        Initialize a detail field.

        Args:
            key: Internal key for this field
            label: Display label (should be translation key)
            value: Field value
            format_type: How to format the value (text, number, badge, url)
            priority: Display priority (lower = shown first)
        """
        self.key = key
        self.label = label
        self.value = value
        self.format_type = format_type
        self.priority = priority

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for template rendering."""
        return {
            'key': self.key,
            'label': self.label,
            'value': self.value,
            'format_type': self.format_type,
            'priority': self.priority,
        }


class ConsumableDetailsExtractor:
    """
    Extracts relevant detail fields from consumable metadata.

    This class determines which fields are important to display based on
    the consumable type and available data.
    """

    # Field priority definitions (lower = more important)
    FIELD_PRIORITIES = {
        # Toner/Ink characteristics (prioritize ink properties)
        'color': 10,
        'chemistry_base': 15,
        'pigment_family': 17,
        'page_yield': 20,
        'unit_of_measure': 25,
        'viscosity': 30,
        'surface_tension': 35,
        'density': 40,
        'ph': 45,
        'conductivity': 50,
        'particle_size_d50': 55,
        'particle_size_d90': 60,
        'zeta_potential': 65,
        'shelf_life': 70,
        'storage_temp': 75,
        'ink_temp': 80,
        'date_of_manufacture': 85,
        'sku': 90,
        'safety_data_sheet': 95,
        'icc_profile': 100,

        # Media characteristics
        'media_type': 10,
        'size': 20,
        'dimensions': 25,
        'weight': 30,
        'brightness': 40,
        'opacity': 45,
        'coating_type': 50,
        'substrate_family': 55,
        'thickness': 60,
        'cie_whiteness': 65,
        'surface_energy': 70,
        'surface_roughness': 75,
        'heat_tolerance': 80,
        'moisture_content': 85,
        'batch_lot': 90,
        'date_of_manufacture': 95,
        'sku': 100,
        'safety_data_sheet': 105,
        'icc_profile': 110,

        # General (lower priority)
        'manufacturer': 110,
        'part_number': 120,
    }

    def __init__(self):
        """Initialize the details extractor."""
        pass

    def extract_toner_details(
        self,
        account: Dict[str, Any],
        inventory_data: Dict[str, Any]
    ) -> List[DetailField]:
        """
        Extract detail fields for toner/ink consumables.

        Args:
            account: Account data from inventory (contains balance, metadata)
            inventory_data: Full inventory data structure

        Returns:
            List of DetailField objects to display
        """
        fields = []
        metadata = account.get('metadata', {})

        # Navigate to deeply nested metadata structure
        nested_metadata = metadata.get('metadata', {})
        if not nested_metadata:
            # Stub structure - simpler metadata
            logger.info("Using stub toner structure")
            return self._extract_stub_toner_details(account, metadata)

        # Real API structure - extract from projectData
        logger.info("Using real API toner structure")
        token_desc = nested_metadata.get('tokenDescription', {})
        project_data = token_desc.get('projectData', {})

        logger.info(f"Toner projectData keys: {list(project_data.keys())}")

        # Extract price, tax, and currency from metadata level (same level as nested metadata)
        price_str = metadata.get('price')
        tax_str = metadata.get('tax')
        currency = metadata.get('currency', '$')

        if price_str:
            try:
                base_price = float(price_str)
                tax_rate = float(tax_str) / 100 if tax_str else 0.0
                total_cost = base_price + (base_price * tax_rate)

                logger.info(f"  → Extracted price: {currency}{base_price} + {tax_str}% tax = {currency}{total_cost:.2f}")

                # Add total cost with tax
                fields.append(DetailField(
                    key='total_cost',
                    label='consumable.total_cost',
                    value=f"{currency}{total_cost:.2f}",
                    format_type='text',
                    priority=5  # High priority - show near top
                ))

                # Add base price (for details section)
                fields.append(DetailField(
                    key='base_price',
                    label='consumable.base_price',
                    value=f"{currency}{base_price:.2f}",
                    format_type='text',
                    priority=85
                ))

                # Add tax percentage (for details section)
                if tax_str:
                    fields.append(DetailField(
                        key='tax_rate',
                        label='consumable.tax_rate',
                        value=f"{tax_str}%",
                        format_type='text',
                        priority=86
                    ))
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse price/tax: {e}")

        # Extract purchase date from metadata level
        date_of_purchase = metadata.get('dateOfPurchase')
        if date_of_purchase:
            logger.info(f"  → Extracted purchase date: {date_of_purchase}")
            fields.append(DetailField(
                key='purchase_date',
                label='consumable.purchase_date',
                value=date_of_purchase,
                format_type='text',
                priority=87  # Show in details section
            ))

        # Extract color
        color = project_data.get('Color', '').upper()
        if color:
            logger.info(f"  → Extracted toner color: {color}")
            fields.append(DetailField(
                key='color',
                label='consumable.color',
                value=color,
                format_type='badge',
                priority=self.FIELD_PRIORITIES.get('color', 100)
            ))

        # Extract page yield
        page_yield = project_data.get('Number Of Pages Yield')
        if page_yield:
            logger.info(f"  → Extracted page yield: {page_yield}")
            fields.append(DetailField(
                key='page_yield',
                label='consumable.page_yield_detail',
                value=f"{page_yield:,} pages",
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('page_yield', 100)
            ))

        # Extract unit of measure for spending
        uom = project_data.get('Unit of Measure for Spending')
        if uom:
            logger.info(f"  → Extracted UOM: {uom}")
            fields.append(DetailField(
                key='unit_of_measure',
                label='consumable.unit_measure',
                value=uom,
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('unit_of_measure', 100)
            ))

        # Extract chemistry base
        chemistry = project_data.get('Chemistry Base')
        if chemistry:
            fields.append(DetailField(
                key='chemistry_base',
                label='consumable.chemistry_base',
                value=chemistry,
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('chemistry_base', 100)
            ))

        # Extract pigment family
        pigment = project_data.get('Pigment Family (Cyan)')
        if pigment:
            fields.append(DetailField(
                key='pigment_family',
                label='consumable.pigment_family',
                value=pigment,
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('pigment_family', 100)
            ))

        # Extract viscosity
        viscosity = project_data.get('Viscosity @25°C (mPa·s)')
        if viscosity:
            fields.append(DetailField(
                key='viscosity',
                label='consumable.viscosity',
                value=f"{viscosity} mPa·s",
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('viscosity', 100)
            ))

        # Extract surface tension
        surface_tension = project_data.get('Surface Tension @23°C (mN/m)')
        if surface_tension:
            fields.append(DetailField(
                key='surface_tension',
                label='consumable.surface_tension',
                value=f"{surface_tension} mN/m",
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('surface_tension', 100)
            ))

        # Extract density
        density = project_data.get('Density @25°C (g/mL)')
        if density:
            fields.append(DetailField(
                key='density',
                label='consumable.density',
                value=f"{density} g/mL",
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('density', 100)
            ))

        # Extract pH
        ph = project_data.get('PH @25°C (aq inks mildly alkaline)')
        if ph:
            fields.append(DetailField(
                key='ph',
                label='consumable.ph',
                value=f"pH {ph}",
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('ph', 100)
            ))

        # Extract conductivity
        conductivity = project_data.get('Conductivity (µS/cm)')
        if conductivity:
            fields.append(DetailField(
                key='conductivity',
                label='consumable.conductivity',
                value=f"{conductivity} µS/cm",
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('conductivity', 100)
            ))

        # Extract particle size D50
        d50 = project_data.get('Particle Size D50 (nm)')
        if d50:
            fields.append(DetailField(
                key='particle_size_d50',
                label='consumable.particle_size_d50',
                value=f"{d50} nm",
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('particle_size_d50', 100)
            ))

        # Extract particle size D90
        d90 = project_data.get('Particle Size D90 (nm)')
        if d90:
            fields.append(DetailField(
                key='particle_size_d90',
                label='consumable.particle_size_d90',
                value=f"{d90} nm",
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('particle_size_d90', 100)
            ))

        # Extract zeta potential
        zeta = project_data.get('Zeta Potential (mV) for Stability')
        if zeta:
            fields.append(DetailField(
                key='zeta_potential',
                label='consumable.zeta_potential',
                value=f"{zeta} mV",
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('zeta_potential', 100)
            ))

        # Extract shelf life
        shelf_life = project_data.get('Shelf Life (months)')
        if shelf_life:
            fields.append(DetailField(
                key='shelf_life',
                label='consumable.shelf_life',
                value=f"{shelf_life} months",
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('shelf_life', 100)
            ))

        # Extract storage temperature
        storage_temp = project_data.get('Storage Temperature Range (°C)')
        if storage_temp:
            fields.append(DetailField(
                key='storage_temp',
                label='consumable.storage_temp',
                value=f"{storage_temp}°C",
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('storage_temp', 100)
            ))

        # Extract recommended ink temperature
        ink_temp = project_data.get('Recommended Ink Temp at Head Inlet (°C)')
        if ink_temp:
            fields.append(DetailField(
                key='ink_temp',
                label='consumable.ink_temp',
                value=f"{ink_temp}°C",
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('ink_temp', 100)
            ))

        # Extract date of manufacture
        date_mfg = project_data.get('Date of Manufacture')
        if date_mfg:
            fields.append(DetailField(
                key='date_of_manufacture',
                label='consumable.manufacturing_date',
                value=date_mfg,
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('date_of_manufacture', 100)
            ))

        # Extract SKU
        sku = project_data.get('SKU')
        if sku:
            fields.append(DetailField(
                key='sku',
                label='consumable.sku',
                value=sku,
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('sku', 100)
            ))

        # Extract Safety Data Sheet
        sds = project_data.get('Safety Data Sheet')
        if sds:
            fields.append(DetailField(
                key='safety_data_sheet',
                label='consumable.safety_data_sheet',
                value=sds,
                format_type='url',
                priority=self.FIELD_PRIORITIES.get('safety_data_sheet', 100)
            ))

        # Extract ICC Profile
        icc = project_data.get('ICC Profile')
        if icc:
            fields.append(DetailField(
                key='icc_profile',
                label='consumable.icc_profile',
                value=icc,
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('icc_profile', 100)
            ))

        # Extract manufacturer if available
        manufacturer = project_data.get('Manufacturer')
        if manufacturer:
            fields.append(DetailField(
                key='manufacturer',
                label='consumable.manufacturer',
                value=manufacturer,
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('manufacturer', 100)
            ))

        # Extract part number if available
        part_number = project_data.get('Part Number')
        if part_number:
            fields.append(DetailField(
                key='part_number',
                label='consumable.part_number',
                value=part_number,
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('part_number', 100)
            ))

        # Extract product image URL (OPTIONAL - may not be present in all tokens)
        product_url = project_data.get('url')
        if product_url:
            logger.info(f"  → Extracted product image URL: {product_url}")
            fields.append(DetailField(
                key='product_image_url',
                label='consumable.product_image',
                value=product_url,
                format_type='url',
                priority=1  # Very high priority - needed for card display
            ))
        else:
            logger.info(f"  → No product image URL found in metadata (will use SVG default)")

        # Sort by priority
        fields.sort(key=lambda f: f.priority)

        logger.info(f"Extracted {len(fields)} toner detail fields")
        return fields

    def extract_media_details(
        self,
        account: Dict[str, Any],
        inventory_data: Dict[str, Any]
    ) -> List[DetailField]:
        """
        Extract detail fields for media consumables.

        Args:
            account: Account data from inventory
            inventory_data: Full inventory data structure

        Returns:
            List of DetailField objects to display
        """
        fields = []
        metadata = account.get('metadata', {})

        # Navigate to deeply nested metadata structure
        nested_metadata = metadata.get('metadata', {})
        if not nested_metadata:
            # Stub structure
            logger.info("Using stub media structure")
            return self._extract_stub_media_details(account, metadata)

        # Real API structure
        logger.info("Using real API media structure")
        token_desc = nested_metadata.get('tokenDescription', {})
        project_data = token_desc.get('projectData', {})

        logger.info(f"Media projectData keys: {list(project_data.keys())}")

        # Extract price, tax, and currency from metadata level (same as toner)
        price_str = metadata.get('price')
        tax_str = metadata.get('tax')
        currency = metadata.get('currency', '$')

        if price_str:
            try:
                base_price = float(price_str)
                tax_rate = float(tax_str) / 100 if tax_str else 0.0
                total_cost = base_price + (base_price * tax_rate)

                logger.info(f"  → Extracted media price: {currency}{base_price} + {tax_str}% tax = {currency}{total_cost:.2f}")

                # Add total cost with tax
                fields.append(DetailField(
                    key='total_cost',
                    label='consumable.total_cost',
                    value=f"{currency}{total_cost:.2f}",
                    format_type='text',
                    priority=5  # High priority - show near top
                ))

                # Add base price (for details section)
                fields.append(DetailField(
                    key='base_price',
                    label='consumable.base_price',
                    value=f"{currency}{base_price:.2f}",
                    format_type='text',
                    priority=85
                ))

                # Add tax percentage (for details section)
                if tax_str:
                    fields.append(DetailField(
                        key='tax_rate',
                        label='consumable.tax_rate',
                        value=f"{tax_str}%",
                        format_type='text',
                        priority=86
                    ))
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse media price/tax: {e}")

        # Extract purchase date from metadata level
        date_of_purchase = metadata.get('dateOfPurchase')
        if date_of_purchase:
            logger.info(f"  → Extracted media purchase date: {date_of_purchase}")
            fields.append(DetailField(
                key='purchase_date',
                label='consumable.purchase_date',
                value=date_of_purchase,
                format_type='text',
                priority=87  # Show in details section
            ))

        # Extract media type
        media_type = project_data.get('Media Type', '').upper()
        if media_type:
            logger.info(f"  → Extracted media type: {media_type}")
            fields.append(DetailField(
                key='media_type',
                label='consumable.media_type',
                value=media_type,
                format_type='badge',
                priority=self.FIELD_PRIORITIES.get('media_type', 100)
            ))

        # Extract size (contains dimensions)
        # Example from API: "8.5" (width) x 14" (height)" or "8.3" (width) x 11.7" (height)"
        size = project_data.get('Size')
        if size:
            logger.info(f"  → Extracted media size: {size}")
            fields.append(DetailField(
                key='size',
                label='consumable.size',
                value=size,
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('size', 100)
            ))

        # NOTE: Do NOT extract "Unit of Measure" from projectData for media
        # That field contains "inches" (dimension units), not spending units
        # Media spending unit is always "sheets" (implicit from token structure)
        # We don't display spending unit for media since it's always sheets

        # Extract grammage (weight) if available
        # Field name in API: "Grammage (g/m²)"
        grammage = project_data.get('Grammage (g/m²)')
        if grammage:
            fields.append(DetailField(
                key='weight',
                label='consumable.weight',
                value=f"{grammage} g/m²",
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('weight', 100)
            ))

        # Extract brightness if available
        # Field name in API: "ISO Brightness (%)"
        brightness = project_data.get('ISO Brightness (%)')
        if brightness:
            fields.append(DetailField(
                key='brightness',
                label='consumable.brightness',
                value=f"{brightness}%",
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('brightness', 100)
            ))

        # Extract opacity if available
        # Field name in API: "Opacity (%)"
        opacity = project_data.get('Opacity (%)')
        if opacity:
            fields.append(DetailField(
                key='opacity',
                label='consumable.opacity',
                value=f"{opacity}%",
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('opacity', 100)
            ))

        # Extract coating type
        coating = project_data.get('Coating Type')
        if coating:
            fields.append(DetailField(
                key='coating_type',
                label='consumable.coating_type',
                value=coating,
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('coating_type', 100)
            ))

        # Extract substrate family
        substrate = project_data.get('Substrate Family')
        if substrate:
            fields.append(DetailField(
                key='substrate_family',
                label='consumable.substrate_family',
                value=substrate,
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('substrate_family', 100)
            ))

        # Extract thickness
        thickness = project_data.get('Thickness (µm)')
        if thickness:
            fields.append(DetailField(
                key='thickness',
                label='consumable.thickness',
                value=f"{thickness} µm",
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('thickness', 100)
            ))

        # Extract CIE whiteness
        cie_white = project_data.get('CIE Whiteness')
        if cie_white:
            fields.append(DetailField(
                key='cie_whiteness',
                label='consumable.cie_whiteness',
                value=str(cie_white),
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('cie_whiteness', 100)
            ))

        # Extract surface energy
        surface_energy = project_data.get('Surface Energy (dynes)')
        if surface_energy:
            fields.append(DetailField(
                key='surface_energy',
                label='consumable.surface_energy',
                value=f"{surface_energy} dynes",
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('surface_energy', 100)
            ))

        # Extract surface roughness
        roughness = project_data.get('Surface Roughness Ra (µm)')
        if roughness:
            fields.append(DetailField(
                key='surface_roughness',
                label='consumable.surface_roughness',
                value=f"{roughness} µm Ra",
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('surface_roughness', 100)
            ))

        # Extract heat tolerance
        heat_tol = project_data.get('Heat Tolerance (°C)')
        if heat_tol:
            fields.append(DetailField(
                key='heat_tolerance',
                label='consumable.heat_tolerance',
                value=f"{heat_tol}°C",
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('heat_tolerance', 100)
            ))

        # Extract moisture content
        moisture = project_data.get('Factory Moisture Content (%)')
        if moisture:
            fields.append(DetailField(
                key='moisture_content',
                label='consumable.moisture_content',
                value=f"{moisture}%",
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('moisture_content', 100)
            ))

        # Extract batch/lot ID
        batch = project_data.get('Batch/Lot ID')
        if batch:
            fields.append(DetailField(
                key='batch_lot',
                label='consumable.lot_number',
                value=batch,
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('batch_lot', 100)
            ))

        # Extract date of manufacture
        date_mfg = project_data.get('Date of Manufacture')
        if date_mfg:
            fields.append(DetailField(
                key='date_of_manufacture',
                label='consumable.manufacturing_date',
                value=date_mfg,
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('date_of_manufacture', 100)
            ))

        # Extract SKU
        sku = project_data.get('SKU')
        if sku:
            fields.append(DetailField(
                key='sku',
                label='consumable.sku',
                value=sku,
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('sku', 100)
            ))

        # Extract Safety Data Sheet
        sds = project_data.get('Safety Data Sheet')
        if sds:
            fields.append(DetailField(
                key='safety_data_sheet',
                label='consumable.safety_data_sheet',
                value=sds,
                format_type='url',
                priority=self.FIELD_PRIORITIES.get('safety_data_sheet', 100)
            ))

        # Extract ICC Profile (check both field names)
        icc = project_data.get('ICC Profile') or project_data.get('ICC Profile Link')
        if icc:
            fields.append(DetailField(
                key='icc_profile',
                label='consumable.icc_profile',
                value=icc,
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('icc_profile', 100)
            ))

        # Extract manufacturer
        manufacturer = project_data.get('Manufacturer')
        if manufacturer:
            fields.append(DetailField(
                key='manufacturer',
                label='consumable.manufacturer',
                value=manufacturer,
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('manufacturer', 100)
            ))

        # Extract product image URL (OPTIONAL - may not be present in all tokens)
        product_url = project_data.get('url')
        if product_url:
            logger.info(f"  → Extracted media product image URL: {product_url}")
            fields.append(DetailField(
                key='product_image_url',
                label='consumable.product_image',
                value=product_url,
                format_type='url',
                priority=1  # Very high priority - needed for card display
            ))
        else:
            logger.info(f"  → No product image URL found in media metadata (will use SVG default)")

        # Sort by priority
        fields.sort(key=lambda f: f.priority)

        logger.info(f"Extracted {len(fields)} media detail fields")
        return fields

    def _extract_stub_toner_details(
        self,
        account: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> List[DetailField]:
        """Extract toner details from stub structure."""
        fields = []

        # Stub has simpler structure - limited metadata
        # Color would be in account ID
        account_id = account.get('accountId', '').upper()
        if account_id in ['CYAN', 'MAGENTA', 'YELLOW', 'BLACK']:
            fields.append(DetailField(
                key='color',
                label='consumable.color',
                value=account_id,
                format_type='badge',
                priority=self.FIELD_PRIORITIES.get('color', 100)
            ))

        # UOM from metadata
        uom = metadata.get('uom', 'mL')
        if uom and uom != 'sheets':  # Not media
            fields.append(DetailField(
                key='unit_of_measure',
                label='consumable.unit_measure',
                value=uom,
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('unit_of_measure', 100)
            ))

        fields.sort(key=lambda f: f.priority)
        return fields

    def _extract_stub_media_details(
        self,
        account: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> List[DetailField]:
        """Extract media details from stub structure."""
        fields = []

        # UOM from metadata
        uom = metadata.get('uom', 'sheets')
        if uom:
            fields.append(DetailField(
                key='unit_of_measure',
                label='consumable.unit_measure',
                value=uom,
                format_type='text',
                priority=self.FIELD_PRIORITIES.get('unit_of_measure', 100)
            ))

        fields.sort(key=lambda f: f.priority)
        return fields

    def get_consumable_details(
        self,
        consumable_type: str,
        account: Dict[str, Any],
        inventory_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Get detail fields for a consumable.

        This is the main entry point for extracting details.

        Args:
            consumable_type: "toner" or "media"
            account: Account data from inventory
            inventory_data: Full inventory data

        Returns:
            List of field dictionaries for template rendering
        """
        if consumable_type == "toner":
            fields = self.extract_toner_details(account, inventory_data)
        elif consumable_type == "media":
            fields = self.extract_media_details(account, inventory_data)
        else:
            logger.warning(f"Unknown consumable type: {consumable_type}")
            return []

        return [field.to_dict() for field in fields]


# Global extractor instance
_details_extractor = ConsumableDetailsExtractor()


def get_consumable_details(
    consumable_type: str,
    account: Dict[str, Any],
    inventory_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Get detail fields for a consumable.

    This is the main public API for extracting consumable details.

    Args:
        consumable_type: "toner" or "media"
        account: Account data from inventory
        inventory_data: Full inventory data

    Returns:
        List of field dictionaries for template rendering

    Example:
        >>> details = get_consumable_details("toner", account, inventory)
        >>> for field in details:
        ...     print(f"{field['label']}: {field['value']}")
        consumable.color: CYAN
        consumable.page_yield_detail: 6,000 pages
        consumable.unit_measure: mL
    """
    return _details_extractor.get_consumable_details(
        consumable_type,
        account,
        inventory_data
    )


def set_field_priority(field_key: str, priority: int) -> None:
    """
    Update the display priority for a field.

    Lower priority values are displayed first.

    Args:
        field_key: Field key (e.g., 'color', 'media_type')
        priority: New priority value

    Example:
        >>> set_field_priority('color', 5)  # Show color first
        >>> set_field_priority('manufacturer', 100)  # Show manufacturer last
    """
    ConsumableDetailsExtractor.FIELD_PRIORITIES[field_key] = priority
    logger.info(f"Updated priority for '{field_key}' to {priority}")


def get_field_priorities() -> Dict[str, int]:
    """
    Get current field priority configuration.

    Returns:
        Dictionary mapping field keys to priority values
    """
    return ConsumableDetailsExtractor.FIELD_PRIORITIES.copy()
