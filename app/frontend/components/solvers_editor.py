from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
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


SOLVER_CONFIG_PATH = Path("config/solver_config.json")
SOLVER_REGISTRY_PATH = Path("config/solver_registry.json")


class SolversEditor(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.solver_config: dict[str, Any] = {}
        self.solver_registry: dict[str, Any] = {}

        self.global_inputs: dict[str, Any] = {}
        self.registry_enabled_inputs: dict[str, QCheckBox] = {}
        self.registry_meta_inputs: dict[str, dict[str, Any]] = {}
        self.solver_param_inputs: dict[str, dict[str, Any]] = {}

        self._build_ui()
        self.load_data()
        self.populate_ui()

    # =========================================================
    # UI
    # =========================================================
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

            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: #1e1e1e;
                color: #f3f3f3;
                border: 1px solid #4a4a4a;
                border-radius: 6px;
                padding: 6px 8px;
                min-height: 30px;
            }

            QPushButton {
                background-color: #2d2d30;
                color: #f3f3f3;
                border: 1px solid #4a4a4a;
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: 700;
            }

            QPushButton:hover {
                background-color: #37373c;
            }

            QCheckBox {
                color: #f3f3f3;
                spacing: 8px;
                font-size: 13px;
            }
        """)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(28, 24, 28, 24)
        root_layout.setSpacing(14)

        title = QLabel("Solvers Configuration")
        title.setStyleSheet("""
            font-size: 28px;
            font-weight: 800;
            color: #f3f3f3;
        """)

        root_layout.addWidget(title)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 10, 0, 10)
        self.content_layout.setSpacing(22)

        self.scroll.setWidget(self.content)
        root_layout.addWidget(self.scroll, 1)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(10)

        self.reload_button = QPushButton("Reload")
        self.reload_button.clicked.connect(self.reload_all)

        self.save_button = QPushButton("Save Solvers Config")
        self.save_button.clicked.connect(self.save_all)

        buttons_row.addWidget(self.reload_button)
        buttons_row.addWidget(self.save_button)
        buttons_row.addStretch()

        root_layout.addLayout(buttons_row)

    # =========================================================
    # LOAD
    # =========================================================
    def load_data(self) -> None:
        self.solver_config = self._load_json(SOLVER_CONFIG_PATH)
        self.solver_registry = self._load_json(SOLVER_REGISTRY_PATH)

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    # =========================================================
    # POPULATE UI
    # =========================================================
    def populate_ui(self) -> None:
        self._clear_content()

        self.global_inputs.clear()
        self.registry_enabled_inputs.clear()
        self.registry_meta_inputs.clear()
        self.solver_param_inputs.clear()

        self._build_global_settings_section()
        self._build_registry_section()
        self._build_solver_params_section()

        self.content_layout.addStretch()

    def _clear_content(self) -> None:
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()

            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                self._clear_layout(child_layout)

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()

            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                self._clear_layout(child_layout)

    # =========================================================
    # SECTION BUILDERS
    # =========================================================
    def _build_global_settings_section(self) -> None:
        section_layout = self._create_section_header("Global Settings")

        global_settings = self.solver_config.get("global_settings", {})
        grid = self._create_form_grid()

        row = 0
        for key, value in global_settings.items():
            label = QLabel(self._pretty_label(key))
            input_widget = self._create_input_widget(value)
            self.global_inputs[key] = input_widget

            grid.addWidget(label, row, 0)
            grid.addWidget(input_widget, row, 1)
            row += 1

        section_layout.addLayout(grid)
        self.content_layout.addLayout(section_layout)
        self.content_layout.addWidget(self._create_separator())

    def _build_registry_section(self) -> None:
        section_layout = self._create_section_header("Solver Registry")

        enabled_solvers = set(self.solver_registry.get("enabled_solvers", []))
        available_solvers = self.solver_registry.get("available_solvers", {})

        for family_name, family_solvers in available_solvers.items():
            family_label = QLabel(self._pretty_label(family_name))
            family_label.setStyleSheet("""
                font-size: 16px;
                font-weight: 700;
                color: #f3f3f3;
                margin-top: 4px;
                margin-bottom: 2px;
            """)
            section_layout.addWidget(family_label)

            for solver_name, solver_meta in family_solvers.items():
                solver_title_row = QHBoxLayout()
                solver_title_row.setContentsMargins(0, 8, 0, 0)

                solver_label = QLabel(solver_name)
                solver_label.setStyleSheet("""
                    font-size: 14px;
                    font-weight: 700;
                    color: #dcdcdc;
                """)

                checkbox = QCheckBox("Enabled")
                checkbox.setChecked(solver_name in enabled_solvers)
                self.registry_enabled_inputs[solver_name] = checkbox

                solver_title_row.addWidget(solver_label)
                solver_title_row.addStretch()
                solver_title_row.addWidget(checkbox)

                section_layout.addLayout(solver_title_row)

                meta_grid = self._create_form_grid()
                self.registry_meta_inputs[solver_name] = {}

                row = 0
                for meta_key, meta_value in solver_meta.items():
                    label = QLabel(self._pretty_label(meta_key))
                    input_widget = self._create_input_widget(meta_value)

                    self.registry_meta_inputs[solver_name][meta_key] = input_widget

                    meta_grid.addWidget(label, row, 0)
                    meta_grid.addWidget(input_widget, row, 1)
                    row += 1

                section_layout.addLayout(meta_grid)
                section_layout.addWidget(self._create_thin_separator())

        self.content_layout.addLayout(section_layout)
        self.content_layout.addWidget(self._create_separator())

    def _build_solver_params_section(self) -> None:
        section_layout = self._create_section_header("Solver Parameters")

        solvers = self.solver_config.get("solvers", {})
        registry_solvers = self._get_all_registry_solver_names()

        all_solver_names = []
        seen = set()

        for name in registry_solvers:
            if name not in seen:
                all_solver_names.append(name)
                seen.add(name)

        for name in solvers.keys():
            if name not in seen:
                all_solver_names.append(name)
                seen.add(name)

        for solver_name in all_solver_names:
            params = solvers.get(solver_name, {})

            solver_label = QLabel(solver_name)
            solver_label.setStyleSheet("""
                font-size: 14px;
                font-weight: 700;
                color: #dcdcdc;
                margin-top: 6px;
            """)
            section_layout.addWidget(solver_label)

            self.solver_param_inputs[solver_name] = {}

            if params:
                grid = self._create_form_grid()

                row = 0
                for param_key, param_value in params.items():
                    label = QLabel(self._pretty_label(param_key))
                    input_widget = self._create_input_widget(param_value)

                    self.solver_param_inputs[solver_name][param_key] = input_widget

                    grid.addWidget(label, row, 0)
                    grid.addWidget(input_widget, row, 1)
                    row += 1

                section_layout.addLayout(grid)
            else:
                empty_label = QLabel("No parameters currently defined for this solver.")
                empty_label.setStyleSheet("""
                    color: #a8a8a8;
                    font-size: 12px;
                    margin-bottom: 4px;
                """)
                section_layout.addWidget(empty_label)

            section_layout.addWidget(self._create_thin_separator())

        self.content_layout.addLayout(section_layout)

    # =========================================================
    # SAVE
    # =========================================================
    def save_all(self) -> None:
        try:
            self._save_solver_config()
            self._save_solver_registry()

            QMessageBox.information(
                self,
                "Saved",
                "solver_config.json and solver_registry.json were updated successfully."
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save solver configuration.\n\n{e}"
            )

    def _save_solver_config(self) -> None:
        if "global_settings" not in self.solver_config:
            self.solver_config["global_settings"] = {}

        for key, widget in self.global_inputs.items():
            self.solver_config["global_settings"][key] = self._read_widget_value(widget)

        if "solvers" not in self.solver_config:
            self.solver_config["solvers"] = {}

        for solver_name, params_widgets in self.solver_param_inputs.items():
            if solver_name not in self.solver_config["solvers"]:
                self.solver_config["solvers"][solver_name] = {}

            for param_key, widget in params_widgets.items():
                self.solver_config["solvers"][solver_name][param_key] = self._read_widget_value(widget)

        self._write_json(SOLVER_CONFIG_PATH, self.solver_config)

    def _save_solver_registry(self) -> None:
        enabled_solvers = [
            solver_name
            for solver_name, checkbox in self.registry_enabled_inputs.items()
            if checkbox.isChecked()
        ]
        self.solver_registry["enabled_solvers"] = enabled_solvers

        if "available_solvers" not in self.solver_registry:
            self.solver_registry["available_solvers"] = {}

        available_solvers = self.solver_registry["available_solvers"]

        for _, family_solvers in available_solvers.items():
            for solver_name, solver_meta in family_solvers.items():
                if solver_name not in self.registry_meta_inputs:
                    continue

                for meta_key, widget in self.registry_meta_inputs[solver_name].items():
                    solver_meta[meta_key] = self._read_widget_value(widget)

        self._write_json(SOLVER_REGISTRY_PATH, self.solver_registry)

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    # =========================================================
    # RELOAD
    # =========================================================
    def reload_all(self) -> None:
        self.load_data()
        self.populate_ui()

    # =========================================================
    # HELPERS
    # =========================================================
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

    def _create_thin_separator(self) -> QWidget:
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #2f2f2f;")
        return line

    def _create_input_widget(self, value: Any):
        if isinstance(value, bool):
            combo = QComboBox()
            combo.addItems(["True", "False"])
            combo.setCurrentText("True" if value else "False")
            return combo

        if isinstance(value, int) and not isinstance(value, bool):
            spin = QSpinBox()
            spin.setRange(-1_000_000_000, 1_000_000_000)
            spin.setValue(value)
            return spin

        if isinstance(value, float):
            spin = QDoubleSpinBox()
            spin.setDecimals(10)
            spin.setRange(-1_000_000_000.0, 1_000_000_000.0)
            spin.setSingleStep(0.1)
            spin.setValue(value)
            return spin

        line = QLineEdit(str(value))
        return line

    def _read_widget_value(self, widget: Any) -> Any:
        if isinstance(widget, QComboBox):
            return widget.currentText() == "True"

        if isinstance(widget, QSpinBox):
            return widget.value()

        if isinstance(widget, QDoubleSpinBox):
            return widget.value()

        if isinstance(widget, QLineEdit):
            return widget.text()

        return None

    def _get_all_registry_solver_names(self) -> list[str]:
        names = []
        available_solvers = self.solver_registry.get("available_solvers", {})
        for family_solvers in available_solvers.values():
            for solver_name in family_solvers.keys():
                names.append(solver_name)
        return names

    @staticmethod
    def _pretty_label(text: str) -> str:
        return text.replace("_", " ").strip().capitalize()