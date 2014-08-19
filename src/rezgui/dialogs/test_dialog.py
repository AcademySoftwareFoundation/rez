from rezgui.qt import QtCore, QtGui
from rezgui.dialogs.ConfiguredDialog import ConfiguredDialog
from rezgui.widgets.PackageLineEdit import PackageLineEdit
from rezgui.widgets.ContextManagerWidget import ContextManagerWidget
from rezgui.config import config


class TestDialog(ConfiguredDialog):
    def __init__(self, parent=None):
        super(TestDialog, self).__init__(config, "layout/window/main", parent)
        self.setWindowTitle("Rez GUI")
        self.mgr = ContextManagerWidget()
        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.mgr)
        self.setLayout(layout)
