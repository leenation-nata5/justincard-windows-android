from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QFrame, QLabel, QHBoxLayout, QWidget


class ToastMessage(QFrame):
    def __init__(self, parent: QWidget, text: str) -> None:
        super().__init__(parent)
        self.setObjectName("JicToast")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setStyleSheet(
            "#JicToast {"
            " background: rgba(18, 132, 82, 242);"
            " border: 2px solid rgba(99, 230, 166, 245);"
            " border-radius: 14px;"
            " }"
            "#JicToast QLabel { color: white; font-size: 18px; font-weight: 700; }"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 15, 24, 15)
        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        layout.addWidget(label)
        self.adjustSize()
        self.setMinimumWidth(min(520, max(300, self.sizeHint().width())))
        self.adjustSize()

    def center_on_parent(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        x = max(8, (parent.width() - self.width()) // 2)
        y = max(8, (parent.height() - self.height()) // 2)
        self.move(x, y)


def show_toast(parent: QWidget, text: str, duration_ms: int = 1150) -> ToastMessage:
    host = parent.window() if parent.window() is not None else parent
    previous = getattr(host, "_jic_active_toast", None)
    if previous is not None:
        try:
            previous.deleteLater()
        except RuntimeError:
            pass
    toast = ToastMessage(host, text)
    host._jic_active_toast = toast  # type: ignore[attr-defined]
    toast.center_on_parent()
    toast.raise_()
    toast.show()

    def close_toast() -> None:
        try:
            toast.hide()
            toast.deleteLater()
        finally:
            if getattr(host, "_jic_active_toast", None) is toast:
                host._jic_active_toast = None  # type: ignore[attr-defined]

    QTimer.singleShot(max(350, int(duration_ms)), close_toast)
    return toast
