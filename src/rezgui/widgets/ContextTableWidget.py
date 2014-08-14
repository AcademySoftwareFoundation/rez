from rezgui.qt import QtCore, QtGui
from rezgui.widgets.PackageLineEdit import PackageLineEdit
from functools import partial


class ContextTableWidget(QtGui.QTableWidget):
    default_row_count = 10

    def __init__(self, settings, parent=None):
        super(ContextTableWidget, self).__init__(self.default_row_count,
                                                 2, parent)
        self.settings = settings
        self.context = None

        self.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.setSelectionMode(QtGui.QAbstractItemView.NoSelection)
        self.setFocusPolicy(QtCore.Qt.NoFocus)

        hh = self.horizontalHeader()
        hh.setDefaultSectionSize(12 * self.fontMetrics().height())

        vh = self.verticalHeader()
        vh.setResizeMode(QtGui.QHeaderView.Fixed)
        vh.setDefaultSectionSize(3 * self.fontMetrics().height() / 2)
        vh.setVisible(False)

        self.set_context()

    def set_context(self, context=None):
        """Set contents to the given `ResolvedContext`."""
        self.clear()
        self.setHorizontalHeaderLabels(["request", "resolve"])
        self.context = context
        if self.context:
            pass
        else:
            self._set_package_edit(0, 0)

    def get_request(self):
        """Get the current request list.

        Returns:
            List of strings.
        """
        request_strs = []
        for i in range(self.rowCount()):
            edit = self.cellWidget(i, 0)
            if edit:
                txt = str(edit.text()).strip()
                if txt:
                    request_strs.append(txt)
            else:
                break
        return request_strs

    def refresh(self):
        for i in range(self.rowCount()):
            edit = self.cellWidget(i, 0)
            if edit:
                edit.refresh()

    def _set_package_edit(self, row, column, txt=None):
        if row >= self.rowCount():
            self.setRowCount(row + 1)
        if self.cellWidget(row, column):
            return

        edit = PackageLineEdit(self.settings)
        edit.setText(txt or "")
        edit.setStyleSheet("QLineEdit { border : 0px;}")
        self.setCellWidget(row, column, edit)
        edit.textChanged.connect(partial(self._packageTextChanged, row, column))
        edit.focusOut.connect(partial(self._packageFocusOut, row, column))
        edit.focusOutViaKeyPress.connect(partial(self._packageFocusOutViaKeyPress, row, column))
        return edit

    def _packageTextChanged(self, row, column, txt):
        if txt:
            self._set_package_edit(row + 1, column)

    def _packageFocusOut(self, row, column, txt):
        if txt:
            self._set_package_edit(row + 1, column)
        elif self.cellWidget(row + 1, column):
            self._delete_cell(row, column)

    def _packageFocusOutViaKeyPress(self, row, column, txt):
        if txt:
            self._set_current_cell(row + 1, column)
        elif self.cellWidget(row + 1, column):
            self._delete_cell(row, column)

    def _delete_cell(self, row, column):
        for i in range(row, self.rowCount()):
            edit = self.cellWidget(i, column)
            next_edit = self.cellWidget(i + 1, column)
            if next_edit:
                next_edit.clone_into(edit)
            else:
                self.removeCellWidget(i, column)
        self._trim_trailing_rows()

    def _trim_trailing_rows(self):
        n = 0
        for i in reversed(range(self.default_row_count, self.rowCount())):
            row_clear = not any(self.cellWidget(i, x)
                                for x in range(self.columnCount()))
            if row_clear:
                n += 1
            else:
                break
        if n:
            row, column = self.currentRow(), self.currentColumn()
            self.setRowCount(self.rowCount() - n)
            self._set_current_cell(row, column)

    def _set_current_cell(self, row, column):
        self.setCurrentCell(row, column)
        edit = self.cellWidget(row, column)
        if edit:
            edit.setFocus()
