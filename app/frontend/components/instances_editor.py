import json
from pathlib import Path

from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
INSTANCES_CONFIG_PATH = PROJECT_ROOT / "config" / "instances_config.json"


class InstanceRow(QWidget):
    def __init__(self, instance_name: str, checked: bool) -> None:
        super().__init__()

        self.instance_name = instance_name
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            InstanceRow {
                border-bottom: 1px solid #2a2a2a;
                background-color: transparent;
            }
            InstanceRow:hover {
                background-color: #333337;
            }
        """)

        layout = QHBoxLayout()
        layout.setContentsMargins(4, 6, 4, 6)
        layout.setSpacing(10)

        name_label = QLabel(instance_name)
        name_label.setStyleSheet("""
            color: #d4d4d4;
            font-size: 13px;
            background: transparent;
        """)
        name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(checked)
        self.checkbox.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.checkbox.setStyleSheet("""
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #5a5a5a;
                border-radius: 4px;
                background-color: #1f1f1f;
            }
            QCheckBox::indicator:checked {
                background-color: #4fc1ff;
                border: 1px solid #4fc1ff;
            }
        """)

        layout.addWidget(name_label, 1)
        layout.addWidget(self.checkbox, 0, Qt.AlignmentFlag.AlignRight)

        self.setLayout(layout)

    def mousePressEvent(self, event: QEvent) -> None:
        self.checkbox.setChecked(not self.checkbox.isChecked())


class InstanceSection(QWidget):
    def __init__(self, section_name: str, instances: list[str], enabled_instances: set[str]) -> None:
        super().__init__()

        self.rows: list[InstanceRow] = []

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)

        title = QLabel(section_name)
        title.setStyleSheet("""
            color: #f3f3f3;
            font-size: 15px;
            font-weight: 700;
        """)

        self.select_all_button = QPushButton("Select all")
        self.clear_all_button = QPushButton("Clear")
        for button in (self.select_all_button, self.clear_all_button):
            button.setFixedHeight(30)
            button.setStyleSheet("""
                QPushButton {
                    background-color: #252526;
                    color: #f3f3f3;
                    border: 1px solid #3a3a3a;
                    border-radius: 6px;
                    padding: 4px 10px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #2d2d30;
                }
            """)

        self.select_all_button.clicked.connect(self.select_all)
        self.clear_all_button.clicked.connect(self.clear_all)

        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(self.select_all_button)
        title_row.addWidget(self.clear_all_button)

        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet("""
            background-color: #3a3a3a;
        """)

        layout.addLayout(title_row)
        layout.addWidget(separator)

        for instance_name in instances:
            row = InstanceRow(instance_name, instance_name in enabled_instances)
            self.rows.append(row)
            layout.addWidget(row)

        self.setLayout(layout)

    def get_checked_instances(self) -> list[str]:
        return [row.instance_name for row in self.rows if row.checkbox.isChecked()]

    def select_all(self) -> None:
        for row in self.rows:
            row.checkbox.setChecked(True)

    def clear_all(self) -> None:
        for row in self.rows:
            row.checkbox.setChecked(False)


class InstancesEditor(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.config_data: dict = {}
        self.sections: list[InstanceSection] = []

        self.setStyleSheet("""
            QWidget {
                background-color: #2f2f2f;
            }
            QLabel {
                color: #d4d4d4;
                background: transparent;
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
        """)

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(28, 24, 28, 24)
        root_layout.setSpacing(16)

        title = QLabel("Instances")
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

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #2f2f2f;
            }
        """)

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background-color: #2f2f2f;")

        self.scroll_layout = QVBoxLayout()
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(16)

        self.scroll_content.setLayout(self.scroll_layout)
        self.scroll_area.setWidget(self.scroll_content)

        root_layout.addWidget(title)
        root_layout.addLayout(controls_layout)
        root_layout.addWidget(self.scroll_area, 1)

        self.setLayout(root_layout)

        self.load_config()

    def clear_sections(self) -> None:
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self.sections.clear()

    def load_config(self) -> None:
        try:
            with INSTANCES_CONFIG_PATH.open("r", encoding="utf-8") as f:
                self.config_data = json.load(f)

            enabled_instances = set(self.config_data.get("enabled_instances", []))
            available_instances = self.config_data.get("available_instances", {})

            self.clear_sections()

            for section_name, instances in available_instances.items():
                section_widget = InstanceSection(
                    section_name=section_name.upper(),
                    instances=instances,
                    enabled_instances=enabled_instances,
                )
                self.sections.append(section_widget)
                self.scroll_layout.addWidget(section_widget)

            self.scroll_layout.addStretch()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load instances_config.json:\n{e}")

    def save_config(self) -> None:
        try:
            enabled_instances: list[str] = []

            for section in self.sections:
                enabled_instances.extend(section.get_checked_instances())

            self.config_data["enabled_instances"] = enabled_instances

            with INSTANCES_CONFIG_PATH.open("w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)

            QMessageBox.information(self, "Saved", "instances_config.json was updated successfully.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save instances_config.json:\n{e}")
