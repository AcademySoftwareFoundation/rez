from rezgui.qt import QtCore, QtGui
from rezgui.widgets.PackageLineEdit import PackageLineEdit
from rezgui.widgets.ContextTableWidget import ContextTableWidget


class TestDialog(QtGui.QDialog):
    def __init__(self, parent=None):
        super(TestDialog, self).__init__(parent)
        self.setWindowTitle("Rez GUI")

        self.edit = PackageLineEdit()
        self.table = ContextTableWidget()
        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.edit)
        layout.addWidget(self.table)
        self.setLayout(layout)

    def sizeHint(self):
        return QtCore.QSize(1000, 600)
