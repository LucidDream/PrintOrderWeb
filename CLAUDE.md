# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Print Order Web is a Flask web application for blockchain-enabled print job ordering. It provides a browser-based interface for submitting print jobs to a blockchain-based consumable tracking system via ConsumableClient API.

**Repository**: https://github.com/LucidDream/PrintOrderWeb

**Key Architecture**: FAIL-FAST operation requiring the ConsumableClient DLL. NO STUB MODE.

## Shell Environment

**Use PowerShell for all shell commands on this machine.** Standard cmd commands (like `del`, `dir`) fail with exit code 127. Wrap operations in `powershell -Command "..."`:

```powershell
# File operations
powershell -Command "Remove-Item -Path 'file.txt' -ErrorAction SilentlyContinue"
powershell -Command "Copy-Item -Path '.env.example' -Destination '.env'"
powershell -Command "Get-ChildItem -Path 'tests' -Name"

# Multiple files
powershell -Command "Remove-Item -Path 'file1.txt', 'file2.txt' -ErrorAction SilentlyContinue"
```

## Development Commands

```powershell
# Setup
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
powershell -Command "Copy-Item -Path '.env.example' -Destination '.env'"

# Run (requires DLL - no stub mode)
python app.py
# Visit http://127.0.0.1:5000

# Build executable (Windows)
pip install pyinstaller
pyinstaller --clean --noconfirm print_order_web.spec
```

## Architecture (Refactored December 2025)

The application was completely refactored to fix the "job minus one" bug where jobs used values from previous jobs. The new architecture ensures **COMPLETE THREAD ISOLATION** between inventory display and job submission.

### Thread Model

```
Main Thread (Flask)
├── DLL initialization (ld3s_open)
├── Flask request handling
└── Cleanup on shutdown (ld3s_close)

Inventory Thread (background, daemon)
└── 30-second refresh loop
    └── Creates OWN ConsumableAPIClient
    └── Stores InventorySnapshot (immutable)

Job Threads (one per submission, non-daemon)
└── Each job creates:
    └── OWN ConsumableAPIClient (NOT shared with inventory!)
    └── Fetches FRESH template from blockchain
    └── Builds payload from FrozenOrder (immutable)
    └── Stores result in JobResultStore
```

**KEY PRINCIPLE**: Inventory and job submission use SEPARATE API clients. No shared state.

### Module Structure

```
print_order_web/
├── app.py                    # Slim (~300 lines) - app factory, blueprints
├── config.py                 # Configuration (no stub mode)
├── logging_config.py         # Thread-aware logging with context
│
├── core/                     # Core infrastructure
│   ├── exceptions.py         # Custom exceptions (fail-fast)
│   ├── dll_manager.py        # DLL lifecycle (ld3s_open/close)
│   └── api_client.py         # Thread-safe API wrapper (NO STUB)
│
├── models/                   # Immutable data models
│   ├── order.py              # Order, FrozenOrder (immutable for threads)
│   ├── job_result.py         # JobResult, LedgerEntry, JobStatus
│   └── inventory.py          # InventorySnapshot (immutable)
│
├── services/                 # Business logic
│   ├── inventory_service.py  # Background refresh thread
│   └── job_service.py        # Job threads + JobResultStore
│
├── routes/                   # Flask blueprints
│   ├── main.py               # / and /demo
│   ├── upload.py             # PDF upload
│   ├── details.py            # Job configuration
│   ├── review.py             # Order review
│   ├── submit.py             # Job submission + /processing
│   ├── confirmation.py       # Results display + /start-over
│   └── api.py                # AJAX endpoints (/status, /sidebar_refresh)
│
├── modules/                  # Helper modules
│   ├── consumable_details.py # Metadata extraction
│   ├── estimator.py          # Toner/media estimation
│   ├── i18n.py               # Translation support
│   ├── image_defaults.py     # Default images for consumables
│   ├── pdf_analyzer.py       # PDF analysis
│   └── printer_config.py     # Printer slot mapping
│
└── templates/                # Jinja2 templates (unchanged)
```

### Request Flow

```
Browser → Flask Route → Service Layer → API Client → Blockchain

Upload  → routes/upload.py    → PDFAnalyzer        → (none)
Details → routes/details.py   → InventoryService   → (snapshot, NOT fresh)
Review  → routes/review.py    → (session only)     → (none)
Submit  → routes/submit.py    → JobService         → FRESH template + submit
Process → routes/submit.py    → JobResultStore     → poll status
Confirm → routes/confirmation.py

CRITICAL: Job submission fetches FRESH template, not cached inventory!
```

### Data Flow for Job Submission

```
1. User clicks Submit
2. Main thread creates FrozenOrder (immutable copy of session)
3. Main thread calls JobService.submit_job(frozen_order)
4. JobService spawns new thread
5. Job thread creates OWN ConsumableAPIClient
6. Job thread calls new_job_template() - FRESH from blockchain!
7. Job thread builds payload from frozen_order
8. Job thread submits to blockchain
9. Job thread stores result in JobResultStore
10. Main thread polls JobResultStore
11. Result stored in session
```

## Configuration (.env)

```bash
# NO ENABLE_API_MODE - DLL is required, no stub mode
CONSUMABLE_DLL_PATH=../CCAPIv2.0.0.2/ConsumableClient.dll
FLASK_SECRET_KEY=change-in-production
FLASK_DEBUG=1                      # 0 for production
FLASK_ENV=development              # development or production
```

## Key Classes

### DLLManager (core/dll_manager.py)
- Manages ConsumableClient.dll lifecycle
- Called only from main thread
- Methods: `initialize()`, `cleanup()`
- Properties: `context_handle`, `library` (for worker threads)

### ConsumableAPIClient (core/api_client.py)
- Thread-safe wrapper for DLL functions
- Each thread creates its own instance
- Methods: `new_job_template()`, `submit_job()`, `get_job_status()`, `wait_for_job_completion()`

### InventoryService (services/inventory_service.py)
- Background thread refreshes every 30 seconds
- Creates its own ConsumableAPIClient
- Stores InventorySnapshot (immutable)
- Methods: `start()`, `stop()`, `get_snapshot()`, `force_refresh()`

### JobService (services/job_service.py)
- Manages job submission threads
- One thread per job
- Each job thread creates its own ConsumableAPIClient
- Methods: `submit_job(frozen_order)`, `get_result(job_id)`

### FrozenOrder (models/order.py)
- Immutable snapshot of order for job submission
- Created via `order.freeze()`
- Contains all job parameters (toner_usage, sheets_required, etc.)

### JobResultStore (services/job_service.py)
- Thread-safe storage for job results
- Job threads write, main thread reads
- Only communication channel between threads

## API Integration

```
1. ld3s_open()           → context handle (main thread only)
2. ld3s_new_job(ctx)     → JSON template with balances
3. ld3s_submit_job(ctx, payload) → job handle (uint64)
4. ld3s_get_job_status(ctx, handle) → poll until complete
5. ld3s_close(ctx)       → cleanup (main thread only)

Memory: All API-returned strings must be freed via ld3s_free(ctx, ptr)
```

## Error Handling

**Fail-Fast Behavior:**
- If DLL not found → Application fails to start
- If DLL init fails → Application fails to start
- No stub mode → Service unavailable without DLL

**Runtime Errors:**
- `DLLNotFoundError` - ConsumableClient.dll not found
- `ServiceUnavailableError` - DLL initialization failed
- `InventoryNotReadyError` - No inventory data available
- `JobSubmissionError` - Job submission failed
- `InsufficientBalanceError` - Not enough consumables
- `BlockchainTimeoutError` - Blockchain response timeout

## Testing Notes

- Application requires real DLL for operation
- Test real blockchain integration via running Flask app
- Sample PDFs available in `sample_pdfs/` folder for testing

## Building Production Executable

```powershell
# Install PyInstaller (if not already installed)
pip install pyinstaller

# Option 1: Use the build script (recommended)
.\build.ps1 -Clean

# Option 2: Direct PyInstaller command
pyinstaller --clean --noconfirm print_order_web.spec

# Output location: dist/PrintOrderWeb/
```

**Build output structure:**
```
dist/PrintOrderWeb/
├── PrintOrderWeb.exe          # Main executable
├── .env                       # Production config (from .env.production)
├── README_TESTER.md           # Tester documentation
├── TROUBLESHOOTING.md         # Troubleshooting guide
├── sample_pdfs/               # Sample PDF files for testing
│   ├── sample_test_page.pdf
│   └── README.txt
└── _internal/
    ├── ConsumableClient.dll   # Blockchain API DLL
    ├── templates/             # Flask HTML templates
    ├── static/                # CSS, JS, images
    │   └── uploads/           # PDF upload folder (created by build)
    ├── translations/          # i18n (EN/DE)
    └── [Python runtime + deps]
```

**To create a ZIP for distribution:**
```powershell
cd dist
Compress-Archive -Path PrintOrderWeb -DestinationPath PrintOrderWeb-v1.0-Beta.zip
```

## Code Style

- Python 3.11+
- Black formatter (88 chars)
- Type hints required
- Google-style docstrings
- Logging: DEBUG for API calls, INFO for operations, ERROR for failures

## Key Design Decisions

1. **No Stub Mode**: Application fails fast if DLL unavailable. This prevents silent failures in production.

2. **Frozen Orders**: Order data is frozen (immutable) before passing to job threads. This prevents session contamination.

3. **Separate API Clients**: Each thread (inventory, job) creates its own ConsumableAPIClient. No shared state.

4. **JobResultStore**: The ONLY communication between job threads and main thread. Thread-safe read/write.

5. **Immutable Snapshots**: InventorySnapshot is frozen dataclass. Safe to read from any thread.

6. **Thread Naming**: All threads have meaningful names for logging (`Inventory`, `Job-{id}`).

## Refactoring Summary (December 2025)

### The "Job Minus One" Bug

The original architecture had a critical bug where job submissions would use consumable values from the **previous** job instead of the current one. This was caused by:

1. **Shared API client state** between inventory display and job submission
2. **Cached template reuse** - jobs used stale inventory data instead of fresh blockchain data
3. **Mutable order objects** - session data could be modified during job processing

### What Changed

**Before (Monolithic app.py ~1200 lines):**
```
app.py contained:
├── All routes inline
├── Single shared ThreadSafeAPIClient
├── Inventory refresh in same thread as requests
├── Job submission using cached inventory template
└── Mutable order dicts passed to threads
```

**After (Modular architecture):**
```
print_order_web/
├── app.py (~300 lines) - Slim app factory
├── core/               - DLL management, API client
├── models/             - Immutable data (FrozenOrder, InventorySnapshot)
├── services/           - InventoryService, JobService (separate threads)
├── routes/             - Flask blueprints (7 modules)
└── modules/            - Helper modules (estimator, i18n, etc.)
```

### Key Architectural Changes

1. **Thread Isolation**: Each thread (inventory, job) creates its OWN `ConsumableAPIClient`
2. **Fresh Templates**: Job submission fetches FRESH template from blockchain, never uses cached inventory
3. **Immutable Data**: `FrozenOrder` and `InventorySnapshot` are frozen dataclasses
4. **Blueprint Routes**: Routes split into 7 focused modules with proper `url_for()` namespacing
5. **JobResultStore**: Thread-safe communication between job threads and main thread
6. **Fail-Fast**: No stub mode - application requires DLL to start

### Fixes Applied Across Sessions

1. **DLLManager path handling** - Fixed str/Path type issue for DLL path
2. **Blueprint url_for()** - Fixed template links to use `blueprint.endpoint` format
3. **Job status parsing** - DLL returns "ready" not "completed" for success
4. **Nested results format** - Correctly parse wallet/account structure in job results
5. **Display name extraction** - Use "Consumable Name" field from deeply nested projectData
6. **Error sidebar** - Provide complete printer config object for error states
7. **Template compatibility** - Include all required keys (default_turnaround_options, etc.)

## Recent Changes (December 2025)

### Display Name Extraction Fix

The "Consumable Name" field in the blockchain API response is located at:
```
account.metadata.metadata.tokenDescription.projectData."Consumable Name"
```

Multiple locations needed updating to extract display names correctly:

1. **`models/inventory.py`** - `InventorySnapshot.from_template()`
   - Added `get_full_account_data()` method for raw template access
   - Fixed display name extraction to use "Consumable Name" field

2. **`routes/details.py`** - `_snapshot_to_inventory_dict()`
   - Now extracts media display names from raw_template
   - Added missing `default_turnaround_options` key for template compatibility

3. **`routes/details.py`** - POST handler for choices
   - Gets accurate media display name from raw_template before session storage
   - Ensures review.html shows proper name via `order.choices.media_display_name`

4. **`routes/api.py`** - `sidebar_refresh()` and `_render_error_sidebar()`
   - Same display name extraction pattern for AJAX sidebar updates
   - Fixed error sidebar to use proper printer config with all required fields

5. **`app.py`** - `inject_printer_config()` context processor
   - Updated to extract display names from raw_template
   - Populates `toner_details` and `media_details` for sidebar

### Job Result Parsing Fixes

1. **Status handling**: DLL returns "ready" when complete, not "completed"
   - `_parse_result()` now accepts both "ready" and "completed" as success states

2. **Nested results format**: DLL response structure is:
   ```python
   status = {
       "transactionSuccess": True,
       "status": "ready",
       "results": {
           "jobID": "...",
           "results": [  # List of wallets
               {
                   "publicKey": "...",
                   "accounts": [...]  # Account entries with actualExpenditure
               }
           ]
       }
   }
   ```

### Error Handling Improvements

1. **Sidebar error state**: `_render_error_sidebar()` now provides complete printer config:
   ```python
   printer = {
       "slots": [],
       "unverified_count": 0,
       "verified_count": 0,
       "total_slots": 0,
       "model_name": "Unknown",
       ...
   }
   ```

2. **Template compatibility**: All inventory dict conversions now include required keys for templates.

## Blockchain API Response Structure

The ConsumableClient DLL returns deeply nested JSON. Key paths:

```python
# Template structure from ld3s_new_job()
template = {
    "inventoryParameters": {
        "wallets": [{
            "accounts": [{
                "mintId": "unique-blockchain-id",
                "estimatedBalance": 5000.0,
                "currentExpenditure": 0,  # SET THIS for submission
                "metadata": {
                    "price": "240",
                    "tax": "9",
                    "metadata": {  # NESTED metadata
                        "uom": "Toner" | "Media",
                        "tokenDescription": {
                            "projectData": {
                                "Consumable Name": "Human-readable name",
                                "Color": "CYAN",  # For toner
                                "Manufacturer": "...",
                                ...
                            }
                        }
                    }
                }
            }]
        }]
    }
}

# Job status from ld3s_get_job_status()
status = {
    "status": "ready",  # or "processing"
    "transactionSuccess": True,
    "final": True,  # Alternative to transactionSuccess
    "results": {
        "jobID": "JOB...",
        "results": [...]  # Wallet/account results
    }
}
```

## Account Matching Logic

- **Toner**: Match by `projectData.Color` (e.g., "CYAN" → "cyan")
- **Media**: Match by `mintId` (blockchain account ID)

Display names should use:
```python
project_data.get("Consumable Name") or project_data.get("ProductName") or fallback
```

## Project Cleanup (December 2025)

### Removed Legacy Modules
The following modules were removed as they were replaced by the new architecture:
- `modules/api_client_threaded.py` → replaced by `core/api_client.py`
- `modules/inventory_threaded.py` → replaced by `services/inventory_service.py`
- `modules/job_processor.py` → replaced by `services/job_service.py`

### Removed Extraneous Files
- `app_old.py` - Old monolithic version
- `instructions.txt` - Developer notes
- `fetch_template.py`, `test_template_structure.py` - Dev scripts
- `UI_MOCKUP*.html` (5 files) - Design mockups
- `CC-Test/` folder and `CC-Test.zip` - Test artifacts
- `docs/archive/` - Old session summaries
- Orphaned `consolelog.txt`, `nul` files

### Documentation Updates
- All documentation updated to remove stub mode references
- Version references generalized (DLL version folder may vary)
- README.md, README_TESTER.md, TROUBLESHOOTING.md all aligned with fail-fast architecture
- DELIVERY_INSTRUCTIONS.md updated with correct paths and structure

### Build Enhancements
- `build.ps1` - New PowerShell build script with verification
- `print_order_web.spec` - Updated to include docs, sample PDFs, and create uploads folder
- `sample_pdfs/` - Sample PDF files for testing included in build

### Logging Improvements (December 2025)

Reduced log verbosity for the 30-second inventory refresh cycle to prevent log flooding in production:

1. **`core/api_client.py`** - `new_job_template()`
   - Changed "Template fetched: X accounts" from INFO → DEBUG level
   - Affects both inventory refresh and job submission template fetch

2. **`services/inventory_service.py`** - `_do_refresh()`
   - Changed "Inventory refreshed: X toners, Y media options" from INFO → DEBUG level
   - Errors and recovery messages remain at WARNING/ERROR/INFO levels

3. **`app.py`** - `load_dotenv()` calls
   - Added `override=True` parameter so `.env` file always takes precedence over shell environment variables
   - Ensures configuration changes in `.env` take effect without clearing shell environment

**Result**: In production mode (`FLASK_DEBUG=0`), the console remains silent during normal 30-second inventory refreshes. Only errors, warnings, and significant events are logged.
