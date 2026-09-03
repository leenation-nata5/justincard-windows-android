from __future__ import annotations

import argparse
import importlib
from pathlib import Path
import sys
import traceback


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODULES = [
    "justincard.api",
    "justincard.constants",
    "justincard.models",
    "justincard.database",
    "justincard.paths",
    "justincard.scanner_engine",
    "justincard.workers",
    "justincard.ui.theme",
    "justincard.ui.widgets",
    "justincard.ui.search_page",
    "justincard.ui.collection_page",
    "justincard.ui.dashboard_page",
    "justincard.ui.decks_page",
    "justincard.ui.scanner_page",
    "justincard.ui.settings_page",
    "justincard.ui.main_window",
    "justincard.v108_core",
    "justincard.v108_features",
    "justincard.v111_core",
    "justincard.price_service",
    "justincard.v111_features",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return a non-zero exit code when an import fails.",
    )
    args = parser.parse_args()

    if sys.version_info[:2] != (3, 11):
        print(
            f"WARNING: expected Python 3.11, got "
            f"{sys.version_info.major}.{sys.version_info.minor}",
            file=sys.stderr,
        )

    failures: list[str] = []
    for module_name in MODULES:
        try:
            importlib.import_module(module_name)
            print(f"OK import {module_name}", flush=True)
        except BaseException as exc:
            failures.append(module_name)
            print(
                f"FAILED import {module_name}: {type(exc).__name__}: {exc}",
                file=sys.stderr,
                flush=True,
            )
            traceback.print_exc()

    if failures:
        print(
            "IMPORT DIAGNOSTIC FAILED FOR: " + ", ".join(failures),
            file=sys.stderr,
            flush=True,
        )
        # This pre-build probe is diagnostic by default.  The authoritative
        # compatibility gate is the --self-test executed against the built EXE.
        return 1 if args.strict else 0

    print("ALL PRE-BUILD IMPORT DIAGNOSTICS PASSED", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
