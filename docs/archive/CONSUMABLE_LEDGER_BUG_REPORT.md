# ConsumableLedger Bug Report: actualExpenditure Not Populated in Job Results

**Date**: November 12, 2025
**Reporter**: Print Order Web Application
**Severity**: HIGH - Breaks transaction display in all consuming applications
**Job ID**: JOB00DD3B6697A91000 (and all recent jobs)

---

## Executive Summary

ConsumableLedger is successfully processing blockchain transactions but writing job result files with **all `actualExpenditure` values set to 0.0** instead of the actual consumed amounts. This causes consuming applications to display "No ledger entries recorded" even though transactions completed successfully.

---

## Evidence Chain

### 1. Print Order Web Sends Correct Payload ✅

**File**: `job_payload_sent_to_ledger.json`

**Structure**:
```json
{
  "inventoryParameters": {
    "wallets": [
      {
        "accounts": [{
          "currentExpenditure": 0.04,
          "estimatedBalance": 5997.57,
          "mintId": "61dVMLbtRCncpBAF5khSxrXdfzToC9Sj6xMbR1ZqnAcu",
          "metadata": {...}
        }]
      }
    ]
  },
  "jobParameters": {
    "jobID": "JOB00DD3B6697A91000",
    "status": "new",
    "timestamp": "2025-11-12T12:49:25Z"
  },
  "jobMetadata": {
    "jobName": "incog06",
    "submittedAt": "2025-11-12T18:49:25.278070+00:00",
    "quantity": 2,
    "colorMode": "full_color",
    "pdfPages": 1,
    "estimatedCost": 0.26
  }
}
```

**Expenditures Sent**:
- CyanIB: `currentExpenditure: 0.04` mL
- YellowIB: `currentExpenditure: 0.04` mL
- BlackIB: `currentExpenditure: 0.05` mL
- MagentaIB: `currentExpenditure: 0.04` mL
- ProGHSLeg: `currentExpenditure: 2.0` sheets

---

### 2. ConsumableLedger Receives Data Correctly ✅

**File**: `Log.txt` (lines 1-4)

```
12:49:25: New job came from the server: JOB00DD3B6697A91000
12:49:25: Prepared transaction data for 5 item(s)
12:49:25: Transaction Order:
{"job":{...},"transactions":[
  {"balance":5997.57,"currentExpenditure":0.04,"mintId":"61dV...","name":"CyanIB",...},
  {"balance":47.0,"currentExpenditure":2.0,"mintId":"GuqV...","name":"ProGHSLeg",...},
  {"balance":5998.8,"currentExpenditure":0.04,"mintId":"GT5V...","name":"YellowIB",...},
  {"balance":5998.88,"currentExpenditure":0.05,"mintId":"GJfi...","name":"BlackIB",...},
  {"balance":5999.2,"currentExpenditure":0.04,"mintId":"4BEs...","name":"MagentaIB",...}
]}
```

**Confirmation**: ConsumableLedger correctly parsed all 5 `currentExpenditure` values.

---

### 3. ConsumableLedger Processes Transactions Successfully ✅

**File**: `Log.txt` (lines 5-6)

```
12:49:28: Raw transaction results:
{"job":{...},"transactions":[
  {"mintId":"61dVMLbtRCncpBAF5khSxrXdfzToC9Sj6xMbR1ZqnAcu","publicKey":"...","success":true},
  {"mintId":"GuqV4c1dAid3LxxVyYVkcvTbQSXd4U6QH6kij7dCXppw","publicKey":"...","success":true},
  {"mintId":"GT5VBn36QrZqw5RdnzKUoTxjNVURhQuEbx9n9cRTXH5N","publicKey":"...","success":true},
  {"mintId":"GJfidm8zqYWHiWDoCrtYKxfdxgufXVqsCDrm7bjTux31","publicKey":"...","success":true},
  {"mintId":"4BEsCz6vzExPMVcwf3LvybmFMew5rt52A1HAbn9cP7Tm","publicKey":"...","success":true}
]}
```

**Confirmation**: All 5 transactions returned `"success": true`.

---

### 4. ConsumableLedger Writes INCORRECT Results File ❌

**File**: `job_JOB00DD3B6697A91000.json`

```json
{
  "jobID": "JOB00DD3B6697A91000",
  "results": [
    {
      "accounts": [{
        "actualExpenditure": 0.0,  // ❌ WRONG! Should be 0.04
        "balance": 5999.2,
        "mintId": "4BEsCz6vzExPMVcwf3LvybmFMew5rt52A1HAbn9cP7Tm"
      }]
    },
    {
      "accounts": [{
        "actualExpenditure": 0.0,  // ❌ WRONG! Should be 2.0
        "balance": 47.0,
        "mintId": "GuqV4c1dAid3LxxVyYVkcvTbQSXd4U6QH6kij7dCXppw"
      }]
    },
    // ... all 5 accounts have actualExpenditure: 0.0
  ]
}
```

**Problem**: ALL accounts show `actualExpenditure: 0.0` even though:
- They were sent with correct `currentExpenditure` values
- They were received correctly by ConsumableLedger
- They were processed successfully (all returned `success: true`)

---

## Root Cause Analysis

The job results file appears to be written from the **initial template state** (before transaction processing) rather than the **post-transaction state** (with expenditures applied).

**Evidence**:
1. The "Raw transaction results" (Log.txt line 5-6) only contain success flags: `{"mintId":"...", "publicKey":"...", "success":true}`
2. They do NOT contain `actualExpenditure` or updated `balance` values
3. The job results JSON file has full metadata but all `actualExpenditure: 0.0`
4. The `balance` values in the results file appear to be the STARTING balances (before expenditure), not ending balances

---

## Expected vs Actual Behavior

### Expected Behavior:
After processing transactions, ConsumableLedger should:
1. ✅ Receive `currentExpenditure` from job payload
2. ✅ Process blockchain transactions
3. ✅ Calculate `actualExpenditure` = amount actually spent
4. ✅ Calculate new `balance` = old balance - actualExpenditure
5. ✅ Write job results file with populated `actualExpenditure` and updated `balance`

### Actual Behavior:
1. ✅ Receives `currentExpenditure` correctly
2. ✅ Processes blockchain transactions successfully
3. ❌ **Writes job results file with original template (actualExpenditure: 0)**
4. ❌ Balance values appear to be starting balances, not ending balances

---

## Impact

**ALL consuming applications are affected:**
- Print Order Web shows "No ledger entries recorded"
- PrintSimulator (if using results file) would show same issue
- Any analytics or reporting tools reading these files would see zero expenditures

**User Impact:**
- Users cannot see what was consumed in their print jobs
- No audit trail of actual consumption
- Cannot verify transactions succeeded despite successful processing

---

## Suspected Code Location (ConsumableLedger)

Look for code that writes the `job_JOB*.json` file (Log.txt line 7-8 indicates the write location).

The bug is likely in one of these scenarios:

### Scenario A: Writing Original Template
```csharp
// WRONG (suspected current behavior):
var jobResults = originalTemplate;  // Still has actualExpenditure: 0
WriteJobResults(jobResults);

// CORRECT (expected behavior):
var jobResults = UpdateTemplateWithTransactionResults(originalTemplate, transactions);
WriteJobResults(jobResults);  // Now has actualExpenditure populated
```

### Scenario B: Not Copying Transaction Results
```csharp
// WRONG:
foreach (var transaction in transactionResults)
{
    // Process transaction but don't update the template
    ProcessTransaction(transaction);  // ✅ Works
}
WriteJobResults(originalTemplate);  // ❌ Still has 0.0

// CORRECT:
foreach (var transaction in transactionResults)
{
    ProcessTransaction(transaction);
    template.UpdateAccount(transaction.MintId, transaction.ActualExpenditure);
}
WriteJobResults(template);  // ✅ Now has actual values
```

---

## Comparison: What Changed?

This bug appeared recently (after unattached consumables feature was added to Print Order Web). Reviewing the changes:

**Print Order Web Changes (November 2025)**:
- ✅ Added `jobMetadata` field (top-level)
- ✅ Template now includes `jobParameters` (was removed in some older versions)
- ✅ All accounts have `currentExpenditure` field (properly populated)

**Payload Structure Now**:
```
{
  "inventoryParameters": {...},  // Always present
  "jobParameters": {...},        // NOW PRESENT (may have been missing before)
  "jobMetadata": {...}           // NEW FIELD (Print Order Web specific)
}
```

**Question for ConsumableLedger Developer**:
Does your code expect a specific structure? Could the presence/absence of `jobParameters` or `jobMetadata` affect how results are written?

---

## Diagnostic Files Provided

1. **compositelog.txt** - Print Order Web application logs showing:
   - Template structure received from API
   - Payload structure sent to ConsumableLedger
   - Result parsing (finds 0 ledger entries)

2. **job_payload_sent_to_ledger.json** - Exact payload sent, with:
   - All currentExpenditure values correctly set
   - Complete account structure
   - jobParameters and jobMetadata fields

3. **job_JOB00DD3B6697A91000.json** - ConsumableLedger's result file with:
   - All actualExpenditure = 0.0 (WRONG)
   - Balance values (unclear if updated)
   - Full account metadata (copied from template)

4. **Log.txt** - ConsumableLedger application log showing:
   - Correct receipt of currentExpenditure values
   - Successful transaction processing
   - File write location

---

## Recommended Actions

### Immediate (ConsumableLedger Developer):
1. Review code that writes `job_JOB*.json` files
2. Verify `actualExpenditure` is being populated after transaction processing
3. Verify `balance` is being updated (old balance - actualExpenditure)
4. Check if `jobMetadata` or `jobParameters` fields affect result writing logic

### Verification Steps:
1. Add logging before writing job results file to confirm template state
2. Log each account's actualExpenditure value before serialization
3. Verify transaction results are being merged back into template structure

### Testing:
After fix, the job results file should contain:
```json
{
  "accounts": [{
    "actualExpenditure": 0.04,  // NOT 0.0!
    "balance": 5997.53,          // Starting 5997.57 - 0.04 = 5997.53
    "mintId": "61dV..."
  }]
}
```

---

## Historical Context

According to Print Order Web documentation:
- This functionality worked previously with older API versions
- Recent changes included cache refresh fixes and unattached consumable display
- **No changes were made to payload structure except adding jobMetadata field**
- jobParameters has always been part of API v2 spec

**Question**: When did ConsumableLedger last successfully write non-zero actualExpenditure values?

---

## Contact

For questions about this bug report or the provided diagnostic files:
- Print Order Web Application: print_order_web/app.py
- Payload Builder: print_order_web/modules/job_processor.py
- Result Parser: print_order_web/modules/job_processor.py::_parse_job_result()

All diagnostic logging has been enhanced to provide maximum visibility into the issue.
