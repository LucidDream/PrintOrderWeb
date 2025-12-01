"""Test account identification with new complex metadata."""

import json

# Sample account from the actual blockchain response
cyan_account = {
    "actualExpenditure": 0.0,
    "balance": 6000.0,
    "metadata": {
        "balance": 6000,
        "currency": "$",
        "dateOfPurchase": "10/29/2025 - 11/04/2025",
        "metadata": {
            "tokenDescription": {
                "projectData": {
                    "Advisory, not a waveform": "Tested on common 600dpi piezo",
                    "Chemistry Base": "Aqueous pigment",
                    "Color": "CYAN",
                    "Conductivity (µS/cm)": "450",
                    "Consumable Description": "Cyan Ink Bottle",
                    "Consumable Name": "Inka Cyan Ink Bottle",
                    "Unit of Measure for Spending": "mL"
                }
            },
            "tokenName": "CyanIB",
            "tokenSymbol": "CyanIB",
            "uom": "Toner"
        },
        "mintAddress": "61dVMLbtRCncpBAF5khSxrXdfzToC9Sj6xMbR1ZqnAcu",
        "name": "CyanIB"
    },
    "mintId": "61dVMLbtRCncpBAF5khSxrXdfzToC9Sj6xMbR1ZqnAcu"
}

media_account = {
    "actualExpenditure": 0.0,
    "balance": 100.0,
    "metadata": {
        "balance": 100,
        "currency": "$",
        "metadata": {
            "tokenDescription": {
                "projectData": {
                    "Consumable Name": "Paper Mills ProGloss Legal",
                    "Media Type": "GLOSSY",
                    "Unit of Measure": "inches"
                }
            },
            "tokenName": "ProGHSLeg",
            "uom": "Media"
        },
        "mintAddress": "GuqV4c1dAid3LxxVyYVkcvTbQSXd4U6QH6kij7dCXppw"
    },
    "mintId": "GuqV4c1dAid3LxxVyYVkcvTbQSXd4U6QH6kij7dCXppw"
}

def identify_account(account):
    """Same logic as job_processor.py"""
    metadata = account.get("metadata", {})
    nested_metadata = metadata.get("metadata", {})

    print(f"\n=== Analyzing Account ===")
    print(f"Has metadata: {bool(metadata)}")
    print(f"Has nested_metadata: {bool(nested_metadata)}")

    if nested_metadata:
        # Real API structure
        type_indicator = nested_metadata.get("uom", "").lower()
        print(f"UOM: '{nested_metadata.get('uom')}' -> '{type_indicator}'")

        token_desc = nested_metadata.get("tokenDescription", {})
        project_data = token_desc.get("projectData", {})

        print(f"Has tokenDescription: {bool(token_desc)}")
        print(f"Has projectData: {bool(project_data)}")

        if type_indicator == "toner":
            color = project_data.get("Color", "").lower()
            print(f"Color field: '{project_data.get('Color')}' -> '{color}'")
            return {"type": "toner", "id": color}
        elif type_indicator == "media":
            mint_id = account.get("mintId", "")
            print(f"MintId: {mint_id}")
            return {"type": "media", "id": mint_id}
        else:
            return {"type": "unknown", "id": account.get("mintId", "")}
    else:
        # Stub structure
        uom = metadata.get("uom", "")
        if uom == "sheets":
            return {"type": "media", "id": account.get("accountId", "")}
        else:
            return {"type": "toner", "id": account.get("accountId", "")}

print("=" * 70)
print("ACCOUNT IDENTIFICATION TEST")
print("=" * 70)

print("\n\n### TEST 1: Cyan Toner Account")
cyan_result = identify_account(cyan_account)
print(f"\nRESULT: {cyan_result}")
print(f"Expected: {{'type': 'toner', 'id': 'cyan'}}")
print(f"Match: {cyan_result == {'type': 'toner', 'id': 'cyan'}}")

print("\n\n### TEST 2: Media Account")
media_result = identify_account(media_account)
print(f"\nRESULT: {media_result}")
expected_media = {'type': 'media', 'id': 'GuqV4c1dAid3LxxVyYVkcvTbQSXd4U6QH6kij7dCXppw'}
print(f"Expected: {expected_media}")
print(f"Match: {media_result == expected_media}")

print("\n\n### TEST 3: Check if accounts would match estimate")
print("\nSimulated estimate:")
estimate = {
    "toner_usage": {"cyan": 0.11, "magenta": 0.11, "yellow": 0.11, "black": 0.14},
    "sheets_required": 6
}
print(json.dumps(estimate, indent=2))

print("\nWould cyan account match?")
if cyan_result["type"] == "toner" and cyan_result["id"] in estimate["toner_usage"]:
    print(f"  YES - Would set currentExpenditure = {estimate['toner_usage'][cyan_result['id']]}")
else:
    print(f"  NO - Cyan account would not match")

print("\nWould media account match?")
media_type_from_order = "GuqV4c1dAid3LxxVyYVkcvTbQSXd4U6QH6kij7dCXppw"  # This comes from user selection
if media_result["type"] == "media" and media_result["id"] == media_type_from_order:
    print(f"  YES - Would set currentExpenditure = {estimate['sheets_required']}")
else:
    print(f"  NO - Media account would not match")
    print(f"  Account mintId: {media_result['id']}")
    print(f"  Order media_type: {media_type_from_order}")

print("\n" + "=" * 70)
