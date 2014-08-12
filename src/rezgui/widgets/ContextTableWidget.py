from rezgui.qt import QtCore, QtGui
from rezgui.widgets.PackageLineEdit import PackageLineEdit
from functools import partial


class ContextTableWidget(QtGui.QTableWidget):
    default_row_count = 10

    def __init__(self, parent=None):
        super(ContextTableWidget, self).__init__(self.default_row_count,
                                                 2, parent)
        self.context = None

        self.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.setSelectionMode(QtGui.QAbstractItemView.NoSelection)
        self.setFocusPolicy(QtCore.Qt.NoFocus)

        hh = self.horizontalHeader()
        hh.setDefaultSectionSize(10 * self.fontMetrics().height())

        vh = self.verticalHeader()
        vh.setResizeMode(QtGui.QHeaderView.Fixed)
        vh.setDefaultSectionSize(3 * self.fontMetrics().height() / 2)
        vh.setVisible(False)

        self.set_context()

    def set_context(self, context=None):
        self.clear()
        self.setHorizontalHeaderLabels(["request", "resolve"])
        self.context = context
        if self.context:
            pass
        else:
            self._set_package_edit(0, 0)

    def _set_package_edit(self, row, column, txt=None):
        edit = PackageLineEdit()
        edit.setText(txt or "")
        edit.setStyleSheet("QLineEdit { border : 0px;}")
        self.setCellWidget(row, column, edit)
        edit.textChanged.connect(partial(self._packageChanged, row, column))
        edit.packageChangeDone.connect(partial(self._packageChangeDone, row, column))
        return edit

    def _packageChanged(self, row, column, txt):
        if txt:
            row += 1
            if row >= self.rowCount():
                self.setRowCount(row + 1)
            next_edit = self.cellWidget(row, column)
            if next_edit is None:
                self._set_package_edit(row, column)

    def _packageChangeDone(self, row, column, txt):
        next_edit = self.cellWidget(row + 1, column)
        if txt:
            if next_edit:
                self.setCurrentCell(row + 1, column)
                next_edit.setFocus()
        elif next_edit:
            self._delete_cell(row, column)

    def _delete_cell(self, row, column):
        for i in range(row, self.rowCount()):
            edit = self.cellWidget(i, column)
            next_edit = self.cellWidget(i + 1, column)
            if next_edit:
                next_edit.clone_into(edit)
            else:
                self.removeCellWidget(i, column)
