"""
Diagnostic script to check if templates contain jobParameters.

This will help us understand if duplicate job IDs are being sent.
"""

import json
from ctypes import cdll, c_void_p, c_char_p
import os
from pathlib import Path

# Load DLL
dll_path = Path("../CCAPIv2.0.0.2/ConsumableClient.dll").resolve()
print(f"Loading DLL: {dll_path}")
print(f"DLL exists: {dll_path.exists()}")

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
print("\nInitializing DLL context...")
ctx = lib.ld3s_open()
print(f"Context: {ctx}")

# Fetch 3 templates and check for jobParameters
for i in range(1, 4):
    print(f"\n{'='*80}")
    print(f"TEMPLATE {i}")
    print(f"{'='*80}")

    template_ptr = lib.ld3s_new_job(ctx)
    template_json = template_ptr.decode('utf-8')
    template = json.loads(template_json)
    lib.ld3s_free(ctx, template_ptr)

    # Check for jobParameters
    if 'jobParameters' in template:
        print("[OK] Template contains 'jobParameters' field:")
        print(f"  jobParameters: {json.dumps(template['jobParameters'], indent=2)}")

        if 'jobID' in template['jobParameters']:
            print(f"\n[WARNING] DUPLICATE JOB ID RISK!")
            print(f"  Job ID: {template['jobParameters']['jobID']}")
    else:
        print("[NO] Template does NOT contain 'jobParameters' field")

    # Show top-level keys
    print(f"\nTop-level keys in template:")
    for key in template.keys():
        print(f"  - {key}")

    # Wait a moment between fetches
    import time
    time.sleep(0.5)

# Cleanup
print(f"\n{'='*80}")
print("Cleaning up...")
lib.ld3s_close(ctx)
print("[OK] Done")
