# -*- mode: python ; coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

ROOT = Path(SPECPATH)
TESSERACT_DIR = os.environ.get("TESSERACT_DIR", "").strip()

hiddenimports = [
    "cv2",
    "numpy",
    "pytesseract",
    "rapidfuzz",
    "certifi",
    "PIL",
    # Recovered application modules. Listing them explicitly keeps the build
    # deterministic even though their source was unavailable in the upload.
    "justincard.api",
    "justincard.constants",
    "justincard.database",
    "justincard.models",
    "justincard.paths",
    "justincard.scanner_engine",
    "justincard.utils",
    "justincard.workers",
    "justincard.ui.collection_page",
    "justincard.ui.dashboard_page",
    "justincard.ui.decks_page",
    "justincard.ui.main_window",
    "justincard.ui.scanner_page",
    "justincard.ui.search_page",
    "justincard.ui.settings_page",
    "justincard.ui.theme",
    "justincard.ui.widgets",
    "justincard.ui.toast",
    "justincard.v108_core",
    "justincard.v108_features",
    "justincard.v111_core",
    "justincard.v111_features",
    "justincard.v110_core",
    "justincard.v110_features",
    "justincard.cloud_sync",
    "justincard.v120_features",
    "justincard.v121_core",
    "justincard.v121_features",
    "justincard.v123_core",
    "justincard.v123_features",
    "justincard.price_service",
]
hiddenimports += collect_submodules("pytesseract")
hiddenimports += collect_submodules("rapidfuzz")
hiddenimports += collect_submodules("googleapiclient")
hiddenimports += collect_submodules("google_auth_oauthlib")
hiddenimports += collect_submodules("google.auth")
hiddenimports += collect_submodules("google.oauth2")
hiddenimports += collect_submodules("oauthlib")
hiddenimports += collect_submodules("requests_oauthlib")
hiddenimports += collect_submodules("httplib2")

datas = [
    (str(ROOT / "assets"), "assets"),
]
datas += collect_data_files("certifi")

binaries = []
binaries += collect_dynamic_libs("cv2")

if TESSERACT_DIR:
    tess = Path(TESSERACT_DIR)
    if tess.is_dir():
        datas.append((str(tess), "tesseract"))
    else:
        print(f"WARNING: TESSERACT_DIR does not exist: {tess}")
else:
    print("WARNING: TESSERACT_DIR is empty; OCR will rely on a system Tesseract installation.")

analysis = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=sorted(set(hiddenimports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="JustInCard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "assets" / "app_icon.ico"),
)

coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="JustInCard",
)
