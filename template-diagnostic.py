"""
Template Diagnostic Script
==========================

This standalone script tests the ConsumableClient DLL to capture the complete
raw JSON template returned by ld3s_new_job(). The output is a human-readable,
pretty-printed JSON file that can be searched for any field or value.

Usage:
    1. Ensure the DLL path is correct in your .env file
    2. Run from the project directory:

       python template-diagnostic.py

    3. Check the output file: template-diagnostic-output.json

What this script does:
    - Loads the ConsumableClient DLL
    - Calls ld3s_open() to initialize context
    - Calls ld3s_new_job() to fetch the current template
    - Saves the complete raw JSON response to template-diagnostic-output.json
    - Pretty-prints with indentation for human readability
    - Properly cleans up with ld3s_close()

Output:
    template-diagnostic-output.json
        Complete API response, pretty-printed with 2-space indentation.
        Open in any text editor and search for fields of interest.

Author: Diagnostic tool for PrintOrderWeb
Date: December 2025
"""

import json
import os
import sys
from ctypes import CDLL, c_void_p, c_char_p
from pathlib import Path
from datetime import datetime

# Try to load .env for DLL path
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    print("Note: python-dotenv not installed, using environment variables directly")


def get_dll_path() -> Path:
    """Get DLL path from environment or default location."""
    dll_path_str = os.environ.get("CONSUMABLE_DLL_PATH")

    if dll_path_str:
        return Path(dll_path_str)

    # Default path relative to project
    return Path("../CCAPIv2.0.0.2/ConsumableClient.dll")


def setup_dll_functions(lib):
    """Configure DLL function signatures."""
    lib.ld3s_open.argtypes = []
    lib.ld3s_open.restype = c_void_p

    lib.ld3s_close.argtypes = [c_void_p]
    lib.ld3s_close.restype = None

    lib.ld3s_new_job.argtypes = [c_void_p]
    lib.ld3s_new_job.restype = c_char_p

    lib.ld3s_free.argtypes = [c_void_p, c_void_p]
    lib.ld3s_free.restype = None

    lib.ld3s_get_last_error.argtypes = [c_void_p]
    lib.ld3s_get_last_error.restype = c_char_p


def main():
    output_file = Path("template-diagnostic-output.json")

    print("=" * 60)
    print("TEMPLATE DIAGNOSTIC")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    # Get DLL path
    dll_path = get_dll_path()
    print(f"DLL path: {dll_path}")

    if not dll_path.exists():
        print(f"ERROR: DLL not found at {dll_path.absolute()}")
        sys.exit(1)

    # Load DLL
    print("Loading DLL...")
    try:
        lib = CDLL(str(dll_path.absolute()))
        setup_dll_functions(lib)
    except Exception as e:
        print(f"ERROR: Failed to load DLL: {e}")
        sys.exit(1)

    # Initialize context
    print("Initializing context...")
    context = lib.ld3s_open()

    if not context:
        print("ERROR: ld3s_open() returned NULL")
        sys.exit(1)

    try:
        # Fetch template
        print("Fetching template from blockchain...")
        result_ptr = lib.ld3s_new_job(c_void_p(context))

        if not result_ptr:
            error_ptr = lib.ld3s_get_last_error(c_void_p(context))
            if error_ptr:
                error = error_ptr.decode('utf-8')
                lib.ld3s_free(c_void_p(context), error_ptr)
                print(f"ERROR: {error}")
            else:
                print("ERROR: ld3s_new_job returned NULL")
            sys.exit(1)

        # Parse and save
        json_str = result_ptr.decode('utf-8')
        template = json.loads(json_str)
        lib.ld3s_free(c_void_p(context), result_ptr)

        # Write pretty-printed output
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(template, f, indent=2, ensure_ascii=False)

        # Calculate file size
        file_size = output_file.stat().st_size
        if file_size > 1024:
            size_str = f"{file_size / 1024:.1f} KB"
        else:
            size_str = f"{file_size} bytes"

        print()
        print("SUCCESS")
        print("-" * 60)
        print(f"Output file: {output_file.absolute()}")
        print(f"File size:   {size_str}")
        print()
        print("Open the output file in a text editor to search for")
        print("any field or value in the template structure.")
        print("=" * 60)

    finally:
        print()
        print("Cleaning up...")
        lib.ld3s_close(c_void_p(context))
        print("Done.")


if __name__ == "__main__":
    main()
