from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
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
            QWidget {
                background-color: #2f2f2f;
                color: #f3f3f3;
            }
            QLabel {
                background: transparent;
                color: #f3f3f3;
                font-size: 13px;
            }
            QComboBox, QLineEdit {
                background-color: #1e1e1e;
                color: #f3f3f3;
                border: 1px solid #4a4a4a;
                border-radius: 6px;
                padding: 6px 8px;
                min-height: 30px;
            }
            QCheckBox {
                color: #f3f3f3;
                spacing: 8px;
                font-size: 13px;
            }
        """)

        root = QVBoxLayout()
        root.setContentsMargins(0, 10, 0, 10)
        root.setSpacing(22)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #d7ba7d; font-weight: 600; font-size: 13px;")
        root.addWidget(self.status_label)

        # ============================================================
        # INSTANCES
        # ============================================================
        self.instances_mode = self._combo(["enabled", "all"])
        instances_section = self._create_section_header("Instances")
        instances_grid = self._create_form_grid()
        instances_grid.addWidget(QLabel("Mode"), 0, 0)
        instances_grid.addWidget(self.instances_mode, 0, 1)
        instances_section.addLayout(instances_grid)
        root.addLayout(instances_section)
        root.addWidget(self._create_separator())

        # ============================================================
        # PIPELINE
        # ============================================================
        self.source_mode = self._combo(["build", "csv"])
        self.features_mode = self._combo(["build", "csv"])
        self.solver_mode = self._combo(["build", "csv"])

        pipeline_section = self._create_section_header("Pipeline")
        pipeline_grid = self._create_form_grid()
        pipeline_grid.addWidget(QLabel("Source table"), 0, 0)
        pipeline_grid.addWidget(self.source_mode, 0, 1)
        pipeline_grid.addWidget(QLabel("Features table"), 1, 0)
        pipeline_grid.addWidget(self.features_mode, 1, 1)
        pipeline_grid.addWidget(QLabel("Solver runtime table"), 2, 0)
        pipeline_grid.addWidget(self.solver_mode, 2, 1)
        pipeline_section.addLayout(pipeline_grid)
        root.addLayout(pipeline_section)
        root.addWidget(self._create_separator())

        # ============================================================
        # OUTPUT
        # ============================================================
        self.save_metadata = QCheckBox("Save metadata")
        self.metadata_path = QLineEdit()

        output_section = self._create_section_header("Output")
        output_grid = self._create_form_grid()
        output_grid.addWidget(self.save_metadata, 0, 0, 1, 2)
        output_grid.addWidget(QLabel("Metadata path"), 1, 0)
        output_grid.addWidget(self.metadata_path, 1, 1)
        output_section.addLayout(output_grid)
        root.addLayout(output_section)
        root.addWidget(self._create_separator())

        # ============================================================
        # LOGGING
        # ============================================================
        self.logging_enabled = QCheckBox("Enable logging")
        self.logging_level = self._combo(["DEBUG", "INFO", "WARNING", "ERROR"])

        logging_section = self._create_section_header("Logging")
        logging_grid = self._create_form_grid()
        logging_grid.addWidget(self.logging_enabled, 0, 0, 1, 2)
        logging_grid.addWidget(QLabel("Logging level"), 1, 0)
        logging_grid.addWidget(self.logging_level, 1, 1)
        logging_section.addLayout(logging_grid)
        root.addLayout(logging_section)

        self.setLayout(root)

        self._connect_signals()

    # ============================================================
    # HELPERS UI
    # ============================================================

    def _combo(self, options: list[str]) -> QComboBox:
        c = QComboBox()
        c.addItems(options)
        return c

    def _create_section_header(self, title_text: str) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel(title_text)
        title.setStyleSheet("""
            font-size: 22px;
            font-weight: 800;
            color: #f3f3f3;
        """)
        layout.addWidget(title)
        return layout

    def _create_form_grid(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        return grid

    def _create_separator(self) -> QWidget:
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #3a3a3a;")
        return line

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