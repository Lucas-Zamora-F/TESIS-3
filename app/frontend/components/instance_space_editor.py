from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QDoubleSpinBox,
    QVBoxLayout,
    QWidget,
)


CONFIG_PATH = Path("config/instance_space_config.json")


class InstanceSpaceEditor(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.setStyleSheet("""
            QWidget {
                background-color: #2f2f2f;
                color: #f3f3f3;
            }
            QLabel {
                font-size: 13px;
            }
        """)

        self.inputs: dict[str, Any] = {}

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Instance Space Configuration")
        title.setStyleSheet("font-size: 22px; font-weight: 800;")
        main_layout.addWidget(title)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.container = QWidget()
        self.container_layout = QVBoxLayout()
        self.container_layout.setSpacing(16)

        self.container.setLayout(self.container_layout)
        self.scroll.setWidget(self.container)

        main_layout.addWidget(self.scroll)

        # botón guardar
        btn_layout = QHBoxLayout()
        self.save_button = QPushButton("Guardar Configuración")
        self.save_button.clicked.connect(self.save_config)

        btn_layout.addWidget(self.save_button)
        btn_layout.addStretch()

        main_layout.addLayout(btn_layout)

        self.setLayout(main_layout)

        self.load_config()

    # =========================================================
    # LOAD
    # =========================================================
    def load_config(self):
        if not CONFIG_PATH.exists():
            return

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)

        build = config.get("build_is_options", {})

        for section, values in build.items():
            self.add_section(section, values)

    # =========================================================
    # UI BUILD
    # =========================================================
    def add_section(self, section_name: str, values: dict):
        section_frame = QFrame()
        section_frame.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border-radius: 10px;
                padding: 10px;
            }
        """)

        layout = QVBoxLayout()

        title = QLabel(section_name)
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(10)

        row = 0
        for key, value in values.items():
            label = QLabel(key)

            widget = self.create_input_widget(section_name, key, value)

            grid.addWidget(label, row, 0)
            grid.addWidget(widget, row, 1)

            row += 1

        layout.addLayout(grid)
        section_frame.setLayout(layout)

        self.container_layout.addWidget(section_frame)

    # =========================================================
    # INPUT FACTORY
    # =========================================================
    def create_input_widget(self, section: str, key: str, value: Any):
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

        # string
        line = QLineEdit(str(value))
        self.inputs[full_key] = line
        return line

    # =========================================================
    # SAVE
    # =========================================================
    def save_config(self):
        if not CONFIG_PATH.exists():
            return

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)

        build = config.get("build_is_options", {})

        for section, values in build.items():
            for key in values.keys():
                full_key = f"{section}.{key}"
                widget = self.inputs.get(full_key)

                if widget is None:
                    continue

                if isinstance(widget, QComboBox):
                    val = widget.currentText() == "True"

                elif isinstance(widget, QSpinBox):
                    val = widget.value()

                elif isinstance(widget, QDoubleSpinBox):
                    val = widget.value()

                elif isinstance(widget, QLineEdit):
                    val = widget.text()

                else:
                    continue

                config["build_is_options"][section][key] = val

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)