import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QSplashScreen


def get_resource_path(relative_path: str) -> str:
    """
    Devuelve la ruta correcta tanto en desarrollo como en PyInstaller.
    """
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

        pixmap = QPixmap(logo_path)

        # Si falla la carga del logo
        if pixmap.isNull():
            pixmap = QPixmap(700, 400)
            pixmap.fill(QColor("#0f172a"))
        else:
            pixmap = pixmap.scaled(
                700,
                400,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        super().__init__(pixmap)

        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)

        self.showMessage(
            "Initializing SDISG...",
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            QColor("#e2e8f0"),
        )

    def set_message(self, message: str) -> None:
        """
        Permite actualizar el mensaje dinámicamente.
        """
        self.showMessage(
            message,
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            QColor("#e2e8f0"),
        )