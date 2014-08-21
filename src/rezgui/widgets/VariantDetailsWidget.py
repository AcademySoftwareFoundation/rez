from rezgui.qt import QtCore, QtGui
from rezgui.widgets.StreamableTextEdit import StreamableTextEdit
from rezgui.util import create_pane


class VariantDetailsWidget(QtGui.QWidget):

    viewGraph = QtCore.Signal(str)  # package_name

    def __init__(self, parent=None):
        super(VariantDetailsWidget, self).__init__(parent)
        self.variant = None

        self.label = QtGui.QLabel()
        self.edit = StreamableTextEdit()
        self.edit.setStyleSheet("font: 9pt 'Courier'")
        self.view_graph_btn = QtGui.QPushButton("View Graph...")
        btn_pane = create_pane([None, self.view_graph_btn], True)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.edit)
        layout.addWidget(btn_pane)
        self.setLayout(layout)

        self.view_graph_btn.clicked.connect(self._view_graph)

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

    def _view_graph(self):
        self.viewGraph.emit(self.variant.name)
