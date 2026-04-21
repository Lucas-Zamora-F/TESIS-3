import sys
import os

# Si corre como ejecutable, apunta a la raíz de TESIS-3
if getattr(sys, 'frozen', False):
    project_root = os.path.abspath(os.path.join(os.path.dirname(sys.executable), '..', '..'))
    os.chdir(project_root)
    sys.path.insert(0, project_root)
else:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from app.frontend.pages.build_page import BuildPage
from app.frontend.pages.configuration_page import ConfigurationPage
from app.frontend.pages.explore_page import ExplorePage
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

        if getattr(sys, 'frozen', False):
            icon_path = os.path.join(os.path.dirname(sys.executable), '..', '..', 'app', 'frontend', 'assets', 'icons', 'sdisg_icon.ico')
        else:
            icon_path = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'assets', 'icons', 'sdisg_icon.ico')

        icon_path = os.path.abspath(icon_path)
        self.setWindowIcon(QIcon(icon_path))
        self.setWindowIcon(QIcon(icon_path))

        self.stack = QStackedWidget()

        self.home_page = HomePage()
        self.configuration_page = ConfigurationPage()
        self.parameters_page = ParametersPage()
        self.metadata_page = MetadataPage()
        self.build_page = BuildPage()
        self.explore_page = ExplorePage()

        self.stack.addWidget(self.home_page)           # index 0
        self.stack.addWidget(self.configuration_page)  # index 1
        self.stack.addWidget(self.parameters_page)     # index 2
        self.stack.addWidget(self.metadata_page)       # index 3
        self.stack.addWidget(self.build_page)          # index 4
        self.stack.addWidget(self.explore_page)        # index 5

        self.setCentralWidget(self.stack)

        # ============================================================
        # HOME PAGE SIGNALS
        # ============================================================
        self.home_page.open_home.connect(self.show_home)
        self.home_page.open_configuration.connect(self.show_configuration)
        self.home_page.open_parameters.connect(self.show_parameters)
        self.home_page.open_metadata.connect(self.show_metadata)
        self.home_page.open_build.connect(self.show_build)
        self.home_page.open_explore.connect(self.show_explore)

        # ============================================================
        # CONFIGURATION PAGE SIGNALS
        # ============================================================
        self.configuration_page.open_home.connect(self.show_home)
        self.configuration_page.open_configuration.connect(self.show_configuration)
        self.configuration_page.open_parameters.connect(self.show_parameters)
        self.configuration_page.open_metadata.connect(self.show_metadata)
        self.configuration_page.open_build.connect(self.show_build)
        self.configuration_page.open_explore.connect(self.show_explore)

        # ============================================================
        # PARAMETERS PAGE SIGNALS
        # ============================================================
        self.parameters_page.open_home.connect(self.show_home)
        self.parameters_page.open_configuration.connect(self.show_configuration)
        self.parameters_page.open_parameters.connect(self.show_parameters)
        self.parameters_page.open_metadata.connect(self.show_metadata)
        self.parameters_page.open_build.connect(self.show_build)
        self.parameters_page.open_explore.connect(self.show_explore)

        # ============================================================
        # METADATA PAGE SIGNALS
        # ============================================================
        self.metadata_page.open_home.connect(self.show_home)
        self.metadata_page.open_configuration.connect(self.show_configuration)
        self.metadata_page.open_parameters.connect(self.show_parameters)
        self.metadata_page.open_metadata.connect(self.show_metadata)
        self.metadata_page.open_build.connect(self.show_build)
        self.metadata_page.open_explore.connect(self.show_explore)

        # ============================================================
        # BUILD PAGE SIGNALS
        # ============================================================
        self.build_page.open_home.connect(self.show_home)
        self.build_page.open_configuration.connect(self.show_configuration)
        self.build_page.open_parameters.connect(self.show_parameters)
        self.build_page.open_metadata.connect(self.show_metadata)
        self.build_page.open_build.connect(self.show_build)
        self.build_page.open_explore.connect(self.show_explore)

        # ============================================================
        # EXPLORE PAGE SIGNALS
        # ============================================================
        self.explore_page.open_home.connect(self.show_home)
        self.explore_page.open_configuration.connect(self.show_configuration)
        self.explore_page.open_parameters.connect(self.show_parameters)
        self.explore_page.open_metadata.connect(self.show_metadata)
        self.explore_page.open_build.connect(self.show_build)
        self.explore_page.open_explore.connect(self.show_explore)

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

    def show_explore(self) -> None:
        self.stack.setCurrentWidget(self.explore_page)


def main() -> None:
    app = QApplication(sys.argv)

    if getattr(sys, 'frozen', False):
        icon_path = os.path.abspath(os.path.join(os.path.dirname(sys.executable), '..', '..', 'app', 'frontend', 'assets', 'icons', 'sdisg_icon.ico'))
    else:
        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend', 'assets', 'icons', 'sdisg_icon.ico'))
    app.setWindowIcon(QIcon(icon_path))

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
            if not getattr(sys, 'frozen', False):
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
