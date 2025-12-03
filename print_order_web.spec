# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Print Order Web - Production Build (Refactored)
#
# Build command: pyinstaller --clean --noconfirm print_order_web.spec
#
# This creates a one-folder distribution with all dependencies bundled.
# The ConsumableClient.dll from CCAPIv2.0.0.2 is included for production mode.
#
# OUTPUT STRUCTURE:
#   dist/PrintOrderWeb/
#   ├── PrintOrderWeb.exe      # Main executable
#   ├── .env                   # Production config (copied from .env.production)
#   └── _internal/             # All bundled dependencies
#       ├── ConsumableClient.dll
#       ├── templates/
#       ├── static/
#       └── ...
#
# ARCHITECTURE:
#   - NO STUB MODE - DLL is required
#   - Inventory service runs in background thread
#   - Job submission uses thread-per-job with complete isolation

import os
import shutil
from pathlib import Path

# Paths
PROJECT_ROOT = Path(SPECPATH)
DLL_PATH = PROJECT_ROOT.parent / 'CCAPIv2.0.0.2' / 'ConsumableClient.dll'
ENV_PRODUCTION = PROJECT_ROOT / '.env.production'

# Verify DLL exists
if not DLL_PATH.exists():
    raise FileNotFoundError(f"ConsumableClient.dll not found at: {DLL_PATH}")

# Verify production env exists
if not ENV_PRODUCTION.exists():
    raise FileNotFoundError(f".env.production not found at: {ENV_PRODUCTION}")

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[str(PROJECT_ROOT)],
    binaries=[
        # Include the latest ConsumableClient DLL (v2.0.0.2)
        (str(DLL_PATH), '.'),
    ],
    datas=[
        # Flask templates
        ('templates', 'templates'),
        # Static assets (CSS, JS, images)
        ('static', 'static'),
        # Translations for i18n support
        ('translations', 'translations'),
        # Environment example file
        ('.env.example', '.'),
        # Application configuration module
        ('config.py', '.'),
        # Logging configuration module
        ('logging_config.py', '.'),
    ],
    hiddenimports=[
        # Flask and dependencies
        'flask',
        'flask.json',
        'werkzeug',
        'werkzeug.serving',
        'werkzeug.debug',
        'jinja2',
        'markupsafe',
        'click',
        'itsdangerous',
        'pypdf',
        'dotenv',
        'bleach',
        'logging.handlers',

        # Application configuration
        'config',
        'logging_config',

        # Core modules (new architecture)
        'core',
        'core.exceptions',
        'core.dll_manager',
        'core.api_client',

        # Models (new architecture)
        'models',
        'models.order',
        'models.job_result',
        'models.inventory',

        # Services (new architecture)
        'services',
        'services.inventory_service',
        'services.job_service',

        # Routes (new architecture)
        'routes',
        'routes.main',
        'routes.upload',
        'routes.details',
        'routes.review',
        'routes.submit',
        'routes.confirmation',
        'routes.api',

        # Legacy modules (still used)
        'modules',
        'modules.estimator',
        'modules.pdf_analyzer',
        'modules.i18n',
        'modules.printer_config',
        'modules.consumable_details',
        'modules.image_defaults',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
        'pytest',
        'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PrintOrderWeb',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Keep console for logging visibility
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PrintOrderWeb',
)

# Post-build: Copy .env.production to dist folder as .env
# This runs after COLLECT completes
import atexit

def copy_env_file():
    """Copy production .env file to dist folder after build."""
    dist_folder = PROJECT_ROOT / 'dist' / 'PrintOrderWeb'
    dest_env = dist_folder / '.env'
    if dist_folder.exists():
        shutil.copy2(ENV_PRODUCTION, dest_env)
        print(f"[Post-build] Copied .env.production -> {dest_env}")

atexit.register(copy_env_file)
