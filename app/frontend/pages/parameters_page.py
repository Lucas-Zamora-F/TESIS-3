from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.frontend.components.sidebar_button import SidebarButton


class ParametersPage(QWidget):
    open_home = Signal()
    open_configuration = Signal()
    open_parameters = Signal()

    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("parametersPage")
        self.setStyleSheet("""
            QWidget#parametersPage {
                background-color: #111111;
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

        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(0, 8, 0, 8)
        sidebar_layout.setSpacing(8)

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

        settings_button = SidebarButton(
            icon_relative_path="app/frontend/assets/icons/settings_icon.png",
            tooltip_text="Configuration",
            icon_size=24,
            button_size=48,
        )
        settings_button.clicked.connect(self.open_configuration.emit)

        sidebar_layout.addWidget(home_button, 0, Qt.AlignmentFlag.AlignHCenter)
        sidebar_layout.addWidget(parameters_button, 0, Qt.AlignmentFlag.AlignHCenter)
        sidebar_layout.addStretch()
        sidebar_layout.addWidget(settings_button, 0, Qt.AlignmentFlag.AlignHCenter)

        left_sidebar.setLayout(sidebar_layout)

        center_area = QFrame()
        center_area.setStyleSheet("""
            QFrame {
                background-color: #2f2f2f;
                border: none;
            }
            QLabel {
                color: #d4d4d4;
                background: transparent;
            }
        """)

        center_layout = QVBoxLayout()
        center_layout.setContentsMargins(28, 24, 28, 24)
        center_layout.setSpacing(18)

        title = QLabel("Parameter Configuration")
        title.setStyleSheet("""
            font-size: 28px;
            font-weight: 800;
            color: #f3f3f3;
        """)

        subtitle = QLabel("Configure model and workflow parameters.")
        subtitle.setStyleSheet("""
            font-size: 14px;
            color: #bdbdbd;
        """)

        panel_1 = QFrame()
        panel_1.setMinimumHeight(120)
        panel_1.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border: 1px solid #3a3a3a;
                border-radius: 12px;
            }
        """)

        panel_2 = QFrame()
        panel_2.setMinimumHeight(180)
        panel_2.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border: 1px solid #3a3a3a;
                border-radius: 12px;
            }
        """)

        panel_3 = QFrame()
        panel_3.setMinimumHeight(180)
        panel_3.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border: 1px solid #3a3a3a;
                border-radius: 12px;
            }
        """)

        center_layout.addWidget(title)
        center_layout.addWidget(subtitle)
        center_layout.addSpacing(8)
        center_layout.addWidget(panel_1)
        center_layout.addWidget(panel_2)
        center_layout.addWidget(panel_3)
        center_layout.addStretch()

        center_area.setLayout(center_layout)

        body_layout.addWidget(left_sidebar)
        body_layout.addWidget(center_area, 1)

        body.setLayout(body_layout)
        root_layout.addWidget(body, 1)

        self.setLayout(root_layout)