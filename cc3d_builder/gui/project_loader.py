from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QPushButton,
    QFileDialog, QApplication, QMessageBox
)
import sys
from pathlib import Path
import traceback
from cc3d_builder.core.project_manager import ProjectManager

CURRENT_FILE = Path(__file__).resolve()
BUILDER_ROOT = CURRENT_FILE.parents[2] 
if str(BUILDER_ROOT) not in sys.path:
    sys.path.insert(0, str(BUILDER_ROOT))
print(f"📍 Project Root: {BUILDER_ROOT}")

try:
    from cc3d_builder.engine.registry.simulation_registry import SimulationRegistry
    from cc3d_builder.core.structure_manager import StructureManager
    from cc3d_builder.gui.main_editor import MainWindow
    from cc3d_builder.core.project_manager import ProjectManager
    from cc3d_builder.injector.steppable_injector import SteppableInjector
    
    print("✅ All modules loaded successfully")
except ImportError as e:
    print(f"❌ CRITICAL ERROR: Could not import necessary modules!")
    traceback.print_exc()
    print(f"Details: {e}")
    sys.exit(1)

class ProjectLoader(QWidget):

    def __init__(self):
        super().__init__()
        self.sandbox_dir = BUILDER_ROOT / "Rules_project"
        self.project_manager = ProjectManager(self.sandbox_dir)

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
        
        source_path = Path(raw_path).resolve()
        
        json_exists = (self.sandbox_dir / "rules.json").exists()
        is_import = False
        
        if json_exists:
            msg = QMessageBox(self)
            msg.setWindowTitle("Load Mode")
            msg.setText("How would you like to load this project?")
            # remove and reset rules.json)
            btn_import = msg.addButton("Import New (Clear Rules)", QMessageBox.ActionRole)
            # keep rules.json)
            btn_resume = msg.addButton("Resume (Keep Rules)", QMessageBox.ActionRole)
            msg.addButton(QMessageBox.Cancel)
            
            msg.exec_()
            
            if msg.clickedButton() == btn_import:
                is_import = True
            elif msg.clickedButton() == btn_resume:
                is_import = False
            else:
                return # user chooses Cancel
        else:
            # initialize import
            is_import = True

        try:
            self.project_manager.initialize_project(source_path, is_import=is_import)

            sm = StructureManager(self.sandbox_dir)
            injector = SteppableInjector(self.sandbox_dir)

            self.registry = SimulationRegistry(self.sandbox_dir, structure_manager=sm)
            
            self.registry.load() # here file would have rules.json

            self.main_window = MainWindow(
                registry=self.registry, 
                sm=sm, 
                injector=injector
            )
            self.main_window.show()
            self.close()

        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Load Failed", f"Error:\n{str(e)}")




if __name__ == "__main__":
    print(">>> ENTER MAIN <<<")

    app = QApplication(sys.argv)

    w = ProjectLoader()
    print(">>> WINDOW CREATED <<<")

    w.show()
    print(">>> WINDOW SHOWN <<<")

    sys.exit(app.exec_())