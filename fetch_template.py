"""Fetch current job template from ConsumableClient API."""

import json
import sys
from pathlib import Path
from ctypes import cdll, c_void_p

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from modules.api_client_threaded import ThreadSafeAPIClient
from config import Config

def main():
    """Fetch and display job template."""
    print("Connecting to ConsumableClient API...", file=sys.stderr)
    print(f"DLL Path: {Config.CONSUMABLE_DLL_PATH}", file=sys.stderr)

    dll_path = Config.CONSUMABLE_DLL_PATH
    context_handle = None
    lib = None

    try:
        # Initialize DLL context (main thread)
        print("Initializing DLL context...", file=sys.stderr)
        lib = cdll.LoadLibrary(dll_path)
        lib.ld3s_open.argtypes = []
        lib.ld3s_open.restype = c_void_p
        context_handle = lib.ld3s_open()

        if not context_handle:
            print("ERROR: Failed to initialize DLL context", file=sys.stderr)
            sys.exit(1)

        print(f"DLL context initialized: {context_handle}", file=sys.stderr)

        # Create threaded API client using shared library handle
        api = ThreadSafeAPIClient(context_handle, lib)

        print("Fetching job template...", file=sys.stderr)
        template = api.new_job_template()

        if not template:
            print("ERROR: Failed to fetch template", file=sys.stderr)
            sys.exit(1)

        print("SUCCESS: Template fetched", file=sys.stderr)
        print(f"Found {len(template.get('inventoryParameters', {}).get('wallets', []))} wallets", file=sys.stderr)
        print()  # Blank line separator

        # Output JSON to stdout
        print(json.dumps(template, indent=2))

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    finally:
        # Cleanup DLL context (main thread)
        if context_handle and lib is not None:
            print("Cleaning up DLL context...", file=sys.stderr)
            lib.ld3s_close.argtypes = [c_void_p]
            lib.ld3s_close.restype = None
            lib.ld3s_close(c_void_p(context_handle))

if __name__ == "__main__":
    main()
