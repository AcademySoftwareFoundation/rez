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
