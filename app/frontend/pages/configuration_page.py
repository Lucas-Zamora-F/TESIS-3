from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.frontend.components.sidebar_button import SidebarButton


class SectionButton(QPushButton):
    def __init__(self, text: str, active: bool = False) -> None:
        super().__init__(text)
        self._active = active
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(42)
        self.apply_style()

    def set_active(self, active: bool) -> None:
        self._active = active
        self.apply_style()

    def apply_style(self) -> None:
        if self._active:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #2d2d30;
                    color: #f3f3f3;
                    border: 1px solid #4a4a4a;
                    border-radius: 8px;
                    text-align: left;
                    padding-left: 12px;
                    font-size: 13px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: #333337;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #c5c5c5;
                    border: 1px solid transparent;
                    border-radius: 8px;
                    text-align: left;
                    padding-left: 12px;
                    font-size: 13px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #252526;
                    border: 1px solid #3a3a3a;
                }
            """)


class ConfigurationPage(QWidget):
    open_home = Signal()
    open_configuration = Signal()
    open_parameters = Signal()
    open_metadata = Signal()
    open_build = Signal()
    open_explore = Signal()

    DEFAULT_CONFIG: Dict[str, Any] = {
        "ui": {
            "compact_mode": False,
            "show_technical_names": True,
            "confirm_before_close": True,
            "confirm_before_reset": True,
            "show_path_status": True,
            "show_quick_actions": True,
            "open_folders_in_explorer": True,
        },
        "project": {
            "config_dir": "config",
            "instances_dir": "data/instances/sdplib",
            "logs_dir": "logs",
            "metadata_dir": "ISA metadata",
            "intermediates_dir": "ISA metadata/intermediates",
            "matilda_out_dir": "matilda_out",
        },
    }

    def __init__(self) -> None:
        super().__init__()

        self.project_root = self._find_project_root()
        self.config_dir = self.project_root / "config"
        self.app_config_path = self.config_dir / "app_ui_config.json"

        self._ensure_config_exists()

        self.loaded_config: Dict[str, Any] = self._load_config()
        self.working_config: Dict[str, Any] = deepcopy(self.loaded_config)

        self.path_inputs: Dict[str, Dict[str, QWidget]] = {}

        self.setObjectName("configurationPage")
        self.setStyleSheet("""
            QWidget#configurationPage {
                background-color: #111111;
            }
            QLabel {
                background: transparent;
            }
            QFrame {
                border: none;
            }
        """)

        self._build_ui()
        self._load_into_widgets()
        self._refresh_status()
        self._refresh_path_status()

    # ============================================================
    # UI
    # ============================================================

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        body = QFrame()
        body.setStyleSheet("""
            QFrame {
                background-color: #111111;
                border: none;
            }
        """)

        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # ============================================================
        # LEFT SIDEBAR
        # ============================================================

        left_sidebar = QFrame()
        left_sidebar.setFixedWidth(64)
        left_sidebar.setStyleSheet("""
            QFrame {
                background-color: #181818;
                border-right: 1px solid #3a3a3a;
            }
        """)

        left_sidebar_layout = QVBoxLayout()
        left_sidebar_layout.setContentsMargins(0, 8, 0, 8)
        left_sidebar_layout.setSpacing(8)

        home_button = SidebarButton(
            icon_relative_path="app/frontend/assets/icons/home_icon.png",
            tooltip_text="Home",
            icon_size=24,
            button_size=48,
        )
        home_button.clicked.connect(self.open_home.emit)

        parameters_button = SidebarButton(
            icon_relative_path="app/frontend/assets/icons/parameters_icon.png",
            tooltip_text="Parameters",
            icon_size=24,
            button_size=48,
        )
        parameters_button.clicked.connect(self.open_parameters.emit)

        metadata_button = SidebarButton(
            icon_relative_path="app/frontend/assets/icons/metadata_icon.png",
            tooltip_text="Metadata",
            icon_size=24,
            button_size=48,
        )
        metadata_button.clicked.connect(self.open_metadata.emit)

        build_button = SidebarButton(
            icon_relative_path="app/frontend/assets/icons/build_icon.png",
            tooltip_text="Build",
            icon_size=24,
            button_size=48,
        )
        build_button.clicked.connect(self.open_build.emit)

        explore_button = SidebarButton(
            icon_relative_path="app/frontend/assets/icons/explore_icon.png",
            tooltip_text="Explore",
            icon_size=24,
            button_size=48,
        )
        explore_button.clicked.connect(self.open_explore.emit)

        settings_button = SidebarButton(
            icon_relative_path="app/frontend/assets/icons/settings_icon.png",
            tooltip_text="Configuration",
            icon_size=24,
            button_size=48,
        )
        settings_button.set_active(True)
        settings_button.clicked.connect(self.open_configuration.emit)

        left_sidebar_layout.addWidget(home_button, 0, Qt.AlignmentFlag.AlignHCenter)
        left_sidebar_layout.addWidget(parameters_button, 0, Qt.AlignmentFlag.AlignHCenter)
        left_sidebar_layout.addWidget(metadata_button, 0, Qt.AlignmentFlag.AlignHCenter)
        left_sidebar_layout.addWidget(build_button, 0, Qt.AlignmentFlag.AlignHCenter)
        left_sidebar_layout.addWidget(explore_button, 0, Qt.AlignmentFlag.AlignHCenter)
        left_sidebar_layout.addStretch()
        left_sidebar_layout.addWidget(settings_button, 0, Qt.AlignmentFlag.AlignHCenter)
        left_sidebar.setLayout(left_sidebar_layout)

        # ============================================================
        # SECOND SIDEBAR
        # ============================================================

        second_sidebar = QFrame()
        second_sidebar.setFixedWidth(240)
        second_sidebar.setStyleSheet("""
            QFrame {
                background-color: #1f1f1f;
                border-right: 1px solid #3a3a3a;
            }
        """)

        second_sidebar_layout = QVBoxLayout()
        second_sidebar_layout.setContentsMargins(16, 20, 16, 16)
        second_sidebar_layout.setSpacing(10)

        section_title = QLabel("Configuration")
        section_title.setStyleSheet("""
            color: #f3f3f3;
            font-size: 18px;
            font-weight: 800;
        """)

        section_subtitle = QLabel("Select a configuration section")
        section_subtitle.setStyleSheet("""
            color: #a8a8a8;
            font-size: 12px;
        """)

        self.general_button = SectionButton("General", active=True)
        self.paths_button = SectionButton("Paths")
        self.quick_actions_button = SectionButton("Quick Actions")
        self.danger_zone_button = SectionButton("Danger Zone")

        self.general_button.clicked.connect(self.show_general)
        self.paths_button.clicked.connect(self.show_paths)
        self.quick_actions_button.clicked.connect(self.show_quick_actions)
        self.danger_zone_button.clicked.connect(self.show_danger_zone)

        second_sidebar_layout.addWidget(section_title)
        second_sidebar_layout.addWidget(section_subtitle)
        second_sidebar_layout.addSpacing(10)
        second_sidebar_layout.addWidget(self.general_button)
        second_sidebar_layout.addWidget(self.paths_button)
        second_sidebar_layout.addWidget(self.quick_actions_button)
        second_sidebar_layout.addWidget(self.danger_zone_button)
        second_sidebar_layout.addStretch()

        second_sidebar.setLayout(second_sidebar_layout)

        # ============================================================
        # CONTENT STACK
        # ============================================================

        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("""
            QStackedWidget {
                background-color: #2f2f2f;
                border: none;
            }
        """)

        self.general_page = self._build_general_page()
        self.paths_page = self._build_paths_page()
        self.quick_actions_page = self._build_quick_actions_page()
        self.danger_zone_page = self._build_danger_zone_page()

        self.content_stack.addWidget(self.general_page)
        self.content_stack.addWidget(self.paths_page)
        self.content_stack.addWidget(self.quick_actions_page)
        self.content_stack.addWidget(self.danger_zone_page)

        body_layout.addWidget(left_sidebar)
        body_layout.addWidget(second_sidebar)
        body_layout.addWidget(self.content_stack, 1)

        body.setLayout(body_layout)
        root_layout.addWidget(body, 1)
        self.setLayout(root_layout)

    def _build_page_container(self, title_text: str, subtitle_text: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()

        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: #2f2f2f;
                border: none;
            }
        """)

        content = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title = QLabel(title_text)
        title.setStyleSheet("""
            font-size: 28px;
            font-weight: 800;
            color: #f3f3f3;
            background: transparent;
        """)

        subtitle = QLabel(subtitle_text)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("""
            font-size: 13px;
            color: #a8a8a8;
            background: transparent;
        """)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("""
            font-size: 13px;
            font-weight: 700;
            color: #d7ba7d;
            background: transparent;
        """)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.status_label)

        content.setLayout(layout)
        scroll.setWidget(content)

        outer_layout.addWidget(scroll)
        page.setLayout(outer_layout)

        return page, layout

    def _build_general_page(self) -> QWidget:
        page, layout = self._build_page_container(
            "General Settings",
            "Adjust general application behavior and save the configuration.",
        )

        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)

        self.save_button = QPushButton("Save")
        self.reload_button = QPushButton("Reload")
        self.close_button = QPushButton("Close Application")

        for button in [self.save_button, self.reload_button, self.close_button]:
            button.setFixedHeight(38)
            button.setStyleSheet("""
                QPushButton {
                    background-color: #252526;
                    color: #f3f3f3;
                    border: 1px solid #3a3a3a;
                    border-radius: 8px;
                    padding: 0 14px;
                    font-size: 13px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #2d2d30;
                }
            """)

        self.save_button.clicked.connect(self.save_config)
        self.reload_button.clicked.connect(self.reload_config)
        self.close_button.clicked.connect(self.request_close)

        actions_row.addWidget(self.save_button)
        actions_row.addWidget(self.reload_button)
        actions_row.addWidget(self.close_button)
        actions_row.addStretch()

        layout.addLayout(actions_row)

        form_frame = QFrame()
        form_frame.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border: 1px solid #3a3a3a;
                border-radius: 12px;
            }
            QLabel {
                color: #f3f3f3;
            }
            QCheckBox {
                color: #f3f3f3;
                spacing: 8px;
            }
            QComboBox {
                background-color: #1f1f1f;
                color: #f3f3f3;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 6px 8px;
            }
        """)
        form_layout = QFormLayout()
        form_layout.setContentsMargins(18, 18, 18, 18)
        form_layout.setHorizontalSpacing(20)
        form_layout.setVerticalSpacing(12)

        self.chk_compact = QCheckBox("Enable compact layout")
        self.chk_technical = QCheckBox("Show technical names")
        self.chk_confirm_close = QCheckBox("Ask confirmation before closing")
        self.chk_confirm_reset = QCheckBox("Ask confirmation before resetting")
        self.chk_show_path_status = QCheckBox("Show path validation status")
        self.chk_show_quick_actions = QCheckBox("Show quick actions section")
        self.chk_open_folders = QCheckBox("Allow opening folders in system explorer")

        self.default_section_combo = QComboBox()
        self.default_section_combo.addItems(
            ["General", "Paths", "Quick Actions", "Danger Zone"]
        )

        form_layout.addRow("Compact mode", self.chk_compact)
        form_layout.addRow("Technical names", self.chk_technical)
        form_layout.addRow("Close confirmation", self.chk_confirm_close)
        form_layout.addRow("Reset confirmation", self.chk_confirm_reset)
        form_layout.addRow("Path status", self.chk_show_path_status)
        form_layout.addRow("Quick actions", self.chk_show_quick_actions)
        form_layout.addRow("System explorer", self.chk_open_folders)
        form_layout.addRow("Default section", self.default_section_combo)

        form_frame.setLayout(form_layout)
        layout.addWidget(form_frame)
        layout.addStretch()

        self._connect_general_change_tracking()

        return page

    def _build_paths_page(self) -> QWidget:
        page, layout = self._build_page_container(
            "Project Paths",
            "Review and edit the main project directories used by the application.",
        )

        paths_frame = QFrame()
        paths_frame.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border: 1px solid #3a3a3a;
                border-radius: 12px;
            }
            QLabel {
                color: #f3f3f3;
            }
            QLineEdit {
                background-color: #1f1f1f;
                color: #f3f3f3;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 8px 10px;
            }
            QPushButton {
                background-color: #1f1f1f;
                color: #f3f3f3;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2d2d30;
            }
        """)

        paths_layout = QVBoxLayout()
        paths_layout.setContentsMargins(18, 18, 18, 18)
        paths_layout.setSpacing(12)

        path_specs = [
            ("config_dir", "Config"),
            ("instances_dir", "Instances"),
            ("logs_dir", "Logs"),
            ("metadata_dir", "Metadata"),
            ("intermediates_dir", "Intermediates"),
            ("matilda_out_dir", "MATILDA Output"),
        ]

        for key, label_text in path_specs:
            row = QHBoxLayout()
            row.setSpacing(8)

            label = QLabel(label_text)
            label.setFixedWidth(120)

            line_edit = QLineEdit()
            line_edit.textChanged.connect(self._on_any_field_changed)

            status = QLabel("")
            status.setFixedWidth(80)
            status.setAlignment(Qt.AlignmentFlag.AlignCenter)

            open_button = QPushButton("Open")
            open_button.setFixedWidth(84)
            open_button.clicked.connect(lambda _, k=key: self._open_path_from_key(k))

            row.addWidget(label)
            row.addWidget(line_edit, 1)
            row.addWidget(status)
            row.addWidget(open_button)

            paths_layout.addLayout(row)

            self.path_inputs[key] = {
                "input": line_edit,
                "status": status,
            }

        help_label = QLabel("All relative paths are resolved from the project root.")
        help_label.setStyleSheet("color: #a8a8a8;")
        paths_layout.addWidget(help_label)

        paths_frame.setLayout(paths_layout)
        layout.addWidget(paths_frame)
        layout.addStretch()

        return page

    def _build_quick_actions_page(self) -> QWidget:
        page, layout = self._build_page_container(
            "Quick Actions",
            "Open commonly used project directories directly from the application.",
        )

        actions_frame = QFrame()
        actions_frame.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border: 1px solid #3a3a3a;
                border-radius: 12px;
            }
            QPushButton {
                background-color: #1f1f1f;
                color: #f3f3f3;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2d2d30;
            }
        """)

        actions_layout = QVBoxLayout()
        actions_layout.setContentsMargins(18, 18, 18, 18)
        actions_layout.setSpacing(10)

        row1 = QHBoxLayout()
        row2 = QHBoxLayout()

        btn_open_config = QPushButton("Open Config")
        btn_open_config.clicked.connect(
            lambda: self._open_path(self.project_root / self._get_path_value("config_dir"))
        )

        btn_open_logs = QPushButton("Open Logs")
        btn_open_logs.clicked.connect(
            lambda: self._open_path(self.project_root / self._get_path_value("logs_dir"))
        )

        btn_open_metadata = QPushButton("Open Metadata")
        btn_open_metadata.clicked.connect(
            lambda: self._open_path(self.project_root / self._get_path_value("metadata_dir"))
        )

        btn_open_intermediates = QPushButton("Open Intermediates")
        btn_open_intermediates.clicked.connect(
            lambda: self._open_path(self.project_root / self._get_path_value("intermediates_dir"))
        )

        btn_open_matilda = QPushButton("Open MATILDA Output")
        btn_open_matilda.clicked.connect(
            lambda: self._open_path(self.project_root / self._get_path_value("matilda_out_dir"))
        )

        btn_open_root = QPushButton("Open Project Root")
        btn_open_root.clicked.connect(lambda: self._open_path(self.project_root))

        row1.addWidget(btn_open_config)
        row1.addWidget(btn_open_logs)
        row1.addWidget(btn_open_metadata)

        row2.addWidget(btn_open_intermediates)
        row2.addWidget(btn_open_matilda)
        row2.addWidget(btn_open_root)

        actions_layout.addLayout(row1)
        actions_layout.addLayout(row2)

        actions_frame.setLayout(actions_layout)
        layout.addWidget(actions_frame)
        layout.addStretch()

        return page

    def _build_danger_zone_page(self) -> QWidget:
        page, layout = self._build_page_container(
            "Danger Zone",
            "Use these actions carefully. They can discard changes or close the application.",
        )

        danger_frame = QFrame()
        danger_frame.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border: 1px solid #5a2a2a;
                border-radius: 12px;
            }
            QPushButton {
                background-color: #1f1f1f;
                color: #f3f3f3;
                border: 1px solid #5a2a2a;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2d2020;
            }
            QLabel {
                color: #e0b4b4;
            }
        """)

        danger_layout = QVBoxLayout()
        danger_layout.setContentsMargins(18, 18, 18, 18)
        danger_layout.setSpacing(10)

        button_row = QHBoxLayout()

        reset_button = QPushButton("Reset to Defaults")
        reset_button.clicked.connect(self.reset_defaults)

        discard_button = QPushButton("Discard Changes")
        discard_button.clicked.connect(self.discard_changes)

        close_now_button = QPushButton("Force Close")
        close_now_button.clicked.connect(self.close_now)

        button_row.addWidget(reset_button)
        button_row.addWidget(discard_button)
        button_row.addWidget(close_now_button)

        warning = QLabel(
            "These actions can overwrite the current configuration or close the application."
        )

        danger_layout.addLayout(button_row)
        danger_layout.addWidget(warning)

        danger_frame.setLayout(danger_layout)
        layout.addWidget(danger_frame)
        layout.addStretch()

        return page

    # ============================================================
    # SECTION NAVIGATION
    # ============================================================

    def set_active_section(self, section_name: str) -> None:
        self.general_button.set_active(section_name == "general")
        self.paths_button.set_active(section_name == "paths")
        self.quick_actions_button.set_active(section_name == "quick_actions")
        self.danger_zone_button.set_active(section_name == "danger_zone")

    def show_general(self) -> None:
        self.content_stack.setCurrentIndex(0)
        self.set_active_section("general")

    def show_paths(self) -> None:
        self.content_stack.setCurrentIndex(1)
        self.set_active_section("paths")

    def show_quick_actions(self) -> None:
        self.content_stack.setCurrentIndex(2)
        self.set_active_section("quick_actions")

    def show_danger_zone(self) -> None:
        self.content_stack.setCurrentIndex(3)
        self.set_active_section("danger_zone")

    # ============================================================
    # CONFIG ACTIONS
    # ============================================================

    def save_config(self) -> None:
        try:
            self.working_config = self._collect()
            normalized = self._merge_with_defaults(self.working_config)
            self._write_json(self.app_config_path, normalized)
            self.loaded_config = deepcopy(normalized)
            self.working_config = deepcopy(normalized)
            self._refresh_status()
            self._refresh_path_status()

            QMessageBox.information(
                self,
                "Configuration",
                "Configuration saved successfully.",
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Save Error",
                f"Could not save configuration.\n\n{exc}",
            )

    def reload_config(self) -> None:
        if self._has_changes():
            reply = QMessageBox.question(
                self,
                "Reload Configuration",
                "There are unsaved changes. Reload from disk and discard them?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self.loaded_config = self._load_config()
        self.working_config = deepcopy(self.loaded_config)
        self._load_into_widgets()
        self._refresh_status()
        self._refresh_path_status()

    def reset_defaults(self) -> None:
        if self.chk_confirm_reset.isChecked():
            reply = QMessageBox.question(
                self,
                "Reset to Defaults",
                "Reset the current in-memory configuration to default values?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self.working_config = deepcopy(self.DEFAULT_CONFIG)
        self._load_into_widgets()
        self._refresh_status()
        self._refresh_path_status()

    def discard_changes(self) -> None:
        if not self._has_changes():
            QMessageBox.information(
                self,
                "Discard Changes",
                "There are no unsaved changes.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Discard Changes",
            "Discard all unsaved changes?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.working_config = deepcopy(self.loaded_config)
        self._load_into_widgets()
        self._refresh_status()
        self._refresh_path_status()

    def request_close(self) -> None:
        self.working_config = self._collect()

        if self.chk_confirm_close.isChecked():
            if self._has_changes():
                msg = QMessageBox(self)
                msg.setWindowTitle("Close Application")
                msg.setText("Unsaved changes were detected.")
                msg.setInformativeText("What would you like to do?")
                save_btn = msg.addButton("Save and Close", QMessageBox.AcceptRole)
                discard_btn = msg.addButton(
                    "Close Without Saving", QMessageBox.DestructiveRole
                )
                msg.addButton("Cancel", QMessageBox.RejectRole)
                msg.setDefaultButton(save_btn)
                msg.exec()

                clicked = msg.clickedButton()
                if clicked == save_btn:
                    self.save_config()
                    self.close_now()
                    return
                if clicked == discard_btn:
                    self.close_now()
                    return
                return

            reply = QMessageBox.question(
                self,
                "Close Application",
                "Are you sure you want to close the application?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self.close_now()

    def close_now(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.quit()
        else:
            sys.exit(0)

    # ============================================================
    # STATE
    # ============================================================

    def _has_changes(self) -> bool:
        return self._collect() != self.loaded_config

    def _refresh_status(self) -> None:
        if self._has_changes():
            self.status_label.setText("Status: unsaved changes")
            self.status_label.setStyleSheet("""
                font-size: 13px;
                font-weight: 700;
                color: #d7ba7d;
                background: transparent;
            """)
        else:
            self.status_label.setText("Status: configuration is up to date")
            self.status_label.setStyleSheet("""
                font-size: 13px;
                font-weight: 700;
                color: #6a9955;
                background: transparent;
            """)

    def _refresh_path_status(self) -> None:
        show_status = self.chk_show_path_status.isChecked()

        for widgets in self.path_inputs.values():
            input_widget = widgets["input"]
            status_widget = widgets["status"]

            if not isinstance(input_widget, QLineEdit) or not isinstance(status_widget, QLabel):
                continue

            status_widget.setVisible(show_status)
            if not show_status:
                continue

            absolute_path = self.project_root / input_widget.text().strip()

            if absolute_path.exists():
                status_widget.setText("Exists")
                status_widget.setStyleSheet("""
                    background: #2d4a34;
                    color: #d7ffd9;
                    border-radius: 6px;
                    padding: 4px 8px;
                """)
            else:
                status_widget.setText("Missing")
                status_widget.setStyleSheet("""
                    background: #5a2a2a;
                    color: #ffd7d7;
                    border-radius: 6px;
                    padding: 4px 8px;
                """)

    # ============================================================
    # WIDGET SYNC
    # ============================================================

    def _load_into_widgets(self) -> None:
        ui = self.working_config.get("ui", {})
        project = self.working_config.get("project", {})

        self.chk_compact.setChecked(ui.get("compact_mode", False))
        self.chk_technical.setChecked(ui.get("show_technical_names", True))
        self.chk_confirm_close.setChecked(ui.get("confirm_before_close", True))
        self.chk_confirm_reset.setChecked(ui.get("confirm_before_reset", True))
        self.chk_show_path_status.setChecked(ui.get("show_path_status", True))
        self.chk_show_quick_actions.setChecked(ui.get("show_quick_actions", True))
        self.chk_open_folders.setChecked(ui.get("open_folders_in_explorer", True))

        self._set_combo_value(
            self.default_section_combo,
            "General",
        )

        for key, widgets in self.path_inputs.items():
            value = project.get(key, "")
            input_widget = widgets["input"]
            if isinstance(input_widget, QLineEdit):
                input_widget.blockSignals(True)
                input_widget.setText(value)
                input_widget.blockSignals(False)

    def _collect(self) -> Dict[str, Any]:
        config = deepcopy(self.DEFAULT_CONFIG)

        config["ui"]["compact_mode"] = self.chk_compact.isChecked()
        config["ui"]["show_technical_names"] = self.chk_technical.isChecked()
        config["ui"]["confirm_before_close"] = self.chk_confirm_close.isChecked()
        config["ui"]["confirm_before_reset"] = self.chk_confirm_reset.isChecked()
        config["ui"]["show_path_status"] = self.chk_show_path_status.isChecked()
        config["ui"]["show_quick_actions"] = self.chk_show_quick_actions.isChecked()
        config["ui"]["open_folders_in_explorer"] = self.chk_open_folders.isChecked()

        for key, widgets in self.path_inputs.items():
            input_widget = widgets["input"]
            if isinstance(input_widget, QLineEdit):
                config["project"][key] = input_widget.text().strip()

        return config

    # ============================================================
    # EVENTS
    # ============================================================

    def _connect_general_change_tracking(self) -> None:
        for checkbox in [
            self.chk_compact,
            self.chk_technical,
            self.chk_confirm_close,
            self.chk_confirm_reset,
            self.chk_show_path_status,
            self.chk_show_quick_actions,
            self.chk_open_folders,
        ]:
            checkbox.stateChanged.connect(self._on_any_field_changed)

        self.default_section_combo.currentIndexChanged.connect(self._on_any_field_changed)

    def _on_any_field_changed(self) -> None:
        self.working_config = self._collect()
        self._refresh_status()
        self._refresh_path_status()

    # ============================================================
    # HELPERS
    # ============================================================

    def _open_path_from_key(self, key: str) -> None:
        self._open_path(self.project_root / self._get_path_value(key))

    def _get_path_value(self, key: str) -> str:
        widgets = self.path_inputs.get(key, {})
        input_widget = widgets.get("input")
        if isinstance(input_widget, QLineEdit):
            return input_widget.text().strip()
        return ""

    def _open_path(self, path: Path) -> None:
        try:
            if not path.exists():
                QMessageBox.warning(
                    self,
                    "Path Error",
                    f"Path does not exist:\n{path}",
                )
                return

            if not self.chk_open_folders.isChecked():
                QMessageBox.information(
                    self,
                    "Action Disabled",
                    "Opening folders in the system explorer is disabled.",
                )
                return

            system_name = platform.system()

            if system_name == "Windows":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif system_name == "Darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Open Path Error",
                f"Could not open path:\n{path}\n\n{exc}",
            )

    def _ensure_config_exists(self) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if not self.app_config_path.exists():
            self._write_json(self.app_config_path, deepcopy(self.DEFAULT_CONFIG))

    def _load_config(self) -> Dict[str, Any]:
        try:
            if not self.app_config_path.exists():
                return deepcopy(self.DEFAULT_CONFIG)

            with self.app_config_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            return self._merge_with_defaults(data)

        except Exception:
            return deepcopy(self.DEFAULT_CONFIG)

    def _write_json(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _merge_with_defaults(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        merged = deepcopy(self.DEFAULT_CONFIG)

        for section, values in user_data.items():
            if section not in merged:
                merged[section] = values
                continue

            if isinstance(merged[section], dict) and isinstance(values, dict):
                merged[section].update(values)
            else:
                merged[section] = values

        return merged

    def _find_project_root(self) -> Path:
        current = Path(__file__).resolve()

        for parent in [current.parent] + list(current.parents):
            if (parent / "config").exists():
                return parent

        return current.parent

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: str) -> None:
        index = combo.findText(value)
        combo.setCurrentIndex(index if index >= 0 else 0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ConfigurationPage()
    window.resize(1400, 850)
    window.show()
    sys.exit(app.exec())
