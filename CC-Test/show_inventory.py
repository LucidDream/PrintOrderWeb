"""Quick script to display current blockchain inventory."""

import json
import sys
from pathlib import Path
from ctypes import cdll, c_void_p, c_char_p

# DLL path
dll_path = Path(__file__).parent.parent.parent / "CCAPIv2.0.0.2" / "ConsumableClient.dll"

print(f"Loading DLL: {dll_path}")
lib = cdll.LoadLibrary(str(dll_path))

# Setup function signatures
lib.ld3s_open.argtypes = []
lib.ld3s_open.restype = c_void_p

lib.ld3s_new_job.argtypes = [c_void_p]
lib.ld3s_new_job.restype = c_char_p

lib.ld3s_free.argtypes = [c_void_p, c_void_p]
lib.ld3s_free.restype = None

lib.ld3s_close.argtypes = [c_void_p]
lib.ld3s_close.restype = None

# Initialize
print("Initializing DLL...")
ctx = lib.ld3s_open()
if not ctx:
    print("Failed to open context")
    sys.exit(1)

# Fetch template
print("Fetching inventory template...\n")
template_ptr = lib.ld3s_new_job(ctx)
template_json = template_ptr.decode('utf-8')
template = json.loads(template_json)
lib.ld3s_free(ctx, template_ptr)

# Display inventory
print("=" * 80)
print("CURRENT BLOCKCHAIN INVENTORY")
print("=" * 80)

wallets = template.get("inventoryParameters", {}).get("wallets", [])
for wallet_idx, wallet in enumerate(wallets):
    pubkey = wallet.get("publicKey", "unknown")
    print(f"\nWallet {wallet_idx}: {pubkey}")
    print("-" * 80)

    for acc_idx, account in enumerate(wallet.get("accounts", [])):
        mintid = account.get("mintId", "unknown")
        balance = account.get("estimatedBalance", 0)

        # Extract metadata
        metadata = account.get("metadata", {}).get("metadata", {})
        uom = metadata.get("uom", "unknown")

        token_desc = metadata.get("tokenDescription", {})
        project_data = token_desc.get("projectData", {})

        name = project_data.get("Consumable Name", "Unknown")
        color = project_data.get("Color", "N/A")
        media_type = project_data.get("Media Type", "N/A")

        print(f"  Account {acc_idx}:")
        print(f"    Name: {name}")
        print(f"    Type: {uom}")
        if color != "N/A":
            print(f"    Color: {color}")
        if media_type != "N/A":
            print(f"    Media Type: {media_type}")
        print(f"    Balance: {balance}")
        print(f"    MintID: {mintid}")
        print()

# Cleanup
print("=" * 80)
lib.ld3s_close(ctx)
print("\nDone!")
