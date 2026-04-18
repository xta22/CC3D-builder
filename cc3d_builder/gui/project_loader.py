from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QPushButton,
    QFileDialog, QApplication, QMessageBox
)
import sys
from pathlib import Path
import traceback

CURRENT_FILE = Path(__file__).resolve()
BUILDER_ROOT = CURRENT_FILE.parents[2] 
if str(BUILDER_ROOT) not in sys.path:
    sys.path.insert(0, str(BUILDER_ROOT))
print(f"📍 Project Root: {BUILDER_ROOT}")

try:
    from Rules_project.Simulation.registry.simulation_registry import SimulationRegistry
    from cc3d_builder.core.structure_manager import StructureManager
    from cc3d_builder.gui.main_editor import MainWindow
    print("✅ All modules loaded successfully")
except ImportError as e:
    print(f"❌ CRITICAL ERROR: Could not import necessary modules!")
    traceback.print_exc()
    print(f"Details: {e}")
    sys.exit(1)

class ProjectLoader(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("CC3D Project Loader")
        self.resize(400, 150)

        layout = QVBoxLayout()

        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Select your CC3D Project folder...")

        self.browse_btn = QPushButton("Browse")
        self.load_btn = QPushButton("Load Project")

        self.browse_btn.clicked.connect(self.browse)
        self.load_btn.clicked.connect(self.load_project)

        layout.addWidget(self.path_input)
        layout.addWidget(self.browse_btn)
        layout.addWidget(self.load_btn)

        self.setLayout(layout)

    def browse(self):
        default_path = str(Path.home() / "src")
        folder = QFileDialog.getExistingDirectory(self, "Select Project Folder", default_path)
        if folder:
            self.path_input.setText(folder)

    def load_project(self):
        raw_path = self.path_input.text().strip()
        if not raw_path:
            QMessageBox.warning(self, "Error", "Please select a project path!")
            return
        
        project_path = Path(raw_path).resolve()
        sim_path = project_path / "Simulation"
        if not sim_path.exists():
            QMessageBox.critical(self, "Invalid Project", f"Cannot find 'Simulation' folder in:\n{project_path}")
            return
        print(f"📂 Loading Project: {project_path}")
 
        try:
            sm = StructureManager(project_path)
            print(">>> REGISTRY & STRUCTUREMANAGER IMPORT OK <<<")

            self.registry = SimulationRegistry(project_path, structure_manager = sm)
            print(">>> REGISTRY CREATED <<<")

            self.registry.load()
            print(">>> REGISTRY LOADED <<<")

            self.main_window = MainWindow(registry=self.registry)
            print(">>> MAINWINDOW CREATED <<<")

            self.main_window.show()

            self.main_window.raise_()
            self.main_window.activateWindow()

            self.close()
            print(">>> DONE <<<")

        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            print(error_msg)
            QMessageBox.critical(self, "Load Failed", f"An error occurred while loading the project:\n{str(e)}")


if __name__ == "__main__":
    print(">>> ENTER MAIN <<<")

    app = QApplication(sys.argv)

    w = ProjectLoader()
    print(">>> WINDOW CREATED <<<")

    w.show()
    print(">>> WINDOW SHOWN <<<")

    sys.exit(app.exec_())