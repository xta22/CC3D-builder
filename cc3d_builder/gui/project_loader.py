from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QPushButton,
    QFileDialog, QApplication
)
import sys
import os

from gui.main_editor import MainWindow   


class ProjectLoader(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()

        self.path_input = QLineEdit()
        self.browse_btn = QPushButton("Browse")
        self.load_btn = QPushButton("Load Project")

        self.browse_btn.clicked.connect(self.browse)

        self.load_btn.clicked.connect(self.load_project)

        layout.addWidget(self.path_input)
        layout.addWidget(self.browse_btn)
        layout.addWidget(self.load_btn)

        self.setLayout(layout)

    def browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Project Folder")
        if folder:
            self.path_input.setText(folder)

    def load_project(self):

        print("LOAD CLICKED")

        try:
            project_path = self.path_input.text().strip()
            print("PATH:", project_path)

            sim_path = os.path.join(project_path, "Simulation")

            if sim_path not in sys.path:
                sys.path.append(sim_path)

            print(">>> BEFORE IMPORT <<<")
            print(os.listdir(sim_path))

            from registry.simulation_registry import SimulationRegistry
            print(">>> REGISTRY IMPORT OK <<<")

            from gui.main_editor import MainWindow
            print(">>> MAINWINDOW IMPORT OK <<<")

            self.registry = SimulationRegistry(project_path)
            print(">>> REGISTRY CREATED <<<")

            self.registry.load()
            print(">>> REGISTRY LOADED <<<")

            self.main_window = MainWindow(self.registry)
            print(">>> MAINWINDOW CREATED <<<")

            self.main_window.show()

            self.main_window.raise_()
            self.main_window.activateWindow()
            self.main_window.setWindowState(self.main_window.windowState() & ~0x00000001)
            
            self.close()
            print(">>> DONE <<<")

        except Exception as e:
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    print(">>> ENTER MAIN <<<")

    app = QApplication(sys.argv)

    w = ProjectLoader()
    print(">>> WINDOW CREATED <<<")

    w.show()
    print(">>> WINDOW SHOWN <<<")

    sys.exit(app.exec_())