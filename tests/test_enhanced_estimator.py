"""Test script for enhanced estimator functionality."""

from modules.estimator import JobEstimator
from modules.inventory import InventoryService
from modules.api_client import ConsumableClientAPIStub

# Create stub API client and inventory service
api_client = ConsumableClientAPIStub()
inventory_service = InventoryService(api_client)
estimator = JobEstimator(inventory_service)

# Get inventory snapshot
inventory = inventory_service.get_inventory_snapshot()

# Test order with 100 pages, 2 copies
test_order_base = {
    "analysis": {
        "pages": 5,
        "color_pages": 5,
        "bw_pages": 0,
    },
    "choices": {
        "quantity": 2,
        "color_mode": "full_color",
        "media_type": list(inventory["media_options"].keys())[0],
        "turnaround_time": "standard",
    }
}

print("=" * 70)
print("ENHANCED ESTIMATOR TEST - Quality Settings Impact")
print("=" * 70)
print(f"\nTest scenario: {test_order_base['analysis']['pages']} pages × {test_order_base['choices']['quantity']} copies = 10 sheets")
print(f"Color mode: {test_order_base['choices']['color_mode']}")
print()

# Test each quality setting
for quality in ["draft", "standard", "high"]:
    test_order = test_order_base.copy()
    test_order["choices"] = test_order_base["choices"].copy()
    test_order["choices"]["quality"] = quality

    estimate = estimator.estimate(test_order, inventory)

    print(f"\n{'='*70}")
    print(f"Quality: {quality.upper()}")
    print(f"{'='*70}")
    print(f"Quality Modifier: {estimate['quality_modifier']:.0%}")
    print(f"Sheets Required: {estimate['sheets_required']}")
    print(f"\nToner Usage:")
    for color, amount in estimate['toner_usage'].items():
        print(f"  {color.title():8s}: {amount:6.2f} mL")
    print(f"\nEstimated Cost: ${estimate['estimated_cost']:.2f}")
    print(f"\nReasoning:")
    print(f"  {estimate['reasoning']}")

print("\n" + "=" * 70)
print("COMPARISON: Mono vs Full Color (Standard Quality)")
print("=" * 70)

# Test mono mode
mono_order = test_order_base.copy()
mono_order["choices"] = test_order_base["choices"].copy()
mono_order["choices"]["color_mode"] = "mono"
mono_order["choices"]["quality"] = "standard"

mono_estimate = estimator.estimate(mono_order, inventory)

# Test full color mode
color_order = test_order_base.copy()
color_order["choices"] = test_order_base["choices"].copy()
color_order["choices"]["color_mode"] = "full_color"
color_order["choices"]["quality"] = "standard"

color_estimate = estimator.estimate(color_order, inventory)

print(f"\nMono Mode:")
print(f"  Toner usage: {mono_estimate['toner_usage']}")
print(f"  Total toner: {sum(mono_estimate['toner_usage'].values()):.2f} mL")

print(f"\nFull Color Mode:")
print(f"  Toner usage: {color_estimate['toner_usage']}")
print(f"  Total toner: {sum(color_estimate['toner_usage'].values()):.2f} mL")
print(f"  (Note: Black gets 1.3x usage for text and shadows)")

print("\n" + "=" * 70)
print("VERIFICATION: Quality Modifiers")
print("=" * 70)

# Verify quality modifiers are applied correctly
draft_total = sum(mono_estimate['toner_usage'].values()) if mono_order["choices"]["quality"] == "draft" else 0
standard_total = sum(mono_estimate['toner_usage'].values())

# Re-calculate with draft
mono_order["choices"]["quality"] = "draft"
draft_estimate = estimator.estimate(mono_order, inventory)
draft_total = sum(draft_estimate['toner_usage'].values())

# Re-calculate with high
mono_order["choices"]["quality"] = "high"
high_estimate = estimator.estimate(mono_order, inventory)
high_total = sum(high_estimate['toner_usage'].values())

print(f"\nDraft quality total:    {draft_total:.2f} mL (should be 70% of standard)")
print(f"Standard quality total: {standard_total:.2f} mL (baseline)")
print(f"High quality total:     {high_total:.2f} mL (should be 120% of standard)")

# Verify ratios
draft_ratio = draft_total / standard_total if standard_total > 0 else 0
high_ratio = high_total / standard_total if standard_total > 0 else 0

print(f"\nVerification:")
print(f"  Draft/Standard ratio:  {draft_ratio:.2%} (expected: 70%)")
print(f"  High/Standard ratio:   {high_ratio:.2%} (expected: 120%)")

if abs(draft_ratio - 0.70) < 0.05 and abs(high_ratio - 1.20) < 0.05:
    print("\n[PASS] Quality modifiers are working correctly!")
else:
    print("\n[FAIL] Warning: Quality modifiers may not be calculating correctly")

print("\n" + "=" * 70)
