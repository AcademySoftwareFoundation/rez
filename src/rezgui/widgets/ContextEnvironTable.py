# Copyright Contributors to the Rez project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


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
