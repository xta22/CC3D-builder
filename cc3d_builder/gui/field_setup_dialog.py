# field_setup_dialog.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QComboBox, 
    QTabWidget, QWidget, QPushButton, QTableWidget, QTableWidgetItem, 
    QCheckBox, QGroupBox, QMessageBox, QHeaderView
)
from PyQt5.QtCore import Qt

class FieldSetupDialog(QDialog):
    def __init__(self, field_name: str, available_celltypes: list, initial_data=None, parent=None):
        super().__init__(parent)
        self.initial_data = initial_data
        self.field_name = field_name
        self.available_celltypes = available_celltypes
        
        self.setWindowTitle(f"Configure Field: {self.field_name}")
        self.resize(600, 500)
        
        self.init_ui()

        if self.initial_data:
            self.load_data_into_ui()

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
        """收集 UI 数据 → 标准化 → 存入 self.field_data"""

        try:
            # =========================
            # 1️⃣ 基础 PDE 参数
            # =========================
            self.field_data = {
                "solver": self.cb_solver.currentText(),
                "diffusion_constant": float(self.le_diff.text()),
                "decay_constant": float(self.le_decay.text()),
                "initial_expression": self.le_init.text().strip(),
                "boundary_conditions": {},
                "chemotaxis": [],
                "python_secretion": self.chk_secretion.isChecked()
            }

            # =========================
            # 2️⃣ Boundary Conditions
            # =========================
            for axis, widgets in self.bc_inputs.items():

                bc_type = widgets["type"].currentText()

                # Periodic 没有数值
                if bc_type == "Periodic":
                    self.field_data["boundary_conditions"][axis] = {
                        "type": "Periodic"
                    }
                else:
                    self.field_data["boundary_conditions"][axis] = {
                        "type": bc_type,
                        "min_val": float(widgets["min"].text()),
                        "max_val": float(widgets["max"].text())
                    }

            # =========================
            # 3️⃣ Chemotaxis
            # =========================
            for row in range(self.table_chemo.rowCount()):

                cell_widget = self.table_chemo.cellWidget(row, 0)
                type_widget = self.table_chemo.cellWidget(row, 2)

                if not cell_widget or not type_widget:
                    continue

                cell_type = cell_widget.currentText()
                lambda_val = float(self.table_chemo.item(row, 1).text())
                chemo_type = type_widget.currentText()
                sat_coef = float(self.table_chemo.item(row, 3).text())

                chemo_entry = {
                    "cell_type": cell_type,
                    "lambda": lambda_val,
                    "mode": chemo_type  # ⭐ 统一命名（避免和 XML 冲突）
                }

                # 只有 saturation / saturation linear 才需要 SatCoef
                if chemo_type in ["saturation", "saturation linear"]:
                    chemo_entry["sat_coef"] = sat_coef

                self.field_data["chemotaxis"].append(chemo_entry)

            # =========================
            # ✅ 校验（非常重要）
            # =========================
            if self.field_data["diffusion_constant"] < 0:
                raise ValueError("Diffusion constant must be >= 0")

            if self.field_data["diffusion_constant"] < 0:
                raise ValueError("Decay constant must be >= 0")

            # =========================
            # ✅ Debug 输出（建议保留）
            # =========================
            print(f"\n✅ Field '{self.field_name}' configuration collected:")
            print(self.field_data)

            # =========================
            # 关闭 dialog
            # =========================
            self.accept()

        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", str(e))

    def get_data(self):
        return self.field_data
    
    def load_data_into_ui(self):
        # --- 1. Basic PDE ---
        data = self.initial_data if self.initial_data is not None else {}
        def get_val(key_big, key_small, default):
            return data.get(key_big, data.get(key_small, default))
        
        # 2. 接下来的所有 get 都针对 data (它是确定的 dict)，不再针对 self.initial_data
        self.cb_solver.setCurrentText(str(get_val("Solver", "solver", "DiffusionSolverFE")))
        
        # 扩散系数
        self.le_diff.setText(str(get_val("GlobalDiffusionConstant", "diffusion_constant", "0.01")))
        
        # 衰减系数
        self.le_decay.setText(str(get_val("GlobalDecayConstant", "decay_constant", "0.0001")))

        # 初始表达式
        self.le_init.setText(str(get_val("InitialConcentrationExpression", "initial_expression", "0.0")))
        
        # 分泌控制
        secretion_val = get_val("ControlSecretionPython", "python_secretion", False)
        self.chk_secretion.setChecked(secretion_val)

        # --- 2. Boundary Conditions ---

        # 2. 第二层兜底：确保获取到的 BoundaryConditions 是字典而不是 None
        bc_data = data.get("BoundaryConditions")
        bc = bc_data if isinstance(bc_data, dict) else {}
        
        for axis, widgets in self.bc_inputs.items():
            if axis in bc:
                # 3. 第三层兜底：确保轴数据（X/Y/Z）存在
                axis_config = bc.get(axis, {})
                widgets["type"].setCurrentText(axis_config.get("type", "Periodic"))
                widgets["min"].setText(str(axis_config.get("min_val", "0.0")))
                widgets["max"].setText(str(axis_config.get("max_val", "0.0")))

        # --- 3. Chemotaxis ---
        # 4. 第四层兜底：确保 chemo_list 是列表而不是 None
        raw_chemo = data.get("Chemotaxis")
        chemo_list = raw_chemo if isinstance(raw_chemo, list) else []
        
        self.table_chemo.setRowCount(0)
        for entry in chemo_list:
            if not isinstance(entry, dict): continue # 安全检查
            
            self.add_chemo_row()
            row = self.table_chemo.rowCount() - 1
            
            # 细胞类型回显
            cb_cell = self.table_chemo.cellWidget(row, 0)
            if isinstance(cb_cell, QComboBox):
                cb_cell.setCurrentText(entry.get("CellType", ""))
            
            # 数值回显 (注意：item 可能为 None，安全起见可以用之前的方法)
            lambda_item = self.table_chemo.item(row, 1)
            if lambda_item:
                lambda_item.setText(str(entry.get("Lambda", "100.0")))
            
            # 趋化类型回显
            cb_type = self.table_chemo.cellWidget(row, 2)
            if isinstance(cb_type, QComboBox):
                cb_type.setCurrentText(entry.get("Type", "regular"))
            
            sat_item = self.table_chemo.item(row, 3)
            if sat_item:
                sat_item.setText(str(entry.get("SatCoef", "0.0")))

