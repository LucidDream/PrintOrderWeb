"""Test that job payload building preserves metadata and sets expenditures correctly."""

import json
import sys
sys.path.insert(0, '.')

from modules.job_processor import JobProcessor
from modules.api_client import ConsumableClientAPIStub

# Create a simulated template with the new complex metadata structure
simulated_template = {
    "inventoryParameters": {
        "wallets": [
            {
                "name": "Toner Wallet",
                "accounts": [
                    {
                        "estimatedBalance": 6000.0,
                        "mintId": "61dVMLbtRCncpBAF5khSxrXdfzToC9Sj6xMbR1ZqnAcu",
                        "metadata": {
                            "balance": 6000,
                            "currency": "$",
                            "metadata": {
                                "tokenDescription": {
                                    "projectData": {
                                        "Color": "CYAN",
                                        "Consumable Name": "Inka Cyan Ink Bottle",
                                        "Unit of Measure for Spending": "mL"
                                    }
                                },
                                "tokenName": "CyanIB",
                                "uom": "Toner"
                            }
                        }
                    },
                    {
                        "estimatedBalance": 6000.0,
                        "mintId": "GJfidm8zqYWHiWDoCrtYKxfdxgufXVqsCDrm7bjTux31",
                        "metadata": {
                            "balance": 6000,
                            "metadata": {
                                "tokenDescription": {
                                    "projectData": {
                                        "Color": "BLACK",
                                        "Consumable Name": "INKA Black Ink Bottle"
                                    }
                                },
                                "tokenName": "BlackIB",
                                "uom": "Toner"
                            }
                        }
                    }
                ]
            },
            {
                "name": "Media Wallet",
                "accounts": [
                    {
                        "estimatedBalance": 100.0,
                        "mintId": "GuqV4c1dAid3LxxVyYVkcvTbQSXd4U6QH6kij7dCXppw",
                        "metadata": {
                            "balance": 100,
                            "metadata": {
                                "tokenDescription": {
                                    "projectData": {
                                        "Consumable Name": "Paper Mills ProGloss Legal"
                                    }
                                },
                                "tokenName": "ProGHSLeg",
                                "uom": "Media"
                            }
                        }
                    }
                ]
            }
        ]
    }
}

# Create simulated order
simulated_order = {
    "job_name": "Test Job",
    "analysis": {"pages": 2},
    "choices": {
        "quantity": 3,
        "color_mode": "full_color",
        "media_type": "GuqV4c1dAid3LxxVyYVkcvTbQSXd4U6QH6kij7dCXppw",
        "turnaround_time": "standard",
        "notes": "Test"
    },
    "estimate": {
        "toner_usage": {"cyan": 0.11, "black": 0.14},
        "sheets_required": 6
    }
}

print("=" * 70)
print("JOB PAYLOAD BUILDING TEST")
print("=" * 70)

# Create job processor
api_client = ConsumableClientAPIStub()
processor = JobProcessor(api_client)

# Build payload
print("\n### Building job payload...")
payload = processor._build_job_payload(simulated_template, simulated_order)

print("\n### Checking payload structure...")
print(f"Has inventoryParameters: {('inventoryParameters' in payload)}")
print(f"Has jobMetadata: {('jobMetadata' in payload)}")

print("\n### Checking expenditures set...")
expenditure_summary = []
for wallet in payload.get("inventoryParameters", {}).get("wallets", []):
    for account in wallet.get("accounts", []):
        exp = account.get("currentExpenditure", -1)
        metadata = account.get("metadata", {})
        nested = metadata.get("metadata", {})
        name = nested.get("tokenName", "Unknown")

        expenditure_summary.append({
            "name": name,
            "expenditure": exp,
            "type": type(exp).__name__
        })

print(f"\nTotal accounts: {len(expenditure_summary)}")
for item in expenditure_summary:
    status = "[OK]" if item["expenditure"] > 0 else "[ZERO]" if item["expenditure"] == 0 else "[?]"
    print(f"  {status} {item['name']}: {item['expenditure']} (type: {item['type']})")

# Verify expected expenditures
print("\n### Verification...")
cyan_found = False
black_found = False
media_found = False

for wallet in payload.get("inventoryParameters", {}).get("wallets", []):
    for account in wallet.get("accounts", []):
        exp = account.get("currentExpenditure", 0)
        metadata = account.get("metadata", {})
        nested = metadata.get("metadata", {})
        name = nested.get("tokenName", "Unknown")

        if name == "CyanIB" and exp == 0.11:
            cyan_found = True
            print(f"[OK] Cyan expenditure set correctly: {exp}")
        elif name == "BlackIB" and exp == 0.14:
            black_found = True
            print(f"[OK] Black expenditure set correctly: {exp}")
        elif name == "ProGHSLeg" and exp == 6:
            media_found = True
            print(f"[OK] Media expenditure set correctly: {exp}")

if not cyan_found:
    print("[FAIL] Cyan expenditure NOT set correctly")
if not black_found:
    print("[FAIL] Black expenditure NOT set correctly")
if not media_found:
    print("[FAIL] Media expenditure NOT set correctly")

# Check metadata preservation
print("\n### Checking metadata preservation...")
for wallet in payload.get("inventoryParameters", {}).get("wallets", []):
    for account in wallet.get("accounts", []):
        metadata = account.get("metadata", {})
        nested = metadata.get("metadata", {})
        token_desc = nested.get("tokenDescription", {})
        project_data = token_desc.get("projectData", {})

        if nested:
            print(f"[OK] Account has nested metadata preserved")
            if token_desc:
                print(f"  [OK] Has tokenDescription")
            if project_data:
                print(f"  [OK] Has projectData")
            break

print("\n### Final Check: Can this payload be JSON serialized?")
try:
    json_str = json.dumps(payload, indent=2)
    print(f"[OK] Payload is valid JSON ({len(json_str)} characters)")

    # Check for any non-serializable types
    print("\n### Sample of payload (first 500 chars):")
    print(json_str[:500] + "...")

except Exception as e:
    print(f"[FAIL] Payload cannot be serialized: {e}")

print("\n" + "=" * 70)
