from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)


class MetadataOrchestratorConfigEditor(QWidget):
    def __init__(self, project_root: Path) -> None:
        super().__init__()

        self.project_root = project_root
        self.config_path = self.project_root / "config" / "metadata_orchestrator_config.json"

        self.config: Dict[str, Any] = {}
        self._building_ui = False

        self._build_ui()
        self.load_config()

    # ============================================================
    # UI
    # ============================================================

    def _build_ui(self) -> None:
        self.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border: 1px solid #3a3a3a;
                border-radius: 12px;
            }
            QLabel {
                color: #f3f3f3;
            }
            QComboBox, QLineEdit {
                background-color: #1f1f1f;
                color: #f3f3f3;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 6px;
            }
            QCheckBox {
                color: #f3f3f3;
            }
        """)

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #d7ba7d; font-weight: 600;")
        root.addWidget(self.status_label)

        frame = QFrame()
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ============================================================
        # INSTANCES
        # ============================================================
        self.instances_mode = self._combo(["enabled", "all"])
        layout.addLayout(self._row("Instances mode", self.instances_mode))

        # ============================================================
        # PIPELINE
        # ============================================================
        self.source_mode = self._combo(["build", "csv"])
        self.features_mode = self._combo(["build", "csv"])
        self.solver_mode = self._combo(["build", "csv"])

        layout.addLayout(self._row("Source table", self.source_mode))
        layout.addLayout(self._row("Features table", self.features_mode))
        layout.addLayout(self._row("Solver runtime table", self.solver_mode))

        # ============================================================
        # OUTPUT
        # ============================================================
        self.save_metadata = QCheckBox("Save metadata")
        self.metadata_path = QLineEdit()

        layout.addWidget(self.save_metadata)
        layout.addLayout(self._row("Metadata path", self.metadata_path))

        # ============================================================
        # LOGGING
        # ============================================================
        self.logging_enabled = QCheckBox("Enable logging")
        self.logging_level = self._combo(["DEBUG", "INFO", "WARNING", "ERROR"])

        layout.addWidget(self.logging_enabled)
        layout.addLayout(self._row("Logging level", self.logging_level))

        frame.setLayout(layout)
        root.addWidget(frame)
        root.addStretch()

        self.setLayout(root)

        self._connect_signals()

    # ============================================================
    # HELPERS UI
    # ============================================================

    def _combo(self, options: list[str]) -> QComboBox:
        c = QComboBox()
        c.addItems(options)
        return c

    def _row(self, label_text: str, widget: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setFixedWidth(180)
        row.addWidget(label)
        row.addWidget(widget)
        return row

    # ============================================================
    # CONFIG LOGIC
    # ============================================================

    def load_config(self) -> None:
        self._building_ui = True

        try:
            if not self.config_path.exists():
                raise FileNotFoundError("Config file not found")

            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)

            self._populate_widgets()
            self._set_status("Config loaded")

        except Exception as e:
            self._set_status(f"Error loading config: {e}")

        self._building_ui = False

    def _populate_widgets(self) -> None:
        cfg = self.config

        self.instances_mode.setCurrentText(cfg["instances"]["mode"])

        self.source_mode.setCurrentText(cfg["pipeline"]["source_table"]["mode"])
        self.features_mode.setCurrentText(cfg["pipeline"]["features_table"]["mode"])
        self.solver_mode.setCurrentText(cfg["pipeline"]["solver_runtime_table"]["mode"])

        self.save_metadata.setChecked(cfg["output"]["save_metadata"])
        self.metadata_path.setText(cfg["output"]["metadata_path"])

        self.logging_enabled.setChecked(cfg["logging"]["enabled"])
        self.logging_level.setCurrentText(cfg["logging"]["level"])

    def _collect(self) -> Dict[str, Any]:
        return {
            "instances": {
                "mode": self.instances_mode.currentText()
            },
            "pipeline": {
                "source_table": {"mode": self.source_mode.currentText()},
                "features_table": {"mode": self.features_mode.currentText()},
                "solver_runtime_table": {"mode": self.solver_mode.currentText()},
            },
            "output": {
                "save_metadata": self.save_metadata.isChecked(),
                "metadata_path": self.metadata_path.text().strip(),
            },
            "logging": {
                "enabled": self.logging_enabled.isChecked(),
                "level": self.logging_level.currentText(),
            },
        }

    def _save(self) -> None:
        try:
            new_config = self._collect()

            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(new_config, f, indent=2)

            self.config = new_config
            self._set_status("Saved")

        except Exception as e:
            self._set_status(f"Save error: {e}")

    # ============================================================
    # SIGNALS
    # ============================================================

    def _connect_signals(self) -> None:
        widgets = [
            self.instances_mode,
            self.source_mode,
            self.features_mode,
            self.solver_mode,
            self.logging_level,
        ]

        for w in widgets:
            w.currentIndexChanged.connect(self._on_change)

        self.save_metadata.stateChanged.connect(self._on_change)
        self.logging_enabled.stateChanged.connect(self._on_change)
        self.metadata_path.textChanged.connect(self._on_change)

    def _on_change(self) -> None:
        if self._building_ui:
            return
        self._save()

    # ============================================================
    # STATUS
    # ============================================================

    def _set_status(self, text: str) -> None:
        self.status_label.setText(f"Status: {text}")