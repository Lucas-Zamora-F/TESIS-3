from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


CONFIG_PATH = Path("config/instance_space_config.json")


class InstanceSpaceEditor(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.inputs: dict[str, Any] = {}
        self.uses_wrapped_options = False

        self.setStyleSheet("""
            QWidget {
                background-color: #2f2f2f;
                color: #f3f3f3;
            }
            QLabel {
                color: #f3f3f3;
                background: transparent;
                font-size: 13px;
            }
            QPushButton {
                background-color: #252526;
                color: #f3f3f3;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 10px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2d2d30;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: #1e1e1e;
                color: #f3f3f3;
                border: 1px solid #4a4a4a;
                border-radius: 6px;
                padding: 6px 8px;
                min-height: 30px;
            }
        """)

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(28, 24, 28, 24)
        root_layout.setSpacing(16)

        title = QLabel("Instance Spaces")
        title.setStyleSheet("""
            font-size: 28px;
            font-weight: 800;
            color: #f3f3f3;
        """)

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)

        self.reload_button = QPushButton("Reload")
        self.save_button = QPushButton("Save")

        self.reload_button.clicked.connect(self.load_config)
        self.save_button.clicked.connect(self.save_config)

        controls_layout.addWidget(self.reload_button)
        controls_layout.addWidget(self.save_button)
        controls_layout.addStretch()

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #2f2f2f;
            }
        """)

        self.container = QWidget()
        self.container.setStyleSheet("background-color: #2f2f2f;")
        self.container_layout = QVBoxLayout()
        self.container_layout.setContentsMargins(0, 10, 0, 10)
        self.container_layout.setSpacing(22)
        self.container.setLayout(self.container_layout)
        self.scroll.setWidget(self.container)

        root_layout.addWidget(title)
        root_layout.addLayout(controls_layout)
        root_layout.addWidget(self.scroll, 1)

        self.setLayout(root_layout)

        self.load_config()

    def load_config(self) -> None:
        # Clear existing widgets
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.inputs.clear()

        if not CONFIG_PATH.exists():
            return

        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)

            build = self._get_build_options(config)
            for section, values in build.items():
                if isinstance(values, dict):
                    self._add_section(section, values)

            self.container_layout.addStretch()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load instance_space_config.json:\n{e}")

    def _get_build_options(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        Support both config layouts used by the pipeline:
        - {"build_is_options": {...}}
        - {...} as the direct buildIS options object.
        """
        if "build_is_options" in config:
            self.uses_wrapped_options = True
            build = config.get("build_is_options", {})
        else:
            self.uses_wrapped_options = False
            build = config

        if not isinstance(build, dict):
            raise TypeError("The buildIS options must be a JSON object.")

        return build

    def _add_section(self, section_name: str, values: dict) -> None:
        section_layout = QVBoxLayout()
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(12)

        title = QLabel(section_name)
        title.setStyleSheet("""
            font-size: 22px;
            font-weight: 800;
            color: #f3f3f3;
        """)
        section_layout.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)

        row = 0
        for key, value in values.items():
            label = QLabel(key.replace("_", " ").capitalize())
            widget = self._create_input_widget(section_name, key, value)
            grid.addWidget(label, row, 0)
            grid.addWidget(widget, row, 1)
            row += 1

        section_layout.addLayout(grid)

        wrapper = QWidget()
        wrapper.setLayout(section_layout)
        self.container_layout.addWidget(wrapper)

        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #3a3a3a;")
        self.container_layout.addWidget(separator)

    def _create_input_widget(self, section: str, key: str, value: Any) -> QWidget:
        full_key = f"{section}.{key}"

        if isinstance(value, bool):
            combo = QComboBox()
            combo.addItems(["True", "False"])
            combo.setCurrentText(str(value))
            self.inputs[full_key] = combo
            return combo

        if isinstance(value, int):
            spin = QSpinBox()
            spin.setMaximum(10_000_000)
            spin.setValue(value)
            self.inputs[full_key] = spin
            return spin

        if isinstance(value, float):
            spin = QDoubleSpinBox()
            spin.setDecimals(6)
            spin.setMaximum(1_000_000)
            spin.setValue(value)
            self.inputs[full_key] = spin
            return spin

        line = QLineEdit(str(value))
        self.inputs[full_key] = line
        return line

    def save_config(self) -> None:
        if not CONFIG_PATH.exists():
            return

        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)

            build = self._get_build_options(config)
            for section, values in build.items():
                if not isinstance(values, dict):
                    continue
                for key in values.keys():
                    full_key = f"{section}.{key}"
                    widget = self.inputs.get(full_key)
                    if widget is None:
                        continue
                    if isinstance(widget, QComboBox):
                        build[section][key] = widget.currentText() == "True"
                    elif isinstance(widget, QSpinBox):
                        build[section][key] = widget.value()
                    elif isinstance(widget, QDoubleSpinBox):
                        build[section][key] = widget.value()
                    elif isinstance(widget, QLineEdit):
                        build[section][key] = widget.text()

            if self.uses_wrapped_options:
                config["build_is_options"] = build
            else:
                config = build

            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)

            QMessageBox.information(self, "Saved", "instance_space_config.json was updated successfully.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save instance_space_config.json:\n{e}")
