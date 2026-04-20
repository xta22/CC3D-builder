from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QComboBox, 
    QTabWidget, QWidget, QPushButton, QTableWidget, QTableWidgetItem, 
    QCheckBox, QGroupBox, QMessageBox, QHeaderView
)
from PyQt5.QtCore import Qt

class FieldSetupDialog(QDialog):
    def __init__(self, field_name: str, available_celltypes: list, parent=None):
        super().__init__(parent)
        self.field_name = field_name
        self.available_celltypes = available_celltypes
        
        self.setWindowTitle(f"Configure Field: {self.field_name}")
        self.resize(600, 500)
        
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # 创建选项卡
        self.tabs = QTabWidget()
        self.tab_basic = QWidget()
        self.tab_bc = QWidget()
        self.tab_chemo = QWidget()
        
        self.tabs.addTab(self.tab_basic, "1. Basic PDE & Init")
        self.tabs.addTab(self.tab_bc, "2. Boundary Conditions")
        self.tabs.addTab(self.tab_chemo, "3. Chemotaxis")
        
        self.setup_basic_tab()
        self.setup_bc_tab()
        self.setup_chemo_tab()
        
        main_layout.addWidget(self.tabs)
        
        # 底部按钮区
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("Confirm")
        self.btn_cancel = QPushButton("Cancel")
        
        self.btn_ok.clicked.connect(self.accept_data)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_ok)
        
        main_layout.addLayout(btn_layout)

    # ==================== Tab 1: 基础参数 ====================
    def setup_basic_tab(self):
        layout = QVBoxLayout(self.tab_basic)
        form = QFormLayout()
        
        self.cb_solver = QComboBox()
        self.cb_solver.addItems(["DiffusionSolverFE", "ReactionDiffusionSolverFE", "SteadyStateDiffusionSolver"])
        
        self.le_diff = QLineEdit("0.01")
        self.le_decay = QLineEdit("0.0001")
        self.le_init = QLineEdit("0.0")
        
        form.addRow("Solver Type:", self.cb_solver)
        form.addRow("Diffusion Constant:", self.le_diff)
        form.addRow("Decay Constant:", self.le_decay)
        form.addRow("Initial Expression:", self.le_init)
        
        layout.addLayout(form)
        layout.addStretch()
        
        # 联动功能的 Checkbox
        self.chk_secretion = QCheckBox("Control Secretion through Python")
        layout.addWidget(self.chk_secretion)

    # ==================== Tab 2: 边界条件 ====================
    def setup_bc_tab(self):
        layout = QVBoxLayout(self.tab_bc)
        self.bc_inputs = {} # 保存 X, Y, Z 的输入框引用
        
        for axis in ["X", "Y", "Z"]:
            group = QGroupBox(f"Along {axis} axis")
            g_layout = QFormLayout()
            
            cb_type = QComboBox()
            cb_type.addItems(["Periodic", "ConstantDerivative", "ConstantValue"])
            
            le_min = QLineEdit("0.0")
            le_max = QLineEdit("0.0")
            
            g_layout.addRow("Condition Type:", cb_type)
            g_layout.addRow(f"Value at {axis.lower()}.min:", le_min)
            g_layout.addRow(f"Value at {axis.lower()}.max:", le_max)
            
            # 当选择 Periodic 时，禁用 min/max 输入
            cb_type.currentTextChanged.connect(
                lambda text, _min=le_min, _max=le_max: 
                (_min.setEnabled(text != "Periodic"), _max.setEnabled(text != "Periodic"))
            )
            
            self.bc_inputs[axis] = {"type": cb_type, "min": le_min, "max": le_max}
            group.setLayout(g_layout)
            layout.addWidget(group)

    # ==================== Tab 3: 趋化性 ====================
    def setup_chemo_tab(self):
        layout = QVBoxLayout(self.tab_chemo)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_add = QPushButton("Add Entry")
        btn_remove = QPushButton("Remove Selected")
        btn_add.clicked.connect(self.add_chemo_row)
        btn_remove.clicked.connect(self.remove_chemo_row)
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_remove)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 表格
        self.table_chemo = QTableWidget(0, 4)
        self.table_chemo.setHorizontalHeaderLabels(["CellType", "Lambda", "Type", "Sat Coef"])
        self.table_chemo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table_chemo)

    def add_chemo_row(self):
        row = self.table_chemo.rowCount()
        self.table_chemo.insertRow(row)
        
        # 细胞类型下拉框
        cb_cell = QComboBox()
        cb_cell.addItems(self.available_celltypes)
        self.table_chemo.setCellWidget(row, 0, cb_cell)
        
        self.table_chemo.setItem(row, 1, QTableWidgetItem("100.0"))
        
        # 趋化类型下拉框
        cb_type = QComboBox()
        cb_type.addItems(["regular", "saturation", "saturation linear"])
        self.table_chemo.setCellWidget(row, 2, cb_type)
        
        self.table_chemo.setItem(row, 3, QTableWidgetItem("0.0"))

    def remove_chemo_row(self):
        current_row = self.table_chemo.currentRow()
        if current_row >= 0:
            self.table_chemo.removeRow(current_row)

    # ==================== 数据导出 ====================
    def accept_data(self):
        """校验并组装终极字典"""
        try:
            # 1. 收集基础参数
            self.field_data = {
                "Solver": self.cb_solver.currentText(),
                "GlobalDiffusionConstant": float(self.le_diff.text()),
                "GlobalDecayConstant": float(self.le_decay.text()),
                "InitialConcentrationExpression": self.le_init.text().strip(),
                "BoundaryConditions": {},
                "Chemotaxis": [],
                "ControlSecretionPython": self.chk_secretion.isChecked()  # 🌟 联动标记
            }
            
            # 2. 收集边界条件
            for axis, widgets in self.bc_inputs.items():
                self.field_data["BoundaryConditions"][axis] = {
                    "type": widgets["type"].currentText(),
                    "min_val": float(widgets["min"].text()),
                    "max_val": float(widgets["max"].text())
                }
                
            # 3. 收集趋化性
            for row in range(self.table_chemo.rowCount()):
                cell_widget = self.table_chemo.cellWidget(row, 0)
                type_widget = self.table_chemo.cellWidget(row, 2)
                
                if cell_widget and type_widget:
                    self.field_data["Chemotaxis"].append({
                        "CellType": cell_widget.currentText(),
                        "Lambda": float(self.table_chemo.item(row, 1).text()),
                        "Type": type_widget.currentText(),
                        "SatCoef": float(self.table_chemo.item(row, 3).text())
                    })
                    
            self.accept() # 关闭弹窗并返回 QDialog.Accepted
            
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please ensure all numerical fields contain valid numbers.")

    def get_data(self):
        return self.field_data