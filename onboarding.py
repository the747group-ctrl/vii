"""
VII First-Run Onboarding — Simple setup flow.
Shows on first launch if no API key is configured.

Developed by The 747 Lab
"""

import sys
import os
import json

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit,
                              QPushButton, QHBoxLayout, QComboBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(PROJECT_ROOT, "config", "vii-settings.json")


class OnboardingDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VII — Setup")
        self.setFixedSize(420, 380)
        self.setStyleSheet("""
            QDialog { background: #0a0a12; color: #ccc; }
            QLabel { color: #aaa; }
            QLineEdit { background: #12121e; border: 1px solid #252535; border-radius: 6px;
                        padding: 10px; color: #ccc; font-size: 13px; }
            QLineEdit:focus { border-color: #c87850; }
            QPushButton { background: #c87850; color: #fff; border: none; border-radius: 6px;
                          padding: 12px 24px; font-weight: 600; font-size: 14px; }
            QPushButton:hover { background: #d89060; }
            QPushButton:pressed { background: #b06840; }
            QPushButton#skip { background: transparent; color: #555; border: 1px solid #252535; }
            QPushButton#skip:hover { color: #888; border-color: #444; }
            QComboBox { background: #12121e; border: 1px solid #252535; border-radius: 6px;
                        padding: 8px; color: #ccc; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(32, 32, 32, 32)

        # Title
        title = QLabel("VII")
        title.setFont(QFont("Helvetica", 28, QFont.Weight.Bold))
        title.setStyleSheet("color: #c87850;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Voice Intelligence Interface")
        subtitle.setStyleSheet("color: #666; font-size: 12px; letter-spacing: 3px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # Provider
        layout.addWidget(QLabel("AI Provider"))
        self.provider = QComboBox()
        self.provider.addItems(["Anthropic (Claude)", "Ollama (Local, Free)"])
        self.provider.currentIndexChanged.connect(self._on_provider_change)
        layout.addWidget(self.provider)

        # API Key
        self.key_label = QLabel("Anthropic API Key")
        layout.addWidget(self.key_label)
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("sk-ant-...")
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.key_input)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        skip = QPushButton("Skip")
        skip.setObjectName("skip")
        skip.clicked.connect(self.reject)
        btn_row.addWidget(skip)

        start = QPushButton("Start VII")
        start.clicked.connect(self._save_and_start)
        btn_row.addWidget(start)
        layout.addLayout(btn_row)

        # Footer
        footer = QLabel("The 747 Lab")
        footer.setStyleSheet("color: #333; font-size: 10px;")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)

    def _on_provider_change(self, index):
        is_anthropic = index == 0
        self.key_label.setVisible(is_anthropic)
        self.key_input.setVisible(is_anthropic)

    def _save_and_start(self):
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)

        settings = {}
        if os.path.exists(SETTINGS_PATH):
            with open(SETTINGS_PATH) as f:
                settings = json.load(f)

        if self.provider.currentIndex() == 0:
            settings["llm_provider"] = "anthropic"
            key = self.key_input.text().strip()
            if key:
                settings.setdefault("api_keys", {})["anthropic"] = key
        else:
            settings["llm_provider"] = "ollama"

        with open(SETTINGS_PATH, "w") as f:
            json.dump(settings, f, indent=2)

        self.accept()


def needs_onboarding():
    """Check if first-run setup is needed."""
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH) as f:
            s = json.load(f)
            # Has API key or using Ollama
            if s.get("llm_provider") == "ollama":
                return False
            keys = s.get("api_keys", {})
            if keys.get("anthropic", "").startswith("sk-"):
                return False

    # Check OpenClaw auth
    auth = os.path.expanduser("~/.openclaw/agents/main/agent/auth-profiles.json")
    if os.path.exists(auth):
        with open(auth) as f:
            k = json.load(f).get("profiles", {}).get("anthropic:manual", {}).get("token", "")
            if k.startswith("sk-"):
                return False

    # Check env
    if os.environ.get("ANTHROPIC_API_KEY", "").startswith("sk-"):
        return False

    return True
