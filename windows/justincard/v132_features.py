from __future__ import annotations

import json
import time
from typing import Any

from PySide6.QtCore import QThreadPool, QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from justincard.account_sync import (
    AUTO_SYNC_SETTING,
    MODE_SETTING,
    TOKEN_SETTING,
    USER_SETTING,
    AccountApiError,
    JustInCardAccountClient,
    load_windows_account,
    sync_windows_account,
    windows_device_name,
)
from justincard.v120_features import _CloudTask
from justincard.v130_features import install_v130_patches

_INSTALLED = False
ACCOUNT_SYNC_INTERVAL_MS = 5 * 60 * 1000


def _layout(widget: QWidget | None) -> Any:
    try:
        return widget.layout() if widget is not None else None
    except Exception:
        return None


def _account_user(database: Any) -> dict[str, Any]:
    raw = str(database.get_setting(USER_SETTING, "") or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _account_token(database: Any) -> str:
    return str(database.get_setting(TOKEN_SETTING, "") or "").strip()


def _save_login(database: Any, token: str, user: dict[str, Any]) -> None:
    database.set_setting(TOKEN_SETTING, token)
    database.set_setting(USER_SETTING, json.dumps(user or {}, ensure_ascii=False))
    database.set_setting(MODE_SETTING, "account")
    database.set_setting(AUTO_SYNC_SETTING, True)


def _clear_login(database: Any) -> None:
    database.set_setting(TOKEN_SETTING, "")
    database.set_setting(USER_SETTING, "")
    database.set_setting(MODE_SETTING, "local")


def _refresh_data_pages(window: QWidget) -> None:
    for widget in window.findChildren(QWidget):
        kind = type(widget).__name__
        if kind == "CollectionPage":
            refresh = getattr(widget, "refresh", None)
            if callable(refresh):
                try:
                    refresh()
                except Exception:
                    pass
        elif kind == "DecksPage":
            for name in ("refresh_collection", "refresh_deck_cards", "refresh_decks"):
                refresh = getattr(widget, name, None)
                if callable(refresh):
                    try:
                        refresh()
                    except Exception:
                        pass


class _LoginDialog(QDialog):
    def __init__(self, parent: QWidget, database: Any) -> None:
        super().__init__(parent)
        self.database = database
        self.setWindowTitle("Just InCard Konto anmelden")
        self.setModal(True)
        self.setMinimumWidth(470)
        self.token = ""
        self.user: dict[str, Any] = {}
        self._task: _CloudTask | None = None

        root = QVBoxLayout(self)
        title = QLabel("Mit Just InCard Konto anmelden", self)
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        root.addWidget(title)
        info = QLabel(
            "Verwende denselben Account wie auf justincard.de. Sammlung und Decks bleiben zusätzlich lokal auf diesem PC "
            "und werden nach erfolgreicher Anmeldung mit dem IONOS-Konto abgeglichen. Die Anmeldung erfolgt vollständig in der App; es wird kein Browser geöffnet.",
            self,
        )
        info.setWordWrap(True)
        info.setObjectName("Muted")
        root.addWidget(info)

        form = QFormLayout()
        self.identity = QLineEdit(self)
        self.identity.setPlaceholderText("Benutzername oder E-Mail")
        self.password = QLineEdit(self)
        self.password.setPlaceholderText("Passwort")
        self.password.setEchoMode(QLineEdit.Password)
        form.addRow("Benutzername / E-Mail", self.identity)
        form.addRow("Passwort", self.password)
        root.addLayout(form)

        self.status = QLabel("", self)
        self.status.setWordWrap(True)
        self.status.setObjectName("Muted")
        root.addWidget(self.status)

        buttons = QHBoxLayout()
        cancel = QPushButton("Abbrechen", self)
        cancel.setProperty("role", "ghost")
        cancel.clicked.connect(self.reject)
        self.login = QPushButton("Anmelden", self)
        self.login.setProperty("role", "primary")
        self.login.clicked.connect(self._start_login)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(self.login)
        root.addLayout(buttons)
        self.password.returnPressed.connect(self._start_login)

    def _start_login(self) -> None:
        identity = self.identity.text().strip()
        password = self.password.text()
        if not identity or not password:
            self.status.setText("Bitte Benutzername/E-Mail und Passwort eingeben.")
            return
        self.login.setEnabled(False)
        self.identity.setEnabled(False)
        self.password.setEnabled(False)
        self.status.setText("Anmeldung am Just-InCard-Server …")
        task = _CloudTask(lambda: JustInCardAccountClient().login(identity, password, windows_device_name()))
        self._task = task

        def done(result: Any) -> None:
            self.login.setEnabled(True)
            self.identity.setEnabled(True)
            self.password.setEnabled(True)
            if not isinstance(result, dict) or not result.get("token"):
                self.status.setText("Der Server hat kein Anmelde-Token zurückgegeben.")
                return
            self.token = str(result.get("token") or "")
            self.user = dict(result.get("user") or {})
            _save_login(self.database, self.token, self.user)
            self.accept()

        def failed(message: str) -> None:
            self.login.setEnabled(True)
            self.identity.setEnabled(True)
            self.password.setEnabled(True)
            friendly = message.split(":", 1)[-1].strip() if ":" in message else message
            if "invalid_credentials" in friendly:
                friendly = "Benutzername/E-Mail oder Passwort ist nicht korrekt."
            self.status.setText(friendly)

        task.signals.done.connect(done)
        task.signals.failed.connect(failed)
        QThreadPool.globalInstance().start(task)


def _run_account_sync(window: QWidget, database: Any, *, interactive: bool = True, finished: Any = None) -> None:
    if getattr(window, "_jic_account_sync_busy", False):
        if interactive:
            QMessageBox.information(window, "Just InCard Konto", "Eine Konto-Synchronisierung läuft bereits.")
        return
    token = _account_token(database)
    if not token:
        if interactive:
            QMessageBox.information(window, "Just InCard Konto", "Bitte zuerst mit deinem Just-InCard-Konto anmelden.")
        return
    window._jic_account_sync_busy = True
    task = _CloudTask(lambda: sync_windows_account(database, token))
    window._jic_account_sync_task = task

    def done(result: Any) -> None:
        window._jic_account_sync_busy = False
        _refresh_data_pages(window)
        if callable(finished):
            try:
                finished(True, result)
            except Exception:
                pass
        if interactive:
            result = result if isinstance(result, dict) else {}
            QMessageBox.information(
                window,
                "Konto synchronisiert",
                f"Sammlung und Decks wurden mit deinem Just-InCard-Konto abgeglichen.\n\n"
                f"Sammlungseinträge: {int(result.get('collection') or 0)}\n"
                f"Decks: {int(result.get('decks') or 0)}",
            )

    def failed(message: str) -> None:
        window._jic_account_sync_busy = False
        if callable(finished):
            try:
                finished(False, message)
            except Exception:
                pass
        if interactive:
            friendly = message.split(":", 1)[-1].strip() if ":" in message else message
            QMessageBox.warning(window, "Konto-Synchronisierung fehlgeschlagen", friendly)

    task.signals.done.connect(done)
    task.signals.failed.connect(failed)
    QThreadPool.globalInstance().start(task)


def _run_account_restore(window: QWidget, database: Any, *, interactive: bool = True, finished: Any = None) -> None:
    """Load the account snapshot before the first upload after login."""
    if getattr(window, "_jic_account_sync_busy", False):
        if interactive:
            QMessageBox.information(window, "Just InCard Konto", "Eine Konto-Übertragung läuft bereits.")
        return
    token = _account_token(database)
    if not token:
        if interactive:
            QMessageBox.information(window, "Just InCard Konto", "Bitte zuerst mit deinem Just-InCard-Konto anmelden.")
        return
    window._jic_account_sync_busy = True
    task = _CloudTask(lambda: load_windows_account(database, token))
    window._jic_account_restore_task = task

    def done(result: Any) -> None:
        window._jic_account_sync_busy = False
        _refresh_data_pages(window)
        if callable(finished):
            try:
                finished(True, result)
            except Exception:
                pass
        if interactive:
            result = result if isinstance(result, dict) else {}
            mode = str(result.get("mode") or "")
            if mode == "downloaded":
                lead = "Der vorhandene Konto-Stand wurde vollständig auf diesen PC geladen."
            elif mode == "seeded":
                lead = "Das Konto war leer. Der vorhandene lokale Stand wurde als erster Konto-Stand gespeichert."
            else:
                lead = "Das Konto ist verbunden. Es waren noch keine Sammlungs- oder Deckdaten gespeichert."
            QMessageBox.information(
                window,
                "Just InCard Konto geladen",
                f"{lead}\n\nSammlungseinträge: {int(result.get('collection') or 0)}\n"
                f"Decks: {int(result.get('decks') or 0)}",
            )

    def failed(message: str) -> None:
        window._jic_account_sync_busy = False
        if callable(finished):
            try:
                finished(False, message)
            except Exception:
                pass
        if interactive:
            friendly = message.split(":", 1)[-1].strip() if ":" in message else message
            QMessageBox.warning(window, "Konto konnte nicht geladen werden", friendly)

    task.signals.done.connect(done)
    task.signals.failed.connect(failed)
    QThreadPool.globalInstance().start(task)


def _login_and_sync(parent: QWidget, database: Any, *, interactive_sync: bool = True, callback: Any = None) -> bool:
    dialog = _LoginDialog(parent, database)
    if dialog.exec() != QDialog.Accepted:
        return False
    _run_account_restore(parent.window(), database, interactive=interactive_sync, finished=callback)
    return True


def _patch_settings() -> None:
    from justincard.ui.settings_page import SettingsPage

    original_init = SettingsPage.__init__

    def settings_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        scroll = self.findChild(QScrollArea)
        content = scroll.widget() if scroll is not None else None
        layout = _layout(content)
        if not isinstance(layout, QVBoxLayout):
            return

        group = QGroupBox("Just InCard Konto (IONOS)", self)
        outer = QVBoxLayout(group)
        intro = QLabel(
            "Die App kann vollständig lokal ohne Konto verwendet werden. Mit einem Just-InCard-Konto werden nur Sammlung und Decks "
            "auf deinem IONOS-Webspace gesichert und zwischen Windows und Android synchronisiert. Kartenbilder bleiben auf den Endgeräten.",
            group,
        )
        intro.setWordWrap(True)
        intro.setObjectName("Muted")
        outer.addWidget(intro)

        status = QLabel(group)
        status.setWordWrap(True)
        outer.addWidget(status)

        auto = QCheckBox("Automatisch beim Start und alle 5 Minuten synchronisieren", group)
        auto.setChecked(bool(self.database.get_setting(AUTO_SYNC_SETTING, True)))
        outer.addWidget(auto)

        buttons = QHBoxLayout()
        local_button = QPushButton("Nur lokal verwenden", group)
        local_button.setProperty("role", "ghost")
        login_button = QPushButton("Mit Konto anmelden", group)
        login_button.setProperty("role", "primary")
        sync_button = QPushButton("Jetzt synchronisieren", group)
        sync_button.setProperty("role", "ghost")
        logout_button = QPushButton("Konto abmelden", group)
        logout_button.setProperty("role", "ghost")
        buttons.addWidget(local_button)
        buttons.addWidget(login_button)
        buttons.addWidget(sync_button)
        buttons.addWidget(logout_button)
        outer.addLayout(buttons)

        def refresh_status() -> None:
            mode = str(self.database.get_setting(MODE_SETTING, "") or "")
            user = _account_user(self.database)
            token = _account_token(self.database)
            if mode == "account" and token:
                name = str(user.get("display_name") or user.get("username") or user.get("email") or "Konto")
                last = str(self.database.get_setting("account_last_sync_v132", "") or "Noch nicht synchronisiert")
                status.setText(f"Angemeldet als: {name} · Letzter Abgleich: {last}")
                login_button.setText("Anderes Konto")
                sync_button.setEnabled(True)
                logout_button.setEnabled(True)
            else:
                status.setText("Lokaler Modus: Sammlung und Decks bleiben nur auf diesem Gerät, bis du dich anmeldest.")
                login_button.setText("Mit Konto anmelden")
                sync_button.setEnabled(False)
                logout_button.setEnabled(False)

        def choose_local() -> None:
            self.database.set_setting(MODE_SETTING, "local")
            refresh_status()

        def login() -> None:
            _login_and_sync(self, self.database, interactive_sync=True, callback=lambda *_: refresh_status())
            refresh_status()

        def sync_now() -> None:
            _run_account_sync(self.window(), self.database, interactive=True, finished=lambda *_: refresh_status())

        def logout() -> None:
            token = _account_token(self.database)
            _clear_login(self.database)
            refresh_status()
            if token:
                task = _CloudTask(lambda: JustInCardAccountClient().logout(token))
                self._jic_account_logout_task = task
                QThreadPool.globalInstance().start(task)

        local_button.clicked.connect(choose_local)
        login_button.clicked.connect(login)
        sync_button.clicked.connect(sync_now)
        logout_button.clicked.connect(logout)
        auto.toggled.connect(lambda checked: self.database.set_setting(AUTO_SYNC_SETTING, bool(checked)))
        layout.insertWidget(0, group)
        self._jic_account_group = group
        self._jic_account_status = status
        refresh_status()

    SettingsPage.__init__ = settings_init


def _patch_main_window() -> None:
    from justincard.ui.main_window import MainWindow

    original_init = MainWindow.__init__

    def window_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        database = self.database
        self._jic_account_sync_busy = False

        timer = QTimer(self)
        timer.setInterval(ACCOUNT_SYNC_INTERVAL_MS)
        self._jic_account_timer = timer

        def periodic() -> None:
            if str(database.get_setting(MODE_SETTING, "") or "") != "account":
                return
            if not bool(database.get_setting(AUTO_SYNC_SETTING, True)):
                return
            if not _account_token(database):
                return
            _run_account_sync(self, database, interactive=False)

        timer.timeout.connect(periodic)
        timer.start()

        def first_start_choice() -> None:
            mode = str(database.get_setting(MODE_SETTING, "") or "").strip()
            if mode in {"local", "account"}:
                if mode == "account" and _account_token(database) and bool(database.get_setting(AUTO_SYNC_SETTING, True)):
                    _run_account_sync(self, database, interactive=False)
                return

            dialog = QDialog(self)
            dialog.setWindowTitle("Just InCard verwenden")
            dialog.setModal(True)
            dialog.setMinimumWidth(540)
            root = QVBoxLayout(dialog)
            title = QLabel("Wie möchtest du Just InCard verwenden?", dialog)
            title.setStyleSheet("font-size: 19px; font-weight: 700;")
            root.addWidget(title)
            info = QLabel(
                "Du kannst die App vollständig lokal verwenden – ohne Account und ohne Cloud. Alternativ kannst du dich mit deinem "
                "Just-InCard-Konto von justincard.de anmelden. Dann werden Sammlung und Decks zusätzlich auf deinem IONOS-Webspace "
                "gesichert und zwischen deinen Windows- und Android-Geräten abgeglichen. Kartenbilder werden nicht auf dem Server gespeichert.",
                dialog,
            )
            info.setWordWrap(True)
            info.setObjectName("Muted")
            root.addWidget(info)
            local = QPushButton("Nur lokal verwenden", dialog)
            local.setProperty("role", "ghost")
            account = QPushButton("Mit Just InCard Konto anmelden", dialog)
            account.setProperty("role", "primary")
            root.addWidget(local)
            root.addWidget(account)

            def pick_local() -> None:
                database.set_setting(MODE_SETTING, "local")
                dialog.accept()

            def pick_account() -> None:
                # Close the choice first, then open the credential dialog.  A
                # cancelled login leaves the app usable locally and the choice
                # can be changed later in Settings.
                dialog.accept()
                if not _login_and_sync(self, database, interactive_sync=True):
                    database.set_setting(MODE_SETTING, "local")

            local.clicked.connect(pick_local)
            account.clicked.connect(pick_account)
            if dialog.exec() != QDialog.Accepted:
                database.set_setting(MODE_SETTING, "local")

        QTimer.singleShot(850, first_start_choice)

    MainWindow.__init__ = window_init


def install_v132_patches() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    install_v130_patches()
    _patch_settings()
    _patch_main_window()
    _INSTALLED = True


__all__ = ["install_v132_patches"]
