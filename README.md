# Print Order Web Application

A production-ready Flask web application for blockchain-enabled print job ordering with real ConsumableClient API v2.0.0.1 integration.

## 🎯 Overview

This application provides a simple browser-based interface for submitting print jobs to a blockchain-based consumable tracking system. It supports both development (stub mode) and production (real blockchain) deployment scenarios.

**Key Features:**
- ✅ Dead-simple 4-step workflow (Upload → Details → Review → Submit)
- ✅ Real-time blockchain inventory integration
- ✅ Quality-aware consumable estimation (draft/standard/high)
- ✅ Live progress updates with AJAX polling (no page blocking)
- ✅ Intelligent error handling with graceful fallbacks
- ✅ Automatic cache invalidation after job submission
- ✅ Comprehensive transaction tracking with blockchain signatures
- ✅ Cross-platform development support (stub mode works anywhere)
- ✅ Production-ready error handling and validation
- ✅ Production-verified blockchain token spending (toner + media)
- ✅ **Authenticated UI with ink verification** - Visual counterfeit detection
- ✅ **Comprehensive metadata extraction** - 17+ fields per consumable from blockchain
- ✅ **Multi-language support** - English and German translations (40+ fields)
- ✅ **Unified sidebar workflow** - Persistent inventory sidebar throughout entire job workflow
- ✅ **API-driven verification** - Ink slot verification based on actual blockchain data presence
- ✅ **Intelligent cache refresh** - Critical decision points force fresh inventory data

**Status:** Phase 1 Complete (100%) + Phase 2 Complete (100%) + Authenticated UI Complete (100%) + Workflow Integration Complete (100%) - Production-ready with comprehensive metadata display

---

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [Configuration](#configuration)
3. [Running from Source](#running-from-source)
4. [Testing](#testing)
5. [Deployment Options](#deployment-options)
6. [Architecture](#architecture)
7. [API Integration](#api-integration)
8. [Error Handling](#error-handling)
9. [Troubleshooting](#troubleshooting)

---

## 🚀 Quick Start

### Option 1: Development Mode (Stub - Works on Any Platform)

```bash
cd print_order_web
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create configuration file
cp .env.example .env

# Run the application
python app.py
```

Visit http://127.0.0.1:5000 to use the application.

### Option 2: Production Mode (Real Blockchain - Windows Only)

```bash
# Follow same setup as Option 1, then:

# Edit .env file and set:
ENABLE_API_MODE=true
CONSUMABLE_DLL_PATH=../CCAPIv2.0.0.1/ConsumableClient.dll

# Run the application
python app.py
```

The application will connect to the real ConsumableClient.dll and submit jobs to the blockchain.

---

## ⚙️ Configuration

### Environment Variables (.env file)

```bash
# Flask Application Settings
FLASK_SECRET_KEY=change-me-to-random-secure-key  # IMPORTANT: Change in production!
FLASK_ENV=development                             # development or production
FLASK_DEBUG=1                                     # 1 for debug, 0 for production

# Upload Configuration
UPLOAD_FOLDER=./print_order_web/static/uploads   # PDF upload directory

# ConsumableClient API Configuration
ENABLE_API_MODE=false                             # true = real blockchain, false = stub
CONSUMABLE_DLL_PATH=../CCAPIv2.0.0.1/ConsumableClient.dll  # Path to DLL
```

### Configuration Modes

| Mode | ENABLE_API_MODE | Platform | Use Case |
|------|----------------|----------|----------|
| **Stub** | `false` | Any | Development, testing, demo |
| **Production** | `true` | Windows only | Real blockchain integration |

---

## 💻 Running from Source

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- Virtual environment support
- **For production mode**: Windows OS with ConsumableClient.dll v2.0.0.1

### Step-by-Step Setup

**1. Clone and Navigate:**
```bash
cd print_order_web
```

**2. Create Virtual Environment:**
```bash
python -m venv .venv
```

**3. Activate Virtual Environment:**

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
.venv\Scripts\activate.bat
```

**macOS/Linux:**
```bash
source .venv/bin/activate
```

**4. Install Dependencies:**
```bash
pip install -r requirements.txt
```

**5. Configure Application:**
```bash
# Copy example configuration
cp .env.example .env

# Edit .env with your preferred text editor
# Windows:
notepad .env
# macOS/Linux:
nano .env
```

**6. Run Application:**
```bash
python app.py
```

**7. Access Application:**
Open browser to http://127.0.0.1:5000

---

## 🧪 Testing

### Run All Tests

```bash
# Activate virtual environment first
pytest tests/ -v
```

### Run Specific Test Suites

```bash
# Inventory service tests (14 tests)
pytest tests/test_inventory.py -v

# Job processor tests (18 tests)
pytest tests/test_job_processor.py -v

# API client tests (6 critical tests - others require GUI context)
pytest tests/test_api_client.py -v
```

### Test Coverage

```bash
pytest --cov=modules tests/
```

**Expected Results:**
- ✅ 32/32 core business logic tests passing
- ⚠️ Some API integration tests fail with wxWidgets DDE error (expected - requires GUI context)

---

## 📦 Deployment Options

### Option 1: Run Directly with Python (Development/Testing)

**Pros:**
- Easy to update
- Full error messages
- Hot reload during development

**Cons:**
- Requires Python installation
- Not portable

**Usage:**
```bash
python app.py
```

### Option 2: Standalone Executable with PyInstaller (Portable)

Create a single-file executable that doesn't require Python installation.

**Step 1: Install PyInstaller**
```bash
pip install pyinstaller
```

**Step 2: Create Spec File**

Create `print_order_web.spec`:
```python
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('.env.example', '.'),
        ('../CCAPIv2.0.0.1/ConsumableClient.dll', '.'),  # Include DLL if available
    ],
    hiddenimports=['flask', 'pypdf', 'dotenv'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PrintOrderWeb',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Set to False to hide console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add .ico file path if you have one
)
```

**Step 3: Build Executable**
```bash
pyinstaller --clean --noconfirm print_order_web.spec
```

**Step 4: Package for Distribution**

The executable will be in `dist/` directory. Create a distribution package:

```
PrintOrderWeb/
├── PrintOrderWeb.exe           # Main executable
├── ConsumableClient.dll        # API library (if using real blockchain)
├── .env                        # Configuration file (create from .env.example)
├── static/                     # Created automatically for uploads
└── README.txt                  # Instructions for users
```

**Usage:**
```bash
# From dist directory:
.\PrintOrderWeb.exe

# Or double-click PrintOrderWeb.exe
# Then open browser to http://127.0.0.1:5000
```

### Option 3: Docker Container (Cross-Platform)

**Create Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create upload directory
RUN mkdir -p static/uploads

# Expose port
EXPOSE 5000

# Set environment variables
ENV FLASK_ENV=production
ENV FLASK_DEBUG=0

# Run application
CMD ["python", "app.py"]
```

**Build and Run:**
```bash
# Build image
docker build -t print-order-web .

# Run container
docker run -p 5000:5000 -v $(pwd)/static/uploads:/app/static/uploads print-order-web

# Access at http://localhost:5000
```

### Option 4: Windows Service (Production Server)

Use `nssm` (Non-Sucking Service Manager) to run as Windows service:

```bash
# Install nssm
choco install nssm  # Or download from nssm.cc

# Create service
nssm install PrintOrderWeb "C:\path\to\.venv\Scripts\python.exe" "C:\path\to\app.py"

# Configure service
nssm set PrintOrderWeb AppDirectory "C:\path\to\print_order_web"
nssm set PrintOrderWeb DisplayName "Print Order Web Application"
nssm set PrintOrderWeb Description "Blockchain-enabled print ordering system"
nssm set PrintOrderWeb Start SERVICE_AUTO_START

# Start service
nssm start PrintOrderWeb

# Check status
nssm status PrintOrderWeb
```

---

## 🏗️ Architecture

### Thread-Per-Job Architecture (November 2025 Refactoring)

The application uses a **Thread-Per-Job architecture** that leverages ConsumableClient API v2.0.0.1 multi-threading support for concurrent, non-blocking job processing.

```
┌─────────────────────────────────────────────────────────┐
│                    Web Browser                          │
│  Upload PDF → Details → Review → Submit → Confirmation │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP/AJAX (non-blocking)
                     ▼
┌─────────────────────────────────────────────────────────┐
│         Flask Application (Main Thread)                 │
│  ┌──────────────────────────────────────────────────┐  │
│  │ DLL Context (ld3s_open - main thread only)      │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Background Inventory Thread (30s auto-refresh)  │◄─┼─ Dedicated thread
│  │  └─ ThreadSafeAPIClient instance                │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Job Thread 1 (independent processing)           │◄─┼─ Spawned per job
│  │  ├─ ThreadSafeAPIClient (shared context)        │  │
│  │  ├─ Fetch fresh template                        │  │
│  │  ├─ Build payload (no deep copy!)               │  │
│  │  ├─ Submit job (non-blocking)                   │  │
│  │  ├─ Poll status (250ms intervals)               │  │
│  │  └─ Store result (thread-safe)                  │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Job Thread 2 (concurrent processing)            │◄─┼─ Multiple jobs
│  │  └─ Same workflow, independent data             │  │    run in parallel
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
             │
    ┌────────┴────────┐
    ▼                 ▼
┌──────────────┐  ┌──────────────────┐
│  Stub Mode   │  │ ConsumableClient │
│  (Dev/Test)  │  │  API v2.0.0.1    │
└──────────────┘  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │   Blockchain     │
                  │   Transactions   │
                  └──────────────────┘
```

### Architecture Benefits

**✅ Eliminated Deep Copy:**
- Each thread owns its data exclusively
- No shared state contamination
- No expensive `copy.deepcopy()` operations

**⚡ Non-Blocking Submission:**
- Jobs run in dedicated threads
- Flask routes return immediately
- AJAX polling for real-time updates

**🔄 Automatic Inventory Refresh:**
- Background thread updates every 30 seconds
- No manual refresh needed
- Independent from job processing

**🧵 Thread-Safe Operations:**
- Main thread handles DLL init/cleanup
- Worker threads share DLL context safely
- Thread-local API client instances
- Locked result storage

### Key Components

**1. API Client (`modules/api_client_threaded.py`)** *(New - Nov 2025)*
- Thread-safe wrapper for ConsumableClient.dll v2.0.0.1
- Each thread creates own client instance with shared context
- Provides stub implementation for development
- Memory management with `ld3s_free()`

**2. Inventory Service (`modules/inventory_threaded.py`)** *(New - Nov 2025)*
- Runs in dedicated background thread
- Fetches blockchain inventory every 30 seconds automatically
- Thread-safe cache with locks for concurrent access
- Graceful fallback on API failure

**3. Job Processor (`modules/job_processor.py`)** *(Simplified - Nov 2025)*
- Builds blockchain job payloads
- Parses transaction results
- No longer handles submission (moved to job threads)
- 49% code reduction (674 → 344 lines)

**4. Flask Routes (`app.py`)** *(Refactored - Nov 2025)*
- `/` - Redirects to demo page (home)
- `/demo` - Home page with functional upload form
- `/upload` - PDF upload processing
- `/details` - Job configuration with inventory validation and forced cache refresh on POST
- `/review` - Order review with sidebar
- `/submit` - Job submission with error handling
- `/processing` - Real-time progress updates with AJAX polling
- `/status` - AJAX endpoint for job status polling
- `/confirmation` - Transaction results
- `/start-over` - Clear session and invalidate cache for new order
- `/health` - Health check endpoint

---

## 🔌 API Integration

### ConsumableClient API v2.0.0.1

**API Workflow:**

1. **Initialize**: `ld3s_open()` → context handle
2. **Fetch Template**: `ld3s_new_job(ctx)` → inventory snapshot
3. **Submit Job**: `ld3s_submit_job(ctx, payload)` → job handle
4. **Poll Status**: `ld3s_get_job_status(ctx, handle)` until complete
5. **Parse Results**: Extract transaction IDs and signatures
6. **Cleanup**: `ld3s_close(ctx)` on shutdown

**Key Features:**
- Job handles for concurrent processing
- Memory management with `ld3s_free()`
- Error reporting via `ld3s_get_last_error()`
- Thread-safe operations (except init/cleanup)

**Stub vs Real Behavior:**

| Feature | Stub Mode | Real API Mode |
|---------|-----------|---------------|
| Inventory | Hardcoded values | Live blockchain data |
| Job Submit | Immediate success | Actual blockchain tx |
| Transaction IDs | Simulated | Real blockchain sigs |
| Performance | Instant | ~1-5 seconds |
| Platform | Any | Windows only |

---

## ⚠️ Error Handling

### Three-Tier Fallback Strategy

**1. Normal Operation:**
- Fresh blockchain inventory fetched
- Jobs submit to real blockchain
- Transaction IDs returned

**2. Stale Cache (API unavailable but cache exists):**
- Warning displayed to user
- Last known inventory shown
- Jobs allowed with warning

**3. Complete Failure (no cache available):**
- Error message displayed
- Minimal fallback inventory shown
- Job submission blocked

### Error Message Enhancement

**Insufficient Inventory:**
```
Before: "Job processing failed"
After:  "Insufficient inventory to complete this job. One or more
         consumables (toner or media) have been depleted. Please
         check current inventory levels and reduce quantity if needed."
```

**Timeout:**
```
Before: "Job processing failed"
After:  "Job submission timed out. The blockchain may be busy.
         Please try again."
```

### Validation

- ✅ PDF file type and size validation
- ✅ Quantity range validation
- ✅ Media availability validation
- ✅ Inventory balance checks
- ✅ Session state validation

---

## 🐛 Troubleshooting

### Issue: "RuntimeError: Not implemented"

**Cause:** API mode enabled but DLL not accessible

**Solution:**
1. Check CONSUMABLE_DLL_PATH in .env
2. Verify DLL file exists
3. Or disable API mode: `ENABLE_API_MODE=false`

### Issue: wxWidgets DDE Error in Tests

**Cause:** ConsumableClient.dll requires GUI context

**Solution:** This is expected. Use Flask app for real API testing, not pytest.

### Issue: "Using cached data" warning

**Cause:** Blockchain unavailable, using stale inventory

**Solution:**
1. Check blockchain connectivity
2. Verify DLL path is correct
3. Application continues with cached data

### Issue: Jobs fail with "insufficient inventory"

**Cause:** Cache shows old data, actual inventory depleted

**Solution:**
1. Wait 30 seconds for cache to expire
2. Or restart application to clear cache
3. Check current inventory on details page

**Note:** As of November 6, 2025, this issue is fixed via forced cache refresh on estimate generation. See CACHE_REFRESH_FIX.md for details.

### Issue: Port 5000 already in use

**Solution:**
```bash
# Windows:
netstat -ano | findstr :5000
taskkill /PID <pid> /F

# macOS/Linux:
lsof -ti:5000 | xargs kill -9

# Or use different port:
# Edit app.py: app.run(port=5001)
```

---

## 📊 Project Status

**Phase 1: Core API Integration** ✅ COMPLETE (100%)
- ✅ Milestone 1.1: API Client Implementation
- ✅ Milestone 1.2: Inventory Service Update
- ✅ Milestone 1.3: Real Job Processor
- ✅ Milestone 1.4: Error Handling & Validation

**Phase 2: Enhanced Estimation & UX** ✅ COMPLETE (100%)
- ✅ Milestone 2.1: Enhanced Estimator with Quality Settings
- ✅ Milestone 2.2: AJAX Status Polling (COMPLETE - Nov 4, 2025)

**Test Results:**
- 32/32 business logic tests passing (100%)
- Comprehensive error handling implemented
- Production-ready blockchain integration
- Input validation and sanitization complete
- Comprehensive logging configuration
- Real-time progress updates functional

**Production Readiness:**
- ✅ All Phase 1 & 2 success criteria met
- ✅ Security hardening (XSS protection)
- ✅ User-friendly error messages
- ✅ Detailed logging with rotation
- ✅ Modern async UX with AJAX polling
- ✅ Ready for production deployment

**Next Steps (Optional Enhancements):**
- Phase 3: Production deployment configuration
- Phase 4: Multi-job management & advanced features
- Future: WebSocket upgrades, job queuing, notifications

---

## 📚 Additional Resources

**Documentation:**
- MILESTONE_1.1_COMPLETE.md - API client implementation
- MILESTONE_1.2_COMPLETE.md - Inventory service updates
- MILESTONE_1.3_COMPLETE.md - Job processor implementation
- MILESTONE_1.4_COMPLETE.md - Error handling and validation
- MILESTONE_2.1_COMPLETE.md - Quality-aware estimation
- MILESTONE_2.2_COMPLETE.md - AJAX status polling
- CACHE_REFRESH_FIX.md - Cache refresh bug fix (November 6, 2025)
- AUTHENTICATED_UI_IMPLEMENTATION.md - Authenticated sidebar implementation
- PRINT_ORDER_WEB_IMPLEMENTATION_PLAN.md - Complete project roadmap

**Related Projects:**
- Main PrintSimulator application (../src/print_simulator/)
- ConsumableClient API v2.0.0.1 (../CCAPIv2.0.0.1/)

---

## 🤝 Contributing

This is part of the PS-Modular print simulation project. See CLAUDE.md in project root for development guidelines.

**Development Workflow:**
1. Create feature branch
2. Make changes with tests
3. Run full test suite
4. Update documentation
5. Submit for review

---

## 📝 License

See project root for license information.

---

**Last Updated:** November 17, 2025
**Version:** Phase 1 & 2 Complete + Thread-Per-Job Architecture Refactoring
**Python:** 3.11+
**Flask:** 3.0.0
**API:** ConsumableClient v2.0.0.1 (Multi-Threading)
