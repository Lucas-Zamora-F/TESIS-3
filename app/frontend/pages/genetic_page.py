from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.frontend.components.sidebar_button import SidebarButton
from app.frontend.pages.build_page import SectionButton


class ClickableInstanceSpaceCanvas(FigureCanvas):
    def __init__(self, parent: QWidget | None = None) -> None:
        self.figure = Figure(figsize=(8, 6), facecolor="#1e1e1e")
        super().__init__(self.figure)
        self.setParent(parent)
        self.ax = self.figure.add_subplot(111)
        self.coords = None
        self.outline = None
        self.selected_point: tuple[float, float] | None = None
        self.on_point_selected = None
        self.mpl_connect("button_press_event", self._on_click)
        self.setMinimumHeight(520)

    def set_data(self, coords, outline=None) -> None:
        self.coords = coords
        self.outline = outline
        self.selected_point = None
        self.draw_map()

    def draw_map(self) -> None:
        self.ax.clear()
        self.ax.set_facecolor("#1e1e1e")

        if self.coords is not None and not self.coords.empty:
            self.ax.scatter(
                self.coords["z_1"],
                self.coords["z_2"],
                s=24,
                color="#808080",
                alpha=0.8,
                label="Existing instances",
            )

        if self.outline is not None and not self.outline.empty:
            self.ax.plot(
                self.outline["z_1"],
                self.outline["z_2"],
                color="#d8d8d8",
                linewidth=2.0,
                alpha=0.9,
                label="Instance space outline",
            )

        if self.selected_point is not None:
            self.ax.scatter(
                [self.selected_point[0]],
                [self.selected_point[1]],
                s=120,
                color="#e05050",
                marker="o",
                edgecolors="white",
                linewidths=0.8,
                label="Selected target",
                zorder=5,
            )

        self.ax.set_aspect("equal", adjustable="box")
        self.ax.set_title("Click a target point", color="#f3f3f3", fontsize=12, pad=8)
        self.ax.set_xlabel("z_1", color="#a8a8a8")
        self.ax.set_ylabel("z_2", color="#a8a8a8")
        self.ax.tick_params(colors="#a8a8a8")
        self.ax.grid(True, alpha=0.15, color="#555555")
        for spine in self.ax.spines.values():
            spine.set_edgecolor("#3a3a3a")
        self.ax.legend(
            loc="best",
            fontsize=8,
            facecolor="#2d2d30",
            edgecolor="#3a3a3a",
            labelcolor="#f3f3f3",
        )
        self.figure.tight_layout()
        self.draw_idle()

    def _on_click(self, event) -> None:
        if event.inaxes != self.ax or event.xdata is None or event.ydata is None:
            return
        self.selected_point = (float(event.xdata), float(event.ydata))
        self.draw_map()
        if callable(self.on_point_selected):
            self.on_point_selected(self.selected_point)


class GeneticPage(QWidget):
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
        self.fill_script_path = (
            self.project_root / "tools" / "genetic_algorithms" / "fill_empty_space.py"
        )
        self.fill_multiple_script_path = (
            self.project_root
            / "tools"
            / "genetic_algorithms"
            / "fill_empty_space_multiple.py"
        )
        self.fill_point_script_path = (
            self.project_root / "tools" / "genetic_algorithms" / "fill_point_target.py"
        )
        self.explore_dir = self.project_root / "matilda_out" / "explore"
        self.build_dir = self.project_root / "matilda_out" / "build"
        self.genetic_output_dir = (
            self.project_root / "matilda_out" / "genetic" / "fill_empty_space"
        )
        self.genetic_multiple_output_dir = (
            self.project_root / "matilda_out" / "genetic" / "fill_empty_space_multiple"
        )
        self.genetic_point_output_dir = (
            self.project_root / "matilda_out" / "genetic" / "fill_point_target"
        )
        self.instance_dest_dir = (
            self.project_root / "data" / "instances" / "genetic generated" / "fill empty space"
        )
        self.point_instance_dest_dir = (
            self.project_root / "data" / "instances" / "genetic generated" / "point target"
        )
        self.instances_config_path = self.project_root / "config" / "instances_config.json"
        self.genetic_config_path = self.project_root / "config" / "genetic_config.json"

        self.process: Optional[QProcess] = None
        self._last_result: Optional[dict] = None
        self._last_multiple_result: Optional[dict] = None
        self._last_point_result: Optional[dict] = None
        self._selected_point: Optional[tuple[float, float]] = None
        self._last_target_id: Optional[str] = None

        self.setObjectName("geneticPage")
        self.setStyleSheet("""
            QWidget#geneticPage {
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

    # =========================================================================
    # UI CONSTRUCTION
    # =========================================================================

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

    # ── Left sidebar (icons) ──────────────────────────────────────────────────

    def _build_left_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setFixedWidth(64)
        sidebar.setStyleSheet("""
            QFrame {
                background-color: #181818;
                border-right: 1px solid #3a3a3a;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(8)

        def _nav_btn(icon_name: str, tooltip: str, signal) -> SidebarButton:
            btn = SidebarButton(
                icon_relative_path=f"app/frontend/assets/icons/{icon_name}",
                tooltip_text=tooltip,
                icon_size=24,
                button_size=48,
            )
            btn.clicked.connect(signal)
            return btn

        layout.addWidget(_nav_btn("home_icon.png",       "Home",          self.open_home.emit),          0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(_nav_btn("parameters_icon.png", "Parameters",    self.open_parameters.emit),    0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(_nav_btn("metadata_icon.png",   "Metadata",      self.open_metadata.emit),      0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(_nav_btn("build_icon.png",      "Build",         self.open_build.emit),         0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(_nav_btn("explore_icon.png",    "Explore",       self.open_explore.emit),       0, Qt.AlignmentFlag.AlignHCenter)

        genetic_btn = SidebarButton(
            icon_relative_path="app/frontend/assets/icons/genetic_icon.png",
            tooltip_text="Genetic",
            icon_size=24,
            button_size=48,
        )
        genetic_btn.set_active(True)
        genetic_btn.clicked.connect(self.open_genetic.emit)
        layout.addWidget(genetic_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch()

        layout.addWidget(_nav_btn("settings_icon.png",   "Configuration", self.open_configuration.emit), 0, Qt.AlignmentFlag.AlignHCenter)

        sidebar.setLayout(layout)
        return sidebar

    # ── Second sidebar (sections) ─────────────────────────────────────────────

    def _build_second_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet("""
            QFrame {
                background-color: #1f1f1f;
                border-right: 1px solid #3a3a3a;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Genetic")
        title.setStyleSheet("color: #f3f3f3; font-size: 18px; font-weight: 800;")

        subtitle = QLabel("Instance generation")
        subtitle.setStyleSheet("color: #a8a8a8; font-size: 12px;")

        self.fill_btn = SectionButton("Fill Empty Space", active=True)
        self.fill_btn.clicked.connect(self._show_fill_page)
        self.fill_multiple_btn = SectionButton("Fill Multiple")
        self.fill_multiple_btn.clicked.connect(self._show_fill_multiple_page)
        self.point_target_btn = SectionButton("Point Target")
        self.point_target_btn.clicked.connect(self._show_point_target_page)
        self.genetic_config_btn = SectionButton("Config")
        self.genetic_config_btn.clicked.connect(self._show_genetic_config_page)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(10)
        layout.addWidget(self.fill_btn)
        layout.addWidget(self.fill_multiple_btn)
        layout.addWidget(self.point_target_btn)
        layout.addWidget(self.genetic_config_btn)
        layout.addStretch()

        sidebar.setLayout(layout)
        return sidebar

    # ── Main content ──────────────────────────────────────────────────────────

    def _build_main_content(self) -> QWidget:
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("""
            QStackedWidget { background-color: #2f2f2f; border: none; }
        """)
        self.content_stack.addWidget(self._build_fill_page())
        self.content_stack.addWidget(self._build_fill_multiple_page())
        self.content_stack.addWidget(self._build_point_target_page())
        self.content_stack.addWidget(self._build_genetic_config_page())
        self._preview_multiple_initial_map()
        return self.content_stack

    def _build_page_container(
        self, title_text: str, subtitle_text: str
    ) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea { background-color: #2f2f2f; border: none; }
            QLabel { background: transparent; border: none; }
        """)

        content = QWidget()
        content.setStyleSheet("background-color: #2f2f2f;")
        layout = QVBoxLayout()
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        lbl_title = QLabel(title_text)
        lbl_title.setStyleSheet(
            "font-size: 28px; font-weight: 800; color: #f3f3f3; background: transparent;"
        )
        lbl_sub = QLabel(subtitle_text)
        lbl_sub.setWordWrap(True)
        lbl_sub.setStyleSheet(
            "font-size: 13px; color: #a8a8a8; background: transparent;"
        )

        layout.addWidget(lbl_title)
        layout.addWidget(lbl_sub)

        content.setLayout(layout)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        page.setLayout(outer)
        return page, layout

    # =========================================================================
    # FILL EMPTY SPACE PAGE
    # =========================================================================

    def _build_fill_page(self) -> QWidget:
        page, layout = self._build_page_container(
            "Fill Empty Space",
            "Select an empty-space target, run the genetic algorithm to generate a "
            "synthetic SDP instance that fills that region, then save it.",
        )

        # ── Target selector row ───────────────────────────────────────────────
        selector_row = QHBoxLayout()
        selector_row.setSpacing(8)

        lbl_target = QLabel("Target:")
        lbl_target.setStyleSheet("color: #f3f3f3; font-size: 13px; font-weight: 700;")

        self.target_combo = QComboBox()
        self.target_combo.setFixedHeight(38)
        self.target_combo.setMinimumWidth(260)
        self.target_combo.setStyleSheet(self._combo_style())

        self.refresh_targets_btn = QPushButton("Refresh")
        self.generate_btn        = QPushButton("Generate")
        self.stop_btn            = QPushButton("Stop")
        self.clear_btn           = QPushButton("Clear Log")

        for btn in [self.refresh_targets_btn, self.generate_btn, self.stop_btn, self.clear_btn]:
            btn.setFixedHeight(38)
            btn.setStyleSheet(self._button_style())

        self.stop_btn.setEnabled(False)

        self.refresh_targets_btn.clicked.connect(self._load_targets)
        self.target_combo.currentIndexChanged.connect(self._preview_selected_target)
        self.generate_btn.clicked.connect(self._run_generate)
        self.stop_btn.clicked.connect(self._stop_process)
        self.clear_btn.clicked.connect(lambda: self.terminal.clear())

        selector_row.addWidget(lbl_target)
        selector_row.addWidget(self.target_combo, 1)
        selector_row.addWidget(self.refresh_targets_btn)
        selector_row.addWidget(self.generate_btn)
        selector_row.addWidget(self.stop_btn)
        selector_row.addWidget(self.clear_btn)
        layout.addLayout(selector_row)

        # ── Status label ──────────────────────────────────────────────────────
        self.status_label = QLabel("Status: idle — load targets to begin")
        self.status_label.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #a8a8a8;"
        )
        self._preview_selected_target()
        layout.addWidget(self.status_label)

        # ── Terminal log ──────────────────────────────────────────────────────
        self.terminal = QPlainTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setFixedHeight(180)
        self.terminal.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3a3a3a;
                border-radius: 10px;
                padding: 8px;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.terminal)

        # ── Side-by-side plots ────────────────────────────────────────────────
        plots_row = QHBoxLayout()
        plots_row.setSpacing(12)

        self.plot_before = self._make_plot_panel("Before — current instance space")
        self.plot_after  = self._make_plot_panel("After — with generated instance")

        plots_row.addWidget(self.plot_before[0], 1)
        plots_row.addWidget(self.plot_after[0],  1)
        layout.addLayout(plots_row)

        # ── Save row ──────────────────────────────────────────────────────────
        save_row = QHBoxLayout()
        save_row.setSpacing(8)

        self.save_btn = QPushButton("Save Instance to Library")
        self.save_btn.setFixedHeight(40)
        self.save_btn.setEnabled(False)
        self.save_btn.setStyleSheet(self._save_button_style(enabled=False))
        self.save_btn.clicked.connect(self._save_instance)

        self.save_status = QLabel("")
        self.save_status.setStyleSheet("font-size: 12px; color: #a8a8a8;")

        save_row.addWidget(self.save_btn)
        save_row.addWidget(self.save_status, 1)
        layout.addLayout(save_row)

        layout.addStretch()

        # Load targets on construction
        self._load_targets()
        return page

    def _make_plot_panel(self, title: str) -> tuple[QFrame, QLabel]:
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border: 1px solid #3a3a3a;
                border-radius: 10px;
            }
            QLabel {
                background: transparent;
                border: none;
                border-radius: 0px;
            }
        """)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(10, 10, 10, 10)
        panel_layout.setSpacing(6)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            "color: #f3f3f3; font-size: 12px; font-weight: 700; background: transparent;"
        )

        img_lbl = QLabel("No plot yet")
        img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_lbl.setMinimumHeight(340)
        img_lbl.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e;
                color: #5a5a5a;
                border: 1px solid #2a2a2a;
                border-radius: 8px;
                font-size: 12px;
            }
        """)

        panel_layout.addWidget(title_lbl)
        panel_layout.addWidget(img_lbl, 1)
        return panel, img_lbl

    def _build_fill_multiple_page(self) -> QWidget:
        page, layout = self._build_page_container(
            "Fill Empty Space Multiple",
            "Generate several synthetic SDP instances, updating a temporary "
            "Instance Space after each candidate until the largest empty region "
            "is below the selected distance.",
        )

        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)

        lbl_threshold = QLabel("Max nearest distance:")
        lbl_threshold.setStyleSheet("color: #f3f3f3; font-size: 13px; font-weight: 700;")

        self.mult_threshold_spin = QDoubleSpinBox()
        self.mult_threshold_spin.setRange(0.0, 1000.0)
        self.mult_threshold_spin.setDecimals(3)
        self.mult_threshold_spin.setSingleStep(0.05)
        self.mult_threshold_spin.setValue(self._load_generation_tolerance())
        self.mult_threshold_spin.setFixedHeight(38)
        self.mult_threshold_spin.setStyleSheet(self._spin_style())

        lbl_max_iter = QLabel("Max instances:")
        lbl_max_iter.setStyleSheet("color: #f3f3f3; font-size: 13px; font-weight: 700;")

        self.mult_iter_spin = QSpinBox()
        self.mult_iter_spin.setRange(1, 100)
        self.mult_iter_spin.setValue(10)
        self.mult_iter_spin.setFixedHeight(38)
        self.mult_iter_spin.setStyleSheet(self._spin_style())

        lbl_grid = QLabel("Grid:")
        lbl_grid.setStyleSheet("color: #f3f3f3; font-size: 13px; font-weight: 700;")

        self.mult_grid_spin = QSpinBox()
        self.mult_grid_spin.setRange(10, 250)
        self.mult_grid_spin.setValue(80)
        self.mult_grid_spin.setFixedHeight(38)
        self.mult_grid_spin.setStyleSheet(self._spin_style())

        self.mult_run_btn = QPushButton("Run Multiple")
        self.mult_stop_btn = QPushButton("Stop")
        self.mult_clear_btn = QPushButton("Clear Log")
        for btn in [self.mult_run_btn, self.mult_stop_btn, self.mult_clear_btn]:
            btn.setFixedHeight(38)
            btn.setStyleSheet(self._button_style())
        self.mult_stop_btn.setEnabled(False)

        self.mult_run_btn.clicked.connect(self._run_generate_multiple)
        self.mult_stop_btn.clicked.connect(self._stop_process)
        self.mult_clear_btn.clicked.connect(lambda: self.mult_terminal.clear())

        controls_row.addWidget(lbl_threshold)
        controls_row.addWidget(self.mult_threshold_spin)
        controls_row.addWidget(lbl_max_iter)
        controls_row.addWidget(self.mult_iter_spin)
        controls_row.addWidget(lbl_grid)
        controls_row.addWidget(self.mult_grid_spin)
        controls_row.addStretch(1)
        controls_row.addWidget(self.mult_run_btn)
        controls_row.addWidget(self.mult_stop_btn)
        controls_row.addWidget(self.mult_clear_btn)
        layout.addLayout(controls_row)

        self.mult_status_label = QLabel("Status: idle - choose a threshold and run")
        self.mult_status_label.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #a8a8a8;"
        )
        layout.addWidget(self.mult_status_label)

        self.mult_terminal = QPlainTextEdit()
        self.mult_terminal.setReadOnly(True)
        self.mult_terminal.setFixedHeight(180)
        self.mult_terminal.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3a3a3a;
                border-radius: 10px;
                padding: 8px;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.mult_terminal)

        plots_row = QHBoxLayout()
        plots_row.setSpacing(12)
        self.mult_plot_initial = self._make_plot_panel("Initial map")
        self.mult_plot_final = self._make_plot_panel("Final map")
        plots_row.addWidget(self.mult_plot_initial[0], 1)
        plots_row.addWidget(self.mult_plot_final[0], 1)
        layout.addLayout(plots_row)

        save_row = QHBoxLayout()
        save_row.setSpacing(8)
        self.mult_save_btn = QPushButton("Save Generated Instances")
        self.mult_save_btn.setFixedHeight(40)
        self.mult_save_btn.setEnabled(False)
        self.mult_save_btn.setStyleSheet(self._save_button_style(enabled=False))
        self.mult_save_btn.clicked.connect(self._save_multiple_instances)

        self.mult_save_status = QLabel("")
        self.mult_save_status.setStyleSheet("font-size: 12px; color: #a8a8a8;")

        save_row.addWidget(self.mult_save_btn)
        save_row.addWidget(self.mult_save_status, 1)
        layout.addLayout(save_row)

        layout.addStretch()
        return page

    def _build_genetic_config_page(self) -> QWidget:
        page, layout = self._build_page_container(
            "Genetic Config",
            "Manage generated-instance records and files used by the genetic tools.",
        )

        threshold_row = QHBoxLayout()
        threshold_row.setSpacing(8)

        threshold_label = QLabel("Generation tolerance / stop threshold:")
        threshold_label.setStyleSheet(
            "color: #f3f3f3; font-size: 13px; font-weight: 700;"
        )

        self.config_stop_threshold_spin = QDoubleSpinBox()
        self.config_stop_threshold_spin.setRange(0.0, 1000.0)
        self.config_stop_threshold_spin.setDecimals(3)
        self.config_stop_threshold_spin.setSingleStep(0.05)
        self.config_stop_threshold_spin.setValue(self._load_generation_tolerance())
        self.config_stop_threshold_spin.setFixedHeight(38)
        self.config_stop_threshold_spin.setStyleSheet(self._spin_style())

        self.save_genetic_config_btn = QPushButton("Save Config")
        self.save_genetic_config_btn.setFixedHeight(38)
        self.save_genetic_config_btn.setStyleSheet(self._button_style())
        self.save_genetic_config_btn.clicked.connect(self._save_genetic_config)

        threshold_row.addWidget(threshold_label)
        threshold_row.addWidget(self.config_stop_threshold_spin)
        threshold_row.addWidget(self.save_genetic_config_btn)
        threshold_row.addStretch(1)
        layout.addLayout(threshold_row)

        warning = QLabel(
            "Remove all generated instances from instances_config.json and delete "
            "their files from the genetic generated folder."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet(
            "font-size: 13px; color: #d7ba7d; font-weight: 700;"
        )
        layout.addWidget(warning)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)

        self.delete_generated_btn = QPushButton("Delete Generated Instances")
        self.delete_generated_btn.setFixedHeight(40)
        self.delete_generated_btn.setStyleSheet("""
            QPushButton {
                background-color: #5a1d1d;
                color: #f3f3f3;
                border: 1px solid #8a2f2f;
                border-radius: 8px;
                padding: 0 18px;
                font-size: 13px;
                font-weight: 800;
            }
            QPushButton:hover { background-color: #6f2525; }
        """)
        self.delete_generated_btn.clicked.connect(self._delete_generated_instances)

        self.delete_generated_status = QLabel("")
        self.delete_generated_status.setStyleSheet(
            "font-size: 12px; color: #a8a8a8;"
        )

        actions_row.addWidget(self.delete_generated_btn)
        actions_row.addWidget(self.delete_generated_status, 1)
        layout.addLayout(actions_row)

        layout.addStretch()
        return page

    def _build_point_target_page(self) -> QWidget:
        page, layout = self._build_page_container(
            "Point Target",
            "Click any point in the Instance Space map, then generate one "
            "synthetic SDP instance aimed at that selected coordinate.",
        )

        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)

        self.point_coords_label = QLabel("Selected point: none")
        self.point_coords_label.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #a8a8a8;"
        )

        self.point_refresh_btn = QPushButton("Refresh Map")
        self.point_generate_btn = QPushButton("Generate")
        self.point_stop_btn = QPushButton("Stop")
        self.point_clear_btn = QPushButton("Clear Log")
        for btn in [
            self.point_refresh_btn,
            self.point_generate_btn,
            self.point_stop_btn,
            self.point_clear_btn,
        ]:
            btn.setFixedHeight(38)
            btn.setStyleSheet(self._button_style())
        self.point_generate_btn.setEnabled(False)
        self.point_stop_btn.setEnabled(False)

        self.point_refresh_btn.clicked.connect(self._load_point_target_map)
        self.point_generate_btn.clicked.connect(self._run_generate_point_target)
        self.point_stop_btn.clicked.connect(self._stop_process)
        self.point_clear_btn.clicked.connect(lambda: self.point_terminal.clear())

        controls_row.addWidget(self.point_coords_label, 1)
        controls_row.addWidget(self.point_refresh_btn)
        controls_row.addWidget(self.point_generate_btn)
        controls_row.addWidget(self.point_stop_btn)
        controls_row.addWidget(self.point_clear_btn)
        layout.addLayout(controls_row)

        self.point_canvas = ClickableInstanceSpaceCanvas(self)
        self.point_canvas.on_point_selected = self._point_selected
        self.point_canvas.setStyleSheet("background-color: #1e1e1e; border: none;")
        layout.addWidget(self.point_canvas, 1)

        self.point_terminal = QPlainTextEdit()
        self.point_terminal.setReadOnly(True)
        self.point_terminal.setFixedHeight(160)
        self.point_terminal.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3a3a3a;
                border-radius: 10px;
                padding: 8px;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.point_terminal)

        save_row = QHBoxLayout()
        self.point_save_btn = QPushButton("Save Generated Instance")
        self.point_save_btn.setFixedHeight(40)
        self.point_save_btn.setEnabled(False)
        self.point_save_btn.setStyleSheet(self._save_button_style(enabled=False))
        self.point_save_btn.clicked.connect(self._save_point_instance)

        self.point_save_status = QLabel("")
        self.point_save_status.setStyleSheet("font-size: 12px; color: #a8a8a8;")
        save_row.addWidget(self.point_save_btn)
        save_row.addWidget(self.point_save_status, 1)
        layout.addLayout(save_row)

        self._load_point_target_map()
        return page

    # =========================================================================
    # SECTION NAVIGATION
    # =========================================================================

    def _show_fill_page(self) -> None:
        self.content_stack.setCurrentIndex(0)
        self.fill_btn.set_active(True)
        self.fill_multiple_btn.set_active(False)
        self.point_target_btn.set_active(False)
        self.genetic_config_btn.set_active(False)

    def _show_fill_multiple_page(self) -> None:
        self.content_stack.setCurrentIndex(1)
        self.fill_btn.set_active(False)
        self.fill_multiple_btn.set_active(True)
        self.point_target_btn.set_active(False)
        self.genetic_config_btn.set_active(False)
        self._preview_multiple_initial_map()

    def _show_point_target_page(self) -> None:
        self.content_stack.setCurrentIndex(2)
        self.fill_btn.set_active(False)
        self.fill_multiple_btn.set_active(False)
        self.point_target_btn.set_active(True)
        self.genetic_config_btn.set_active(False)
        self._load_point_target_map()

    def _show_genetic_config_page(self) -> None:
        self.content_stack.setCurrentIndex(3)
        self.fill_btn.set_active(False)
        self.fill_multiple_btn.set_active(False)
        self.point_target_btn.set_active(False)
        self.genetic_config_btn.set_active(True)

    # =========================================================================
    # TARGET LOADING
    # =========================================================================

    def _load_targets(self) -> None:
        targets_path = self.explore_dir / "empty_space_targets.csv"
        self.target_combo.clear()

        if not targets_path.exists():
            self.status_label.setText(
                "Status: empty_space_targets.csv not found — run Explore first"
            )
            self.status_label.setStyleSheet(
                "font-size: 13px; font-weight: 700; color: #f48771;"
            )
            return

        try:
            import csv
            with open(targets_path, newline="", encoding="utf-8-sig") as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
        except Exception as exc:
            self.status_label.setText(f"Status: error reading targets — {exc}")
            return

        if not rows:
            self.status_label.setText("Status: empty_space_targets.csv has no rows")
            return

        for row in rows:
            tid  = row.get("target_id", "?")
            z1   = float(row.get("z_1", 0))
            z2   = float(row.get("z_2", 0))
            dist = row.get("nearest_instance_distance", "?")
            dist_str = f"{float(dist):.3f}" if dist != "?" else "?"
            label = f"{tid}   z=({z1:.3f}, {z2:.3f})   Δ={dist_str}"
            self.target_combo.addItem(label, tid)

        self.status_label.setText(
            f"Status: {len(rows)} empty-space targets loaded — select one and press Generate"
        )
        self.status_label.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #a8a8a8;"
        )

    # =========================================================================
    # GENERATION PROCESS
    # =========================================================================

    def _run_generate(self) -> None:
        if self.target_combo.count() == 0:
            QMessageBox.information(self, "No Targets", "Load empty-space targets first.")
            return

        if self.process is not None and self.process.state() != QProcess.NotRunning:
            QMessageBox.information(self, "Running", "Generation already in progress.")
            return

        target_id = self.target_combo.currentData()
        if not target_id:
            return

        self._last_target_id = target_id
        self._last_result = None
        self._preview_selected_target()
        self._set_after_plot_placeholder()
        self.save_btn.setEnabled(False)
        self.save_btn.setStyleSheet(self._save_button_style(enabled=False))
        self.save_status.setText("")

        python = self._find_python()
        if python is None:
            QMessageBox.critical(self, "Python Not Found", "Could not locate Python.")
            return

        self.terminal.appendPlainText("=" * 60)
        self.terminal.appendPlainText(f"Starting generation for: {target_id}")
        self.terminal.appendPlainText("=" * 60)

        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(self.project_root))

        env = QProcessEnvironment.systemEnvironment()
        existing = env.value("PYTHONPATH", "")
        root_str = str(self.project_root)
        env.insert("PYTHONPATH", root_str + os.pathsep + existing if existing else root_str)
        self.process.setProcessEnvironment(env)

        self.process.setProgram(python)
        self.process.setArguments(
            [
                str(self.fill_script_path),
                "--target-id",
                target_id,
                "--tolerance",
                f"{self._load_generation_tolerance()}",
            ]
        )

        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.finished.connect(self._generation_finished)

        self.generate_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._set_status("running", f"Running Evolution Strategy for {target_id} ...")
        self.process.start()

    def _stop_process(self) -> None:
        if self.process and self.process.state() != QProcess.NotRunning:
            self.terminal.appendPlainText("\n[INFO] Stop requested by user.")
            self.process.kill()
            self.process.waitForFinished(2000)

    def _read_stdout(self) -> None:
        if self.process is None:
            return
        data = self.process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        if data:
            self.terminal.insertPlainText(data)
            self.terminal.ensureCursorVisible()

    def _read_stderr(self) -> None:
        if self.process is None:
            return
        data = self.process.readAllStandardError().data().decode("utf-8", errors="replace")
        if data:
            self.terminal.insertPlainText(data)
            self.terminal.ensureCursorVisible()

    def _generation_finished(self, exit_code: int, _: QProcess.ExitStatus) -> None:
        self.generate_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        if exit_code != 0:
            self._set_status("error", f"Generation failed (exit code {exit_code})")
            self.terminal.appendPlainText(
                f"\n[ERROR] Process exited with code {exit_code}."
            )
            return

        # Load result JSON
        target_id = self._last_target_id or ""
        result_json = (
            self.genetic_output_dir / target_id / "result.json"
        )

        if not result_json.exists():
            self._set_status("error", "Generation finished but result.json not found.")
            return

        with open(result_json, encoding="utf-8") as fh:
            self._last_result = json.load(fh)

        self._show_plots(self._last_result)
        self._set_status(
            "ok",
            f"Generation complete — candidate ready to save  "
            f"(target: {target_id})",
        )

        self.save_btn.setEnabled(True)
        self.save_btn.setStyleSheet(self._save_button_style(enabled=True))
        self.terminal.appendPlainText("\n[INFO] Generation complete. Press 'Save Instance to Library' to register it.")

    def _run_generate_multiple(self) -> None:
        if self.process is not None and self.process.state() != QProcess.NotRunning:
            QMessageBox.information(self, "Running", "Generation already in progress.")
            return

        python = self._find_python()
        if python is None:
            QMessageBox.critical(self, "Python Not Found", "Could not locate Python.")
            return

        self._last_multiple_result = None
        self.mult_save_btn.setEnabled(False)
        self.mult_save_btn.setStyleSheet(self._save_button_style(enabled=False))
        self.mult_save_status.setText("")
        self._preview_multiple_initial_map()
        _, final_img_lbl = self.mult_plot_final
        final_img_lbl.setPixmap(QPixmap())
        final_img_lbl.setText("Generating ...")

        threshold = self.mult_threshold_spin.value()
        max_iterations = self.mult_iter_spin.value()
        grid_size = self.mult_grid_spin.value()

        self.mult_terminal.appendPlainText("=" * 60)
        self.mult_terminal.appendPlainText(
            f"Starting multiple generation: distance <= {threshold:.3f}"
        )
        self.mult_terminal.appendPlainText("=" * 60)

        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(self.project_root))

        env = QProcessEnvironment.systemEnvironment()
        existing = env.value("PYTHONPATH", "")
        root_str = str(self.project_root)
        env.insert("PYTHONPATH", root_str + os.pathsep + existing if existing else root_str)
        self.process.setProcessEnvironment(env)

        self.process.setProgram(python)
        self.process.setArguments(
            [
                "-u",
                str(self.fill_multiple_script_path),
                "--max-nearest-distance",
                f"{threshold}",
                "--max-iterations",
                str(max_iterations),
                "--grid-size",
                str(grid_size),
                "--tolerance",
                f"{self._load_generation_tolerance()}",
                "--mu",
                "5",
                "--lam",
                "15",
                "--generations",
                "40",
                "--stall-generations",
                "10",
            ]
        )

        self.process.readyReadStandardOutput.connect(self._read_multiple_stdout)
        self.process.readyReadStandardError.connect(self._read_multiple_stderr)
        self.process.finished.connect(self._multiple_generation_finished)

        self.mult_run_btn.setEnabled(False)
        self.mult_stop_btn.setEnabled(True)
        self._set_multiple_status("running", "Running multiple generation ...")
        self.process.start()

    def _read_multiple_stdout(self) -> None:
        if self.process is None:
            return
        data = self.process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        if data:
            self.mult_terminal.insertPlainText(data)
            self.mult_terminal.ensureCursorVisible()
            if "Current target plot" in data:
                self._refresh_multiple_current_target_plot()
            for line in data.splitlines():
                if line.startswith("[PROGRESS PLOT]"):
                    self._refresh_multiple_progress_plot(line[len("[PROGRESS PLOT]"):].strip())
                    break

    def _read_multiple_stderr(self) -> None:
        if self.process is None:
            return
        data = self.process.readAllStandardError().data().decode("utf-8", errors="replace")
        if data:
            self.mult_terminal.insertPlainText(data)
            self.mult_terminal.ensureCursorVisible()

    def _multiple_generation_finished(self, exit_code: int, _: QProcess.ExitStatus) -> None:
        self.mult_run_btn.setEnabled(True)
        self.mult_stop_btn.setEnabled(False)

        if exit_code != 0:
            self._set_multiple_status("error", f"Generation failed (exit code {exit_code})")
            self.mult_terminal.appendPlainText(
                f"\n[ERROR] Process exited with code {exit_code}."
            )
            return

        result_json = self._latest_multiple_result_json()
        if result_json is None:
            self._set_multiple_status("error", "Generation finished but result.json not found.")
            return

        with open(result_json, encoding="utf-8") as fh:
            self._last_multiple_result = json.load(fh)

        self._show_multiple_plots(self._last_multiple_result)
        count = len(self._last_multiple_result.get("generated_candidates", []))
        final_dist = self._last_multiple_result.get("final_nearest_instance_distance")
        self._set_multiple_status(
            "ok",
            f"Generation complete - {count} candidates, final distance {final_dist:.3f}",
        )

        self.mult_save_btn.setEnabled(count > 0)
        self.mult_save_btn.setStyleSheet(self._save_button_style(enabled=count > 0))
        self.mult_terminal.appendPlainText(
            "\n[INFO] Multiple generation complete. Press Save Generated Instances to register them."
        )

    def _load_point_target_map(self) -> None:
        if not hasattr(self, "point_canvas"):
            return

        try:
            from tools.genetic_algorithms.fill_empty_space import (
                _default_coordinates_csv,
                _load_coordinates_csv,
                _load_instance_space_outline,
            )

            coordinates_csv = _default_coordinates_csv(self.build_dir, self.explore_dir)
            coords = _load_coordinates_csv(coordinates_csv)
            outline = _load_instance_space_outline(
                build_dir=self.build_dir,
                explore_dir=self.explore_dir,
            )
            self.point_canvas.set_data(coords, outline)
            self._selected_point = None
            self.point_coords_label.setText("Selected point: none")
            self.point_generate_btn.setEnabled(False)
        except Exception as exc:
            self.point_coords_label.setText(f"Could not load map: {exc}")

    def _point_selected(self, point: tuple[float, float]) -> None:
        self._selected_point = point
        self.point_coords_label.setText(
            f"Selected point: z=({point[0]:.6f}, {point[1]:.6f})"
        )
        self.point_generate_btn.setEnabled(True)
        self.point_save_btn.setEnabled(False)
        self.point_save_btn.setStyleSheet(self._save_button_style(enabled=False))
        self._last_point_result = None

    def _run_generate_point_target(self) -> None:
        if self._selected_point is None:
            QMessageBox.information(self, "No Point", "Click a point in the map first.")
            return

        if self.process is not None and self.process.state() != QProcess.NotRunning:
            QMessageBox.information(self, "Running", "Generation already in progress.")
            return

        python = self._find_python()
        if python is None:
            QMessageBox.critical(self, "Python Not Found", "Could not locate Python.")
            return

        z1, z2 = self._selected_point
        target_id = f"point_target_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._last_point_result = None
        self.point_save_status.setText("")
        self.point_save_btn.setEnabled(False)
        self.point_save_btn.setStyleSheet(self._save_button_style(enabled=False))

        self.point_terminal.appendPlainText("=" * 60)
        self.point_terminal.appendPlainText(
            f"Starting point-target generation at z=({z1:.6f}, {z2:.6f})"
        )
        self.point_terminal.appendPlainText("=" * 60)

        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(self.project_root))

        env = QProcessEnvironment.systemEnvironment()
        existing = env.value("PYTHONPATH", "")
        root_str = str(self.project_root)
        env.insert("PYTHONPATH", root_str + os.pathsep + existing if existing else root_str)
        self.process.setProcessEnvironment(env)

        self.process.setProgram(python)
        self.process.setArguments(
            [
                str(self.fill_point_script_path),
                "--target-z1",
                f"{z1}",
                "--target-z2",
                f"{z2}",
                "--target-id",
                target_id,
                "--tolerance",
                f"{self._load_generation_tolerance()}",
            ]
        )

        self.process.readyReadStandardOutput.connect(self._read_point_stdout)
        self.process.readyReadStandardError.connect(self._read_point_stderr)
        self.process.finished.connect(
            lambda exit_code, status, result_id=target_id: self._point_generation_finished(
                exit_code,
                status,
                result_id,
            )
        )

        self.point_generate_btn.setEnabled(False)
        self.point_stop_btn.setEnabled(True)
        self.process.start()

    def _read_point_stdout(self) -> None:
        if self.process is None:
            return
        data = self.process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        if data:
            self.point_terminal.insertPlainText(data)
            self.point_terminal.ensureCursorVisible()

    def _read_point_stderr(self) -> None:
        if self.process is None:
            return
        data = self.process.readAllStandardError().data().decode("utf-8", errors="replace")
        if data:
            self.point_terminal.insertPlainText(data)
            self.point_terminal.ensureCursorVisible()

    def _point_generation_finished(
        self,
        exit_code: int,
        _: QProcess.ExitStatus,
        target_id: str,
    ) -> None:
        self.point_generate_btn.setEnabled(self._selected_point is not None)
        self.point_stop_btn.setEnabled(False)

        if exit_code != 0:
            self.point_terminal.appendPlainText(
                f"\n[ERROR] Process exited with code {exit_code}."
            )
            return

        result_json = self.genetic_point_output_dir / target_id / "result.json"
        if not result_json.exists():
            self.point_terminal.appendPlainText("\n[ERROR] result.json not found.")
            return

        with open(result_json, encoding="utf-8") as fh:
            self._last_point_result = json.load(fh)

        best_z1 = self._last_point_result.get("best_z1")
        best_z2 = self._last_point_result.get("best_z2")
        if best_z1 is not None and best_z2 is not None:
            self.point_canvas.selected_point = (float(best_z1), float(best_z2))
            self.point_canvas.draw_map()

        self.point_save_btn.setEnabled(True)
        self.point_save_btn.setStyleSheet(self._save_button_style(enabled=True))
        self.point_terminal.appendPlainText(
            "\n[INFO] Point-target generation complete. Press Save Generated Instance to register it."
        )

    # =========================================================================
    # PLOTS
    # =========================================================================

    def _set_plots_placeholder(self) -> None:
        for _, img_lbl in [self.plot_before, self.plot_after]:
            img_lbl.setPixmap(QPixmap())
            img_lbl.setText("Generating …")

    def _set_after_plot_placeholder(self) -> None:
        _, img_lbl = self.plot_after
        img_lbl.setPixmap(QPixmap())
        img_lbl.setText("Generating ...")

    def _preview_selected_target(self) -> None:
        if not hasattr(self, "target_combo") or self.target_combo.count() == 0:
            return

        target_id = self.target_combo.currentData()
        if not target_id:
            return

        target = self._target_coordinates(str(target_id))
        if target is None:
            return

        run_dir = self.genetic_output_dir / str(target_id)
        plot_before_path = run_dir / "plot_before.png"

        try:
            from tools.genetic_algorithms.fill_empty_space import (
                _dark_scatter_plot,
                _default_coordinates_csv,
                _load_coordinates_csv,
                _load_instance_space_outline,
            )

            coordinates_csv = _default_coordinates_csv(self.build_dir, self.explore_dir)
            coords = _load_coordinates_csv(coordinates_csv)
            outline = _load_instance_space_outline(
                build_dir=self.build_dir,
                explore_dir=self.explore_dir,
            )
            run_dir.mkdir(parents=True, exist_ok=True)
            _dark_scatter_plot(
                coords=coords,
                out_path=plot_before_path,
                title="Instance Space - before generation",
                target_z=target,
                generated_z=None,
                outline=outline,
                target_label=f"Target: {target_id}",
            )
        except Exception as exc:
            _, img_lbl = self.plot_before
            img_lbl.setPixmap(QPixmap())
            img_lbl.setText(f"Could not preview target:\n{exc}")
            return

        self._show_plot_image(plot_before_path, self.plot_before[1])
        _, after_lbl = self.plot_after
        after_lbl.setPixmap(QPixmap())
        after_lbl.setText("No generated instance yet")

    def _preview_multiple_initial_map(self) -> None:
        if not hasattr(self, "mult_plot_initial"):
            return

        plot_initial_path = self.genetic_multiple_output_dir / "_preview_initial_map.png"

        try:
            from tools.genetic_algorithms.fill_empty_space import (
                _dark_scatter_plot,
                _default_coordinates_csv,
                _load_coordinates_csv,
                _load_instance_space_outline,
            )

            coordinates_csv = _default_coordinates_csv(self.build_dir, self.explore_dir)
            coords = _load_coordinates_csv(coordinates_csv)
            outline = _load_instance_space_outline(
                build_dir=self.build_dir,
                explore_dir=self.explore_dir,
            )
            _dark_scatter_plot(
                coords=coords,
                out_path=plot_initial_path,
                title="Instance Space - initial",
                outline=outline,
            )
        except Exception as exc:
            _, img_lbl = self.mult_plot_initial
            img_lbl.setPixmap(QPixmap())
            img_lbl.setText(f"Could not load initial map:\n{exc}")
            return

        self._show_plot_image(plot_initial_path, self.mult_plot_initial[1])

        if self._last_multiple_result is None:
            _, final_lbl = self.mult_plot_final
            final_lbl.setPixmap(QPixmap())
            final_lbl.setText("No generated instances yet")

    def _target_coordinates(self, target_id: str) -> tuple[float, float] | None:
        targets_path = self.explore_dir / "empty_space_targets.csv"
        if not targets_path.exists():
            return None

        try:
            import csv
            with open(targets_path, newline="", encoding="utf-8-sig") as fh:
                for row in csv.DictReader(fh):
                    if row.get("target_id") == target_id:
                        return float(row["z_1"]), float(row["z_2"])
        except Exception:
            return None

        return None

    def _show_plot_image(self, path: Path, img_lbl: QLabel) -> None:
        if not path.exists():
            img_lbl.setText(f"File not found:\n{path.name}")
            return

        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            img_lbl.setText("Could not load image")
            return

        scaled = pixmap.scaled(
            img_lbl.width() or 600,
            img_lbl.height() or 360,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        img_lbl.setPixmap(scaled)
        img_lbl.setText("")

    def _show_plots(self, result: dict) -> None:
        for key, (_, img_lbl) in [
            ("plot_before", self.plot_before),
            ("plot_after",  self.plot_after),
        ]:
            path_str = result.get(key, "")
            if not path_str:
                img_lbl.setText("Plot not available")
                continue
            path = Path(path_str)
            self._show_plot_image(path, img_lbl)

    def _show_multiple_plots(self, result: dict) -> None:
        for key, (_, img_lbl) in [
            ("plot_initial", self.mult_plot_initial),
            ("plot_final", self.mult_plot_final),
        ]:
            path_str = result.get(key, "")
            if not path_str:
                img_lbl.setText("Plot not available")
                continue
            self._show_plot_image(Path(path_str), img_lbl)

    def _latest_multiple_result_json(self) -> Optional[Path]:
        if not self.genetic_multiple_output_dir.exists():
            return None

        candidates = sorted(
            self.genetic_multiple_output_dir.glob("multiple_*/result.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else None

    def _latest_multiple_run_dir(self) -> Optional[Path]:
        if not self.genetic_multiple_output_dir.exists():
            return None

        candidates = sorted(
            (p for p in self.genetic_multiple_output_dir.glob("multiple_*") if p.is_dir()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return candidates[0] if candidates else None

    def _refresh_multiple_current_target_plot(self) -> None:
        run_dir = self._latest_multiple_run_dir()
        if run_dir is None:
            return

        plot_path = run_dir / "plot_initial.png"
        if plot_path.exists():
            self._show_plot_image(plot_path, self.mult_plot_initial[1])

    def _refresh_multiple_progress_plot(self, path_str: str) -> None:
        from pathlib import Path
        path = Path(path_str)
        if path.exists():
            self._show_plot_image(path, self.mult_plot_final[1])

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Re-scale plots on window resize if we have a result
        if self._last_result:
            self._show_plots(self._last_result)
        if self._last_multiple_result:
            self._show_multiple_plots(self._last_multiple_result)

    # =========================================================================
    # SAVE INSTANCE
    # =========================================================================

    def _save_instance(self) -> None:
        if self._last_result is None:
            return

        candidate_path = Path(self._last_result.get("candidate_path", ""))
        if not candidate_path.exists():
            QMessageBox.critical(
                self,
                "File Not Found",
                f"Candidate file not found:\n{candidate_path}",
            )
            return

        target_id = self._last_result.get("target_id", "generated")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"{target_id}_{timestamp}.dat-s"

        name, ok = QInputDialog.getText(
            self,
            "Save Instance",
            "Enter file name for the new instance:",
            text=default_name,
        )
        if not ok or not name.strip():
            return

        name = name.strip()
        if not name.endswith(".dat-s"):
            name += ".dat-s"

        # Copy to destination
        self.point_instance_dest_dir.mkdir(parents=True, exist_ok=True)
        dest = self.point_instance_dest_dir / name

        if dest.exists():
            reply = QMessageBox.question(
                self,
                "File Exists",
                f"'{name}' already exists. Overwrite?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        shutil.copy2(candidate_path, dest)

        # Update instances_config.json
        try:
            self._register_instance(name)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Config Update Failed",
                f"Instance saved to:\n{dest}\n\nBut could not update instances_config.json:\n{exc}",
            )
            self.save_status.setText(f"Saved (config not updated): {dest.name}")
            return

        self.save_status.setText(f"Saved and registered: {dest.name}")
        self.save_status.setStyleSheet("font-size: 12px; color: #6a9955; font-weight: 700;")
        QMessageBox.information(
            self,
            "Instance Saved",
            f"Instance saved and registered:\n{dest}\n\n"
            f"Section in instances_config.json: 'genetic generated'",
        )

    def _save_multiple_instances(self) -> None:
        if self._last_multiple_result is None:
            return

        candidates = self._last_multiple_result.get("generated_candidates", [])
        if not candidates:
            QMessageBox.information(self, "No Candidates", "No generated instances to save.")
            return

        self.instance_dest_dir.mkdir(parents=True, exist_ok=True)
        saved_names: list[str] = []

        try:
            for candidate in candidates:
                src = Path(candidate.get("candidate_path", ""))
                if not src.exists():
                    raise FileNotFoundError(f"Candidate file not found: {src}")

                dest = self.instance_dest_dir / src.name
                counter = 2
                while dest.exists():
                    dest = self.instance_dest_dir / f"{src.stem}_v{counter}{src.suffix}"
                    counter += 1

                shutil.copy2(src, dest)
                self._register_instance(dest.name)
                saved_names.append(dest.name)
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))
            self.mult_save_status.setText(f"Save failed: {exc}")
            self.mult_save_status.setStyleSheet(
                "font-size: 12px; color: #f48771; font-weight: 700;"
            )
            return

        self.mult_save_status.setText(f"Saved and registered {len(saved_names)} instances")
        self.mult_save_status.setStyleSheet(
            "font-size: 12px; color: #6a9955; font-weight: 700;"
        )
        QMessageBox.information(
            self,
            "Instances Saved",
            "Saved and registered:\n" + "\n".join(saved_names),
        )

    def _save_point_instance(self) -> None:
        if self._last_point_result is None:
            return

        src = Path(self._last_point_result.get("candidate_path", ""))
        if not src.exists():
            QMessageBox.critical(self, "File Not Found", f"Candidate file not found:\n{src}")
            return

        target_id = self._last_point_result.get("target_id", "point_target")
        default_name = f"{target_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.dat-s"
        name, ok = QInputDialog.getText(
            self,
            "Save Instance",
            "Enter file name for the new instance:",
            text=default_name,
        )
        if not ok or not name.strip():
            return

        name = name.strip()
        if not name.endswith(".dat-s"):
            name += ".dat-s"

        self.instance_dest_dir.mkdir(parents=True, exist_ok=True)
        dest = self.instance_dest_dir / name
        if dest.exists():
            reply = QMessageBox.question(
                self,
                "File Exists",
                f"'{name}' already exists. Overwrite?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        try:
            shutil.copy2(src, dest)
            self._register_instance(dest.name, section_name="genetic point target")
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", str(exc))
            self.point_save_status.setText(f"Save failed: {exc}")
            self.point_save_status.setStyleSheet(
                "font-size: 12px; color: #f48771; font-weight: 700;"
            )
            return

        self.point_save_status.setText(f"Saved and registered: {dest.name}")
        self.point_save_status.setStyleSheet(
            "font-size: 12px; color: #6a9955; font-weight: 700;"
        )
        QMessageBox.information(self, "Instance Saved", f"Saved and registered:\n{dest}")

    def _register_instance(
        self,
        instance_name: str,
        section_name: str = "genetic generated",
    ) -> None:
        """Add instance to instances_config.json under the requested generated section."""
        config_path = self.instances_config_path
        if config_path.exists():
            with open(config_path, encoding="utf-8") as fh:
                config = json.load(fh)
        else:
            config = {"enabled_instances": [], "available_instances": {}}

        available = config.setdefault("available_instances", {})
        section: list = available.setdefault(section_name, [])
        if instance_name not in section:
            section.append(instance_name)

        if section_name == "genetic generated":
            legacy_section = available.pop("geneticamente_generadas", [])
            if isinstance(legacy_section, list):
                for legacy_name in legacy_section:
                    if legacy_name not in section:
                        section.append(legacy_name)

        if "enabled_instances" not in config:
            config["enabled_instances"] = []
        if instance_name not in config["enabled_instances"]:
            config["enabled_instances"].append(instance_name)

        with open(config_path, "w", encoding="utf-8") as fh:
            json.dump(config, fh, indent=2)

    def _delete_generated_instances(self) -> None:
        reply = QMessageBox.question(
            self,
            "Delete Generated Instances",
            "Delete all generated instance files and remove them from instances_config.json?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        generated_names: set[str] = set()
        config: dict = {"enabled_instances": [], "available_instances": {}}

        if self.instances_config_path.exists():
            with open(self.instances_config_path, encoding="utf-8") as fh:
                config = json.load(fh)

        available = config.setdefault("available_instances", {})
        for section_name in (
            "genetic generated",
            "genetic point target",
            "geneticamente_generadas",
        ):
            section = available.get(section_name, [])
            if isinstance(section, list):
                generated_names.update(str(name) for name in section)
                available[section_name] = []

        enabled = config.get("enabled_instances", [])
        if isinstance(enabled, list):
            config["enabled_instances"] = [
                name for name in enabled if str(name) not in generated_names
            ]

        deleted_files = 0
        for directory in (self.instance_dest_dir, self.point_instance_dest_dir):
            if directory.exists():
                for path in directory.rglob("*"):
                    if path.is_file() and (not generated_names or path.name in generated_names):
                        path.unlink()
                        deleted_files += 1

        with open(self.instances_config_path, "w", encoding="utf-8") as fh:
            json.dump(config, fh, indent=2)

        self.delete_generated_status.setText(
            f"Removed {len(generated_names)} registrations and deleted {deleted_files} files."
        )
        self.delete_generated_status.setStyleSheet(
            "font-size: 12px; color: #6a9955; font-weight: 700;"
        )
        QMessageBox.information(
            self,
            "Generated Instances Deleted",
            f"Removed {len(generated_names)} registrations and deleted {deleted_files} files.",
        )

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _set_status(self, level: str, text: str) -> None:
        color = {"ok": "#6a9955", "error": "#f48771", "running": "#d7ba7d"}.get(
            level, "#a8a8a8"
        )
        self.status_label.setText(f"Status: {text}")
        self.status_label.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {color};"
        )

    def _set_multiple_status(self, level: str, text: str) -> None:
        color = {"ok": "#6a9955", "error": "#f48771", "running": "#d7ba7d"}.get(
            level, "#a8a8a8"
        )
        self.mult_status_label.setText(f"Status: {text}")
        self.mult_status_label.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {color};"
        )

    def _load_generation_tolerance(self) -> float:
        if not self.genetic_config_path.exists():
            return 0.25

        try:
            with open(self.genetic_config_path, encoding="utf-8") as fh:
                config = json.load(fh)
            return float(
                config.get(
                    "generation_tolerance",
                    config.get("fill_multiple_stop_threshold", 0.25),
                )
            )
        except Exception:
            return 0.25

    def _save_genetic_config(self) -> None:
        value = self.config_stop_threshold_spin.value()
        config = {"generation_tolerance": value}

        self.genetic_config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.genetic_config_path, "w", encoding="utf-8") as fh:
            json.dump(config, fh, indent=2)

        if hasattr(self, "mult_threshold_spin"):
            self.mult_threshold_spin.setValue(value)

        self.delete_generated_status.setText(
            f"Config saved. Generation tolerance / stop threshold: {value:.3f}"
        )
        self.delete_generated_status.setStyleSheet(
            "font-size: 12px; color: #6a9955; font-weight: 700;"
        )

    def _find_project_root(self) -> Path:
        current = Path(__file__).resolve()
        for parent in [current.parent] + list(current.parents):
            if (parent / "config").exists():
                return parent
        return current.parent

    def _find_python(self) -> Optional[str]:
        if not getattr(sys, "frozen", False):
            return sys.executable
        import shutil as _shutil
        for candidate in ["python", "python3", "python.exe"]:
            path = _shutil.which(candidate)
            if path:
                return path
        return None

    def _to_relative_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.project_root))
        except Exception:
            return str(path)

    # ── Styles ────────────────────────────────────────────────────────────────

    def _button_style(self) -> str:
        return """
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
            QPushButton:disabled { color: #5a5a5a; }
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

    def _spin_style(self) -> str:
        return """
            QSpinBox, QDoubleSpinBox {
                background-color: #252526;
                color: #f3f3f3;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 0 10px;
                font-size: 13px;
            }
            QSpinBox:hover, QDoubleSpinBox:hover { background-color: #2d2d30; }
        """

    def _save_button_style(self, enabled: bool) -> str:
        if enabled:
            return """
                QPushButton {
                    background-color: #1a472a;
                    color: #f3f3f3;
                    border: 1px solid #2d6a3f;
                    border-radius: 8px;
                    padding: 0 18px;
                    font-size: 13px;
                    font-weight: 700;
                }
                QPushButton:hover { background-color: #226032; }
            """
        return """
            QPushButton {
                background-color: #1e1e1e;
                color: #4a4a4a;
                border: 1px solid #2a2a2a;
                border-radius: 8px;
                padding: 0 18px;
                font-size: 13px;
                font-weight: 700;
            }
        """


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GeneticPage()
    window.resize(1400, 850)
    window.show()
    sys.exit(app.exec())
