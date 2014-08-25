from rezgui.qt import QtCore, QtGui
from rezgui.widgets.ToolWidget import ToolWidget


class VariantToolsList(QtGui.QTableWidget):
    def __init__(self, parent=None):
        super(VariantToolsList, self).__init__(0, 1, parent)
        self.variant = None
        self.context = None

        self.setGridStyle(QtCore.Qt.DotLine)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)

        hh = self.horizontalHeader()
        hh.setStretchLastSection(True)
        hh.setVisible(False)
        vh = self.verticalHeader()
        vh.setVisible(False)

    def clear(self):
        self.setRowCount(0)
        self.setEnabled(False)

    def refresh(self):
        variant = self.variant
        self.variant = None
        self.set_variant(variant)

    def set_context(self, context):
        self.context = context
        self.variant = None

    def set_variant(self, variant):
        if variant == self.variant:
            return

        if variant is None:
            self.clear()
        else:
            assert self.context
            tools = sorted(variant.tools or [])
            self.setRowCount(len(tools))
            self.setEnabled(True)

            for i, tool in enumerate(tools):
                widget = ToolWidget(self.context, tool, self)
                widget.clicked.connect(self._clear_selection)
                self.setCellWidget(i, 0, widget)

        self.variant = variant

    def _clear_selection(self):
        self.clearSelection()
