import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from app.frontend.pages.build_page import BuildPage
from app.frontend.pages.configuration_page import ConfigurationPage
from app.frontend.pages.home_page import HomePage
from app.frontend.pages.metadata_page import MetadataPage
from app.frontend.pages.parameters_page import ParametersPage
from app.frontend.pages.splash_screen import SplashScreen
from tools.installation.check_environment import ensure_environment


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
        self.build_page = BuildPage()

        self.stack.addWidget(self.home_page)           # index 0
        self.stack.addWidget(self.configuration_page)  # index 1
        self.stack.addWidget(self.parameters_page)     # index 2
        self.stack.addWidget(self.metadata_page)       # index 3
        self.stack.addWidget(self.build_page)          # index 4

        self.setCentralWidget(self.stack)

        # ============================================================
        # HOME PAGE SIGNALS
        # ============================================================
        self.home_page.open_home.connect(self.show_home)
        self.home_page.open_configuration.connect(self.show_configuration)
        self.home_page.open_parameters.connect(self.show_parameters)
        self.home_page.open_metadata.connect(self.show_metadata)
        self.home_page.open_build.connect(self.show_build)

        # ============================================================
        # CONFIGURATION PAGE SIGNALS
        # ============================================================
        self.configuration_page.open_home.connect(self.show_home)
        self.configuration_page.open_configuration.connect(self.show_configuration)
        self.configuration_page.open_parameters.connect(self.show_parameters)
        self.configuration_page.open_metadata.connect(self.show_metadata)
        self.configuration_page.open_build.connect(self.show_build)

        # ============================================================
        # PARAMETERS PAGE SIGNALS
        # ============================================================
        self.parameters_page.open_home.connect(self.show_home)
        self.parameters_page.open_configuration.connect(self.show_configuration)
        self.parameters_page.open_parameters.connect(self.show_parameters)
        self.parameters_page.open_metadata.connect(self.show_metadata)
        self.parameters_page.open_build.connect(self.show_build)

        # ============================================================
        # METADATA PAGE SIGNALS
        # ============================================================
        self.metadata_page.open_home.connect(self.show_home)
        self.metadata_page.open_configuration.connect(self.show_configuration)
        self.metadata_page.open_parameters.connect(self.show_parameters)
        self.metadata_page.open_metadata.connect(self.show_metadata)
        self.metadata_page.open_build.connect(self.show_build)

        # ============================================================
        # BUILD PAGE SIGNALS
        # ============================================================
        self.build_page.open_home.connect(self.show_home)
        self.build_page.open_configuration.connect(self.show_configuration)
        self.build_page.open_parameters.connect(self.show_parameters)
        self.build_page.open_metadata.connect(self.show_metadata)
        self.build_page.open_build.connect(self.show_build)

    def show_home(self) -> None:
        self.stack.setCurrentWidget(self.home_page)

    def show_configuration(self) -> None:
        self.stack.setCurrentWidget(self.configuration_page)

    def show_parameters(self) -> None:
        self.stack.setCurrentWidget(self.parameters_page)

    def show_metadata(self) -> None:
        self.stack.setCurrentWidget(self.metadata_page)

    def show_build(self) -> None:
        self.stack.setCurrentWidget(self.build_page)


def main() -> None:
    app = QApplication(sys.argv)

    splash = SplashScreen()
    splash.show()

    app.processEvents()

    window = MainWindow()

    def log(msg: str) -> None:
        splash.set_message(msg)
        print(msg)
        app.processEvents()

    def load_app() -> None:
        try:
            log("Checking environment...")
            ensure_environment(log)

            log("Loading main interface...")
            window.show()
            splash.finish(window)

        except Exception as e:
            splash.set_message(f"Environment setup failed: {e}")
            print(f"[ERROR] {e}")
            sys.exit(1)

    QTimer.singleShot(100, load_app)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()