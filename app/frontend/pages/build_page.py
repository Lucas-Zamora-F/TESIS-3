from __future__ import annotations

import csv
import os
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
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
        self._apply_style()

    def set_active(self, active: bool) -> None:
        self._active = active
        self._apply_style()

    def _apply_style(self) -> None:
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


class BuildPage(QWidget):
    open_home = Signal()
    open_configuration = Signal()
    open_parameters = Signal()
    open_metadata = Signal()
    open_build = Signal()

    def __init__(self) -> None:
        super().__init__()

        self.project_root = self._find_project_root()
        self.build_script_path = self.project_root / "tools" / "isa" / "run_build_is.py"
        self.build_output_dir = self.project_root / "matilda_out" / "build"

        self.process: Optional[QProcess] = None

        self.selected_run_folder: Optional[Path] = None
        self.current_explorer_path: Optional[Path] = None

        self.setObjectName("buildPage")
        self.setStyleSheet("""
            QWidget#buildPage {
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

        body_layout.addWidget(self._build_left_sidebar())
        body_layout.addWidget(self._build_second_sidebar())
        body_layout.addWidget(self._build_main_content(), 1)

        body.setLayout(body_layout)
        root_layout.addWidget(body, 1)
        self.setLayout(root_layout)

    def _build_left_sidebar(self) -> QWidget:
        left_sidebar = QFrame()
        left_sidebar.setFixedWidth(64)
        left_sidebar.setStyleSheet("""
            QFrame {
                background-color: #181818;
                border-right: 1px solid #3a3a3a;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(8)

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
        build_button.set_active(True)
        build_button.clicked.connect(self.open_build.emit)

        settings_button = SidebarButton(
            icon_relative_path="app/frontend/assets/icons/settings_icon.png",
            tooltip_text="Configuration",
            icon_size=24,
            button_size=48,
        )
        settings_button.clicked.connect(self.open_configuration.emit)

        layout.addWidget(home_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(parameters_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(metadata_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(build_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()
        layout.addWidget(settings_button, 0, Qt.AlignmentFlag.AlignHCenter)

        left_sidebar.setLayout(layout)
        return left_sidebar

    def _build_second_sidebar(self) -> QWidget:
        second_sidebar = QFrame()
        second_sidebar.setFixedWidth(240)
        second_sidebar.setStyleSheet("""
            QFrame {
                background-color: #1f1f1f;
                border-right: 1px solid #3a3a3a;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Build")
        title.setStyleSheet("""
            color: #f3f3f3;
            font-size: 18px;
            font-weight: 800;
        """)

        subtitle = QLabel("Select a build section")
        subtitle.setStyleSheet("""
            color: #a8a8a8;
            font-size: 12px;
        """)

        self.run_button = SectionButton("Run", active=True)
        self.explorer_button = SectionButton("Explorer", active=False)

        self.run_button.clicked.connect(self.show_run_page)
        self.explorer_button.clicked.connect(self.show_explorer_page)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(10)
        layout.addWidget(self.run_button)
        layout.addWidget(self.explorer_button)
        layout.addStretch()

        second_sidebar.setLayout(layout)
        return second_sidebar

    def _build_main_content(self) -> QWidget:
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("""
            QStackedWidget {
                background-color: #2f2f2f;
                border: none;
            }
        """)

        self.content_stack.addWidget(self._build_run_page())
        self.content_stack.addWidget(self._build_explorer_page())

        return self.content_stack

    def _build_page_container(
        self,
        title_text: str,
        subtitle_text: str,
    ) -> tuple[QWidget, QVBoxLayout]:
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
            QWidget {
                background-color: #2f2f2f;
            }
        """)

        content = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title_label = QLabel(title_text)
        title_label.setStyleSheet("""
            font-size: 28px;
            font-weight: 800;
            color: #f3f3f3;
            background: transparent;
        """)

        subtitle_label = QLabel(subtitle_text)
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet("""
            font-size: 13px;
            color: #a8a8a8;
            background: transparent;
        """)

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)

        content.setLayout(layout)
        scroll.setWidget(content)

        outer_layout.addWidget(scroll)
        page.setLayout(outer_layout)

        return page, layout

    # ============================================================
    # RUN PAGE
    # ============================================================

    def _build_run_page(self) -> QWidget:
        page, layout = self._build_page_container(
            "Run Build",
            "Execute tools/isa/run_build_is.py and inspect the output in real time.",
        )

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.generate_button = QPushButton("Run Build")
        self.stop_button = QPushButton("Stop")
        self.clear_terminal_button = QPushButton("Clear Terminal")

        for button in [self.generate_button, self.stop_button, self.clear_terminal_button]:
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

        self.generate_button.clicked.connect(self.run_build)
        self.stop_button.clicked.connect(self.stop_process)
        self.clear_terminal_button.clicked.connect(self.clear_terminal)
        self.stop_button.setEnabled(False)

        top_row.addWidget(self.generate_button)
        top_row.addWidget(self.stop_button)
        top_row.addWidget(self.clear_terminal_button)
        top_row.addStretch()

        layout.addLayout(top_row)

        self.run_status_label = QLabel("Status: idle")
        self.run_status_label.setStyleSheet("""
            font-size: 13px;
            font-weight: 700;
            color: #a8a8a8;
        """)
        layout.addWidget(self.run_status_label)

        self.script_path_label = QLabel(
            f"Script: {self._to_relative_path(self.build_script_path)}"
        )
        self.script_path_label.setStyleSheet("""
            font-size: 12px;
            color: #8f8f8f;
        """)
        layout.addWidget(self.script_path_label)

        self.output_path_label = QLabel(
            f"Output folder: {self._to_relative_path(self.build_output_dir)}"
        )
        self.output_path_label.setStyleSheet("""
            font-size: 12px;
            color: #8f8f8f;
        """)
        layout.addWidget(self.output_path_label)

        self.terminal_output = QPlainTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setMinimumHeight(420)
        self.terminal_output.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3a3a3a;
                border-radius: 10px;
                padding: 10px;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.terminal_output)

        layout.addStretch()
        return page

    # ============================================================
    # EXPLORER PAGE
    # ============================================================

    def _build_explorer_page(self) -> QWidget:
        page, layout = self._build_page_container(
            "Build Explorer",
            "Select a run folder inside matilda_out/build and browse CSV and PNG files separately.",
        )

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.refresh_explorer_button = QPushButton("Refresh")
        self.open_output_path_button = QPushButton("Show Output Path")

        for button in [self.refresh_explorer_button, self.open_output_path_button]:
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

        self.refresh_explorer_button.clicked.connect(self.refresh_explorer)
        self.open_output_path_button.clicked.connect(self.show_output_path_message)

        top_row.addWidget(self.refresh_explorer_button)
        top_row.addWidget(self.open_output_path_button)
        top_row.addStretch()
        layout.addLayout(top_row)

        self.explorer_status_label = QLabel("Status: waiting for build outputs")
        self.explorer_status_label.setStyleSheet("""
            font-size: 13px;
            font-weight: 700;
            color: #a8a8a8;
        """)
        layout.addWidget(self.explorer_status_label)

        run_selector_row = QHBoxLayout()
        run_selector_row.setSpacing(10)

        run_selector_label = QLabel("Run folder")
        run_selector_label.setStyleSheet("""
            color: #f3f3f3;
            font-size: 13px;
            font-weight: 700;
        """)

        self.run_folder_combo = QComboBox()
        self.run_folder_combo.setFixedHeight(38)
        self.run_folder_combo.setStyleSheet("""
            QComboBox {
                background-color: #252526;
                color: #f3f3f3;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 0 12px;
                font-size: 13px;
            }
            QComboBox:hover {
                background-color: #2d2d30;
            }
            QComboBox::drop-down {
                border: none;
                width: 28px;
            }
            QComboBox QAbstractItemView {
                background-color: #252526;
                color: #f3f3f3;
                border: 1px solid #3a3a3a;
                selection-background-color: #2d2d30;
            }
        """)
        self.run_folder_combo.currentIndexChanged.connect(self.on_run_folder_changed)

        run_selector_row.addWidget(run_selector_label)
        run_selector_row.addWidget(self.run_folder_combo, 1)
        layout.addLayout(run_selector_row)

        lists_splitter = QSplitter(Qt.Orientation.Horizontal)
        lists_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #3a3a3a;
            }
        """)

        csv_panel = QFrame()
        csv_panel.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border: 1px solid #3a3a3a;
                border-radius: 10px;
            }
        """)
        csv_layout = QVBoxLayout(csv_panel)
        csv_layout.setContentsMargins(14, 14, 14, 14)
        csv_layout.setSpacing(10)

        csv_title = QLabel("CSV Files")
        csv_title.setStyleSheet("""
            color: #f3f3f3;
            font-size: 15px;
            font-weight: 700;
        """)

        self.csv_list = QListWidget()
        self.csv_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                color: #f3f3f3;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 6px;
            }
            QListWidget::item {
                padding: 8px;
            }
            QListWidget::item:selected {
                background-color: #2d2d30;
                border-radius: 6px;
            }
        """)
        self.csv_list.itemClicked.connect(self.on_file_selected)

        csv_layout.addWidget(csv_title)
        csv_layout.addWidget(self.csv_list)

        png_panel = QFrame()
        png_panel.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border: 1px solid #3a3a3a;
                border-radius: 10px;
            }
        """)
        png_layout = QVBoxLayout(png_panel)
        png_layout.setContentsMargins(14, 14, 14, 14)
        png_layout.setSpacing(10)

        png_title = QLabel("PNG Files")
        png_title.setStyleSheet("""
            color: #f3f3f3;
            font-size: 15px;
            font-weight: 700;
        """)

        self.png_list = QListWidget()
        self.png_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                color: #f3f3f3;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 6px;
            }
            QListWidget::item {
                padding: 8px;
            }
            QListWidget::item:selected {
                background-color: #2d2d30;
                border-radius: 6px;
            }
        """)
        self.png_list.itemClicked.connect(self.on_file_selected)

        png_layout.addWidget(png_title)
        png_layout.addWidget(self.png_list)

        lists_splitter.addWidget(csv_panel)
        lists_splitter.addWidget(png_panel)
        lists_splitter.setSizes([520, 520])

        layout.addWidget(lists_splitter)

        preview_panel = QFrame()
        preview_panel.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border: 1px solid #3a3a3a;
                border-radius: 10px;
            }
        """)

        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(14, 14, 14, 14)
        preview_layout.setSpacing(10)

        self.preview_title = QLabel("Preview")
        self.preview_title.setStyleSheet("""
            color: #f3f3f3;
            font-size: 15px;
            font-weight: 700;
        """)

        self.image_preview = QLabel("Select a file to preview")
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setMinimumHeight(320)
        self.image_preview.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e;
                color: #a8a8a8;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 10px;
            }
        """)

        self.table_preview = QTableWidget()
        self.table_preview.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e1e;
                color: #f3f3f3;
                gridline-color: #3a3a3a;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
            }
            QHeaderView::section {
                background-color: #252526;
                color: #f3f3f3;
                padding: 6px;
                border: none;
                border-right: 1px solid #3a3a3a;
                border-bottom: 1px solid #3a3a3a;
                font-weight: 700;
            }
        """)

        preview_layout.addWidget(self.preview_title)
        preview_layout.addWidget(self.image_preview)
        preview_layout.addWidget(self.table_preview, 1)

        layout.addWidget(preview_panel, 1)

        self.refresh_explorer()
        return page

    # ============================================================
    # SECTION NAVIGATION
    # ============================================================

    def set_active_section(self, section_name: str) -> None:
        self.run_button.set_active(section_name == "run")
        self.explorer_button.set_active(section_name == "explorer")

    def show_run_page(self) -> None:
        self.content_stack.setCurrentIndex(0)
        self.set_active_section("run")

    def show_explorer_page(self) -> None:
        self.content_stack.setCurrentIndex(1)
        self.set_active_section("explorer")
        self.refresh_explorer()

    # ============================================================
    # RUN / TERMINAL
    # ============================================================

    def run_build(self) -> None:
        if not self.build_script_path.exists():
            QMessageBox.critical(
                self,
                "Script Not Found",
                f"Could not find:\n{self.build_script_path}",
            )
            return

        if self.process is not None and self.process.state() != QProcess.NotRunning:
            QMessageBox.information(
                self,
                "Process Running",
                "The build process is already running.",
            )
            return

        self.terminal_output.appendPlainText("=" * 80)
        self.terminal_output.appendPlainText("Starting build...")
        self.terminal_output.appendPlainText(f"Working directory: {self.project_root}")
        self.terminal_output.appendPlainText(f"Script: {self.build_script_path}")
        self.terminal_output.appendPlainText(f"Output folder: {self.build_output_dir}")
        self.terminal_output.appendPlainText("=" * 80)

        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(self.project_root))

        env = QProcessEnvironment.systemEnvironment()
        existing_pythonpath = env.value("PYTHONPATH", "")
        project_root_str = str(self.project_root)

        if existing_pythonpath:
            env.insert("PYTHONPATH", project_root_str + os.pathsep + existing_pythonpath)
        else:
            env.insert("PYTHONPATH", project_root_str)

        self.process.setProcessEnvironment(env)
        self.process.setProgram(sys.executable)
        self.process.setArguments([str(self.build_script_path)])

        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.finished.connect(self._process_finished)

        self.generate_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        self.run_status_label.setText("Status: running")
        self.run_status_label.setStyleSheet("""
            font-size: 13px;
            font-weight: 700;
            color: #d7ba7d;
        """)

        self.process.start()

    def stop_process(self) -> None:
        if self.process is None or self.process.state() == QProcess.NotRunning:
            return

        self.terminal_output.appendPlainText("")
        self.terminal_output.appendPlainText("[INFO] Stop requested by user.")
        self.process.kill()
        self.process.waitForFinished(2000)

    def clear_terminal(self) -> None:
        self.terminal_output.clear()

    def _read_stdout(self) -> None:
        if self.process is None:
            return

        data = self.process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        if data:
            self.terminal_output.insertPlainText(data)
            self.terminal_output.ensureCursorVisible()

    def _read_stderr(self) -> None:
        if self.process is None:
            return

        data = self.process.readAllStandardError().data().decode("utf-8", errors="replace")
        if data:
            self.terminal_output.insertPlainText(data)
            self.terminal_output.ensureCursorVisible()

    def _process_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        self.generate_button.setEnabled(True)
        self.stop_button.setEnabled(False)

        if exit_code == 0:
            self.run_status_label.setText("Status: completed successfully")
            self.run_status_label.setStyleSheet("""
                font-size: 13px;
                font-weight: 700;
                color: #6a9955;
            """)
            self.terminal_output.appendPlainText("")
            self.terminal_output.appendPlainText("[INFO] Build completed successfully.")
            self.refresh_explorer()
        else:
            self.run_status_label.setText(f"Status: failed (exit code {exit_code})")
            self.run_status_label.setStyleSheet("""
                font-size: 13px;
                font-weight: 700;
                color: #f48771;
            """)
            self.terminal_output.appendPlainText("")
            self.terminal_output.appendPlainText(
                f"[ERROR] Build finished with exit code {exit_code}."
            )

    # ============================================================
    # EXPLORER LOGIC
    # ============================================================

    def refresh_explorer(self) -> None:
        self.run_folder_combo.blockSignals(True)
        self.run_folder_combo.clear()
        self.csv_list.clear()
        self.png_list.clear()

        self.image_preview.setPixmap(QPixmap())
        self.image_preview.setText("Select a file to preview")

        self.table_preview.clear()
        self.table_preview.setRowCount(0)
        self.table_preview.setColumnCount(0)

        if not self.build_output_dir.exists():
            self.explorer_status_label.setText("Status: build folder not found")
            self.run_folder_combo.blockSignals(False)
            return

        run_folders = [p for p in self.build_output_dir.iterdir() if p.is_dir()]
        run_folders = sorted(run_folders, reverse=True)

        if not run_folders:
            self.explorer_status_label.setText("Status: no run folders found")
            self.run_folder_combo.blockSignals(False)
            return

        for folder in run_folders:
            self.run_folder_combo.addItem(folder.name, folder)

        self.run_folder_combo.blockSignals(False)

        # seleccionar automáticamente el más reciente
        self.run_folder_combo.setCurrentIndex(0)
        self.on_run_folder_changed()

    def on_run_folder_changed(self) -> None:
        data = self.run_folder_combo.currentData()
        if not data:
            return

        self.selected_run_folder = Path(data)

        self.csv_list.clear()
        self.png_list.clear()

        files = list(self.selected_run_folder.rglob("*"))

        csv_files = [f for f in files if f.is_file() and f.suffix.lower() == ".csv"]
        png_files = [f for f in files if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg"}]

        for f in sorted(csv_files):
            item = QListWidgetItem(f.name)
            item.setData(Qt.ItemDataRole.UserRole, str(f))
            self.csv_list.addItem(item)

        for f in sorted(png_files):
            item = QListWidgetItem(f.name)
            item.setData(Qt.ItemDataRole.UserRole, str(f))
            self.png_list.addItem(item)

        self.explorer_status_label.setText(
            f"Status: {len(csv_files)} CSV | {len(png_files)} images"
        )

    def on_file_selected(self, item: QListWidgetItem) -> None:
        file_path = Path(item.data(Qt.ItemDataRole.UserRole))
        self.current_explorer_path = file_path

        self.preview_title.setText(f"Preview: {file_path.name}")

        self.image_preview.setPixmap(QPixmap())
        self.image_preview.setText("Loading...")

        self.table_preview.clear()
        self.table_preview.setRowCount(0)
        self.table_preview.setColumnCount(0)

        suffix = file_path.suffix.lower()

        if suffix in {".png", ".jpg", ".jpeg"}:
            self._preview_image(file_path)
        elif suffix == ".csv":
            self._preview_csv(file_path)
        else:
            self.image_preview.setText("Preview not supported")

    def _preview_image(self, file_path: Path) -> None:
        pixmap = QPixmap(str(file_path))

        if pixmap.isNull():
            self.image_preview.setText("Could not load image")
            return

        scaled = pixmap.scaled(
            900,
            500,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self.image_preview.setPixmap(scaled)
        self.image_preview.setText("")

    def _preview_csv(self, file_path: Path) -> None:
        try:
            with open(file_path, newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                rows = list(reader)

            if not rows:
                self.image_preview.setText("Empty CSV")
                return

            headers = rows[0]
            data_rows = rows[1:200]

            self.table_preview.setColumnCount(len(headers))
            self.table_preview.setRowCount(len(data_rows))
            self.table_preview.setHorizontalHeaderLabels(headers)

            for i, row in enumerate(data_rows):
                for j, val in enumerate(row):
                    self.table_preview.setItem(i, j, QTableWidgetItem(val))

            self.table_preview.resizeColumnsToContents()
            self.image_preview.setText("CSV preview below")

        except Exception as e:
            self.image_preview.setText(f"Error reading CSV: {e}")

    def show_output_path_message(self) -> None:
        QMessageBox.information(
            self,
            "Build Output Path",
            str(self.build_output_dir),
        )

    # ============================================================
    # HELPERS
    # ============================================================

    def _find_project_root(self) -> Path:
        current = Path(__file__).resolve()
        for parent in [current.parent] + list(current.parents):
            if (parent / "config").exists():
                return parent
        return current.parent

    def _to_relative_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.project_root))
        except Exception:
            return str(path)
        
    def _find_python(self) -> Optional[str]:
        if not getattr(sys, 'frozen', False):
            return sys.executable
        import shutil
        for candidate in ["python", "python3", "python.exe"]:
            path = shutil.which(candidate)
            if path:
                return path
        return None


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BuildPage()
    window.resize(1400, 850)
    window.show()
    sys.exit(app.exec())