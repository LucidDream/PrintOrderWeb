# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Print Order Web is a Flask web application for blockchain-enabled print job ordering. It provides a browser-based interface for submitting print jobs to a blockchain-based consumable tracking system via ConsumableClient API.

**Repository**: https://github.com/LucidDream/PrintOrderWeb

**Key Architecture**: Dual-mode operation supporting both development (stub) and production (real blockchain via Windows DLL).

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

# Run (stub mode by default)
python app.py
# Visit http://127.0.0.1:5000

# Production mode (Windows only): set ENABLE_API_MODE=true in .env

# Tests
pytest tests/ -v                           # All tests
pytest tests/test_inventory.py -v          # Specific suite
pytest tests/test_job_processor.py::TestClassName::test_name -v  # Single test
pytest --cov=modules tests/                # With coverage

# Build executable (Windows)
pip install pyinstaller
pyinstaller --clean --noconfirm print_order_web.spec
```

## Architecture

### Request Flow

```
Browser → Flask Route → Service Layer → API Client → Blockchain
Upload  → /upload     → PDFAnalyzer   → (none)
Details → /details    → Inventory     → API.new_job (cached 30s)
Review  → /review     → Estimator     → (cached inv)
Submit  → /submit     → JobProcessor  → API.submit → Transaction
Process → /processing → AJAX polling  → API.get_status
Confirm → /confirmation

Independent: Sidebar → 30s auto-refresh → Inventory cache → Fresh data
```

### Core Modules

| Module | Purpose |
|--------|---------|
| `app.py` | Flask routes, DLL initialization, job threads |
| `modules/api_client_threaded.py` | Thread-safe DLL wrapper + stub implementation |
| `modules/inventory_threaded.py` | Background refresh thread, 30s cache |
| `modules/job_processor.py` | Build payloads, parse blockchain results |
| `modules/estimator.py` | Quality-aware consumable estimation |
| `modules/consumable_details.py` | Extract 17+ metadata fields from blockchain |
| `modules/printer_config.py` | Roland TrueVIS VG3-640 ink slot mapping |
| `modules/image_defaults.py` | SVG fallbacks for consumable images |
| `modules/pdf_analyzer.py` | PDF page analysis |
| `modules/i18n.py` | Translation support (EN/DE) |

### Thread Model

- **Main thread**: DLL init/close (`ld3s_open`/`ld3s_close`)
- **Inventory thread**: Background refresh every 30 seconds
- **Job threads**: One per submission, independent lifecycle

All threads share the DLL context handle but create their own `ThreadSafeAPIClient` instances.

## Configuration (.env)

```bash
ENABLE_API_MODE=false              # true = real blockchain (Windows only)
CONSUMABLE_DLL_PATH=../CCAPIv2.0.0.2/ConsumableClient.dll
FLASK_SECRET_KEY=change-in-production
FLASK_DEBUG=1                      # 0 for production
FLASK_ENV=development              # development or production
```

## Critical Data Structures

**Blockchain Template (deeply nested):**
```python
{
  "inventoryParameters": {
    "wallets": [{
      "accounts": [{
        "estimatedBalance": 5000.0,
        "mintId": "unique-id",
        "currentExpenditure": 0,  # Set this for job submission
        "metadata": {
          "price": "240", "tax": "9",
          "metadata": {  # Nested!
            "uom": "Toner" | "Media",
            "tokenDescription": {
              "projectData": {"Color": "CYAN", ...}
            }
          }
        }
      }]
    }]
  }
}
```

**Account Matching:**
- Toner: Match by `projectData.Color` (e.g., "CYAN" → "cyan")
- Media: Match by `mintId`

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

**Three-tier fallback:**
1. Fresh API data → full functionality
2. Stale cache → warning shown, cached data used
3. Complete failure → error shown, submission blocked

**Enhanced error detection:** Keywords "insufficient", "balance", "timeout" trigger user-friendly messages.

## Testing Notes

- **Tests are outdated**: Test files import from old module names (`modules.api_client`, `modules.inventory`) that were refactored to `modules.api_client_threaded` and `modules.inventory_threaded`. The new modules have a different API (threaded architecture). Tests need updating before they will pass.
- Some API tests require GUI context (ConsumableClient.dll has wxWidgets dependency)
- Test real blockchain integration via running Flask app, not pytest
- 7 test files in `tests/`:
  - `test_inventory.py`, `test_job_processor.py` (core business logic)
  - `test_api_client.py`, `test_enhanced_estimator.py`
  - `test_account_identification.py`, `test_job_payload_building.py`
  - `test_details_extraction.py`

**To fix tests**: Update imports from `modules.inventory.InventoryService` to `modules.inventory_threaded.ThreadedInventoryService` and adapt tests for the threaded API.

## Known Issues

- **Unicode logging on Windows**: Checkmark characters (✓) in log messages fail to encode in Windows cp1252 console. Cosmetic issue only - app functions normally.
- **ConsumableLedger server required**: With `ENABLE_API_MODE=true`, the DLL loads but requires the ConsumableLedger backend service (`LDConsumables.SSS`) to be running. Set `ENABLE_API_MODE=false` for stub mode.

## Code Style

- Python 3.13+ (tested), compatible with 3.11+
- Black formatter (88 chars)
- Type hints required
- Google-style docstrings
- Logging: DEBUG for API calls, INFO for operations, ERROR for failures

## Key Files Reference

| File | Lines | Purpose |
|------|-------|---------|
| `app.py` | ~1250 | Main Flask app, routes, thread management, DLL lifecycle |
| `modules/api_client_threaded.py` | ~300 | `ThreadSafeAPIClient` (real DLL) + `ConsumableClientAPIStub` |
| `modules/inventory_threaded.py` | ~440 | `ThreadedInventoryService` with background refresh |
| `modules/job_processor.py` | ~350 | Payload building, result parsing |
| `modules/estimator.py` | - | Quality-aware toner/media estimation |
| `modules/consumable_details.py` | - | Metadata extraction (17+ fields) |
| `modules/printer_config.py` | - | Roland TrueVIS VG3-640 slot mapping |
| `print_order_web.spec` | ~100 | PyInstaller spec for production builds |

## Building Production Executable

The spec file `print_order_web.spec` creates a production-ready executable with the latest ConsumableClient DLL bundled.

```powershell
# Install PyInstaller (if not already installed)
pip install pyinstaller

# Build production executable
pyinstaller --clean --noconfirm print_order_web.spec

# Output location
# dist/PrintOrderWeb/PrintOrderWeb.exe
```

**Build output structure:**
```
dist/PrintOrderWeb/
├── PrintOrderWeb.exe          # Main executable
├── README_TESTER.md           # Tester documentation
├── TROUBLESHOOTING.md         # Troubleshooting guide
└── _internal/
    ├── ConsumableClient.dll   # Latest DLL (v2.0.0.2)
    ├── .env                   # Production config (ENABLE_API_MODE=true)
    ├── .env.example           # Template config
    ├── templates/             # Flask HTML templates
    ├── static/                # CSS, JS, images
    ├── translations/          # i18n (EN/DE)
    └── [Python runtime + deps]
```

**Production `.env` settings (pre-configured in build):**
```bash
ENABLE_API_MODE=true           # Real blockchain enabled
FLASK_ENV=production
FLASK_DEBUG=0
CONSUMABLE_DLL_PATH=ConsumableClient.dll
```

**Spec file features:**
- Bundles ConsumableClient.dll from `../CCAPIv2.0.0.2/`
- Includes templates, static assets, translations
- Excludes unnecessary packages (tkinter, matplotlib, numpy, etc.)
- Console mode enabled for logging visibility

**Current DLL version:** v2.0.0.2 (as of December 2025)
