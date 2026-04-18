"""
VII Text Input — Quick text entry dialog.
Type instead of speak. Right-click → Type Command.
Developed by The 747 Lab
"""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit
from PyQt6.QtCore import Qt


class TextInputDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("VII")
        self.setFixedSize(400, 80)
        self.setStyleSheet(
            "QDialog{background:#0a0a14;border:1px solid #252535;border-radius:10px}"
            "QLineEdit{background:#12121e;border:1px solid #303045;border-radius:8px;"
            "padding:12px 16px;color:#ddd;font-size:15px}"
            "QLineEdit:focus{border-color:#c87850}"
        )
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a command or question...")
        self.input.returnPressed.connect(self.accept)
        layout.addWidget(self.input)

    def get_text(self):
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.center().x() - self.width() // 2, screen.height() // 3)
        self.input.clear()
        self.input.setFocus()
        if self.exec() == QDialog.DialogCode.Accepted:
            return self.input.text().strip()
        return None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
