from __future__ import annotations

import csv
import sys
import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.frontend.components.metadata_orchestrator_config_editor import (
    MetadataOrchestratorConfigEditor,
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


class MetadataPage(QWidget):
    open_home = Signal()
    open_configuration = Signal()
    open_parameters = Signal()
    open_metadata = Signal()
    open_build = Signal()
    open_explore = Signal()
    open_genetic = Signal()

    def __init__(self) -> None:
        super().__init__()

        self.project_root = self._find_project_root()
        self.metadata_csv_path = self.project_root / "ISA metadata" / "metadata.csv"
        self.orchestrator_script_path = (
            self.project_root
            / "tools"
            / "isa"
            / "build_metadata"
            / "orchestrate_isa_metadata.py"
        )

        self.process: Optional[QProcess] = None

        self.setObjectName("metadataPage")
        self.setStyleSheet("""
            QWidget#metadataPage {
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
        metadata_button.set_active(True)
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

        genetic_button = SidebarButton(
            icon_relative_path="app/frontend/assets/icons/genetic_icon.png",
            tooltip_text="Genetic",
            icon_size=24,
            button_size=48,
        )
        genetic_button.clicked.connect(self.open_genetic.emit)

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
        layout.addWidget(explore_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(genetic_button, 0, Qt.AlignmentFlag.AlignHCenter)
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

        title = QLabel("Metadata")
        title.setStyleSheet("""
            color: #f3f3f3;
            font-size: 18px;
            font-weight: 800;
        """)

        subtitle = QLabel("Select a metadata section")
        subtitle.setStyleSheet("""
            color: #a8a8a8;
            font-size: 12px;
        """)

        self.config_button = SectionButton("Config", active=True)
        self.run_button = SectionButton("Run")
        self.explorer_button = SectionButton("Explorer")

        self.config_button.clicked.connect(self.show_config_page)
        self.run_button.clicked.connect(self.show_run_page)
        self.explorer_button.clicked.connect(self.show_explorer_page)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(10)
        layout.addWidget(self.config_button)
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

        self.content_stack.addWidget(self._build_config_page())
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
        """)

        content = QWidget()
        content.setStyleSheet("background-color: #2f2f2f;")
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
    # CONFIG PAGE
    # ============================================================

    def _build_config_page(self) -> QWidget:
        page, layout = self._build_page_container(
            "Metadata Configuration",
            "Edit metadata_orchestrator_config.json directly from the interface.",
        )

        self.config_editor = MetadataOrchestratorConfigEditor(self.project_root)
        layout.addWidget(self.config_editor)
        layout.addStretch()

        return page

    # ============================================================
    # RUN PAGE
    # ============================================================

    def _build_run_page(self) -> QWidget:
        page, layout = self._build_page_container(
            "Generate Metadata",
            "Run the metadata orchestrator and inspect the terminal output in real time.",
        )

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.generate_button = QPushButton("Generate Metadata")
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

        self.generate_button.clicked.connect(self.run_metadata_generation)
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
            f"Script: {self._to_relative_path(self.orchestrator_script_path)}"
        )
        self.script_path_label.setStyleSheet("""
            font-size: 12px;
            color: #8f8f8f;
        """)
        layout.addWidget(self.script_path_label)

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
            "Metadata Explorer",
            "Inspect the generated ISA metadata table from ISA metadata/metadata.csv.",
        )

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.refresh_table_button = QPushButton("Refresh Table")
        self.open_csv_path_button = QPushButton("Show CSV Path")

        for button in [self.refresh_table_button, self.open_csv_path_button]:
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

        self.refresh_table_button.clicked.connect(self.load_metadata_table)
        self.open_csv_path_button.clicked.connect(self.show_csv_path_message)

        top_row.addWidget(self.refresh_table_button)
        top_row.addWidget(self.open_csv_path_button)
        top_row.addStretch()

        layout.addLayout(top_row)

        self.table_status_label = QLabel("Status: waiting for metadata.csv")
        self.table_status_label.setStyleSheet("""
            font-size: 13px;
            font-weight: 700;
            color: #a8a8a8;
        """)
        layout.addWidget(self.table_status_label)

        self.table_widget = QTableWidget()
        self.table_widget.setStyleSheet("""
            QTableWidget {
                background-color: #252526;
                color: #f3f3f3;
                gridline-color: #3a3a3a;
                border: 1px solid #3a3a3a;
                border-radius: 10px;
            }
            QHeaderView::section {
                background-color: #1f1f1f;
                color: #f3f3f3;
                padding: 6px;
                border: none;
                border-right: 1px solid #3a3a3a;
                border-bottom: 1px solid #3a3a3a;
                font-weight: 700;
            }
        """)
        self.table_widget.setAlternatingRowColors(False)
        layout.addWidget(self.table_widget, 1)

        return page

    # ============================================================
    # SECTION NAVIGATION
    # ============================================================

    def set_active_section(self, section_name: str) -> None:
        self.config_button.set_active(section_name == "config")
        self.run_button.set_active(section_name == "run")
        self.explorer_button.set_active(section_name == "explorer")

    def show_config_page(self) -> None:
        self.content_stack.setCurrentIndex(0)
        self.set_active_section("config")

    def show_run_page(self) -> None:
        self.content_stack.setCurrentIndex(1)
        self.set_active_section("run")

    def show_explorer_page(self) -> None:
        self.content_stack.setCurrentIndex(2)
        self.set_active_section("explorer")
        self.load_metadata_table()

    # ============================================================
    # PROCESS / TERMINAL
    # ============================================================

    def run_metadata_generation(self) -> None:
        if not self.orchestrator_script_path.exists():
            QMessageBox.critical(
                self,
                "Script Not Found",
                f"Could not find:\n{self.orchestrator_script_path}",
            )
            return

        if self.process is not None and self.process.state() != QProcess.NotRunning:
            QMessageBox.information(
                self,
                "Process Running",
                "The metadata generation process is already running.",
            )
            return

        self.terminal_output.appendPlainText("=" * 80)
        self.terminal_output.appendPlainText("Starting metadata generation...")
        self.terminal_output.appendPlainText(f"Working directory: {self.project_root}")
        self.terminal_output.appendPlainText(f"Script: {self.orchestrator_script_path}")
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

        if getattr(sys, 'frozen', False):
            python_executable = self._find_python()
        else:
            python_executable = sys.executable

        if not python_executable:
            QMessageBox.critical(self, "Python Not Found", "Could not find a Python interpreter.")
            return

        self.process.setProgram(python_executable)
        self.process.setArguments([str(self.orchestrator_script_path)])

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
        if self.process is None:
            return

        if self.process.state() == QProcess.NotRunning:
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
            self.terminal_output.appendPlainText("[INFO] Metadata generation completed successfully.")
            self.load_metadata_table()
        else:
            self.run_status_label.setText(f"Status: failed (exit code {exit_code})")
            self.run_status_label.setStyleSheet("""
                font-size: 13px;
                font-weight: 700;
                color: #f48771;
            """)
            self.terminal_output.appendPlainText("")
            self.terminal_output.appendPlainText(
                f"[ERROR] Metadata generation finished with exit code {exit_code}."
            )

    # ============================================================
    # CSV EXPLORER
    # ============================================================

    def load_metadata_table(self) -> None:
        if not self.metadata_csv_path.exists():
            self.table_widget.clear()
            self.table_widget.setRowCount(0)
            self.table_widget.setColumnCount(0)
            self.table_status_label.setText("Status: metadata.csv not found")
            self.table_status_label.setStyleSheet("""
                font-size: 13px;
                font-weight: 700;
                color: #f48771;
            """)
            return

        try:
            with self.metadata_csv_path.open("r", encoding="utf-8-sig", newline="") as file:
                reader = csv.reader(file)
                rows = list(reader)

            if not rows:
                self.table_widget.clear()
                self.table_widget.setRowCount(0)
                self.table_widget.setColumnCount(0)
                self.table_status_label.setText("Status: metadata.csv is empty")
                self.table_status_label.setStyleSheet("""
                    font-size: 13px;
                    font-weight: 700;
                    color: #d7ba7d;
                """)
                return

            headers = rows[0]
            data_rows = rows[1:]

            self.table_widget.clear()
            self.table_widget.setColumnCount(len(headers))
            self.table_widget.setRowCount(len(data_rows))
            self.table_widget.setHorizontalHeaderLabels(headers)

            for row_idx, row_data in enumerate(data_rows):
                for col_idx, cell_value in enumerate(row_data):
                    item = QTableWidgetItem(cell_value)
                    self.table_widget.setItem(row_idx, col_idx, item)

            self.table_widget.resizeColumnsToContents()

            self.table_status_label.setText(
                f"Status: loaded {len(data_rows)} rows and {len(headers)} columns"
            )
            self.table_status_label.setStyleSheet("""
                font-size: 13px;
                font-weight: 700;
                color: #6a9955;
            """)

        except Exception as exc:
            self.table_widget.clear()
            self.table_widget.setRowCount(0)
            self.table_widget.setColumnCount(0)
            self.table_status_label.setText(f"Status: failed to load CSV ({exc})")
            self.table_status_label.setStyleSheet("""
                font-size: 13px;
                font-weight: 700;
                color: #f48771;
            """)

    def show_csv_path_message(self) -> None:
        QMessageBox.information(
            self,
            "Metadata CSV Path",
            str(self.metadata_csv_path),
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
        import shutil
        for candidate in ["python", "python3", "python.exe"]:
            path = shutil.which(candidate)
            if path:
                return path
        return None


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MetadataPage()
    window.resize(1400, 850)
    window.show()
    sys.exit(app.exec())
