# Print Order Web Application

A production-ready Flask web application for blockchain-enabled print job ordering with ConsumableClient API integration.

## Overview

This application provides a simple browser-based interface for submitting print jobs to a blockchain-based consumable tracking system.

**Key Features:**
- Dead-simple 4-step workflow (Upload → Details → Review → Submit)
- Real-time blockchain inventory integration with 30-second auto-refresh
- Quality-aware consumable estimation (draft/standard/high)
- Thread-per-job architecture for concurrent, non-blocking job processing
- Multi-language support (English and German)
- Authenticated UI with ink slot verification against blockchain data

**Architecture:** Fail-fast design requiring the ConsumableClient DLL. No stub/offline mode.

---

## Quick Start

### Development Setup

```powershell
cd print_order_web
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

Visit http://127.0.0.1:5000 to use the application.

**Note:** The application requires ConsumableClient.dll to start. Configure the path in `.env`:
```
CONSUMABLE_DLL_PATH=../CCAPIv2.0.0.2/ConsumableClient.dll
```

---

## Configuration

### Environment Variables (.env file)

```bash
# Flask Application Settings
FLASK_SECRET_KEY=your-secret-key-here
FLASK_ENV=development
FLASK_DEBUG=1

# Upload Configuration
UPLOAD_FOLDER=./static/uploads

# Path to ConsumableClient.dll (version folder may vary)
CONSUMABLE_DLL_PATH=../CCAPIv2.0.0.2/ConsumableClient.dll
```

---

## Running from Source

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- Windows OS with ConsumableClient.dll

### Step-by-Step Setup

**1. Navigate to project:**
```powershell
cd print_order_web
```

**2. Create Virtual Environment:**
```powershell
python -m venv .venv
```

**3. Activate Virtual Environment:**
```powershell
.venv\Scripts\Activate.ps1
```

**4. Install Dependencies:**
```powershell
pip install -r requirements.txt
```

**5. Configure Application:**
```powershell
Copy-Item .env.example .env
# Edit .env with your preferred text editor
```

**6. Run Application:**
```powershell
python app.py
```

**7. Access Application:**
Open browser to http://127.0.0.1:5000

---

## Building Production Executable

```powershell
# Install PyInstaller
pip install pyinstaller

# Build executable
pyinstaller --clean --noconfirm print_order_web.spec

# Output location: dist/PrintOrderWeb/
```

**Build output structure:**
```
dist/PrintOrderWeb/
├── PrintOrderWeb.exe          # Main executable
├── .env                       # Production config
└── _internal/
    ├── ConsumableClient.dll   # Blockchain API
    ├── templates/             # Flask HTML templates
    ├── static/                # CSS, JS, images
    │   └── uploads/           # PDF upload folder
    ├── translations/          # i18n (EN/DE)
    └── [Python runtime + deps]
```

---

## Architecture

The application uses a **Thread-Per-Job architecture** with complete thread isolation.

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
    └── OWN ConsumableAPIClient
    └── Fetches FRESH template from blockchain
    └── Builds payload from FrozenOrder (immutable)
    └── Submits to blockchain
```

**Key Principle:** Inventory and job submission use SEPARATE API clients. No shared state.

### Module Structure

```
print_order_web/
├── app.py                    # Slim app factory, blueprints
├── config.py                 # Configuration
├── logging_config.py         # Thread-aware logging
│
├── core/                     # Core infrastructure
│   ├── exceptions.py         # Custom exceptions (fail-fast)
│   ├── dll_manager.py        # DLL lifecycle
│   └── api_client.py         # Thread-safe API wrapper
│
├── models/                   # Immutable data models
│   ├── order.py              # Order, FrozenOrder
│   ├── job_result.py         # JobResult, JobStatus
│   └── inventory.py          # InventorySnapshot
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
│   ├── submit.py             # Job submission
│   ├── confirmation.py       # Results display
│   └── api.py                # AJAX endpoints
│
├── modules/                  # Helper modules
│   ├── estimator.py          # Toner/media estimation
│   ├── pdf_analyzer.py       # PDF analysis
│   ├── printer_config.py     # Printer slot mapping
│   ├── consumable_details.py # Metadata extraction
│   └── i18n.py               # Translation support
│
├── templates/                # Jinja2 templates
├── static/                   # CSS, JS, uploads
└── translations/             # EN/DE language files
```

---

## API Integration

### ConsumableClient API

**API Workflow:**

1. **Initialize**: `ld3s_open()` → context handle (main thread only)
2. **Fetch Template**: `ld3s_new_job(ctx)` → inventory snapshot
3. **Submit Job**: `ld3s_submit_job(ctx, payload)` → job handle
4. **Poll Status**: `ld3s_get_job_status(ctx, handle)` until complete
5. **Cleanup**: `ld3s_close(ctx)` on shutdown

**Memory Management:** All API-returned strings must be freed via `ld3s_free(ctx, ptr)`

---

## Error Handling

### Fail-Fast Behavior

- If DLL not found → Application fails to start
- If DLL init fails → Application fails to start
- No stub mode → Service unavailable without DLL

### Runtime Errors

- `DLLNotFoundError` - ConsumableClient.dll not found
- `ServiceUnavailableError` - DLL initialization failed
- `InventoryNotReadyError` - No inventory data available
- `JobSubmissionError` - Job submission failed
- `InsufficientBalanceError` - Not enough consumables

---

## Troubleshooting

### Issue: Application won't start

**Cause:** DLL not found or initialization failed

**Solution:**
1. Check CONSUMABLE_DLL_PATH in .env
2. Verify DLL file exists at specified path
3. For production builds, DLL should be in `_internal/`

### Issue: "Port 5000 already in use"

**Solution:**
```powershell
# Find and kill process using port
Get-Process -Id (Get-NetTCPConnection -LocalPort 5000).OwningProcess | Stop-Process -Force

# Or use different port by editing app.py
```

### Issue: Jobs fail with "insufficient inventory"

**Cause:** Requested quantity exceeds available inventory

**Solution:**
1. Check current inventory in sidebar
2. Reduce quantity
3. Wait for inventory to be replenished

---

## Flask Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Redirects to demo |
| `/demo` | GET | Home page with upload |
| `/upload` | POST | PDF upload processing |
| `/details` | GET/POST | Job configuration |
| `/review` | GET | Order review |
| `/submit` | POST | Job submission |
| `/processing` | GET | Progress page |
| `/status` | GET | AJAX status polling |
| `/confirmation` | GET | Results display |
| `/start-over` | GET | Reset and start new order |
| `/sidebar_refresh` | GET | AJAX sidebar update |

---

## Code Style

- Python 3.11+
- Type hints required
- Google-style docstrings
- Logging: DEBUG for API calls, INFO for operations, ERROR for failures

---

## Testing

Tests are located in `tests/` folder. Note that full integration testing requires the ConsumableClient DLL.

```powershell
# Run tests
pytest tests/ -v
```

---

## Repository

**GitHub**: https://github.com/LucidDream/PrintOrderWeb

---

**Last Updated:** December 2025
**Python:** 3.11+
**Flask:** 3.0.0
