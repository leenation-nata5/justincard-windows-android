from __future__ import annotations

import hashlib
import importlib.util
import marshal
from pathlib import Path
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "recovered" / "PYZ.pyz"
EXPECTED_PYTHON = (3, 11)
SKIP = {
    "justincard",
    "justincard.ui",
    "justincard.ui.search_page",
    "justincard.version",
}
EXPECTED_MODULES = {
    "justincard.api",
    "justincard.constants",
    "justincard.database",
    "justincard.models",
    "justincard.paths",
    "justincard.scanner_engine",
    "justincard.ui.collection_page",
    "justincard.ui.dashboard_page",
    "justincard.ui.decks_page",
    "justincard.ui.main_window",
    "justincard.ui.scanner_page",
    "justincard.ui.settings_page",
    "justincard.ui.theme",
    "justincard.ui.widgets",
    "justincard.utils",
    "justincard.workers",
}


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"ERROR: {message}")


def main() -> int:
    if sys.version_info[:2] != EXPECTED_PYTHON:
        fail(
            f"Python {EXPECTED_PYTHON[0]}.{EXPECTED_PYTHON[1]} wird benötigt; "
            f"gefunden wurde {sys.version_info.major}.{sys.version_info.minor}."
        )
    if not ARCHIVE.is_file():
        fail(f"Recovery-Archiv fehlt: {ARCHIVE}")

    raw = ARCHIVE.read_bytes()
    if raw[:4] != b"PYZ\0" or len(raw) < 12:
        fail("Ungültiges PyInstaller-PYZ-Archiv.")
    archive_magic = raw[4:8]
    if archive_magic != importlib.util.MAGIC_NUMBER:
        fail(
            "Bytecode-Version passt nicht zum Interpreter. "
            f"Archiv={archive_magic.hex()} Python={importlib.util.MAGIC_NUMBER.hex()}"
        )

    toc_offset = struct.unpack("!I", raw[8:12])[0]
    toc = marshal.loads(raw[toc_offset:])
    entries = dict(toc)
    available = {name for name in entries if name.startswith("justincard") and name not in SKIP}
    missing = EXPECTED_MODULES - available
    if missing:
        fail(f"Recovery-Archiv unvollständig: {sorted(missing)}")

    written: list[Path] = []
    for module in sorted(EXPECTED_MODULES):
        _kind, position, length = entries[module]
        marshalled_code = zlib.decompress(raw[position : position + length])
        # Legacy/sourceless .pyc header: magic + flags + mtime + source-size.
        pyc = importlib.util.MAGIC_NUMBER + struct.pack("<III", 0, 0, 0) + marshalled_code
        target = ROOT / (module.replace(".", "/") + ".pyc")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(pyc)
        written.append(target)

    digest = hashlib.sha256(raw).hexdigest()
    print(f"Recovery archive SHA256: {digest}")
    print(f"Generated {len(written)} Python 3.11 legacy modules:")
    for target in written:
        print(f" - {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
