from __future__ import annotations

import csv
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QProcess, QProcessEnvironment, Qt, Signal
from PySide6.QtGui import QColor, QPixmap
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
    open_genetic = Signal()

    def __init__(self) -> None:
        super().__init__()

        self.project_root = self._find_project_root()
        self.prepare_script_path = self.project_root / "tools" / "isa" / "prepare_metadata_test.py"
        self.explore_script_path = self.project_root / "tools" / "isa" / "run_explore_is.py"
        self.add_instance_script_path = self.project_root / "tools" / "isa" / "add_instance_to_metadata_test.py"
        self.metadata_test_path = self.project_root / "matilda_out" / "explore_inputs" / "metadata_test.csv"
        self.base_metadata_path = self.project_root / "ISA metadata" / "metadata.csv"
        self.solver_registry_path = self.project_root / "config" / "solver_registry.json"
        self.solver_runtime_table_path = self.project_root / "ISA metadata" / "intermediates" / "solver_runtime_table.csv"
        self.explore_output_dir = self.project_root / "matilda_out" / "explore"

        self.process: Optional[QProcess] = None
        self.add_process: Optional[QProcess] = None
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
        genetic_button = SidebarButton("app/frontend/assets/icons/genetic_icon.png", "Genetic", 24, 48)
        settings_button = SidebarButton("app/frontend/assets/icons/settings_icon.png", "Configuration", 24, 48)

        explore_button.set_active(True)

        home_button.clicked.connect(self.open_home.emit)
        parameters_button.clicked.connect(self.open_parameters.emit)
        metadata_button.clicked.connect(self.open_metadata.emit)
        build_button.clicked.connect(self.open_build.emit)
        explore_button.clicked.connect(self.open_explore.emit)
        genetic_button.clicked.connect(self.open_genetic.emit)
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

        title = QLabel("Explore")
        title.setStyleSheet("color: #f3f3f3; font-size: 18px; font-weight: 800;")

        subtitle = QLabel("Control exploreIS")
        subtitle.setStyleSheet("color: #a8a8a8; font-size: 12px;")

        self.run_button = SectionButton("Run", active=True)
        self.metadata_button = SectionButton("Metadata Test")
        self.results_button = SectionButton("Results")
        self.recommendations_button = SectionButton("Recommendations")
        self.promote_button = SectionButton("Promote")

        self.run_button.clicked.connect(self.show_run_page)
        self.metadata_button.clicked.connect(self.show_metadata_page)
        self.results_button.clicked.connect(self.show_results_page)
        self.recommendations_button.clicked.connect(self.show_recommendations_page)
        self.promote_button.clicked.connect(self.show_promote_page)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(10)
        layout.addWidget(self.run_button)
        layout.addWidget(self.metadata_button)
        layout.addWidget(self.results_button)
        layout.addWidget(self.recommendations_button)
        layout.addWidget(self.promote_button)
        layout.addStretch()

        second_sidebar.setLayout(layout)
        return second_sidebar

    def _build_main_content(self) -> QWidget:
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("QStackedWidget { background-color: #2f2f2f; border: none; }")

        self.content_stack.addWidget(self._build_run_page())           # index 0
        self.content_stack.addWidget(self._build_metadata_page())      # index 1
        self.content_stack.addWidget(self._build_results_page())       # index 2
        self.content_stack.addWidget(self._build_recommendations_page())  # index 3
        self.content_stack.addWidget(self._build_promote_page())       # index 4

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

    # =========================================================================
    # RUN PAGE
    # =========================================================================

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

    # =========================================================================
    # METADATA TEST PAGE
    # =========================================================================

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

        # Small terminal for add-instance process output (hidden until used)
        self.add_instance_terminal = QPlainTextEdit()
        self.add_instance_terminal.setReadOnly(True)
        self.add_instance_terminal.setMaximumHeight(130)
        self.add_instance_terminal.setVisible(False)
        self.add_instance_terminal.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 8px;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.add_instance_terminal)

        self.metadata_table = QTableWidget()
        self.metadata_table.setMinimumHeight(560)
        self.metadata_table.setStyleSheet(self._table_style())
        layout.addWidget(self.metadata_table, 1)

        self.load_metadata_test_table()
        return page

    # =========================================================================
    # RESULTS PAGE
    # =========================================================================

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

        self.preview_stack = QStackedWidget()
        self.preview_stack.addWidget(self.image_preview)   # index 0
        self.preview_stack.addWidget(self.table_preview)   # index 1

        preview_layout.addWidget(self.preview_title)
        preview_layout.addWidget(self.preview_stack, 1)
        layout.addWidget(preview_panel, 1)

        self.refresh_results()
        return page

    # =========================================================================
    # RECOMMENDATIONS PAGE
    # =========================================================================

    def _make_rec_chart_panel(self, title: str) -> tuple[QFrame, QLabel]:
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border: 1px solid #3a3a3a;
                border-radius: 10px;
            }
            QLabel { background: transparent; border: none; border-radius: 0px; }
        """)
        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(10, 10, 10, 10)
        vbox.setSpacing(6)
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: #f3f3f3; font-size: 12px; font-weight: 700;")
        img_lbl = QLabel("No data yet")
        img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_lbl.setMinimumHeight(280)
        img_lbl.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
                color: #5a5a5a;
                border: 1px solid #2a2a2a;
                border-radius: 8px;
                font-size: 12px;
            }
        """)
        vbox.addWidget(lbl_title)
        vbox.addWidget(img_lbl, 1)
        return panel, img_lbl

    def _set_chart_image(self, label: QLabel, path: "Path | None") -> None:
        if path is None or not path.exists():
            label.setPixmap(QPixmap())
            label.setText("Not available")
            return
        px = QPixmap(str(path))
        if px.isNull():
            label.setText("Could not load image")
            return
        w = label.width() if label.width() > 50 else 700
        h = label.height() if label.height() > 50 else 500
        scaled = px.scaled(
            w, h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        label.setPixmap(scaled)
        label.setText("")

    def _render_recommendation_charts(
        self, run_dir: "Path"
    ) -> "tuple[Path | None, Path | None, Path | None]":
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
        import pandas as pd

        BG = "#1e1e1e"

        def _abbrev(s: str, n: int = 17) -> str:
            return s[:n] + "…" if len(s) > n else s

        def _dark_ax(ax, fig):
            fig.patch.set_facecolor(BG)
            ax.set_facecolor(BG)
            ax.tick_params(colors="#a8a8a8")
            ax.grid(True, alpha=0.08, color="#555555")
            for sp in ax.spines.values():
                sp.set_edgecolor("#3a3a3a")

        # ── paths ──────────────────────────────────────────────────────────
        diff_path  = run_dir / "_rec_difficulty.png"
        feat_path  = run_dir / "_rec_features.png"
        corr_path  = run_dir / "_rec_correlation.png"

        coords_csv   = run_dir / "coordinates.csv"
        good_csv     = run_dir / "good_algos.csv"
        targets_csv  = run_dir / "empty_space_targets.csv"
        feat_raw_csv = run_dir / "feature_raw.csv"
        model_mat    = run_dir / "model.mat"

        # ── 1. INSTANCE SPACE + DIFFICULTY DIRECTION ───────────────────────
        p1: "Path | None" = None
        if coords_csv.exists():
            try:
                coords = pd.read_csv(coords_csv)
                coords.columns = [c.strip() for c in coords.columns]
                z1c = next((c for c in coords.columns if c.lower() in ("z_1","z1")), None)
                z2c = next((c for c in coords.columns if c.lower() in ("z_2","z2")), None)
                if z1c and z2c:
                    z1 = coords[z1c].values.astype(float)
                    z2 = coords[z2c].values.astype(float)

                    # difficulty score per instance (0=hard, 1=easy)
                    diff = np.full(len(z1), 0.5)
                    if good_csv.exists():
                        g = pd.read_csv(good_csv)
                        g.columns = [c.strip() for c in g.columns]
                        num_cols = g.select_dtypes(include=[float, int]).columns
                        if len(num_cols) == 1:
                            vals = g[num_cols[0]].values.astype(float)
                        elif len(num_cols) > 1:
                            vals = g[num_cols].sum(axis=1).values.astype(float)
                        else:
                            vals = None
                        if vals is not None and len(vals) == len(z1):
                            vmax = vals.max() or 1.0
                            diff = vals / vmax

                    fig, ax = plt.subplots(figsize=(5.5, 4.8))
                    _dark_ax(ax, fig)
                    ax.set_aspect("equal", adjustable="box")

                    sc = ax.scatter(z1, z2, c=diff, cmap="RdYlGn",
                                    vmin=0, vmax=1, s=28, alpha=0.85, zorder=2)
                    cb = fig.colorbar(sc, ax=ax, fraction=0.038, pad=0.02)
                    cb.set_ticks([0.0, 1.0])
                    cb.set_ticklabels(["Hard", "Easy"])
                    cb.ax.yaxis.set_tick_params(color="#a8a8a8")
                    plt.setp(cb.ax.yaxis.get_ticklabels(), color="#a8a8a8", fontsize=8)

                    # difficulty direction arrow — spans across the IS space
                    med = np.median(diff)
                    easy_m, hard_m = diff >= med, diff < med
                    if easy_m.sum() > 1 and hard_m.sum() > 1:
                        ec = np.array([z1[easy_m].mean(), z2[easy_m].mean()])
                        hc = np.array([z1[hard_m].mean(), z2[hard_m].mean()])
                        direction = hc - ec
                        norm = np.linalg.norm(direction) + 1e-12
                        direction = direction / norm

                        # anchor the arrow at the plot centre and extend it
                        cx = (z1.min() + z1.max()) / 2
                        cy = (z2.min() + z2.max()) / 2
                        span = 0.30 * max(z1.max() - z1.min(),
                                          z2.max() - z2.min(), 1.0)
                        arrow_start = np.array([cx, cy]) - direction * span
                        arrow_end   = np.array([cx, cy]) + direction * span

                        ax.annotate(
                            "", xy=arrow_end, xytext=arrow_start,
                            arrowprops=dict(arrowstyle="-|>", color="#ff6b6b",
                                            lw=2.5, mutation_scale=20),
                            zorder=6,
                        )
                        ax.text(*arrow_start, "Easy",
                                color="#4fc1ff", fontsize=8, fontweight="bold",
                                ha="center", va="center", zorder=7,
                                bbox=dict(facecolor=BG, edgecolor="none",
                                          alpha=0.75, pad=2))
                        ax.text(*arrow_end, "Hard",
                                color="#ff6b6b", fontsize=8, fontweight="bold",
                                ha="center", va="center", zorder=7,
                                bbox=dict(facecolor=BG, edgecolor="none",
                                          alpha=0.75, pad=2))

                    ax.set_xlabel("z₁", color="#a8a8a8", fontsize=10)
                    ax.set_ylabel("z₂", color="#a8a8a8", fontsize=10)
                    ax.set_title("Instance Space — difficulty",
                                 color="#f3f3f3", fontsize=11, fontweight="bold")
                    fig.tight_layout()
                    fig.savefig(diff_path, dpi=110, bbox_inches="tight", facecolor=BG)
                    plt.close(fig)
                    p1 = diff_path
            except Exception as exc:
                print(f"[WARN] difficulty chart: {exc}")

        # ── 2. FEATURE → z CONTRIBUTION ────────────────────────────────────
        p2: "Path | None" = None
        if model_mat.exists():
            try:
                import scipy.io as sio
                mdl = sio.loadmat(str(model_mat), squeeze_me=True, struct_as_record=False)
                A = np.asarray(mdl["pilot"].A)          # (2, n_feats)
                labels_raw = [str(x) for x in np.atleast_1d(mdl["data"].featlabels)]
                labels = [_abbrev(l) for l in labels_raw]
                n_f = len(labels)

                w1, w2 = A[0], A[1]
                order = np.argsort(np.abs(w1) + np.abs(w2))   # ascending

                fig, ax = plt.subplots(figsize=(5.5, 4.8))
                _dark_ax(ax, fig)
                ax.grid(True, axis="x", alpha=0.12, color="#555555")
                ax.grid(False, axis="y")

                y = np.arange(n_f)
                bh = 0.36
                ax.barh(y + bh/2, w1[order], height=bh,
                        color="#4fc1ff", alpha=0.85, label="z₁")
                ax.barh(y - bh/2, w2[order], height=bh,
                        color="#f0c040", alpha=0.85, label="z₂")
                ax.set_yticks(y)
                ax.set_yticklabels([labels[i] for i in order],
                                   color="#d4d4d4", fontsize=8)
                ax.axvline(0, color="#555555", linewidth=0.8)
                ax.set_xlabel("Projection weight", color="#a8a8a8", fontsize=10)
                ax.set_title("Feature → z contribution",
                             color="#f3f3f3", fontsize=11, fontweight="bold")
                ax.legend(fontsize=9, facecolor="#2d2d30",
                          edgecolor="#3a3a3a", labelcolor="#f3f3f3")
                fig.tight_layout()
                fig.savefig(feat_path, dpi=110, bbox_inches="tight", facecolor=BG)
                plt.close(fig)
                p2 = feat_path
            except Exception as exc:
                print(f"[WARN] feature chart: {exc}")

        # ── 3. FEATURE CORRELATION HEATMAP ─────────────────────────────────
        p3: "Path | None" = None
        if feat_raw_csv.exists():
            try:
                import pandas as _pd
                fdf = _pd.read_csv(feat_raw_csv, index_col=0)
                fdf = fdf.select_dtypes(include=[float, int]).dropna(axis=1, how="all")
                corr = fdf.corr()
                n = len(corr)
                col_labels = [_abbrev(c) for c in corr.columns]

                # scale figure to number of features so labels never get cramped
                cell_size = max(0.52, 5.5 / max(n, 1))
                fig_side = max(5.5, cell_size * n + 1.5)
                fig, ax = plt.subplots(figsize=(fig_side, fig_side))
                _dark_ax(ax, fig)
                ax.grid(False)
                im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
                cb = fig.colorbar(im, ax=ax, fraction=0.038, pad=0.04)
                cb.set_label("Pearson r", color="#a8a8a8", fontsize=9)
                cb.ax.yaxis.set_tick_params(color="#a8a8a8")
                plt.setp(cb.ax.yaxis.get_ticklabels(), color="#a8a8a8", fontsize=8)
                ax.set_xticks(range(n))
                ax.set_yticks(range(n))
                lbl_fs = max(5.5, min(8, 60 / max(n, 1)))
                ax.set_xticklabels(col_labels, rotation=45, ha="right",
                                   color="#d4d4d4", fontsize=lbl_fs)
                ax.set_yticklabels(col_labels, color="#d4d4d4", fontsize=lbl_fs)
                if n <= 12:
                    val_fs = max(4.5, min(6.5, 55 / max(n, 1)))
                    for i in range(n):
                        for j in range(n):
                            v = corr.values[i, j]
                            txt_color = "white" if abs(v) > 0.65 else "#999999"
                            ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                                    fontsize=val_fs, color=txt_color)
                ax.set_title("Feature correlation matrix",
                             color="#f3f3f3", fontsize=11, fontweight="bold")
                ax.tick_params(length=0)
                fig.savefig(corr_path, dpi=110, bbox_inches="tight", facecolor=BG)
                plt.close(fig)
                p3 = corr_path
            except Exception as exc:
                print(f"[WARN] correlation chart: {exc}")

        return p1, p2, p3

    def _build_recommendations_page(self) -> QWidget:
        page, layout = self._build_page_container(
            "Recommendations",
            "Instance space analytics — difficulty map, feature contributions, and feature correlations.",
        )

        # ── action buttons ────────────────────────────────────────────────
        top_row = QHBoxLayout()
        self.refresh_recommendations_button = QPushButton("Refresh")
        self.regenerate_targets_button = QPushButton("Recompute Empty Spaces")
        for button in [self.refresh_recommendations_button, self.regenerate_targets_button]:
            self._style_button(button)
        self.refresh_recommendations_button.clicked.connect(self.refresh_recommendations)
        self.regenerate_targets_button.clicked.connect(self.recompute_empty_spaces)
        top_row.addWidget(self.refresh_recommendations_button)
        top_row.addWidget(self.regenerate_targets_button)
        top_row.addStretch()
        layout.addLayout(top_row)

        # ── three analytics charts ────────────────────────────────────────
        charts_row = QHBoxLayout()
        charts_row.setSpacing(12)

        diff_panel, self._rec_difficulty_lbl  = self._make_rec_chart_panel("Difficulty map")
        feat_panel, self._rec_features_lbl    = self._make_rec_chart_panel("Feature → z contribution")
        corr_panel, self._rec_correlation_lbl = self._make_rec_chart_panel("Feature correlations")
        for panel in (diff_panel, feat_panel, corr_panel):
            panel.setMinimumHeight(320)

        charts_row.addWidget(diff_panel, 1)
        charts_row.addWidget(feat_panel, 1)
        charts_row.addWidget(corr_panel, 1)
        layout.addLayout(charts_row, 3)

        # ── summary text ──────────────────────────────────────────────────
        self.recommendations_text = QPlainTextEdit()
        self.recommendations_text.setReadOnly(True)
        self.recommendations_text.setMaximumHeight(110)
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

        # ── empty-space targets table ─────────────────────────────────────
        self.empty_space_table = QTableWidget()
        self.empty_space_table.setMinimumHeight(200)
        self.empty_space_table.setStyleSheet(self._table_style())
        layout.addWidget(self.empty_space_table, 1)

        self.refresh_recommendations()
        return page

    # =========================================================================
    # PROMOTE PAGE
    # =========================================================================

    def _build_promote_page(self) -> QWidget:
        page, layout = self._build_page_container(
            "Promote to Metadata",
            "Overwrite ISA metadata/metadata.csv with the current contents of metadata_test.csv.",
        )

        promote_row = QHBoxLayout()
        self.promote_btn = QPushButton("Promote metadata_test to metadata.csv")
        self._style_button(self.promote_btn)
        self.promote_btn.clicked.connect(self._promote_metadata)
        promote_row.addWidget(self.promote_btn)
        promote_row.addStretch()
        layout.addLayout(promote_row)

        self.promote_status = QLabel("Status: ready")
        self.promote_status.setStyleSheet("font-size: 13px; font-weight: 700; color: #a8a8a8;")
        layout.addWidget(self.promote_status)

        paths_info = QLabel(
            f"Source : {self._to_relative_path(self.metadata_test_path)}\n"
            f"Target : {self._to_relative_path(self.base_metadata_path)}"
        )
        paths_info.setStyleSheet(
            "font-size: 12px; color: #8f8f8f; font-family: Consolas, 'Courier New', monospace;"
        )
        layout.addWidget(paths_info)
        layout.addStretch()
        return page

    def _promote_metadata(self) -> None:
        if not self.metadata_test_path.exists():
            QMessageBox.warning(self, "File Not Found", "metadata_test.csv does not exist. Prepare it first.")
            return

        reply = QMessageBox.question(
            self,
            "Promote to Metadata",
            (
                f"This will overwrite:\n  {self.base_metadata_path}\n\n"
                f"with:\n  {self.metadata_test_path}\n\nContinue?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self.base_metadata_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.metadata_test_path, self.base_metadata_path)
            ts = datetime.now().strftime("%H:%M:%S")
            self.promote_status.setText(f"Status: promoted successfully at {ts}")
            self.promote_status.setStyleSheet("font-size: 13px; font-weight: 700; color: #6a9955;")
        except Exception as exc:
            self.promote_status.setText(f"Status: error — {exc}")
            self.promote_status.setStyleSheet("font-size: 13px; font-weight: 700; color: #f48771;")

    # =========================================================================
    # SECTION NAVIGATION
    # =========================================================================

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

    def show_promote_page(self) -> None:
        self.content_stack.setCurrentIndex(4)
        self._set_active_section("promote")

    def _set_active_section(self, section: str) -> None:
        self.run_button.set_active(section == "run")
        self.metadata_button.set_active(section == "metadata")
        self.results_button.set_active(section == "results")
        self.recommendations_button.set_active(section == "recommendations")
        self.promote_button.set_active(section == "promote")

    # =========================================================================
    # MAIN PROCESS (explore / prepare)
    # =========================================================================

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
        if self.process is not None and self.process.state() != QProcess.ProcessState.NotRunning:
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
        if self.process is None or self.process.state() == QProcess.ProcessState.NotRunning:
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

    # =========================================================================
    # ADD-INSTANCE PROCESS
    # =========================================================================

    def _resolve_instance_path(self, source: str, instance_name: str) -> Optional[Path]:
        """Map a source group + instance name from instances_config to a real file path."""
        if source == "sdplib":
            p = self.project_root / "data" / "instances" / "sdplib" / instance_name
        elif source == "dimacs":
            p = self.project_root / "data" / "instances" / "DIMACS" / "instances" / instance_name
        elif source in ("genetic generated", "geneticamente_generadas"):
            p = self.project_root / "data" / "instances" / "genetic generated" / "fill empty space" / instance_name
        elif source == "genetic point target":
            p = self.project_root / "data" / "instances" / "genetic generated" / "point target" / instance_name
        else:
            candidates = list((self.project_root / "data" / "instances").rglob(Path(instance_name).name))
            p = candidates[0] if candidates else None
        return p if p is not None and p.exists() else None

    def _load_available_instances_for_add(self) -> dict[str, list[tuple[str, Path]]]:
        """Return {source: [(display_name, file_path)]} for instances not yet in metadata_test."""
        in_test: set[str] = set()
        if self.metadata_test_path.exists():
            try:
                with self.metadata_test_path.open("r", encoding="utf-8-sig", newline="") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        name = row.get("instances", "").strip()
                        if name:
                            in_test.add(name)
            except Exception:
                pass

        instances_config_path = self.project_root / "config" / "instances_config.json"
        try:
            config = json.loads(instances_config_path.read_text(encoding="utf-8"))
            available = config.get("available_instances", {})
        except Exception:
            return {}

        result: dict[str, list[tuple[str, Path]]] = {}
        for source, instances in available.items():
            group: list[tuple[str, Path]] = []
            for inst_name in instances:
                if inst_name in in_test:
                    continue
                file_path = self._resolve_instance_path(source, inst_name)
                if file_path is not None:
                    group.append((inst_name, file_path))
            if group:
                result[source] = group

        return result

    def _show_instance_picker_dialog(self) -> Optional[Path]:
        """Show grouped instance picker. Returns the selected file path or None."""
        available = self._load_available_instances_for_add()

        if not available:
            QMessageBox.information(
                self,
                "No Instances Available",
                "All available instances are already in metadata_test.csv, "
                "or no instance files were found on disk.",
            )
            return None

        dialog = QDialog(self)
        dialog.setWindowTitle("Add Instance to Metadata Test")
        dialog.setMinimumWidth(440)
        dialog.setMinimumHeight(520)
        dialog.setStyleSheet("""
            QDialog { background-color: #252526; color: #f3f3f3; }
            QLabel { color: #f3f3f3; font-size: 13px; }
            QListWidget {
                background-color: #1e1e1e;
                color: #f3f3f3;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 4px;
            }
            QListWidget::item { padding: 5px 8px; }
            QListWidget::item:selected { background-color: #2d2d30; border-radius: 4px; }
            QPushButton {
                background-color: #2d2d30;
                color: #f3f3f3;
                border: 1px solid #4a4a4a;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #3a3a3a; }
        """)

        dlg_layout = QVBoxLayout(dialog)
        dlg_layout.setContentsMargins(16, 16, 16, 16)
        dlg_layout.setSpacing(10)

        hint = QLabel(
            "Select an instance to add. Features and solver runtimes will be extracted "
            "for the columns already present in metadata_test."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #a8a8a8; font-size: 12px;")
        dlg_layout.addWidget(hint)

        list_widget = QListWidget()
        path_map: dict[str, Path] = {}

        for source, instances in available.items():
            header = QListWidgetItem(source.upper().replace("_", " "))
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            header.setForeground(QColor("#d7ba7d"))
            font = header.font()
            font.setBold(True)
            header.setFont(font)
            list_widget.addItem(header)

            for display_name, file_path in instances:
                item = QListWidgetItem("    " + display_name)
                item.setData(Qt.ItemDataRole.UserRole, display_name)
                list_widget.addItem(item)
                path_map[display_name] = file_path

        dlg_layout.addWidget(list_widget, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        dlg_layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None

        selected = list_widget.currentItem()
        if selected is None:
            return None
        display_name = selected.data(Qt.ItemDataRole.UserRole)
        if display_name is None:
            return None
        return path_map.get(display_name)

    def _run_add_instance_process(self, instance_path: Path) -> None:
        if self.add_process is not None and self.add_process.state() != QProcess.ProcessState.NotRunning:
            QMessageBox.information(self, "Process Running", "An add-instance process is already running.")
            return

        python = self._find_python()
        if python is None:
            QMessageBox.critical(self, "Python Not Found", "Could not locate a Python interpreter.")
            return

        args = [
            str(self.add_instance_script_path),
            "--instance-path", str(instance_path),
            "--metadata-test-path", str(self.metadata_test_path),
        ]

        self.add_instance_terminal.clear()
        self.add_instance_terminal.setVisible(True)
        self.add_instance_terminal.appendPlainText(f"[INFO] Extracting: {instance_path.name} ...")

        self.add_process = QProcess(self)
        self.add_process.setWorkingDirectory(str(self.project_root))

        env = QProcessEnvironment.systemEnvironment()
        existing = env.value("PYTHONPATH", "")
        root_str = str(self.project_root)
        env.insert("PYTHONPATH", root_str + os.pathsep + existing if existing else root_str)
        self.add_process.setProcessEnvironment(env)

        self.add_process.setProgram(python)
        self.add_process.setArguments(args)
        self.add_process.readyReadStandardOutput.connect(self._add_process_stdout)
        self.add_process.readyReadStandardError.connect(self._add_process_stderr)
        self.add_process.finished.connect(self._add_process_finished)

        self.add_column_button.setEnabled(False)
        self.metadata_table_status.setText("Status: extracting features and solver runtimes...")
        self.metadata_table_status.setStyleSheet("font-size: 13px; font-weight: 700; color: #d7ba7d;")
        self.add_process.start()

    def _add_process_stdout(self) -> None:
        if self.add_process is None:
            return
        data = self.add_process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        if data:
            self.add_instance_terminal.insertPlainText(data)
            self.add_instance_terminal.ensureCursorVisible()

    def _add_process_stderr(self) -> None:
        if self.add_process is None:
            return
        data = self.add_process.readAllStandardError().data().decode("utf-8", errors="replace")
        if data:
            self.add_instance_terminal.insertPlainText(data)
            self.add_instance_terminal.ensureCursorVisible()

    def _add_process_finished(self, exit_code: int, _: QProcess.ExitStatus) -> None:
        self.add_column_button.setEnabled(True)
        if exit_code == 0:
            self.metadata_table_status.setText("Status: instance added successfully")
            self.metadata_table_status.setStyleSheet("font-size: 13px; font-weight: 700; color: #6a9955;")
            self.load_metadata_test_table()
        else:
            self.metadata_table_status.setText(f"Status: failed (exit code {exit_code})")
            self.metadata_table_status.setStyleSheet("font-size: 13px; font-weight: 700; color: #f48771;")

    # =========================================================================
    # METADATA TABLE EDITING
    # =========================================================================

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
            QDialog { background-color: #252526; color: #f3f3f3; }
            QLabel { color: #f3f3f3; font-size: 13px; }
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
            # Open the grouped instance picker and launch extraction process
            file_path = self._show_instance_picker_dialog()
            if file_path is not None:
                self._run_add_instance_process(file_path)

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

    # =========================================================================
    # RESULTS
    # =========================================================================

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

        suffix = file_path.suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg"}:
            self.table_preview.clear()
            self.table_preview.setRowCount(0)
            self.table_preview.setColumnCount(0)
            self.image_preview.setPixmap(QPixmap())
            self.image_preview.setText("Loading...")
            self.preview_stack.setCurrentIndex(0)
            self._preview_image(file_path)
        elif suffix == ".csv":
            self.image_preview.setPixmap(QPixmap())
            self.preview_stack.setCurrentIndex(1)
            self._preview_csv(file_path)
        else:
            self._clear_preview("Preview not supported")

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
                self.preview_title.setText(f"Preview: {file_path.name} — empty")
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
        except Exception as exc:
            self.preview_title.setText(f"Preview: error — {exc}")
            self._clear_preview(f"Error reading CSV: {exc}")

    # =========================================================================
    # RECOMMENDATIONS
    # =========================================================================

    def refresh_recommendations(self) -> None:
        if not hasattr(self, "recommendations_text"):
            return

        run_dir = self._selected_or_latest_run()

        # ── clear charts if no data ────────────────────────────────────────
        no_data_labels = getattr(self, "_rec_difficulty_lbl", None)
        if run_dir is None:
            self.recommendations_text.setPlainText("No explore output is available yet.")
            self.empty_space_table.clear()
            self.empty_space_table.setRowCount(0)
            self.empty_space_table.setColumnCount(0)
            for lbl_attr in ("_rec_difficulty_lbl", "_rec_features_lbl", "_rec_correlation_lbl"):
                lbl = getattr(self, lbl_attr, None)
                if lbl is not None:
                    lbl.setPixmap(QPixmap())
                    lbl.setText("No data yet")
            return

        # ── render analytics charts ────────────────────────────────────────
        try:
            p1, p2, p3 = self._render_recommendation_charts(run_dir)
        except Exception as exc:
            p1 = p2 = p3 = None
            print(f"[WARN] chart rendering failed: {exc}")

        self._set_chart_image(self._rec_difficulty_lbl,  p1)
        self._set_chart_image(self._rec_features_lbl,    p2)
        self._set_chart_image(self._rec_correlation_lbl, p3)

        # ── summary text ───────────────────────────────────────────────────
        lines = [f"Explore output: {self._to_relative_path(run_dir)}"]
        coordinates_path = run_dir / "coordinates.csv"
        empty_targets_path = run_dir / "empty_space_targets.csv"
        footprint_path = run_dir / "footprint_performance.csv"

        if coordinates_path.exists():
            rows = self._read_csv_rows(coordinates_path)
            lines.append(f"Projected instances: {max(0, len(rows) - 1)}")

        if empty_targets_path.exists():
            rows = self._read_csv_rows(empty_targets_path)
            lines.append(f"Empty-space targets: {max(0, len(rows) - 1)}")
            self._load_csv_into_table(empty_targets_path, self.empty_space_table)
        else:
            lines.append("Empty-space targets not available — use Recompute Empty Spaces.")
            self.empty_space_table.clear()
            self.empty_space_table.setRowCount(0)
            self.empty_space_table.setColumnCount(0)

        if footprint_path.exists():
            lines.append("Footprint summary available.")

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
        self.preview_stack.setCurrentIndex(0)

    def show_output_path_message(self) -> None:
        QMessageBox.information(self, "Explore Output Path", str(self.explore_output_dir))

    # =========================================================================
    # SHARED HELPERS
    # =========================================================================

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

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        run_dir = self._selected_or_latest_run()
        if run_dir is None:
            return
        for attr, path_name in (
            ("_rec_difficulty_lbl",  "_rec_difficulty.png"),
            ("_rec_features_lbl",    "_rec_features.png"),
            ("_rec_correlation_lbl", "_rec_correlation.png"),
        ):
            lbl = getattr(self, attr, None)
            if lbl is not None:
                self._set_chart_image(lbl, run_dir / path_name)

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
        import shutil as _shutil
        for candidate in ["python", "python3", "python.exe"]:
            path = _shutil.which(candidate)
            if path:
                return path
        return None


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ExplorePage()
    window.resize(1400, 850)
    window.show()
    sys.exit(app.exec())
