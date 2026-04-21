import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap, QPainter, QBrush
from PySide6.QtWidgets import QSplashScreen


def get_resource_path(relative_path: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..")
        )
        base_path = project_root

    return os.path.join(base_path, relative_path)


class SplashScreen(QSplashScreen):
    def __init__(self) -> None:
        logo_path = get_resource_path("app/frontend/assets/sdisg_logo.png")

        # Crear canvas con fondo sólido
        canvas = QPixmap(700, 400)
        canvas.fill(QColor("#0f172a"))

        logo = QPixmap(logo_path)
        if not logo.isNull():
            logo = logo.scaled(
                500,
                300,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            # Centrar el logo sobre el fondo
            painter = QPainter(canvas)
            x = (700 - logo.width()) // 2
            y = (400 - logo.height()) // 2
            painter.drawPixmap(x, y, logo)
            painter.end()

        super().__init__(canvas)

        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)

        self.showMessage(
            "Initializing SDISG...",
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            QColor("#e2e8f0"),
        )

    def set_message(self, message: str) -> None:
        self.showMessage(
            message,
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            QColor("#e2e8f0"),
        )