from rezgui.qt import QtCore, QtGui
from rezgui.widgets.StreamableTextEdit import StreamableTextEdit
from rezgui.dialogs.WriteGraphDialog import view_graph
from rezgui.util import create_pane


class VariantDetailsWidget(QtGui.QWidget):
    def __init__(self, parent=None):
        super(VariantDetailsWidget, self).__init__(parent)
        self.context = None
        self.variant = None

        self.label = QtGui.QLabel()
        self.edit = StreamableTextEdit()
        self.edit.setStyleSheet("font: 9pt 'Courier'")
        self.view_graph_btn = QtGui.QPushButton("View Graph...")
        self.view_graph_btn.hide()
        btn_pane = create_pane([None, self.view_graph_btn], True, compact=True)

        create_pane([self.label, self.edit, btn_pane], False, compact=True,
                    parent_widget=self)

        self.view_graph_btn.clicked.connect(self._view_graph)
        self.clear()

    def clear(self):
        self.label.setText("no package selected")
        self.view_graph_btn.hide()
        self.edit.clear()
        self.setEnabled(False)

    def set_context(self, context):
        self.context = context
        self.view_graph_btn.setVisible(context is not None)

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
            self.view_graph_btn.setVisible(self.context is not None)

        self.variant = variant

    def _view_graph(self):
        graph_str = self.context.graph(as_dot=True)
        view_graph(graph_str, self, prune_to=self.variant.name)
