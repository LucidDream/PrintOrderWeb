# Ink Mapping Analysis - Print Order Web to Blockchain Consumables

**Date:** November 11, 2025
**Status:** Active Investigation
**API Version:** ConsumableClient v2.0.0.1

---

## Executive Summary

The Print Order Web application needs to correctly map 8 ink slots in the printer configuration to consumables loaded in the SmartSupplySystem blockchain. This document analyzes the current state and provides recommendations for proper mapping.

---

## Current Blockchain Inventory

**Inks loaded (8 total):**

| Token Name    | Color Field Value | Balance (mL) | Status |
|---------------|-------------------|--------------|--------|
| CyanIB        | `"CYAN"`         | 5,998.24     | ✅ Active |
| MagentaIB     | `"MAGENTA"`      | 5,999.87     | ✅ Active |
| YellowIB      | `"YELLOW"`       | 5,999.47     | ✅ Active |
| BlackIB       | `"BLACK"`        | 5,999.74     | ✅ Active |
| LightCyan     | `"lt-cyan"`      | 10.00        | ✅ Active |
| LightMage*    | `"lt-magenta"`   | 10.00        | ✅ Active |
| Orange        | `"orange"`       | 10.00        | ✅ Active |
| PhotoBlac*    | `"photo-blk"`    | 10.00        | ✅ Active |

**Media loaded (2 total):**
- ProMHSA4 (ProMatte A4) - 70 sheets
- ProGHSLeg (ProGloss Legal) - 61 sheets

*Note: Token names truncated in display

---

## Current Printer Configuration

**Model:** Epson SureColor P8000
**Ink Set:** 8-Color UltraChrome HDX Ink Set

**Configured Slots (from `printer_config.py`):**

| Slot | Color Name      | Account ID       | Verified By Default |
|------|-----------------|------------------|---------------------|
| 1    | cyan            | `"cyan"`         | ❌ False            |
| 2    | magenta         | `"magenta"`      | ❌ False            |
| 3    | yellow          | `"yellow"`       | ❌ False            |
| 4    | black           | `"black"`        | ❌ False            |
| 5    | light_cyan      | `"light_cyan"`   | ❌ False            |
| 6    | light_magenta   | `"light_magenta"`| ❌ False            |
| 7    | light_black     | `"light_black"`  | ❌ False            |
| 8    | orange          | `"orange"`       | ❌ False            |

---

## Current Mapping Logic

**Location:** `print_order_web/modules/inventory.py` (lines 308-320)

```python
def _parse_real_api_account(self, ...):
    if type_indicator == "toner":
        # Extract color from blockchain
        color = project_data.get("Color", "").lower()  # ← Converts to lowercase

        return {
            "id": color,  # Used as the account ID for matching
            "type": "toner",
            "display_name": display_name,
            "balance": balance,
            "uom": uom,
            "color": color
        }
```

**How it works:**
1. Fetches blockchain template via `api_client.new_job_template()`
2. Extracts `Color` field from `projectData`
3. Converts to **lowercase** (e.g., "CYAN" → "cyan", "lt-cyan" → "lt-cyan")
4. Uses this as the `id` for matching against printer slots

---

## The Mapping Problem

**Issue:** Inconsistent naming conventions between blockchain and printer config

### Naming Convention Conflicts

| Blockchain Color | After `.lower()` | Printer Slot ID | Match? |
|------------------|------------------|-----------------|--------|
| `"CYAN"`         | `"cyan"`         | `"cyan"`        | ✅ YES |
| `"MAGENTA"`      | `"magenta"`      | `"magenta"`     | ✅ YES |
| `"YELLOW"`       | `"yellow"`       | `"yellow"`      | ✅ YES |
| `"BLACK"`        | `"black"`        | `"black"`       | ✅ YES |
| `"lt-cyan"`      | `"lt-cyan"`      | `"light_cyan"`  | ❌ NO  |
| `"lt-magenta"`   | `"lt-magenta"`   | `"light_magenta"` | ❌ NO  |
| `"orange"`       | `"orange"`       | `"orange"`      | ✅ YES |
| `"photo-blk"`    | `"photo-blk"`    | `"light_black"` | ❌ NO  |

**Result:**
- **5 inks match correctly** (CMYK + Orange)
- **3 inks fail to match** (Light Cyan, Light Magenta, Photo Black)

---

## Root Cause Analysis

### The Naming Convention Mismatch

**Blockchain (from INK_COLORS construct):**
```javascript
{ fullname: "Light Cyan", abbreviation: "lt-cyan" }      // Hyphen separator
{ fullname: "Light Magenta", abbreviation: "lt-magenta" } // Hyphen separator
{ fullname: "Photo Black", abbreviation: "photo-blk" }    // Hyphen separator
```

**Printer Config (Python):**
```python
color_name="light_cyan"    # Underscore separator
color_name="light_magenta" # Underscore separator
color_name="light_black"   # Underscore separator, different name!
```

**Why this matters:**
- The `Color` field from blockchain is the source of truth
- The printer config's `account_id` must match the normalized color value
- Currently: `"lt-cyan"` ≠ `"light_cyan"` (string mismatch)

---

## Recommended Solution

### Strategy: Normalize Both Sides with Mapping Layer

**Approach:** Create a bidirectional mapping function that handles:
1. Hyphen ↔ Underscore conversion (`lt-cyan` ↔ `lt_cyan`)
2. Abbreviation expansion (`lt` → `light`)
3. Color name variations (`photo-blk` → `photo_black`)

### Implementation Plan

#### Option 1: Update Printer Config (Simple, Recommended)

**Change printer slot `account_id` values to match blockchain after normalization:**

```python
# In printer_config.py
InkSlot(slot_number=5, color_name="light_cyan",
        account_id="lt-cyan",  # ← Changed from "light_cyan"
        ...)
InkSlot(slot_number=6, color_name="light_magenta",
        account_id="lt-magenta",  # ← Changed from "light_magenta"
        ...)
InkSlot(slot_number=7, color_name="light_black",
        account_id="photo-blk",  # ← Changed from "light_black"
        ...)
```

**Pros:**
- ✅ Simple, minimal code changes
- ✅ Uses blockchain naming as source of truth
- ✅ No normalization logic needed
- ✅ Printer config automatically matches API data

**Cons:**
- ❌ Requires updating printer config whenever blockchain naming changes
- ❌ Less flexible for multiple printers with different naming

---

#### Option 2: Add Normalization Function (Robust, Future-Proof)

**Create a mapping layer that handles variations:**

```python
# In inventory.py or new mapping.py module

TONER_COLOR_ALIASES = {
    # Blockchain color → Printer account_id mappings
    "cyan": ["cyan"],
    "magenta": ["magenta"],
    "yellow": ["yellow"],
    "black": ["black"],
    "lt-cyan": ["light_cyan", "lt_cyan", "lightcyan"],
    "lt-magenta": ["light_magenta", "lt_magenta", "lightmagenta"],
    "orange": ["orange"],
    "photo-blk": ["photo_black", "photo-black", "photoblack", "light_black"],
    "green": ["green"],
    "violet": ["violet"],
    "red": ["red"],
    "blue": ["blue"],
    "gray": ["gray", "grey"],
    "lt-gray": ["light_gray", "lt_gray", "light_grey"],
    "matte-blk": ["matte_black", "matteblack"],
    "ltlt-black": ["light_light_black", "ltlt_black"],
    "white": ["white"],
}

def normalize_color_id(color: str) -> str:
    """
    Normalize a color identifier from blockchain to match printer config.

    Args:
        color: Color string from blockchain (e.g., "CYAN", "lt-cyan")

    Returns:
        Normalized color ID for matching
    """
    # Convert to lowercase first
    color_lower = color.lower()

    # Direct match - return as-is
    if color_lower in TONER_COLOR_ALIASES:
        return color_lower

    # Check if it's a known alias
    for canonical, aliases in TONER_COLOR_ALIASES.items():
        if color_lower in aliases:
            return canonical

    # Unknown color - return lowercase version
    return color_lower

def matches_printer_slot(blockchain_color: str, printer_account_id: str) -> bool:
    """
    Check if blockchain color matches a printer slot account ID.

    Args:
        blockchain_color: Color from blockchain API (e.g., "lt-cyan")
        printer_account_id: Account ID from printer config (e.g., "light_cyan")

    Returns:
        True if they represent the same color
    """
    normalized_color = normalize_color_id(blockchain_color)

    # Direct match
    if normalized_color == printer_account_id:
        return True

    # Check aliases
    if normalized_color in TONER_COLOR_ALIASES:
        return printer_account_id in TONER_COLOR_ALIASES[normalized_color]

    return False
```

**Update inventory parsing:**

```python
def _parse_real_api_account(self, ...):
    if type_indicator == "toner":
        color = project_data.get("Color", "").lower()
        normalized_id = normalize_color_id(color)  # ← Add normalization

        return {
            "id": normalized_id,  # Use normalized ID
            "type": "toner",
            "display_name": display_name,
            "balance": balance,
            "uom": uom,
            "color": color  # Keep original for display
        }
```

**Update printer verification:**

```python
def update_slot_verification(self, inventory_accounts: Dict[str, Any]) -> PrinterConfig:
    for slot in config.slots:
        if slot.account_id:
            # Try direct match first
            if slot.account_id in inventory_accounts:
                slot.verified = True
                ...
            else:
                # Try fuzzy match with normalization
                for inv_id in inventory_accounts.keys():
                    if matches_printer_slot(inv_id, slot.account_id):
                        slot.verified = True
                        account = inventory_accounts[inv_id]
                        ...
                        break
```

**Pros:**
- ✅ Future-proof for new ink colors
- ✅ Handles multiple naming conventions
- ✅ Easy to extend with new aliases
- ✅ Works with any printer configuration
- ✅ Centralized mapping logic

**Cons:**
- ❌ More code to maintain
- ❌ Requires testing for all color variations
- ❌ Slight performance overhead (negligible)

---

## Recommended Implementation: Hybrid Approach

**Best Practice:**

1. **Short-term (Immediate):** Update printer config to match blockchain naming exactly
   - Change `account_id` values in `printer_config.py` to use blockchain format
   - Slots 5, 6, 7 updated to `"lt-cyan"`, `"lt-magenta"`, `"photo-blk"`

2. **Long-term (Future):** Add normalization layer for robustness
   - Implement `TONER_COLOR_ALIASES` mapping dictionary
   - Add `normalize_color_id()` and `matches_printer_slot()` functions
   - Update slot verification to use fuzzy matching
   - Support future ink additions without config changes

---

## Verification Strategy

### After Implementation, Test:

**1. Inventory Fetch Test:**
```bash
cd print_order_web
python fetch_template.py > template.json
python -c "
from modules.inventory import InventoryService
from modules.api_client import ConsumableClientAPI
from config import Config

api = ConsumableClientAPI(Config.CONSUMABLE_DLL_PATH)
inv = InventoryService(api)
snapshot = inv.get_inventory_snapshot(force_refresh=True)

print('Toner Balances Found:')
for color, data in snapshot['toner_balances'].items():
    print(f'  {color}: {data[\"available\"]} mL')
"
```

**Expected Output:**
```
Toner Balances Found:
  cyan: 5998.24 mL
  magenta: 5999.87 mL
  yellow: 5999.47 mL
  black: 5999.74 mL
  lt-cyan: 10.0 mL          ← Must appear
  lt-magenta: 10.0 mL       ← Must appear
  orange: 10.0 mL
  photo-blk: 10.0 mL        ← Must appear
```

**2. Printer Slot Verification Test:**
```python
from modules.printer_config import update_printer_from_inventory

printer = update_printer_from_inventory(snapshot['toner_balances'])
print(f"Verified slots: {printer['verified_count']}/8")

for slot in printer['slots']:
    status = '✅' if slot['verified'] else '❌'
    print(f"{status} Slot {slot['slot_number']}: {slot['color_name']}")
```

**Expected Output:**
```
Verified slots: 8/8
✅ Slot 1: cyan
✅ Slot 2: magenta
✅ Slot 3: yellow
✅ Slot 4: black
✅ Slot 5: light_cyan
✅ Slot 6: light_magenta
✅ Slot 7: light_black (mapped to photo-blk)
✅ Slot 8: orange
```

**3. Job Submission Test:**
- Submit a full-color print job
- Verify all 8 inks are correctly matched in job payload
- Check confirmation page shows correct ink consumption
- Verify blockchain transaction includes all consumed inks

---

## Critical Files to Modify

| File | Changes Required | Priority |
|------|-----------------|----------|
| `print_order_web/modules/printer_config.py` | Update slot `account_id` values | 🔴 High |
| `print_order_web/modules/inventory.py` | Add normalization logic (optional) | 🟡 Medium |
| `print_order_web/modules/job_processor.py` | Verify account matching logic | 🟡 Medium |
| `print_order_web/tests/test_inventory.py` | Add color mapping tests | 🟢 Low |

---

## Additional Considerations

### 1. Color Profile Definitions

**Current toner profiles:**
```python
toner_profiles = {
    "full_color": ["cyan", "magenta", "yellow", "black"],
    "mono": ["black"],
}
```

**Should be updated to:**
```python
toner_profiles = {
    "full_color": ["cyan", "magenta", "yellow", "black"],
    "mono": ["black"],
    "enhanced_color": ["cyan", "magenta", "yellow", "black", "lt-cyan", "lt-magenta"],
    "photo": ["cyan", "magenta", "yellow", "black", "lt-cyan", "lt-magenta", "photo-blk"],
    "extended": ["cyan", "magenta", "yellow", "black", "lt-cyan", "lt-magenta", "orange", "photo-blk"],
}
```

### 2. Estimator Updates

The `JobEstimator` currently only calculates for CMYK. Extended color sets require:
- Coverage models for light inks (typically 20-40% of standard)
- Profile-aware estimation based on selected color mode
- Quality multipliers for draft/standard/high

### 3. User Interface

The web UI should:
- Display all 8 verified inks in the demo/details pages
- Show which inks will be used for each color mode
- Indicate when extended gamut colors are available
- Warn when light inks are low (quality degradation)

---

## Summary & Next Steps

### Current State
- ✅ 8 inks loaded in blockchain
- ✅ 5/8 inks mapping correctly (CMYK + Orange)
- ❌ 3/8 inks failing to match (Light Cyan, Light Magenta, Photo Black)

### Root Cause
- Naming convention mismatch: hyphens vs underscores
- Missing normalization layer

### Immediate Action
**Update `printer_config.py` slot 5-7 `account_id` values:**
```python
InkSlot(slot_number=5, account_id="lt-cyan", ...)
InkSlot(slot_number=6, account_id="lt-magenta", ...)
InkSlot(slot_number=7, account_id="photo-blk", ...)
```

### Future Enhancements
- Implement normalization mapping layer
- Add extended color profiles
- Update estimator for light ink coverage
- Enhance UI to show all available inks

---

**Document Version:** 1.0
**Last Updated:** November 11, 2025
**Status:** Ready for implementation
