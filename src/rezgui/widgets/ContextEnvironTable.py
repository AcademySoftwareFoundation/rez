from Qt import QtCompat, QtCore, QtWidgets


class ContextEnvironTable(QtWidgets.QTableWidget):
    def __init__(self, parent=None):
        super(ContextEnvironTable, self).__init__(0, 2, parent)
        self.context = None
        self.split_char = None

        self.setGridStyle(QtCore.Qt.DotLine)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setAlternatingRowColors(True)
        self.setStyleSheet("font: 12pt 'Courier'")

        hh = self.horizontalHeader()
        hh.setStretchLastSection(True)
        hh.setVisible(False)
        vh = self.verticalHeader()
        vh.setVisible(False)
        QtCompat.QHeaderView.setSectionResizeMode(
            vh, QtWidgets.QHeaderView.ResizeToContents)
        self.setEnabled(False)

    def clear(self):
        super(ContextEnvironTable, self).clear()
        self.setEnabled(False)
        hh = self.horizontalHeader()
        hh.setVisible(False)

    def set_split_character(self, ch=None):
        """Set the 'split' character.

        If a 'split' character is set, values containing this character are
        split across newlines. This makes it easier to read variables like PATH.

        Note: If ch is space, this is treated as 'split on whitespace'
        """
        self.split_char = ch
        self.refresh()

    def refresh(self):
        context = self.context
        self.context = None
        self.set_context(context)

    def set_context(self, context):
        self.clear()
        self.context = context
        if self.context is None:
            return

        environ = self.context.get_environ()
        self.setRowCount(len(environ))

        for i, (name, value) in enumerate(sorted(environ.items())):
            item = QtWidgets.QTableWidgetItem(name)
            self.setItem(i, 0, item)
            if self.split_char == ' ':
                value = '\n'.join(value.strip().split())
            elif self.split_char is not None:
                value = value.strip(self.split_char).replace(self.split_char, '\n')
            item = QtWidgets.QTableWidgetItem(value)
            self.setItem(i, 1, item)

        self.setHorizontalHeaderLabels(["variable", "value"])
        self.resizeRowsToContents()
        self.resizeColumnsToContents()
        hh = self.horizontalHeader()
        hh.setStretchLastSection(True)
        hh.setVisible(True)
        self.setEnabled(True)


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
