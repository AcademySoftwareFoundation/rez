from rezgui.qt import QtCore, QtGui
from rezgui.widgets.StreamableTextEdit import StreamableTextEdit
from rezgui.util import create_pane


class VariantDetailsWidget(QtGui.QWidget):
    def __init__(self, parent=None):
        super(VariantDetailsWidget, self).__init__(parent)
        self.variant = None

        self.label = QtGui.QLabel()
        self.edit = StreamableTextEdit()
        self.edit.setStyleSheet("font: 9pt 'Courier'")

        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.edit)
        self.setLayout(layout)

        self.clear()

    def clear(self):
        self.label.setText("no package selected")
        self.edit.clear()
        self.setEnabled(False)

    def set_variant(self, variant):
        if variant == self.variant:
            return

        if variant is None:
            self.clear()
        else:
            self.setEnabled(True)
            self.label.setText(str(variant))
            self.edit.clear()
            variant.print_info(self.edit)
            self.edit.moveCursor(QtGui.QTextCursor.Start)

        self.variant = variant
