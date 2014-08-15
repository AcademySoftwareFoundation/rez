from rezgui.qt import QtCore, QtGui
from rezgui.widgets.PackageLineEdit import PackageLineEdit
from rezgui.widgets.ContextManagerWidget import ContextManagerWidget


class TestDialog(QtGui.QDialog):
    def __init__(self, parent=None):
        super(TestDialog, self).__init__(parent)
        self.setWindowTitle("Rez GUI")

        self.mgr = ContextManagerWidget()
        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.mgr)
        self.setLayout(layout)

    def sizeHint(self):
        return QtCore.QSize(800, 500)
