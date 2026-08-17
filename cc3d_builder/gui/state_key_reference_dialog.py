from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from cc3d_builder.core.state_key_catalog import (
    format_state_key_catalog_page,
    state_key_catalog_pages,
)


class StateKeyReferenceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("State Key Reference")
        self.resize(820, 640)

        self.pages = state_key_catalog_pages()
        self.page_index = 0

        self.page_combo = QComboBox(self)
        for index, page in enumerate(self.pages, start=1):
            self.page_combo.addItem(f"{index}. {page['title']}")
        self.page_combo.currentIndexChanged.connect(self.set_page)

        self.page_label = QLabel(self)

        self.text = QTextEdit(self)
        self.text.setReadOnly(True)

        self.prev_btn = QPushButton("Previous", self)
        self.prev_btn.clicked.connect(self.previous_page)

        self.next_btn = QPushButton("Next", self)
        self.next_btn.clicked.connect(self.next_page)

        close_btn = QPushButton("Close", self)
        close_btn.clicked.connect(self.accept)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Page:", self))
        top_row.addWidget(self.page_combo, 1)
        top_row.addWidget(self.page_label)

        bottom_row = QHBoxLayout()
        bottom_row.addWidget(self.prev_btn)
        bottom_row.addWidget(self.next_btn)
        bottom_row.addStretch()
        bottom_row.addWidget(close_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(top_row)
        layout.addWidget(self.text)
        layout.addLayout(bottom_row)

        self.update_page()

    def set_page(self, page_index):
        if 0 <= page_index < len(self.pages):
            self.page_index = page_index
            self.update_page()

    def previous_page(self):
        if self.page_index > 0:
            self.page_index -= 1
            self.update_page()

    def next_page(self):
        if self.page_index < len(self.pages) - 1:
            self.page_index += 1
            self.update_page()

    def update_page(self):
        total = len(self.pages)
        self.text.setPlainText(format_state_key_catalog_page(self.page_index))
        self.page_label.setText(f"{self.page_index + 1}/{total}")
        self.prev_btn.setEnabled(self.page_index > 0)
        self.next_btn.setEnabled(self.page_index < total - 1)

        if self.page_combo.currentIndex() != self.page_index:
            self.page_combo.blockSignals(True)
            self.page_combo.setCurrentIndex(self.page_index)
            self.page_combo.blockSignals(False)


def show_state_key_reference_dialog(parent=None):
    dialog = StateKeyReferenceDialog(parent)
    return dialog.exec_()
