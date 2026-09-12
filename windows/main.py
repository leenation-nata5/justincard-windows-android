from __future__ import annotations

import importlib
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
import traceback

APP_SELF_TEST_FLAG = "--self-test"
APP_UI_SELF_TEST_FLAG = "--ui-self-test"

SELF_TEST_MODULES = (
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
    "justincard.v110_core",
    "justincard.price_service",
    "justincard.v111_features",
    "justincard.v110_features",
    "justincard.cloud_sync",
    "justincard.v120_features",
    "justincard.v121_core",
    "justincard.v121_features",
    "justincard.v123_core",
    "justincard.v123_features",
    "justincard.v128_features",
)


def configure_logging(log_directory: str | Path) -> None:
    log_dir = Path(log_directory)
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "justincard.log",
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])


def _self_test_emit(message: str, *, error: bool = False) -> None:
    """Write self-test diagnostics safely for console and windowed builds."""
    line = str(message)
    stream = sys.stderr if error else sys.stdout
    if stream is not None:
        try:
            print(line, file=stream, flush=True)
        except Exception:
            pass

    log_path = os.environ.get("JIC_SELFTEST_LOG", "").strip()
    if log_path:
        try:
            path = Path(log_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.write("\n")
        except Exception:
            # The exit code remains the authoritative self-test result.
            pass


def run_self_test() -> int:
    """Import packaged modules without opening the GUI.

    The production executable is built with ``console=False``.  Therefore the
    self-test must not rely on stdout/stderr being present.  GitHub Actions sets
    JIC_SELFTEST_LOG to collect diagnostics from the windowed executable.
    """
    _self_test_emit("Just InCard packaged self-test")
    _self_test_emit(f"Python: {sys.version}")

    failures: list[tuple[str, BaseException]] = []
    for module_name in SELF_TEST_MODULES:
        try:
            importlib.import_module(module_name)
            _self_test_emit(f"OK import {module_name}")
        except BaseException as exc:
            failures.append((module_name, exc))
            _self_test_emit(
                f"FAILED import {module_name}: {type(exc).__name__}: {exc}",
                error=True,
            )
            _self_test_emit(traceback.format_exc(), error=True)

    if failures:
        _self_test_emit(
            f"SELF-TEST FAILED: {len(failures)} module(s)",
            error=True,
        )
        return 20

    try:
        from dataclasses import fields
        from justincard.models import SearchFilters
        from justincard.search_core import (
            DISPLAY_LANGUAGES,
            english_set_query,
            infer_set_language,
            localized_collection_print,
        )
        from justincard.v108_features import install_v108_patches
        from justincard.v128_features import install_v128_patches

        install_v108_patches()
        install_v128_patches()

        field_names = {field.name for field in fields(SearchFilters)}
        required = {"language", "set_query", "sort_by", "limit", "quick_text", "passcode"}
        missing = required - field_names
        if missing:
            raise RuntimeError(f"SearchFilters fields missing: {sorted(missing)}")

        checks = {
            "LOB-DE001": "de",
            "LOB-EN001": "en",
            "ABC-TC012": "zh-tw",
            "CORI-DE": "de",
        }
        for value, expected in checks.items():
            actual = infer_set_language(value)
            if actual != expected:
                raise RuntimeError(
                    f"Language inference failed for {value}: expected {expected}, got {actual}"
                )

        if english_set_query("BLMR-DE001") != "BLMR-EN001":
            raise RuntimeError("v1.2.6 EN reference set-code normalization failed")
        collection_card, collection_print = localized_collection_print(
            {"id": 1, "name": "Self Test", "_language": "en"},
            {"set_code": "BLMR-EN001", "set_name": "Self Test", "set_rarity": "Common"},
            "BLMR-DE001",
        )
        if collection_card.get("_language") != "de" or (collection_print or {}).get("set_code") != "BLMR-DE001":
            raise RuntimeError("v1.2.6 collection language restoration failed")

        if not any(code == "all" for code, _ in DISPLAY_LANGUAGES):
            raise RuntimeError("Language option 'all' missing")
        if not any(code == "auto" for code, _ in DISPLAY_LANGUAGES):
            raise RuntimeError("Language option 'auto' missing")

        # v1.0.8 functional smoke test: schema migration + real placeholder flow.
        import tempfile
        from justincard.database import CardDatabase
        from justincard.v108_core import is_placeholder_item, normalize_backup_payload, visibility_preset
        from justincard.v111_core import normalize_profiles, profile_for
        from justincard.v110_core import artwork_label
        from justincard.cloud_sync import (MONSTER_HEADERS, MONSTER_SHEET, category_sheet_rows, deck_sheet_map, merge_collection_records, normalize_spreadsheet_id, parse_raw_sheet_rows, raw_sheet_rows)
        from justincard.price_service import estimate_price
        from justincard.v123_core import resolved_deck_zone

        normalized = normalize_backup_payload({
            "sammlung": [{"id": 12345678, "name": "Self Test", "count": 1}]
        })
        if normalized["collection"][0]["quantity"] != 1:
            raise RuntimeError("Legacy backup normalization failed")
        if not all(visibility_preset("all").values()):
            raise RuntimeError("Display visibility preset failed")
        profiles = normalize_profiles(None, {"atk": False, "def": True})
        if profile_for(profiles, "search_results").get("atk") is not False:
            raise RuntimeError("v1.0.11 profile migration failed")
        price_test = estimate_price({
            "id": 12345678,
            "card_sets": [{"set_code": "TEST-EN001", "set_rarity": "Ultra Rare", "set_price": "10.00"}],
            "card_prices": [{"cardmarket_price": "5.00"}],
        }, print_code="TEST-EN001", rarity="Ultra Rare", language="en", condition="Near Mint", live=False)
        if price_test.print_price_usd != 10.0 or price_test.condition_factor != 1.0:
            raise RuntimeError("v1.0.11 price estimation core failed")
        art_test = artwork_label({
            "card_images": [
                {"image_url": "https://img/1.jpg"},
                {"image_url": "https://img/2.jpg"},
            ],
            "artwork_url": "https://img/2.jpg",
        }, "collection")
        if "Alt Art" not in art_test:
            raise RuntimeError("v1.1.0 artwork labeling failed")
        cloud_sample = [{
            "collection_key": "cloud-test",
            "print_code": "TEST-DE001",
            "rarity": "Common",
            "language": "de",
            "quantity": 2,
            "condition": "Near Mint",
            "updated_at": 10.0,
            "card": test_card if "test_card" in locals() else {"id": 12345678, "name": "Cloud Test"},
        }]
        parsed_cloud = parse_raw_sheet_rows(raw_sheet_rows(cloud_sample))
        if len(parsed_cloud) != 1 or int(parsed_cloud[0].get("quantity") or 0) != 2:
            raise RuntimeError("v1.2.0 Google Sheets serialization failed")
        merged_cloud = merge_collection_records(cloud_sample, [{**cloud_sample[0], "quantity": 3, "updated_at": 20.0}])
        if int(merged_cloud[0].get("quantity") or 0) != 3:
            raise RuntimeError("v1.2.0 cloud merge failed")
        if normalize_spreadsheet_id("https://docs.google.com/spreadsheets/d/abcDEF_12345678901234567890/edit") != "abcDEF_12345678901234567890":
            raise RuntimeError("v1.2.0 sheet URL parser failed")
        v122_sample = [{
            **cloud_sample[0],
            "card": {
                "id": 12345678,
                "name": "Cloud Volltest",
                "type": "Effect Monster",
                "race": "Warrior",
                "attribute": "LIGHT",
                "atk": 1000,
                "def": 1000,
                "level": 4,
                "desc": "Vollständiger Effekttext",
            },
        }]
        template_tabs = category_sheet_rows(v122_sample)
        if MONSTER_SHEET not in template_tabs or tuple(template_tabs[MONSTER_SHEET][0]) != MONSTER_HEADERS:
            raise RuntimeError("v1.2.6 Google Sheets template export failed")
        if any("Vollständiger Effekttext" in str(cell) for row in template_tabs[MONSTER_SHEET] for cell in row):
            raise RuntimeError("v1.2.6 template leaked effect text")
        tuner_sample = [{**v122_sample[0], "collection_key": "tuner-test", "card": {**v122_sample[0]["card"], "type": "Tuner Monster"}}]
        tuner_tabs = category_sheet_rows(tuner_sample)
        if tuner_tabs[MONSTER_SHEET][1][4] != "Empfänger" or "Empfänger" in tuner_tabs:
            raise RuntimeError("v1.2.6 Empfänger category mapping failed")
        if resolved_deck_zone({"type": "Link Monster", "frameType": "link"}, "main") != "extra":
            raise RuntimeError("v1.2.3 automatic Extra Deck routing failed")
        if resolved_deck_zone({"type": "Effect Monster", "frameType": "effect"}, "extra") != "main":
            raise RuntimeError("v1.2.3 automatic Main Deck routing failed")
        deck_tabs = deck_sheet_map([{
            "deck_id": "selftest-deck",
            "name": "Self Test Deck",
            "cards": [{**v122_sample[0], "zone": "main", "quantity": 1}],
        }])
        if "Self Test Deck" not in deck_tabs:
            raise RuntimeError("v1.2.6 deck template sheet generation failed")

        with tempfile.TemporaryDirectory(prefix="jic-selftest-") as temp_dir:
            test_db = CardDatabase(Path(temp_dir) / "v108.sqlite3")
            with test_db.connect() as connection:
                deck_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(deck_cards)").fetchall()}
            if not {"is_placeholder", "source_collection_key"}.issubset(deck_columns):
                raise RuntimeError(f"v1.0.8 deck schema migration missing: {sorted(deck_columns)}")

            test_card = {
                "id": 12345678,
                "name": "Just InCard Self Test",
                "desc": "",
                "type": "Effect Monster",
                "race": "Warrior",
                "attribute": "LIGHT",
                "atk": 1000,
                "def": 1000,
                "level": 4,
                "card_sets": [{
                    "set_code": "TEST-DE001",
                    "set_name": "Self Test Set",
                    "set_rarity": "Common",
                }],
                "card_images": [],
                "_language": "de",
            }
            test_print = {
                "set_code": "TEST-DE001",
                "set_name": "Self Test Set",
                "set_rarity": "Common",
            }
            test_db.add_to_collection(test_card, test_print, 1)
            collection_key = test_db.collection_key(test_card, test_print, "")
            deck_id = test_db.create_deck("Self Test Deck", "")
            test_db.add_deck_card(deck_id, collection_key, "main")
            test_db.add_deck_card(deck_id, collection_key, "main", allow_placeholder=True)
            test_rows = test_db.deck_cards(deck_id)
            if sum(1 for row in test_rows if is_placeholder_item(row)) != 1:
                raise RuntimeError("Deck placeholder persistence test failed")
    except BaseException:
        _self_test_emit(traceback.format_exc(), error=True)
        _self_test_emit("SELF-TEST FAILED: search compatibility", error=True)
        return 21

    _self_test_emit("SELF-TEST PASSED")
    return 0


def run_ui_self_test() -> int:
    """Construct the complete main window off-screen and close it again.

    The normal packaged self-test intentionally imports modules without building
    the GUI.  This second test catches Qt/PySide runtime compatibility failures
    that only happen while widgets are being created (for example enum/userData
    handling in the v1.0.8 sort bars).
    """
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    _self_test_emit("Just InCard packaged UI self-test")
    try:
        import tempfile
        from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QSpinBox

        from justincard.database import CardDatabase
        from justincard.paths import ensure_data_directories
        from justincard.ui.collection_page import CollectionPage
        from justincard.ui.main_window import MainWindow
        from justincard.ui.search_page import SearchPage
        from justincard.ui.scanner_page import ScannerPage
        from justincard.v108_features import install_v108_patches
        from justincard.v128_features import install_v128_patches

        install_v108_patches()
        install_v128_patches()
        app = QApplication.instance()
        if app is None:
            app = QApplication(["JustInCard", APP_UI_SELF_TEST_FLAG])

        directories = ensure_data_directories()
        with tempfile.TemporaryDirectory(prefix="jic-ui-selftest-") as temp_dir:
            database = CardDatabase(Path(temp_dir) / "ui-selftest.sqlite3")
            value_card = {
                "id": 87654321,
                "name": "Collection Value Self Test",
                "desc": "Self-test effect text",
                "type": "Effect Monster",
                "race": "Warrior",
                "attribute": "LIGHT",
                "atk": 1000,
                "def": 1000,
                "level": 4,
                "card_sets": [{
                    "set_code": "VAL-EN001",
                    "set_name": "Value Test Set",
                    "set_rarity": "Ultra Rare",
                    "set_price": "10.00",
                }],
                "card_prices": [{"cardmarket_price": "8.00"}],
                "card_images": [],
                "_language": "en",
            }
            value_print = {
                "set_code": "VAL-EN001",
                "set_name": "Value Test Set",
                "set_rarity": "Ultra Rare",
            }
            database.add_to_collection(value_card, value_print, 2)
            window = MainWindow(database, directories)
            window.show()
            app.processEvents()

            # Exercise the exact collection path that previously crashed after
            # refresh/delete when the current selection becomes None.
            collection_pages = window.findChildren(CollectionPage)
            if not collection_pages:
                raise RuntimeError("UI self-test could not resolve CollectionPage")
            for page in collection_pages:
                page.refresh()
                page._show_item(None)
                model = page.table.model()
                columns = tuple(getattr(model, "COLUMNS", ())) if model is not None else ()
                keys = {str(item[0]) for item in columns if isinstance(item, tuple) and item}
                if "market_value" not in keys:
                    raise RuntimeError("Collection market-value column missing")
                if "purchase_price" in keys or "flags" in keys:
                    raise RuntimeError("Removed collection columns are still active")
                for check in page.findChildren(QCheckBox):
                    text = str(check.text() or "").casefold()
                    if ("wunsch" in text or "tausch" in text) and check.isVisible():
                        raise RuntimeError(f"Removed collection checkbox still visible: {check.text()}")
                visible_labels = [
                    str(label.text() or "")
                    for label in page.findChildren(QLabel)
                    if label.isVisible()
                ]
                if any("tausch" in value.casefold() or "trade" in value.casefold() for value in visible_labels):
                    raise RuntimeError("Legacy trade stock is still visible in collection summary")
                if not any(value.strip() == "Geschätzter Sammlungswert" for value in visible_labels):
                    raise RuntimeError("Estimated collection-total title missing")
                value_labels = [value for value in visible_labels if value.strip().endswith("€")]
                if not any("16,00 €" in value for value in value_labels):
                    raise RuntimeError(f"Estimated collection total is not quantity-aware/Cardmarket-based: {value_labels}")
                if any("Geschätzter Sammlungswert:" in value for value in visible_labels):
                    raise RuntimeError(f"Duplicate estimated collection-total text still visible: {visible_labels}")
                app.processEvents()

            search_pages = window.findChildren(SearchPage)
            if not search_pages:
                raise RuntimeError("UI self-test could not resolve SearchPage")
            for page in search_pages:
                quantity = getattr(page, "add_quantity", None)
                if not isinstance(quantity, QSpinBox) or quantity.value() != 1 or quantity.minimum() != 1:
                    raise RuntimeError("Search add-quantity control missing or invalid")

            scanner_pages = window.findChildren(ScannerPage)
            if not scanner_pages:
                raise RuntimeError("UI self-test could not resolve ScannerPage")
            for page in scanner_pages:
                quantity = getattr(page, "_jic_add_quantity", None)
                if not isinstance(quantity, QSpinBox) or quantity.value() != 1 or quantity.minimum() != 1:
                    raise RuntimeError("Scanner add-quantity control missing or invalid")

            window.close()
            window.deleteLater()
            app.processEvents()

        app.quit()
        _self_test_emit("UI SELF-TEST PASSED")
        return 0
    except BaseException as exc:
        _self_test_emit(
            f"UI SELF-TEST FAILED: {type(exc).__name__}: {exc}",
            error=True,
        )
        _self_test_emit(traceback.format_exc(), error=True)
        return 22


def _run_gui() -> int:
    # GUI imports are intentionally delayed.  This makes --self-test useful on
    # CI runners and ensures its traceback is not swallowed by Qt startup.
    from PySide6.QtCore import QLockFile, Qt
    from PySide6.QtGui import QColor, QIcon, QPixmap
    from PySide6.QtWidgets import QApplication, QMessageBox, QSplashScreen

    from justincard.database import CardDatabase
    from justincard.paths import ensure_data_directories, resource_path
    from justincard.ui.main_window import MainWindow
    from justincard.v108_features import install_v108_patches
    from justincard.v128_features import install_v128_patches
    from justincard.version import APP_NAME, APP_VERSION

    # Install schema/UI compatibility overlays before CardDatabase and MainWindow
    # are instantiated.  The legacy 1.0.3 modules remain untouched on disk.
    install_v108_patches()
    install_v128_patches()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("leenation")
    app.setWindowIcon(QIcon(str(resource_path("assets/app_icon.png"))))
    app.setStyle("Fusion")

    directories = ensure_data_directories()
    configure_logging(directories["logs"])

    def handle_exception(
        exc_type: type[BaseException],
        exc: BaseException,
        tb: object,
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        logging.critical("Unbehandelte Ausnahme", exc_info=(exc_type, exc, tb))
        try:
            QMessageBox.critical(
                None,
                "Just InCard – unerwarteter Fehler",
                "Ein unerwarteter Fehler ist aufgetreten. Details wurden in justincard.log gespeichert.",
            )
        except Exception:
            traceback.print_exception(exc_type, exc, tb)

    sys.excepthook = handle_exception

    lock_path = Path(directories["root"]) / "justincard.lock"
    instance_lock = QLockFile(str(lock_path))
    instance_lock.setStaleLockTime(0)
    if not instance_lock.tryLock(100):
        QMessageBox.information(None, APP_NAME, "Just InCard läuft bereits.")
        return 0

    # Keep a live reference until QApplication exits.
    app._justincard_instance_lock = instance_lock  # type: ignore[attr-defined]

    pixmap = QPixmap(str(resource_path("assets/app_logo.png")))
    splash = None
    if not pixmap.isNull():
        scaled = pixmap.scaled(520, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        splash = QSplashScreen(scaled)
        splash.showMessage(
            "Windows Desktop wird vorbereitet …",
            Qt.AlignHCenter | Qt.AlignBottom,
            QColor("#ffffff"),
        )
        splash.show()
        app.processEvents()

    database = CardDatabase(Path(directories["root"]) / "justincard_windows.sqlite3")
    window = MainWindow(database, directories)
    window.show()
    if splash is not None:
        splash.finish(window)

    logging.info("Just InCard Windows %s started", APP_VERSION)
    return app.exec()


def main() -> int:
    if APP_UI_SELF_TEST_FLAG in sys.argv:
        return run_ui_self_test()
    if APP_SELF_TEST_FLAG in sys.argv:
        return run_self_test()
    return _run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
