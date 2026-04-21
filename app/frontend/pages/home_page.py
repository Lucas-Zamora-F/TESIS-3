from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
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


class HomePage(QWidget):
    open_home = Signal()
    open_configuration = Signal()
    open_parameters = Signal()
    open_metadata = Signal()
    open_build = Signal()
    open_explore = Signal()

    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("homePage")
        self.setStyleSheet("""
            QWidget#homePage {
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

        left_sidebar = self._build_left_sidebar()
        second_sidebar = self._build_second_sidebar()
        main_content = self._build_main_content()

        body_layout.addWidget(left_sidebar)
        body_layout.addWidget(second_sidebar)
        body_layout.addWidget(main_content, 1)

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

        left_sidebar_layout = QVBoxLayout()
        left_sidebar_layout.setContentsMargins(0, 8, 0, 8)
        left_sidebar_layout.setSpacing(8)

        # ============================================================
        # HOME BUTTON
        # ============================================================
        home_button = SidebarButton(
            icon_relative_path="app/frontend/assets/icons/home_icon.png",
            tooltip_text="Home",
            icon_size=24,
            button_size=48,
        )
        home_button.set_active(True)
        home_button.clicked.connect(self.open_home.emit)

        # ============================================================
        # PARAMETERS BUTTON
        # ============================================================
        parameters_button = SidebarButton(
            icon_relative_path="app/frontend/assets/icons/parameters_icon.png",
            tooltip_text="Parameters",
            icon_size=24,
            button_size=48,
        )
        parameters_button.clicked.connect(self.open_parameters.emit)

        # ============================================================
        # METADATA BUTTON
        # ============================================================
        metadata_button = SidebarButton(
            icon_relative_path="app/frontend/assets/icons/metadata_icon.png",
            tooltip_text="Metadata",
            icon_size=24,
            button_size=48,
        )
        metadata_button.clicked.connect(self.open_metadata.emit)

        # ============================================================
        # CONFIGURATION BUTTON
        # ============================================================
        settings_button = SidebarButton(
            icon_relative_path="app/frontend/assets/icons/settings_icon.png",
            tooltip_text="Configuration",
            icon_size=24,
            button_size=48,
        )
        settings_button.clicked.connect(self.open_configuration.emit)

        # ============================================================
        # BUILD BUTTON
        # ============================================================
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

        left_sidebar_layout.addWidget(home_button, 0, Qt.AlignmentFlag.AlignHCenter)
        left_sidebar_layout.addWidget(parameters_button, 0, Qt.AlignmentFlag.AlignHCenter)
        left_sidebar_layout.addWidget(metadata_button, 0, Qt.AlignmentFlag.AlignHCenter)
        left_sidebar_layout.addWidget(build_button, 0, Qt.AlignmentFlag.AlignHCenter)
        left_sidebar_layout.addWidget(explore_button, 0, Qt.AlignmentFlag.AlignHCenter)
        left_sidebar_layout.addStretch()
        left_sidebar_layout.addWidget(settings_button, 0, Qt.AlignmentFlag.AlignHCenter)

        left_sidebar.setLayout(left_sidebar_layout)
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

        second_sidebar_layout = QVBoxLayout()
        second_sidebar_layout.setContentsMargins(16, 20, 16, 16)
        second_sidebar_layout.setSpacing(10)

        section_title = QLabel("Home")
        section_title.setStyleSheet("""
            color: #f3f3f3;
            font-size: 18px;
            font-weight: 800;
        """)

        section_subtitle = QLabel("Select a home section")
        section_subtitle.setStyleSheet("""
            color: #a8a8a8;
            font-size: 12px;
        """)

        self.overview_button = SectionButton("Overview", active=True)
        self.about_button = SectionButton("About")

        self.overview_button.clicked.connect(self.show_overview)
        self.about_button.clicked.connect(self.show_about)

        second_sidebar_layout.addWidget(section_title)
        second_sidebar_layout.addWidget(section_subtitle)
        second_sidebar_layout.addSpacing(10)
        second_sidebar_layout.addWidget(self.overview_button)
        second_sidebar_layout.addWidget(self.about_button)
        second_sidebar_layout.addStretch()

        second_sidebar.setLayout(second_sidebar_layout)
        return second_sidebar

    def _build_main_content(self) -> QWidget:
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("""
            QStackedWidget {
                background-color: #2f2f2f;
                border: none;
            }
        """)

        self.content_stack.addWidget(self._build_overview_page())
        self.content_stack.addWidget(self._build_about_page())

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

    def _build_overview_page(self) -> QWidget:
        page, layout = self._build_page_container(
            "Welcome to SDISG",
            "A central interface for managing solver configuration, metadata workflows, and thesis-related experimentation.",
        )

        intro_title = QLabel("Welcome to SDISG")
        intro_title.setStyleSheet("""
            font-size: 22px;
            font-weight: 800;
            color: #f3f3f3;
            background: transparent;
            margin-top: 8px;
        """)

        intro_text = QLabel(
            "SDISG provides a unified front-end for organizing your thesis workflow.\n\n"
            "From this application, you can navigate through parameter editing, metadata "
            "management, and configuration tools in a single interface.\n\n"
            "The goal is to make experimentation, benchmarking, and ISA-related tasks "
            "cleaner, faster, and easier to manage."
        )
        intro_text.setWordWrap(True)
        intro_text.setStyleSheet("""
            font-size: 13px;
            color: #d0d0d0;
            background: transparent;
            line-height: 1.5;
        """)

        layout.addSpacing(8)
        layout.addWidget(intro_title)
        layout.addWidget(intro_text)
        layout.addStretch()

        return page

    def _build_about_page(self) -> QWidget:
        page, layout = self._build_page_container(
            "About SDISG",
            "A short introduction to the purpose of the platform.",
        )

        about_title = QLabel("Purpose")
        about_title.setStyleSheet("""
            font-size: 20px;
            font-weight: 700;
            color: #f3f3f3;
            background: transparent;
            margin-top: 8px;
        """)

        about_text = QLabel(
            "This interface is intended to support the configuration and execution of "
            "your SDP and ISA pipeline components. It serves as a front-end layer for "
            "editing settings, navigating project areas, and later connecting core "
            "workflow actions."
        )
        about_text.setWordWrap(True)
        about_text.setStyleSheet("""
            font-size: 13px;
            color: #d0d0d0;
            background: transparent;
        """)

        layout.addSpacing(8)
        layout.addWidget(about_title)
        layout.addWidget(about_text)
        layout.addStretch()

        return page

    # ============================================================
    # SECTION NAVIGATION
    # ============================================================

    def set_active_section(self, section_name: str) -> None:
        self.overview_button.set_active(section_name == "overview")
        self.about_button.set_active(section_name == "about")

    def show_overview(self) -> None:
        self.content_stack.setCurrentIndex(0)
        self.set_active_section("overview")

    def show_about(self) -> None:
        self.content_stack.setCurrentIndex(1)
        self.set_active_section("about")
