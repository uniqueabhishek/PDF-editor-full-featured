"""
Ultra PDF Editor - Preferences Dialog

Exposes only settings that actually take effect. Emits ``settings_changed`` with
the changed values so the main window can apply them live and persist them.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QFormLayout,
    QComboBox, QSpinBox, QCheckBox, QGroupBox
)
from PyQt6.QtCore import pyqtSignal
from typing import Dict, Any

from config import UserSettings, config


class SettingsDialog(QDialog):
    """Application preferences dialog."""

    settings_changed = pyqtSignal(dict)

    def __init__(self, settings: UserSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(420)

        self._settings = settings
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Appearance
        appearance = QGroupBox("Appearance")
        appearance_form = QFormLayout(appearance)
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["System", "Light", "Dark"])
        appearance_form.addRow("Theme:", self._theme_combo)
        layout.addWidget(appearance)

        # View
        view = QGroupBox("View")
        view_form = QFormLayout(view)
        self._sidebar_width = QSpinBox()
        self._sidebar_width.setRange(150, 500)
        self._sidebar_width.setSuffix(" px")
        view_form.addRow("Sidebar width:", self._sidebar_width)
        layout.addWidget(view)

        # File handling
        files = QGroupBox("File Handling")
        files_layout = QVBoxLayout(files)
        self._confirm_close = QCheckBox("Confirm before closing unsaved documents")
        files_layout.addWidget(self._confirm_close)
        layout.addWidget(files)

        # Auto-save
        autosave = QGroupBox("Auto-Save")
        autosave_form = QFormLayout(autosave)
        self._autosave_enabled = QCheckBox("Keep a recovery copy of unsaved changes")
        autosave_form.addRow(self._autosave_enabled)
        self._autosave_interval = QSpinBox()
        self._autosave_interval.setRange(30, 3600)
        self._autosave_interval.setSuffix(" seconds")
        autosave_form.addRow("Interval:", self._autosave_interval)
        layout.addWidget(autosave)

        # Buttons
        btn_layout = QHBoxLayout()
        self._restore_btn = QPushButton("Restore Defaults")
        self._restore_btn.clicked.connect(self._restore_defaults)
        btn_layout.addWidget(self._restore_btn)
        btn_layout.addStretch()
        self._ok_btn = QPushButton("OK")
        self._ok_btn.setDefault(True)
        self._ok_btn.clicked.connect(self._save_and_close)
        btn_layout.addWidget(self._ok_btn)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._cancel_btn)
        layout.addLayout(btn_layout)

    def _load_settings(self):
        theme_map = {"system": 0, "light": 1, "dark": 2}
        self._theme_combo.setCurrentIndex(theme_map.get(self._settings.theme, 0))
        self._sidebar_width.setValue(self._settings.sidebar_width)
        self._confirm_close.setChecked(self._settings.confirm_close_unsaved)
        self._autosave_enabled.setChecked(self._settings.autosave_enabled)
        self._autosave_interval.setValue(self._settings.autosave_interval)

    def _gather_settings(self) -> Dict[str, Any]:
        theme_map = {0: "system", 1: "light", 2: "dark"}
        return {
            "theme": theme_map.get(self._theme_combo.currentIndex(), "system"),
            "sidebar_width": self._sidebar_width.value(),
            "confirm_close_unsaved": self._confirm_close.isChecked(),
            "autosave_enabled": self._autosave_enabled.isChecked(),
            "autosave_interval": self._autosave_interval.value(),
        }

    def _save_and_close(self):
        changes = self._gather_settings()
        # Mutate the caller's settings object in place (preserving other fields)
        # then persist and notify.
        for key, value in changes.items():
            setattr(self._settings, key, value)
        self._settings.save(config.SETTINGS_PATH)
        self.settings_changed.emit(changes)
        self.accept()

    def _restore_defaults(self):
        """Reset the controls to defaults (applied only if the user clicks OK)."""
        defaults = UserSettings()
        theme_map = {"system": 0, "light": 1, "dark": 2}
        self._theme_combo.setCurrentIndex(theme_map.get(defaults.theme, 0))
        self._sidebar_width.setValue(defaults.sidebar_width)
        self._confirm_close.setChecked(defaults.confirm_close_unsaved)
        self._autosave_enabled.setChecked(defaults.autosave_enabled)
        self._autosave_interval.setValue(defaults.autosave_interval)
