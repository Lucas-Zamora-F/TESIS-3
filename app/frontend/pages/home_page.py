from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from app.frontend.components.sidebar_button import SidebarButton


class HomePage(QWidget):
    open_configuration = Signal()
    open_parameters = Signal()

    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("homePage")
        self.setStyleSheet("""
            QWidget#homePage {
                background-color: #111111;
            }
        """)

        # ============================================================
        # ROOT LAYOUT
        # ============================================================
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ============================================================
        # BODY
        # ============================================================
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

        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(0, 8, 0, 8)
        sidebar_layout.setSpacing(8)

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
        # SETTINGS BUTTON
        # ============================================================
        settings_button = SidebarButton(
            icon_relative_path="app/frontend/assets/icons/settings_icon.png",
            tooltip_text="Configuration",
            icon_size=24,
            button_size=48,
        )
        settings_button.clicked.connect(self.open_configuration.emit)

        # ============================================================
        # SIDEBAR LAYOUT
        # ============================================================
        sidebar_layout.addWidget(home_button, 0, Qt.AlignmentFlag.AlignHCenter)
        sidebar_layout.addWidget(parameters_button, 0, Qt.AlignmentFlag.AlignHCenter)

        sidebar_layout.addStretch()

        sidebar_layout.addWidget(settings_button, 0, Qt.AlignmentFlag.AlignHCenter)

        left_sidebar.setLayout(sidebar_layout)

        # ============================================================
        # CENTRAL AREA
        # ============================================================
        center_area = QFrame()
        center_area.setStyleSheet("""
            QFrame {
                background-color: #2f2f2f;
                border: none;
            }
        """)

        body_layout.addWidget(left_sidebar)
        body_layout.addWidget(center_area, 1)

        body.setLayout(body_layout)

        root_layout.addWidget(body, 1)
        self.setLayout(root_layout)