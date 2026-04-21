from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
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
from app.frontend.pages.build_page import SectionButton


class ExplorePage(QWidget):
    open_home = Signal()
    open_configuration = Signal()
    open_parameters = Signal()
    open_metadata = Signal()
    open_build = Signal()
    open_explore = Signal()

    def __init__(self) -> None:
        super().__init__()

        self.project_root = self._find_project_root()
        self.prepare_script_path = self.project_root / "tools" / "isa" / "prepare_metadata_test.py"
        self.explore_script_path = self.project_root / "tools" / "isa" / "run_explore_is.py"
        self.metadata_test_path = self.project_root / "matilda_out" / "explore_inputs" / "metadata_test.csv"
        self.base_metadata_path = self.project_root / "ISA metadata" / "metadata.csv"
        self.solver_registry_path = self.project_root / "config" / "solver_registry.json"
        self.solver_runtime_table_path = self.project_root / "ISA metadata" / "intermediates" / "solver_runtime_table.csv"
        self.explore_output_dir = self.project_root / "matilda_out" / "explore"

        self.process: Optional[QProcess] = None
        self.selected_run_folder: Optional[Path] = None
        self.current_preview_path: Optional[Path] = None

        self.setObjectName("explorePage")
        self.setStyleSheet("""
            QWidget#explorePage {
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

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        body = QFrame()
        body.setStyleSheet("QFrame { background-color: #111111; border: none; }")

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

        home_button = SidebarButton("app/frontend/assets/icons/home_icon.png", "Home", 24, 48)
        parameters_button = SidebarButton("app/frontend/assets/icons/parameters_icon.png", "Parameters", 24, 48)
        metadata_button = SidebarButton("app/frontend/assets/icons/metadata_icon.png", "Metadata", 24, 48)
        build_button = SidebarButton("app/frontend/assets/icons/build_icon.png", "Build", 24, 48)
        explore_button = SidebarButton("app/frontend/assets/icons/explore_icon.png", "Explore", 24, 48)
        settings_button = SidebarButton("app/frontend/assets/icons/settings_icon.png", "Configuration", 24, 48)

        explore_button.set_active(True)

        home_button.clicked.connect(self.open_home.emit)
        parameters_button.clicked.connect(self.open_parameters.emit)
        metadata_button.clicked.connect(self.open_metadata.emit)
        build_button.clicked.connect(self.open_build.emit)
        explore_button.clicked.connect(self.open_explore.emit)
        settings_button.clicked.connect(self.open_configuration.emit)

        layout.addWidget(home_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(parameters_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(metadata_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(build_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(explore_button, 0, Qt.AlignmentFlag.AlignHCenter)
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

        title = QLabel("Explore")
        title.setStyleSheet("color: #f3f3f3; font-size: 18px; font-weight: 800;")

        subtitle = QLabel("Control exploreIS")
        subtitle.setStyleSheet("color: #a8a8a8; font-size: 12px;")

        self.run_button = SectionButton("Run", active=True)
        self.metadata_button = SectionButton("Metadata Test")
        self.results_button = SectionButton("Results")
        self.recommendations_button = SectionButton("Recommendations")

        self.run_button.clicked.connect(self.show_run_page)
        self.metadata_button.clicked.connect(self.show_metadata_page)
        self.results_button.clicked.connect(self.show_results_page)
        self.recommendations_button.clicked.connect(self.show_recommendations_page)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(10)
        layout.addWidget(self.run_button)
        layout.addWidget(self.metadata_button)
        layout.addWidget(self.results_button)
        layout.addWidget(self.recommendations_button)
        layout.addStretch()

        second_sidebar.setLayout(layout)
        return second_sidebar

    def _build_main_content(self) -> QWidget:
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("QStackedWidget { background-color: #2f2f2f; border: none; }")

        self.content_stack.addWidget(self._build_run_page())
        self.content_stack.addWidget(self._build_metadata_page())
        self.content_stack.addWidget(self._build_results_page())
        self.content_stack.addWidget(self._build_recommendations_page())

        return self.content_stack

    def _build_page_container(self, title_text: str, subtitle_text: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea { background-color: #2f2f2f; border: none; }
            QWidget { background-color: #2f2f2f; }
        """)

        content = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title_label = QLabel(title_text)
        title_label.setStyleSheet("font-size: 28px; font-weight: 800; color: #f3f3f3;")

        subtitle_label = QLabel(subtitle_text)
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet("font-size: 13px; color: #a8a8a8;")

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)

        content.setLayout(layout)
        scroll.setWidget(content)
        outer_layout.addWidget(scroll)
        page.setLayout(outer_layout)
        return page, layout

    def _style_button(self, button: QPushButton) -> None:
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
            QPushButton:hover { background-color: #2d2d30; }
            QPushButton:disabled { color: #686868; background-color: #1e1e1e; }
        """)

    def _build_run_page(self) -> QWidget:
        page, layout = self._build_page_container(
            "Run Explore",
            "Prepare metadata_test.csv, run exploreIS, and generate empty-space target coordinates.",
        )

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.prepare_metadata_button = QPushButton("Prepare Metadata Test")
        self.run_explore_button = QPushButton("Run Explore")
        self.stop_button = QPushButton("Stop")
        self.clear_terminal_button = QPushButton("Clear Terminal")

        for button in [
            self.prepare_metadata_button,
            self.run_explore_button,
            self.stop_button,
            self.clear_terminal_button,
        ]:
            self._style_button(button)

        self.prepare_metadata_button.clicked.connect(self.prepare_metadata_test)
        self.run_explore_button.clicked.connect(self.run_explore)
        self.stop_button.clicked.connect(self.stop_process)
        self.clear_terminal_button.clicked.connect(self.clear_terminal)
        self.stop_button.setEnabled(False)

        top_row.addWidget(self.prepare_metadata_button)
        top_row.addWidget(self.run_explore_button)
        top_row.addWidget(self.stop_button)
        top_row.addWidget(self.clear_terminal_button)
        top_row.addStretch()
        layout.addLayout(top_row)

        self.run_status_label = QLabel("Status: idle")
        self.run_status_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #a8a8a8;")
        layout.addWidget(self.run_status_label)

        self.metadata_test_path_label = QLabel(f"Metadata test: {self._to_relative_path(self.metadata_test_path)}")
        self.metadata_test_path_label.setStyleSheet("font-size: 12px; color: #8f8f8f;")
        layout.addWidget(self.metadata_test_path_label)

        self.explore_script_label = QLabel(f"Script: {self._to_relative_path(self.explore_script_path)}")
        self.explore_script_label.setStyleSheet("font-size: 12px; color: #8f8f8f;")
        layout.addWidget(self.explore_script_label)

        self.terminal_output = QPlainTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setMinimumHeight(460)
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

    def _build_metadata_page(self) -> QWidget:
        page, layout = self._build_page_container(
            "Metadata Test",
            "Inspect and edit the metadata_test.csv that exploreIS will use.",
        )

        top_row = QHBoxLayout()
        self.load_metadata_button = QPushButton("Load")
        self.save_metadata_button = QPushButton("Save")
        self.add_row_button = QPushButton("Add Row")
        self.add_column_button = QPushButton("Add...")

        for button in [self.load_metadata_button, self.save_metadata_button, self.add_row_button, self.add_column_button]:
            self._style_button(button)

        self.load_metadata_button.clicked.connect(self.load_metadata_test_table)
        self.save_metadata_button.clicked.connect(self.save_metadata_test_table)
        self.add_row_button.clicked.connect(self.add_metadata_row)
        self.add_column_button.clicked.connect(self.open_add_metadata_dialog)

        top_row.addWidget(self.load_metadata_button)
        top_row.addWidget(self.save_metadata_button)
        top_row.addWidget(self.add_row_button)
        top_row.addWidget(self.add_column_button)
        top_row.addStretch()
        layout.addLayout(top_row)

        self.metadata_table_status = QLabel("Status: waiting for metadata_test.csv")
        self.metadata_table_status.setStyleSheet("font-size: 13px; font-weight: 700; color: #a8a8a8;")
        layout.addWidget(self.metadata_table_status)

        self.metadata_table = QTableWidget()
        self.metadata_table.setMinimumHeight(560)
        self.metadata_table.setStyleSheet(self._table_style())
        layout.addWidget(self.metadata_table, 1)

        self.load_metadata_test_table()
        return page

    def _build_results_page(self) -> QWidget:
        page, layout = self._build_page_container(
            "Explore Results",
            "Browse exploreIS CSV files, plots, and generated empty-space targets.",
        )

        top_row = QHBoxLayout()
        self.refresh_results_button = QPushButton("Refresh")
        self.show_output_path_button = QPushButton("Show Output Path")
        for button in [self.refresh_results_button, self.show_output_path_button]:
            self._style_button(button)
        self.refresh_results_button.clicked.connect(self.refresh_results)
        self.show_output_path_button.clicked.connect(self.show_output_path_message)
        top_row.addWidget(self.refresh_results_button)
        top_row.addWidget(self.show_output_path_button)
        top_row.addStretch()
        layout.addLayout(top_row)

        run_selector_row = QHBoxLayout()
        run_label = QLabel("Output folder")
        run_label.setStyleSheet("color: #f3f3f3; font-size: 13px; font-weight: 700;")
        self.run_folder_combo = QComboBox()
        self.run_folder_combo.setFixedHeight(38)
        self.run_folder_combo.setStyleSheet(self._combo_style())
        self.run_folder_combo.currentIndexChanged.connect(self.on_run_folder_changed)
        run_selector_row.addWidget(run_label)
        run_selector_row.addWidget(self.run_folder_combo, 1)
        layout.addLayout(run_selector_row)

        self.results_status_label = QLabel("Status: waiting for explore outputs")
        self.results_status_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #a8a8a8;")
        layout.addWidget(self.results_status_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background-color: #3a3a3a; }")

        csv_panel, self.csv_list = self._build_file_list("CSV Files")
        png_panel, self.png_list = self._build_file_list("Images")
        self.csv_list.itemClicked.connect(self.on_file_selected)
        self.png_list.itemClicked.connect(self.on_file_selected)
        splitter.addWidget(csv_panel)
        splitter.addWidget(png_panel)
        splitter.setSizes([520, 520])
        layout.addWidget(splitter)

        preview_panel = QFrame()
        preview_panel.setStyleSheet(self._panel_style())
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(14, 14, 14, 14)
        preview_layout.setSpacing(10)

        self.preview_title = QLabel("Preview")
        self.preview_title.setStyleSheet("color: #f3f3f3; font-size: 15px; font-weight: 700;")
        self.image_preview = QLabel("Select a file to preview")
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setMinimumHeight(280)
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
        self.table_preview.setStyleSheet(self._table_style())
        preview_layout.addWidget(self.preview_title)
        preview_layout.addWidget(self.image_preview)
        preview_layout.addWidget(self.table_preview, 1)
        layout.addWidget(preview_panel, 1)

        self.refresh_results()
        return page

    def _build_recommendations_page(self) -> QWidget:
        page, layout = self._build_page_container(
            "Recommendations",
            "Review empty-space targets and high-level guidance for future instance generation.",
        )

        top_row = QHBoxLayout()
        self.refresh_recommendations_button = QPushButton("Refresh Recommendations")
        self.regenerate_targets_button = QPushButton("Recompute Empty Spaces")
        for button in [self.refresh_recommendations_button, self.regenerate_targets_button]:
            self._style_button(button)
        self.refresh_recommendations_button.clicked.connect(self.refresh_recommendations)
        self.regenerate_targets_button.clicked.connect(self.recompute_empty_spaces)
        top_row.addWidget(self.refresh_recommendations_button)
        top_row.addWidget(self.regenerate_targets_button)
        top_row.addStretch()
        layout.addLayout(top_row)

        self.recommendations_text = QPlainTextEdit()
        self.recommendations_text.setReadOnly(True)
        self.recommendations_text.setMinimumHeight(180)
        self.recommendations_text.setStyleSheet("""
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
        layout.addWidget(self.recommendations_text)

        self.empty_space_table = QTableWidget()
        self.empty_space_table.setMinimumHeight(420)
        self.empty_space_table.setStyleSheet(self._table_style())
        layout.addWidget(self.empty_space_table, 1)

        self.refresh_recommendations()
        return page

    def show_run_page(self) -> None:
        self.content_stack.setCurrentIndex(0)
        self._set_active_section("run")

    def show_metadata_page(self) -> None:
        self.content_stack.setCurrentIndex(1)
        self._set_active_section("metadata")
        self.load_metadata_test_table()

    def show_results_page(self) -> None:
        self.content_stack.setCurrentIndex(2)
        self._set_active_section("results")
        self.refresh_results()

    def show_recommendations_page(self) -> None:
        self.content_stack.setCurrentIndex(3)
        self._set_active_section("recommendations")
        self.refresh_recommendations()

    def _set_active_section(self, section: str) -> None:
        self.run_button.set_active(section == "run")
        self.metadata_button.set_active(section == "metadata")
        self.results_button.set_active(section == "results")
        self.recommendations_button.set_active(section == "recommendations")

    def prepare_metadata_test(self) -> None:
        self._start_process(
            [str(self.prepare_script_path), "--output", str(self.metadata_test_path)],
            "Preparing metadata_test.csv...",
        )

    def run_explore(self) -> None:
        if not self.metadata_test_path.exists():
            QMessageBox.information(
                self,
                "metadata_test.csv Not Found",
                "Prepare metadata_test.csv before running exploreIS.",
            )
            return
        self._start_process(
            [str(self.explore_script_path), "--metadata-test-path", str(self.metadata_test_path)],
            "Starting exploreIS...",
        )

    def recompute_empty_spaces(self) -> None:
        run_dir = self._selected_or_latest_run()
        if run_dir is None:
            QMessageBox.information(self, "No Explore Output", "No explore output folder was found.")
            return

        script_path = self.project_root / "tools" / "isa" / "analyze_explore_empty_space.py"
        self._start_process(
            [str(script_path), "--explore-run-dir", str(run_dir), "--top-k", "12", "--grid-size", "90"],
            "Recomputing empty-space targets...",
        )

    def _start_process(self, arguments: list[str], heading: str) -> None:
        if self.process is not None and self.process.state() != QProcess.NotRunning:
            QMessageBox.information(self, "Process Running", "An explore process is already running.")
            return

        python = self._find_python()
        if python is None:
            QMessageBox.critical(self, "Python Not Found", "Could not locate a Python interpreter.")
            return

        self.terminal_output.appendPlainText("=" * 80)
        self.terminal_output.appendPlainText(heading)
        self.terminal_output.appendPlainText(f"Working directory: {self.project_root}")
        self.terminal_output.appendPlainText(" ".join([python] + arguments))
        self.terminal_output.appendPlainText("=" * 80)

        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(self.project_root))

        env = QProcessEnvironment.systemEnvironment()
        existing_pythonpath = env.value("PYTHONPATH", "")
        project_root_str = str(self.project_root)
        env.insert("PYTHONPATH", project_root_str + os.pathsep + existing_pythonpath if existing_pythonpath else project_root_str)
        self.process.setProcessEnvironment(env)

        self.process.setProgram(python)
        self.process.setArguments(arguments)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.finished.connect(self._process_finished)

        self.prepare_metadata_button.setEnabled(False)
        self.run_explore_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.run_status_label.setText("Status: running")
        self.run_status_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #d7ba7d;")
        self.process.start()

    def stop_process(self) -> None:
        if self.process is None or self.process.state() == QProcess.NotRunning:
            return
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
        self.prepare_metadata_button.setEnabled(True)
        self.run_explore_button.setEnabled(True)
        self.stop_button.setEnabled(False)

        if exit_code == 0:
            self.run_status_label.setText("Status: completed successfully")
            self.run_status_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #6a9955;")
            self.terminal_output.appendPlainText("[INFO] Process completed successfully.")
            self.load_metadata_test_table()
            self.refresh_results()
            self.refresh_recommendations()
        else:
            self.run_status_label.setText(f"Status: failed (exit code {exit_code})")
            self.run_status_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #f48771;")
            self.terminal_output.appendPlainText(f"[ERROR] Process finished with exit code {exit_code}.")

    def load_metadata_test_table(self) -> None:
        self.metadata_table.clear()
        self.metadata_table.setRowCount(0)
        self.metadata_table.setColumnCount(0)

        if not self.metadata_test_path.exists():
            self.metadata_table_status.setText("Status: metadata_test.csv not found")
            return

        try:
            with self.metadata_test_path.open("r", encoding="utf-8-sig", newline="") as file:
                rows = list(csv.reader(file))

            if not rows:
                self.metadata_table_status.setText("Status: metadata_test.csv is empty")
                return

            headers = rows[0]
            data_rows = rows[1:]
            self.metadata_table.setColumnCount(len(headers))
            self.metadata_table.setRowCount(len(data_rows))
            self.metadata_table.setHorizontalHeaderLabels(headers)

            for row_idx, row in enumerate(data_rows):
                for col_idx, value in enumerate(row):
                    self.metadata_table.setItem(row_idx, col_idx, QTableWidgetItem(value))

            self.metadata_table.resizeColumnsToContents()
            self.metadata_table_status.setText(
                f"Status: loaded {len(data_rows)} rows and {len(headers)} columns"
            )
        except Exception as exc:
            self.metadata_table_status.setText(f"Status: error loading CSV: {exc}")

    def save_metadata_test_table(self) -> None:
        if self.metadata_table.columnCount() == 0:
            return

        headers = [
            self.metadata_table.horizontalHeaderItem(col).text()
            if self.metadata_table.horizontalHeaderItem(col)
            else f"column_{col + 1}"
            for col in range(self.metadata_table.columnCount())
        ]

        self.metadata_test_path.parent.mkdir(parents=True, exist_ok=True)
        with self.metadata_test_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(headers)
            for row in range(self.metadata_table.rowCount()):
                writer.writerow([
                    self.metadata_table.item(row, col).text()
                    if self.metadata_table.item(row, col)
                    else ""
                    for col in range(self.metadata_table.columnCount())
                ])

        self.metadata_table_status.setText(f"Status: saved {self._to_relative_path(self.metadata_test_path)}")

    def add_metadata_row(self) -> None:
        self.metadata_table.insertRow(self.metadata_table.rowCount())

    def open_add_metadata_dialog(self) -> None:
        if self.metadata_table.columnCount() == 0:
            self.load_metadata_test_table()

        dialog = QDialog(self)
        dialog.setWindowTitle("Add to metadata_test")
        dialog.setStyleSheet("""
            QDialog {
                background-color: #252526;
                color: #f3f3f3;
            }
            QLabel {
                color: #f3f3f3;
                font-size: 13px;
            }
            QComboBox {
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
                border-radius: 6px;
                padding: 6px 12px;
            }
        """)

        layout = QFormLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        action_combo = QComboBox()
        action_combo.addItem("Solver", "solver")
        action_combo.addItem("Feature column", "feature")
        action_combo.addItem("Instance row", "instance")
        layout.addRow("Add", action_combo)

        solver_combo = QComboBox()
        for solver_name, display_name in self._load_available_solvers():
            solver_combo.addItem(f"{display_name} ({solver_name})", solver_name)
        layout.addRow("Solver", solver_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        def update_visibility() -> None:
            solver_combo.setVisible(action_combo.currentData() == "solver")
            layout.labelForField(solver_combo).setVisible(action_combo.currentData() == "solver")

        action_combo.currentIndexChanged.connect(update_visibility)
        update_visibility()

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        action = action_combo.currentData()
        if action == "solver":
            solver_name = solver_combo.currentData()
            if solver_name:
                self.add_solver_column(str(solver_name))
        elif action == "feature":
            self.add_feature_column_with_prompt()
        elif action == "instance":
            self.add_instance_row_with_prompt()

    def add_solver_column(self, solver_name: str) -> None:
        column_name = f"algo_{solver_name}"
        if self._find_table_column(column_name) is not None:
            QMessageBox.information(
                self,
                "Solver Already Present",
                f"The column {column_name} already exists in metadata_test.csv.",
            )
            return

        values_by_instance = self._load_solver_values_by_instance(column_name)
        col = self.metadata_table.columnCount()
        self.metadata_table.insertColumn(col)
        self.metadata_table.setHorizontalHeaderItem(col, QTableWidgetItem(column_name))

        instance_col = self._find_instances_column()
        filled = 0
        for row in range(self.metadata_table.rowCount()):
            instance_name = ""
            if instance_col is not None and self.metadata_table.item(row, instance_col):
                instance_name = self.metadata_table.item(row, instance_col).text().strip()
            value = values_by_instance.get(instance_name, "")
            if value != "":
                filled += 1
            self.metadata_table.setItem(row, col, QTableWidgetItem(value))

        self.metadata_table.resizeColumnsToContents()
        self.metadata_table_status.setText(
            f"Status: added {column_name}; filled {filled}/{self.metadata_table.rowCount()} rows"
        )

    def add_feature_column_with_prompt(self) -> None:
        text, ok = QInputDialog.getText(
            self,
            "Add Feature",
            "Feature name without prefix:",
            text="new_feature",
        )
        if not ok:
            return
        feature_name = text.strip()
        if not feature_name:
            return
        column_name = feature_name if feature_name.startswith("feature_") else f"feature_{feature_name}"
        if self._find_table_column(column_name) is not None:
            QMessageBox.information(self, "Feature Already Present", f"{column_name} already exists.")
            return
        col = self.metadata_table.columnCount()
        self.metadata_table.insertColumn(col)
        self.metadata_table.setHorizontalHeaderItem(col, QTableWidgetItem(column_name))
        for row in range(self.metadata_table.rowCount()):
            self.metadata_table.setItem(row, col, QTableWidgetItem(""))
        self.metadata_table_status.setText(f"Status: added empty feature column {column_name}")

    def add_instance_row_with_prompt(self) -> None:
        text, ok = QInputDialog.getText(
            self,
            "Add Instance",
            "Instance name:",
            text="new_instance",
        )
        if not ok:
            return
        instance_name = text.strip()
        if not instance_name:
            return
        row = self.metadata_table.rowCount()
        self.metadata_table.insertRow(row)
        instance_col = self._find_instances_column()
        if instance_col is not None:
            self.metadata_table.setItem(row, instance_col, QTableWidgetItem(instance_name))
        self.metadata_table_status.setText(f"Status: added instance row {instance_name}")

    def _load_available_solvers(self) -> list[tuple[str, str]]:
        if not self.solver_registry_path.exists():
            return []
        try:
            data = json.loads(self.solver_registry_path.read_text(encoding="utf-8"))
        except Exception:
            return []

        solvers: list[tuple[str, str]] = []
        available = data.get("available_solvers", {})
        for family in available.values():
            if not isinstance(family, dict):
                continue
            for solver_name, solver_meta in family.items():
                display_name = solver_name
                if isinstance(solver_meta, dict):
                    display_name = str(solver_meta.get("display_name", solver_name))
                solvers.append((str(solver_name), display_name))
        return sorted(solvers, key=lambda item: item[0])

    def _load_solver_values_by_instance(self, column_name: str) -> dict[str, str]:
        for csv_path in [self.solver_runtime_table_path, self.base_metadata_path]:
            values = self._load_column_by_instance(csv_path, column_name)
            if values:
                return values
        return {}

    def _load_column_by_instance(self, csv_path: Path, column_name: str) -> dict[str, str]:
        if not csv_path.exists():
            return {}

        try:
            with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
                reader = csv.DictReader(file)
                if not reader.fieldnames or column_name not in reader.fieldnames:
                    return {}

                instance_field = None
                for candidate in ["instances", "Instances", "Instance", "instance"]:
                    if candidate in reader.fieldnames:
                        instance_field = candidate
                        break
                if instance_field is None:
                    return {}

                values: dict[str, str] = {}
                for row in reader:
                    instance_name = str(row.get(instance_field, "")).strip()
                    if instance_name:
                        values[instance_name] = str(row.get(column_name, "")).strip()
                return values
        except Exception:
            return {}

    def _find_table_column(self, column_name: str) -> Optional[int]:
        for col in range(self.metadata_table.columnCount()):
            item = self.metadata_table.horizontalHeaderItem(col)
            if item and item.text().strip().lower() == column_name.lower():
                return col
        return None

    def _find_instances_column(self) -> Optional[int]:
        for candidate in ["instances", "Instances", "Instance", "instance"]:
            col = self._find_table_column(candidate)
            if col is not None:
                return col
        return None

    def refresh_results(self) -> None:
        if not hasattr(self, "run_folder_combo"):
            return

        self.run_folder_combo.blockSignals(True)
        self.run_folder_combo.clear()
        self.csv_list.clear()
        self.png_list.clear()
        self._clear_preview("Select a file to preview")

        if not self.explore_output_dir.exists():
            self.results_status_label.setText("Status: explore folder not found")
            self.run_folder_combo.blockSignals(False)
            return

        files = [p for p in self.explore_output_dir.rglob("*") if p.is_file()]
        if not files:
            self.results_status_label.setText("Status: no explore outputs found")
            self.run_folder_combo.blockSignals(False)
            return

        self.run_folder_combo.addItem(
            self._to_relative_path(self.explore_output_dir),
            self.explore_output_dir,
        )

        self.run_folder_combo.blockSignals(False)
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
        csv_files = sorted([f for f in files if f.is_file() and f.suffix.lower() == ".csv"])
        png_files = sorted([f for f in files if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg"}])

        for file_path in csv_files:
            item = QListWidgetItem(file_path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(file_path))
            self.csv_list.addItem(item)

        for file_path in png_files:
            item = QListWidgetItem(file_path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(file_path))
            self.png_list.addItem(item)

        self.results_status_label.setText(f"Status: {len(csv_files)} CSV | {len(png_files)} images")

    def on_file_selected(self, item: QListWidgetItem) -> None:
        file_path = Path(item.data(Qt.ItemDataRole.UserRole))
        self.current_preview_path = file_path
        self.preview_title.setText(f"Preview: {file_path.name}")
        self._clear_preview("Loading...")

        if file_path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            self._preview_image(file_path)
        elif file_path.suffix.lower() == ".csv":
            self._preview_csv(file_path)

    def _preview_image(self, file_path: Path) -> None:
        pixmap = QPixmap(str(file_path))
        if pixmap.isNull():
            self.image_preview.setText("Could not load image")
            return
        scaled = pixmap.scaled(900, 500, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.image_preview.setPixmap(scaled)
        self.image_preview.setText("")

    def _preview_csv(self, file_path: Path) -> None:
        try:
            with file_path.open(newline="", encoding="utf-8-sig") as file:
                rows = list(csv.reader(file))
            if not rows:
                self.image_preview.setText("Empty CSV")
                return
            headers = rows[0]
            data_rows = rows[1:200]
            self.table_preview.setColumnCount(len(headers))
            self.table_preview.setRowCount(len(data_rows))
            self.table_preview.setHorizontalHeaderLabels(headers)
            for row_idx, row in enumerate(data_rows):
                for col_idx, value in enumerate(row):
                    self.table_preview.setItem(row_idx, col_idx, QTableWidgetItem(value))
            self.table_preview.resizeColumnsToContents()
            self.image_preview.setText("CSV preview below")
        except Exception as exc:
            self.image_preview.setText(f"Error reading CSV: {exc}")

    def refresh_recommendations(self) -> None:
        if not hasattr(self, "recommendations_text"):
            return

        run_dir = self._selected_or_latest_run()
        lines = []
        if run_dir is None:
            self.recommendations_text.setPlainText("No explore output is available yet.")
            self.empty_space_table.clear()
            self.empty_space_table.setRowCount(0)
            self.empty_space_table.setColumnCount(0)
            return

        lines.append(f"Explore output: {self._to_relative_path(run_dir)}")
        coordinates_path = run_dir / "coordinates.csv"
        empty_targets_path = run_dir / "empty_space_targets.csv"
        footprint_path = run_dir / "footprint_performance.csv"

        if coordinates_path.exists():
            rows = self._read_csv_rows(coordinates_path)
            lines.append(f"Projected instances: {max(0, len(rows) - 1)}")

        if empty_targets_path.exists():
            rows = self._read_csv_rows(empty_targets_path)
            lines.append(f"Empty-space targets: {max(0, len(rows) - 1)}")
            lines.append("Use z_1/z_2 targets as objectives for the future instance generator.")
            self._load_csv_into_table(empty_targets_path, self.empty_space_table)
        else:
            lines.append("Empty-space targets are not available. Recompute them from this page.")
            self.empty_space_table.clear()
            self.empty_space_table.setRowCount(0)
            self.empty_space_table.setColumnCount(0)

        if footprint_path.exists():
            lines.append("Footprint summary is available for algorithm coverage analysis.")

        manifest_path = run_dir / "explore_manifest.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                source = manifest.get("metadata_test_source")
                if source:
                    lines.append(f"Metadata source: {source}")
            except Exception:
                pass

        self.recommendations_text.setPlainText("\n".join(lines))

    def _load_csv_into_table(self, file_path: Path, table: QTableWidget) -> None:
        rows = self._read_csv_rows(file_path)
        table.clear()
        table.setRowCount(0)
        table.setColumnCount(0)
        if not rows:
            return
        headers = rows[0]
        data_rows = rows[1:]
        table.setColumnCount(len(headers))
        table.setRowCount(len(data_rows))
        table.setHorizontalHeaderLabels(headers)
        for row_idx, row in enumerate(data_rows):
            for col_idx, value in enumerate(row):
                table.setItem(row_idx, col_idx, QTableWidgetItem(value))
        table.resizeColumnsToContents()

    def _read_csv_rows(self, file_path: Path) -> list[list[str]]:
        with file_path.open("r", encoding="utf-8-sig", newline="") as file:
            return list(csv.reader(file))

    def _selected_or_latest_run(self) -> Optional[Path]:
        if self.selected_run_folder and self.selected_run_folder.exists():
            return self.selected_run_folder
        if not self.explore_output_dir.exists():
            return None
        if (self.explore_output_dir / "coordinates.csv").exists():
            return self.explore_output_dir
        return None

    def _clear_preview(self, text: str) -> None:
        self.image_preview.setPixmap(QPixmap())
        self.image_preview.setText(text)
        self.table_preview.clear()
        self.table_preview.setRowCount(0)
        self.table_preview.setColumnCount(0)

    def show_output_path_message(self) -> None:
        QMessageBox.information(self, "Explore Output Path", str(self.explore_output_dir))

    def _build_file_list(self, title: str) -> tuple[QFrame, QListWidget]:
        panel = QFrame()
        panel.setStyleSheet(self._panel_style())
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        label = QLabel(title)
        label.setStyleSheet("color: #f3f3f3; font-size: 15px; font-weight: 700;")
        list_widget = QListWidget(panel)
        list_widget.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                color: #f3f3f3;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 6px;
            }
            QListWidget::item { padding: 8px; }
            QListWidget::item:selected { background-color: #2d2d30; border-radius: 6px; }
        """)
        layout.addWidget(label)
        layout.addWidget(list_widget)
        return panel, list_widget

    def _panel_style(self) -> str:
        return """
            QFrame {
                background-color: #252526;
                border: 1px solid #3a3a3a;
                border-radius: 10px;
            }
        """

    def _table_style(self) -> str:
        return """
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
        """

    def _combo_style(self) -> str:
        return """
            QComboBox {
                background-color: #252526;
                color: #f3f3f3;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 0 12px;
                font-size: 13px;
            }
            QComboBox:hover { background-color: #2d2d30; }
            QComboBox::drop-down { border: none; width: 28px; }
            QComboBox QAbstractItemView {
                background-color: #252526;
                color: #f3f3f3;
                border: 1px solid #3a3a3a;
                selection-background-color: #2d2d30;
            }
        """

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
        if not getattr(sys, "frozen", False):
            return sys.executable
        import shutil
        for candidate in ["python", "python3", "python.exe"]:
            path = shutil.which(candidate)
            if path:
                return path
        return None


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ExplorePage()
    window.resize(1400, 850)
    window.show()
    sys.exit(app.exec())
