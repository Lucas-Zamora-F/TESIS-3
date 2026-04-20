import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from tools.installation.check_environment import ensure_environment

from app.frontend.pages.configuration_page import ConfigurationPage
from app.frontend.pages.home_page import HomePage
from app.frontend.pages.metadata_page import MetadataPage
from app.frontend.pages.parameters_page import ParametersPage
from app.frontend.pages.splash_screen import SplashScreen


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("SDISG")
        self.resize(1280, 820)

        self.stack = QStackedWidget()

        self.home_page = HomePage()
        self.configuration_page = ConfigurationPage()
        self.parameters_page = ParametersPage()
        self.metadata_page = MetadataPage()

        self.stack.addWidget(self.home_page)           # index 0
        self.stack.addWidget(self.configuration_page)  # index 1
        self.stack.addWidget(self.parameters_page)     # index 2
        self.stack.addWidget(self.metadata_page)       # index 3

        self.setCentralWidget(self.stack)

        # ============================================================
        # HOME PAGE SIGNALS
        # ============================================================
        self.home_page.open_configuration.connect(self.show_configuration)
        self.home_page.open_parameters.connect(self.show_parameters)
        self.home_page.open_metadata.connect(self.show_metadata)

        # ============================================================
        # CONFIGURATION PAGE SIGNALS
        # ============================================================
        self.configuration_page.open_home.connect(self.show_home)
        self.configuration_page.open_configuration.connect(self.show_configuration)
        self.configuration_page.open_parameters.connect(self.show_parameters)
        self.configuration_page.open_metadata.connect(self.show_metadata)

        # ============================================================
        # PARAMETERS PAGE SIGNALS
        # ============================================================
        self.parameters_page.open_home.connect(self.show_home)
        self.parameters_page.open_configuration.connect(self.show_configuration)
        self.parameters_page.open_parameters.connect(self.show_parameters)
        self.parameters_page.open_metadata.connect(self.show_metadata)

        # ============================================================
        # METADATA PAGE SIGNALS
        # ============================================================
        self.metadata_page.open_home.connect(self.show_home)
        self.metadata_page.open_configuration.connect(self.show_configuration)
        self.metadata_page.open_parameters.connect(self.show_parameters)
        self.metadata_page.open_metadata.connect(self.show_metadata)

    def show_home(self) -> None:
        self.stack.setCurrentIndex(0)

    def show_configuration(self) -> None:
        self.stack.setCurrentIndex(1)

    def show_parameters(self) -> None:
        self.stack.setCurrentIndex(2)

    def show_metadata(self) -> None:
        self.stack.setCurrentIndex(3)


def main() -> None:
    app = QApplication(sys.argv)

    splash = SplashScreen()
    splash.show()

    app.processEvents()

    window = MainWindow()

    def log(msg: str):
        splash.set_message(msg)
        QApplication.processEvents()

    def load_app():
        try:
            log("Checking environment...")
            ensure_environment(log)

            log("Loading main interface...")
            window.show()
            splash.finish(window)

        except Exception as e:
            splash.set_message(f"Environment setup failed: {e}")
            QMessageBox.critical(None, "Error", str(e))
            sys.exit(1)

    QTimer.singleShot(100, load_app)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()