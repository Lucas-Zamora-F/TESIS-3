from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.frontend.components.features_editor import FeaturesEditor
from app.frontend.components.instance_space_editor import InstanceSpaceEditor
from app.frontend.components.instances_editor import InstancesEditor
from app.frontend.components.sidebar_button import SidebarButton
from app.frontend.components.solvers_editor import SolversEditor


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


class ParametersPage(QWidget):
    open_home = Signal()
    open_configuration = Signal()
    open_parameters = Signal()
    open_metadata = Signal()

    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("parametersPage")
        self.setStyleSheet("""
            QWidget#parametersPage {
                background-color: #111111;
            }
            QLabel {
                background: transparent;
            }
            QFrame {
                border: none;
            }
        """)

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
        parameters_button.set_active(True)
        parameters_button.clicked.connect(self.open_parameters.emit)

        metadata_button = SidebarButton(
            icon_relative_path="app/frontend/assets/icons/metadata_icon.png",
            tooltip_text="Metadata",
            icon_size=24,
            button_size=48,
        )
        metadata_button.clicked.connect(self.open_metadata.emit)

        settings_button = SidebarButton(
            icon_relative_path="app/frontend/assets/icons/settings_icon.png",
            tooltip_text="Configuration",
            icon_size=24,
            button_size=48,
        )
        settings_button.clicked.connect(self.open_configuration.emit)

        left_sidebar_layout.addWidget(home_button, 0, Qt.AlignmentFlag.AlignHCenter)
        left_sidebar_layout.addWidget(parameters_button, 0, Qt.AlignmentFlag.AlignHCenter)
        left_sidebar_layout.addWidget(metadata_button, 0, Qt.AlignmentFlag.AlignHCenter)
        left_sidebar_layout.addStretch()
        left_sidebar_layout.addWidget(settings_button, 0, Qt.AlignmentFlag.AlignHCenter)

        left_sidebar.setLayout(left_sidebar_layout)

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

        section_title = QLabel("Parameters")
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

        self.features_button = SectionButton("Features", active=True)
        self.instance_spaces_button = SectionButton("Instance Spaces")
        self.instances_button = SectionButton("Instances")
        self.solvers_button = SectionButton("Solvers")

        second_sidebar_layout.addWidget(section_title)
        second_sidebar_layout.addWidget(section_subtitle)
        second_sidebar_layout.addSpacing(10)
        second_sidebar_layout.addWidget(self.features_button)
        second_sidebar_layout.addWidget(self.instance_spaces_button)
        second_sidebar_layout.addWidget(self.instances_button)
        second_sidebar_layout.addWidget(self.solvers_button)
        second_sidebar_layout.addStretch()

        second_sidebar.setLayout(second_sidebar_layout)

        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("""
            QStackedWidget {
                background-color: #2f2f2f;
                border: none;
            }
        """)

        features_page = FeaturesEditor()
        instance_spaces_page = InstanceSpaceEditor()
        instances_page = InstancesEditor()

        solvers_page = SolversEditor()

        self.content_stack.addWidget(features_page)
        self.content_stack.addWidget(instance_spaces_page)
        self.content_stack.addWidget(instances_page)
        self.content_stack.addWidget(solvers_page)

        self.features_button.clicked.connect(self.show_features)
        self.instance_spaces_button.clicked.connect(self.show_instance_spaces)
        self.instances_button.clicked.connect(self.show_instances)
        self.solvers_button.clicked.connect(self.show_solvers)

        body_layout.addWidget(left_sidebar)
        body_layout.addWidget(second_sidebar)
        body_layout.addWidget(self.content_stack, 1)

        body.setLayout(body_layout)
        root_layout.addWidget(body, 1)

        self.setLayout(root_layout)

    def build_section_page(self, title_text: str, subtitle_text: str) -> QWidget:
        page = QWidget()

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

        placeholder = QFrame()
        placeholder.setMinimumHeight(500)
        placeholder.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border: 1px solid #3a3a3a;
                border-radius: 12px;
            }
        """)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(placeholder, 1)

        page.setLayout(layout)
        return page

    def set_active_section(self, section_name: str) -> None:
        self.features_button.set_active(section_name == "features")
        self.instance_spaces_button.set_active(section_name == "instance_spaces")
        self.instances_button.set_active(section_name == "instances")
        self.solvers_button.set_active(section_name == "solvers")

    def show_features(self) -> None:
        self.content_stack.setCurrentIndex(0)
        self.set_active_section("features")

    def show_instance_spaces(self) -> None:
        self.content_stack.setCurrentIndex(1)
        self.set_active_section("instance_spaces")

    def show_instances(self) -> None:
        self.content_stack.setCurrentIndex(2)
        self.set_active_section("instances")

    def show_solvers(self) -> None:
        self.content_stack.setCurrentIndex(3)
        self.set_active_section("solvers")