import os
import sys

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout


def get_resource_path(relative_path: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..")
        )
        base_path = project_root

    return os.path.join(base_path, relative_path)


class SidebarButton(QPushButton):
    def __init__(
        self,
        icon_relative_path: str,
        tooltip_text: str = "",
        icon_size: int = 24,
        button_size: int = 48,
    ) -> None:
        super().__init__()

        self.icon_relative_path = icon_relative_path
        self.icon_size_value = icon_size
        self.button_size_value = button_size
        self.is_active = False

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip_text)
        self.setFixedSize(QSize(self.button_size_value, self.button_size_value))

        self.icon_label = QLabel(self)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._build_ui()
        self._load_icon()
        self._apply_style()

    # ============================================================
    # UI
    # ============================================================
    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.icon_label)
        self.setLayout(layout)

    # ============================================================
    # ICON
    # ============================================================
    def _load_icon(self) -> None:
        from PySide6.QtGui import QPainter, QColor

        icon_path = get_resource_path(self.icon_relative_path)
        pixmap = QPixmap(icon_path)

        if pixmap.isNull():
            return

        self._raw_pixmap = pixmap.scaled(
            self.icon_size_value,
            self.icon_size_value,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._tint_icon()

    def _tint_icon(self) -> None:
        from PySide6.QtGui import QPainter, QColor

        if not hasattr(self, "_raw_pixmap") or self._raw_pixmap is None:
            return

        color = QColor("#4fc1ff") if self.is_active else QColor("#c5c5c5")

        recolored = QPixmap(self._raw_pixmap.size())
        recolored.fill(Qt.GlobalColor.transparent)

        painter = QPainter(recolored)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.drawPixmap(0, 0, self._raw_pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(recolored.rect(), color)
        painter.end()

        self.icon_label.setPixmap(recolored)
        
    # ============================================================
    # STATE
    # ============================================================
    def set_active(self, active: bool) -> None:
        self.is_active = active
        self._apply_style()
        self._tint_icon()

    # ============================================================
    # STYLE
    # ============================================================
    def _apply_style(self) -> None:
        if self.is_active:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #2d2d30;
                    border-left: 3px solid #4fc1ff;
                    border-radius: 0px;
                }
                QPushButton:hover {
                    background-color: #333337;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #2a2a2a;
                }
            """)