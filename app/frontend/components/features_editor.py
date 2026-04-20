import json
from pathlib import Path

from PySide6.QtCore import Qt
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
FEATURES_CONFIG_PATH = PROJECT_ROOT / "config" / "features_config.json"


class FeatureRow(QWidget):
    def __init__(self, feature_name: str, checked: bool) -> None:
        super().__init__()

        self.feature_name = feature_name

        layout = QHBoxLayout()
        layout.setContentsMargins(4, 6, 4, 6)
        layout.setSpacing(10)

        name_label = QLabel(feature_name)
        name_label.setStyleSheet("""
            color: #d4d4d4;
            font-size: 13px;
        """)

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(checked)

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


class FeatureSection(QWidget):
    def __init__(self, section_name: str, features: list[str], enabled_features: set[str]) -> None:
        super().__init__()

        self.rows: list[FeatureRow] = []

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title = QLabel(section_name)
        title.setStyleSheet("""
            color: #f3f3f3;
            font-size: 15px;
            font-weight: 700;
        """)

        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet("""
            background-color: #3a3a3a;
        """)

        layout.addWidget(title)
        layout.addWidget(separator)

        for feature_name in features:
            row = FeatureRow(feature_name, feature_name in enabled_features)
            self.rows.append(row)
            layout.addWidget(row)

        self.setLayout(layout)

    def get_checked_features(self) -> list[str]:
        return [row.feature_name for row in self.rows if row.checkbox.isChecked()]
    

class FeaturesEditor(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.config_data: dict = {}
        self.sections: list[FeatureSection] = []

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

        title = QLabel("Features")
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
            with FEATURES_CONFIG_PATH.open("r", encoding="utf-8") as f:
                self.config_data = json.load(f)

            enabled_features = set(self.config_data.get("enabled_features", []))
            available_features = self.config_data.get("available_features", {})

            self.clear_sections()

            for section_name, section_data in available_features.items():
                features = section_data.get("features", [])
                section_widget = FeatureSection(
                    section_name=section_name.capitalize(),
                    features=features,
                    enabled_features=enabled_features,
                )
                self.sections.append(section_widget)
                self.scroll_layout.addWidget(section_widget)

            self.scroll_layout.addStretch()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load features_config.json:\n{e}")

    def save_config(self) -> None:
        try:
            enabled_features: list[str] = []

            for section in self.sections:
                enabled_features.extend(section.get_checked_features())

            self.config_data["enabled_features"] = enabled_features

            with FEATURES_CONFIG_PATH.open("w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)

            QMessageBox.information(self, "Saved", "features_config.json was updated successfully.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save features_config.json:\n{e}")