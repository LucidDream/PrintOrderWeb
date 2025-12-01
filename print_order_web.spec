# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Print Order Web - Production Build
#
# Build command: pyinstaller --clean --noconfirm print_order_web.spec
#
# This creates a one-folder distribution with all dependencies bundled.
# The ConsumableClient.dll from CCAPIv2.0.0.2 is included for production mode.

import os
from pathlib import Path

# Paths
PROJECT_ROOT = Path(SPECPATH)
DLL_PATH = PROJECT_ROOT.parent / 'CCAPIv2.0.0.2' / 'ConsumableClient.dll'

# Verify DLL exists
if not DLL_PATH.exists():
    raise FileNotFoundError(f"ConsumableClient.dll not found at: {DLL_PATH}")

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
    ],
    hiddenimports=[
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
