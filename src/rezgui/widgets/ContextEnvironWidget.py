from rezgui.qt import QtGui
from rezgui.widgets.ContextEnvironTable import ContextEnvironTable
from rezgui.util import create_pane
from rezgui.objects.App import app


class ContextEnvironWidget(QtGui.QWidget):

    split_entries = [("None", None),
                     ("Colon (:)", ':'),
                     ("Semicolon (;)", ';'),
                     ("Comma (,)", ','),
                     ("Whitespace", ' ')]

    def __init__(self, parent=None):
        super(ContextEnvironWidget, self).__init__(parent)

        self.table = ContextEnvironTable()
        self.split_combo = QtGui.QComboBox()
        for label, _ in self.split_entries:
            self.split_combo.addItem(label)

        label = QtGui.QLabel("split values by:")
        btn_pane = create_pane([None, label, self.split_combo], True)

        self.layout = QtGui.QVBoxLayout()
        self.layout.addWidget(self.table)
        self.layout.addWidget(btn_pane)
        self.setLayout(self.layout)

        self.split_combo.currentIndexChanged.connect(self._set_split_char)
        app.config.attach(self.split_combo, "split_char")

    def set_context(self, context):
        self.table.set_context(context)

    def _set_split_char(self):
        index = self.split_combo.currentIndex()
        ch = self.split_entries[index][1]
        self.table.set_split_character(ch)


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
