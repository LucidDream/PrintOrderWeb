# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Print Order Web - Production Build
#
# Build command: pyinstaller --clean --noconfirm print_order_web.spec
#
# This creates a one-folder distribution with all dependencies bundled.
# The ConsumableClient.dll is included from the CCAPIv2.0.0.2 folder.
#
# OUTPUT STRUCTURE:
#   dist/PrintOrderWeb/
#   ├── PrintOrderWeb.exe          # Main executable
#   ├── .env                       # Production config (from .env.production)
#   ├── README_TESTER.md           # Tester documentation
#   ├── TROUBLESHOOTING.md         # Troubleshooting guide
#   ├── sample_pdfs/               # Sample PDF files for testing
#   └── _internal/                 # All bundled dependencies
#       ├── ConsumableClient.dll
#       ├── templates/
#       ├── static/
#       │   └── uploads/           # Upload folder (created post-build)
#       ├── translations/
#       └── ...
#
# ARCHITECTURE:
#   - FAIL-FAST - DLL is required, no stub mode
#   - Inventory service runs in background thread
#   - Job submission uses thread-per-job with complete isolation
#
# MULTIPROCESSING NOTE (December 2025):
#   The reverse_geocoder library uses scipy which internally spawns child processes.
#   app.py calls multiprocessing.freeze_support() at module level to prevent
#   infinite process spawning in the frozen executable. This is CRITICAL.

import os
import shutil
from pathlib import Path

# Paths
PROJECT_ROOT = Path(SPECPATH)
DLL_PATH = PROJECT_ROOT.parent / 'CCAPIv2.0.0.2' / 'ConsumableClient.dll'
ENV_PRODUCTION = PROJECT_ROOT / '.env.production'
DOCS_PATH = PROJECT_ROOT / 'docs'
SAMPLE_PDFS_PATH = PROJECT_ROOT / 'sample_pdfs'

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
        # Include the ConsumableClient DLL
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
        # Reverse geocoder data file (city coordinates database)
        ('.venv/Lib/site-packages/reverse_geocoder', 'reverse_geocoder'),
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

        # Helper modules
        'modules',
        'modules.estimator',
        'modules.pdf_analyzer',
        'modules.i18n',
        'modules.printer_config',
        'modules.consumable_details',
        'modules.image_defaults',

        # Reverse geocoder for location data feature
        'reverse_geocoder',
        'reverse_geocoder.cKDTree_MP',
        'scipy.spatial',
        'scipy.spatial._ckdtree',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        # 'numpy' - REQUIRED for reverse_geocoder (location data feature)
        'pandas',
        # 'scipy' - REQUIRED for reverse_geocoder (location data feature)
        'PIL',
        'cv2',
        'pytest',
        # 'unittest' - REQUIRED for reverse_geocoder
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

# Post-build: Copy additional files and create folders
import atexit

def post_build_setup():
    """Post-build setup: copy files and create required folders."""
    dist_folder = PROJECT_ROOT / 'dist' / 'PrintOrderWeb'

    if not dist_folder.exists():
        return

    # Copy .env.production as .env
    dest_env = dist_folder / '.env'
    shutil.copy2(ENV_PRODUCTION, dest_env)
    print(f"[Post-build] Copied .env.production -> {dest_env}")

    # Copy documentation files
    readme_tester = DOCS_PATH / 'README_TESTER.md'
    if readme_tester.exists():
        shutil.copy2(readme_tester, dist_folder / 'README_TESTER.md')
        print(f"[Post-build] Copied README_TESTER.md")

    troubleshooting = DOCS_PATH / 'TROUBLESHOOTING.md'
    if troubleshooting.exists():
        shutil.copy2(troubleshooting, dist_folder / 'TROUBLESHOOTING.md')
        print(f"[Post-build] Copied TROUBLESHOOTING.md")

    # Copy sample PDFs folder
    if SAMPLE_PDFS_PATH.exists():
        dest_samples = dist_folder / 'sample_pdfs'
        if dest_samples.exists():
            shutil.rmtree(dest_samples)
        shutil.copytree(SAMPLE_PDFS_PATH, dest_samples)
        print(f"[Post-build] Copied sample_pdfs folder")

    # Create uploads folder
    uploads_folder = dist_folder / '_internal' / 'static' / 'uploads'
    uploads_folder.mkdir(parents=True, exist_ok=True)
    print(f"[Post-build] Created uploads folder: {uploads_folder}")

    # Create a placeholder file in uploads to ensure folder is included
    placeholder = uploads_folder / '.gitkeep'
    placeholder.touch()

atexit.register(post_build_setup)
