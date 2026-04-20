import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from app.frontend.pages.configuration_page import ConfigurationPage
from app.frontend.pages.home_page import HomePage
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

        self.stack.addWidget(self.home_page)           # index 0
        self.stack.addWidget(self.configuration_page)  # index 1
        self.stack.addWidget(self.parameters_page)     # index 2

        self.setCentralWidget(self.stack)

        self.home_page.open_configuration.connect(self.show_configuration)
        self.home_page.open_parameters.connect(self.show_parameters)

        self.configuration_page.open_home.connect(self.show_home)
        self.configuration_page.open_configuration.connect(self.show_configuration)
        self.configuration_page.open_parameters.connect(self.show_parameters)

        self.parameters_page.open_home.connect(self.show_home)
        self.parameters_page.open_configuration.connect(self.show_configuration)
        self.parameters_page.open_parameters.connect(self.show_parameters)

    def show_home(self) -> None:
        self.stack.setCurrentIndex(0)

    def show_configuration(self) -> None:
        self.stack.setCurrentIndex(1)

    def show_parameters(self) -> None:
        self.stack.setCurrentIndex(2)


def main() -> None:
    app = QApplication(sys.argv)

    splash = SplashScreen()
    splash.show()

    app.processEvents()

    window = MainWindow()

    def load_app() -> None:
        splash.set_message("Loading main interface...")
        window.show()
        splash.finish(window)

    QTimer.singleShot(1200, load_app)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()