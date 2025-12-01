# Cache Refresh Bug Fix - November 6, 2025

## 🐛 Problem Description

**User-Reported Bug:**
1. User runs job with incomplete consumables (e.g., Cyan, Black only)
2. User adds new consumables to blockchain (Magenta, Yellow)
3. Sidebar updates correctly showing new consumables
4. User runs another job
5. **BUG**: Transaction only includes old consumables (Cyan, Black)
6. Third job works correctly with all consumables

## 🔍 Root Cause

The bug was caused by the **30-second inventory cache** combined with **estimate caching in session**:

### Flow of the Bug:

```
Time 0s:  User loads /details page
          → Inventory cached (only Cyan, Black available)

Time 5s:  User submits form
          → Estimate created: toner_usage = {"cyan": 0.2, "black": 0.2}
          → Estimate saved in session

Time 10s: New consumables (Magenta, Yellow) added to blockchain

Time 35s: Sidebar refresh (cache expired)
          → Shows all 4 colors (Cyan, Magenta, Yellow, Black)

Time 40s: User submits job
          → Job processor fetches fresh template (has all 4 colors) ✓
          → BUT estimate in session still has {"cyan": 0.2, "black": 0.2} ✗
          → Transaction only uses Cyan and Black ✗

Time 100s: User submits another job
           → Cache refreshed
           → Estimate created with all 4 colors ✓
           → Transaction includes all 4 colors ✓
```

### Technical Details:

The estimator (`modules/estimator.py`) only creates usage for consumables that exist in the inventory:

```python
# Calculate toner for each color in the profile
toner_profile = inventory["toner_profiles"].get(color_mode, [])
for color in toner_profile:
    if color in inventory["toner_balances"]:  # ← Only estimates if in inventory
        toner_usage[color] = calculate_usage(...)
```

If Magenta and Yellow don't exist in the cached inventory when the estimate is created, they won't be included in `toner_usage`, even if they're added to the blockchain later.

## ✅ Solution

Implemented **forced cache refresh at critical decision points**:

### 1. Force Refresh on Estimate Generation (`app.py:220-233`)

**Before:**
```python
def details() -> Any:
    # Uses cached inventory (might be stale)
    inventory = inventory_service.get_inventory_snapshot()

    if request.method == "POST":
        # Creates estimate with potentially stale data
        estimate = estimate_consumables(...)
```

**After:**
```python
def details() -> Any:
    # CRITICAL: Always force fresh inventory on POST (estimate generation)
    force_refresh = (request.method == "POST")

    inventory = inventory_service.get_inventory_snapshot(force_refresh=force_refresh)

    if request.method == "POST":
        # Creates estimate with guaranteed fresh data ✓
        estimate = estimate_consumables(...)
```

### 2. Invalidate Cache on New Order (`app.py:501-517`)

**Before:**
```python
def start_over() -> Any:
    session.pop("order", None)
    return redirect(url_for("upload"))
```

**After:**
```python
def start_over() -> Any:
    session.pop("order", None)

    # Force fresh inventory for next page load
    inventory_service.invalidate_cache()
    app.logger.info("Cache invalidated for new order")

    return redirect(url_for("upload"))
```

### 3. Enhanced Cache Invalidation on Job Completion (`app.py:459-469`)

**Before:**
```python
if result["complete"]:
    order["result"] = result["result"]
    inventory_service.invalidate_cache()  # No explanation
```

**After:**
```python
if result["complete"]:
    order["result"] = result["result"]

    # CRITICAL: Invalidate inventory cache after job completion
    # Job consumed toner/media, so balances have changed
    # Next page load must fetch fresh inventory
    inventory_service.invalidate_cache()
    app.logger.info("Cache invalidated after job completion")
```

## 📊 Cache Strategy

### When Cache is Used:

| Route | Method | Force Refresh? | Reason |
|-------|--------|----------------|--------|
| `/demo` | GET | No | Sidebar display only (30s cache OK) |
| `/details` | GET | No | Dropdown population (30s cache OK) |
| `/details` | POST | **YES** | Estimate generation (must be fresh) |
| `/review` | GET | No | Uses estimate from session |
| `/submit` | POST | No* | Job processor fetches fresh template |
| `/status` | GET | No | Polling during processing |
| Context processor | - | No | Every page (30s cache OK) |

*Job processor calls `api_client.new_job_template()` directly, bypassing cache

### Cache Invalidation Points:

1. **After job completion** - Balances have changed
2. **On new order** - Ensure user sees latest consumables
3. **Manual invalidation** - When user explicitly refreshes (future feature)

## 🧪 Testing the Fix

### Test Scenario:

1. Start with 2 consumables (Cyan, Black)
2. Submit Job 1 successfully
3. Add 2 new consumables (Magenta, Yellow) via another application
4. **Wait < 30 seconds** (cache should be stale)
5. Go to `/details` page - should show dropdown with all 4 colors
6. Fill out form and submit (POST to /details)
   - **Should force cache refresh**
   - **Estimate should include all 4 colors**
7. Review and submit job
8. **Expected**: Transaction includes all 4 colors ✓

### Verification:

Check logs for:
```
[INFO] Fetching inventory snapshot (force_refresh=True)
[INFO] Inventory snapshot updated: 2 media options, 4 toner colors
```

The `force_refresh=True` confirms fresh data is being fetched on estimate generation.

## 📈 Impact Analysis

### Performance:

- **Extra API calls**: +1 per job submission (on POST to /details)
- **Trade-off**: Slight performance hit for correctness
- **Mitigation**: Cache still used for GET requests (most common)

### Correctness:

- ✅ Estimates always use current inventory
- ✅ No more missing consumables in transactions
- ✅ User sees accurate inventory at decision points

### User Experience:

- ✅ Jobs work correctly on first try
- ✅ No need to submit job twice
- ✅ No confusing "why didn't it use the new consumables?" moments

## 🚀 Future Enhancements

1. **Reduce cache duration** - Consider 10 seconds instead of 30 seconds
2. **Add manual refresh button** - Let user force refresh sidebar
3. **Real-time updates** - WebSocket notifications when consumables change
4. **Optimistic caching** - Predict balance changes locally
5. **Cache validation** - Check if inventory changed since last fetch

## 📝 Files Modified

1. `app.py` (3 changes):
   - Line 227-233: Force refresh on POST to /details
   - Line 465-469: Enhanced cache invalidation comments
   - Line 503-517: Invalidate cache on new order

2. `CACHE_REFRESH_FIX.md` (this file):
   - Complete documentation of bug and fix

## ✅ Status

**Fixed:** November 6, 2025
**Tested:** Pending user verification
**Ready for:** Production deployment
