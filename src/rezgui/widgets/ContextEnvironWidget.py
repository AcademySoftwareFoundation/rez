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


from Qt import QtWidgets
from rezgui.widgets.ContextEnvironTable import ContextEnvironTable
from rezgui.util import create_pane
from rezgui.objects.App import app


class ContextEnvironWidget(QtWidgets.QWidget):

    split_entries = [("None", None),
                     ("Colon (:)", ':'),
                     ("Semicolon (;)", ';'),
                     ("Comma (,)", ','),
                     ("Whitespace", ' ')]

    def __init__(self, parent=None):
        super(ContextEnvironWidget, self).__init__(parent)

        self.table = ContextEnvironTable()
        self.split_combo = QtWidgets.QComboBox()
        for label, _ in self.split_entries:
            self.split_combo.addItem(label)

        label = QtWidgets.QLabel("split values by:")
        btn_pane = create_pane([None, label, self.split_combo], True)

        self.layout = QtWidgets.QVBoxLayout()
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
