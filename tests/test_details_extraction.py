"""
Diagnostic script to test consumable details extraction.
Run this to see exactly what data is being extracted from the API.
"""

import os
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Set environment
os.environ['ENABLE_API_MODE'] = 'true'
os.environ['CONSUMABLE_DLL_PATH'] = '../CCAPIv2.0.0.1/ConsumableClient.dll'

from modules.api_client import ConsumableClientAPI
from modules.inventory import InventoryService
from modules.consumable_details import get_consumable_details
import logging

# Configure logging to see debug messages
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)-8s | %(name)s | %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    print("=" * 80)
    print("CONSUMABLE DETAILS EXTRACTION DIAGNOSTIC")
    print("=" * 80)
    print()

    # Initialize API client
    dll_path = os.environ['CONSUMABLE_DLL_PATH']
    print(f"Initializing API client from: {dll_path}")
    api_client = ConsumableClientAPI(dll_path=dll_path, logger=logger)
    print("✓ API client initialized")
    print()

    # Initialize inventory service
    inventory_service = InventoryService(api_client=api_client, logger=logger)
    print("✓ Inventory service initialized")
    print()

    # Fetch inventory
    print("Fetching inventory snapshot...")
    inventory = inventory_service.get_inventory_snapshot(force_refresh=True)
    print(f"✓ Inventory fetched: {len(inventory.get('toner_balances', {}))} toners, {len(inventory.get('media_options', {}))} media")
    print()

    # Test toner details extraction
    print("=" * 80)
    print("TONER DETAILS EXTRACTION")
    print("=" * 80)

    for color_id in inventory.get("toner_balances", {}).keys():
        print(f"\n--- {color_id.upper()} ---")
        account = inventory_service.get_full_account_data(color_id, "toner")

        if not account:
            print(f"  ERROR: No account data for {color_id}")
            continue

        # Show raw structure
        metadata = account.get('metadata', {})
        nested = metadata.get('metadata', {})
        if nested:
            project_data = nested.get('tokenDescription', {}).get('projectData', {})
            print(f"  projectData keys: {list(project_data.keys())[:5]}...")  # First 5 keys
            print(f"  Color: {project_data.get('Color')}")
            print(f"  Number Of Pages Yield: {project_data.get('Number Of Pages Yield')}")
            print(f"  Unit of Measure for Spending: {project_data.get('Unit of Measure for Spending')}")
        else:
            print(f"  Using stub structure")
            print(f"  uom: {metadata.get('uom')}")

        # Extract details
        print(f"\n  Extracted fields:")
        details = get_consumable_details("toner", account, inventory)
        for field in details:
            print(f"    - {field['label']}: {field['value']}")

    # Test media details extraction
    print()
    print("=" * 80)
    print("MEDIA DETAILS EXTRACTION")
    print("=" * 80)

    for media_id in inventory.get("media_options", {}).keys():
        print(f"\n--- {media_id} ---")
        account = inventory_service.get_full_account_data(media_id, "media")

        if not account:
            print(f"  ERROR: No account data for {media_id}")
            continue

        # Show raw structure
        metadata = account.get('metadata', {})
        nested = metadata.get('metadata', {})
        if nested:
            project_data = nested.get('tokenDescription', {}).get('projectData', {})
            print(f"  projectData keys: {list(project_data.keys())[:5]}...")  # First 5 keys
            print(f"  Media Type: {project_data.get('Media Type')}")
            print(f"  Size: {project_data.get('Size')}")
            print(f"  Grammage (g/m²): {project_data.get('Grammage (g/m²)')}")
            print(f"  ISO Brightness (%): {project_data.get('ISO Brightness (%)')}")
            print(f"  Opacity (%): {project_data.get('Opacity (%)')}")
        else:
            print(f"  Using stub structure")
            print(f"  uom: {metadata.get('uom')}")

        # Extract details
        print(f"\n  Extracted fields:")
        details = get_consumable_details("media", account, inventory)
        for field in details:
            print(f"    - {field['label']}: {field['value']}")

    print()
    print("=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
