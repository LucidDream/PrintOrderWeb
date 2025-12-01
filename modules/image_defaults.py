"""
SVG Default Images for Consumables

Centralized location for fallback images when product URL is not available.
Organized by consumable type (Toner, Media).

Edit these SVG definitions to customize the default appearance.
"""

# SVG for ALL Toner/Ink consumables (when URL field is missing)
TONER_DEFAULT_SVG = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
    "width='200' height='80' viewBox='0 0 200 80'%3E"
    "%3Crect fill='%23e8e8e8' width='200' height='80'/%3E"
    "%3Crect x='60' y='15' width='80' height='50' rx='5' fill='%23666' stroke='%23333' stroke-width='2'/%3E"
    "%3Ctext x='100' y='72' font-family='Arial,sans-serif' font-size='11' "
    "fill='%23333' text-anchor='middle'%3EINK CARTRIDGE%3C/text%3E"
    "%3C/svg%3E"
)

# SVG for ALL Media consumables (when URL field is missing)
MEDIA_DEFAULT_SVG = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
    "width='200' height='80' viewBox='0 0 200 80'%3E"
    "%3Crect fill='%23f5f5f5' width='200' height='80'/%3E"
    "%3Crect x='50' y='20' width='100' height='40' fill='white' stroke='%23999' stroke-width='1.5'/%3E"
    "%3Cline x1='60' y1='25' x2='140' y2='25' stroke='%23ccc' stroke-width='1'/%3E"
    "%3Cline x1='60' y1='32' x2='140' y2='32' stroke='%23ccc' stroke-width='1'/%3E"
    "%3Cline x1='60' y1='39' x2='140' y2='39' stroke='%23ccc' stroke-width='1'/%3E"
    "%3Ctext x='100' y='72' font-family='Arial,sans-serif' font-size='11' "
    "fill='%23666' text-anchor='middle'%3EPAPER MEDIA%3C/text%3E"
    "%3C/svg%3E"
)

# Generic fallback if type is unknown
GENERIC_DEFAULT_SVG = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
    "width='200' height='80' viewBox='0 0 200 80'%3E"
    "%3Crect fill='%23f0f0f0' width='200' height='80'/%3E"
    "%3Ccircle cx='100' cy='35' r='15' fill='none' stroke='%23999' stroke-width='2'/%3E"
    "%3Ctext x='100' y='72' font-family='Arial,sans-serif' font-size='11' "
    "fill='%23999' text-anchor='middle'%3ECONSUMABLE%3C/text%3E"
    "%3C/svg%3E"
)


def get_default_image(consumable_type: str) -> str:
    """
    Get the default SVG image for a consumable type.

    Args:
        consumable_type: Type of consumable ("Toner" or "Media")

    Returns:
        Data URI string for SVG image

    Example:
        >>> get_default_image('Toner')
        'data:image/svg+xml,...'
    """
    type_map = {
        'Toner': TONER_DEFAULT_SVG,
        'Media': MEDIA_DEFAULT_SVG,
    }

    return type_map.get(consumable_type, GENERIC_DEFAULT_SVG)
