from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane
from rezgui.mixins.StoreSizeMixin import StoreSizeMixin
from rezgui.widgets.BrowsePackageWidget import BrowsePackageWidget
from rezgui.objects.App import app


class BrowsePackageDialog(QtGui.QDialog, StoreSizeMixin):
    def __init__(self, context_model, package_text=None, parent=None):
        config_key = "layout/window/browse_package"
        super(BrowsePackageDialog, self).__init__(parent)
        StoreSizeMixin.__init__(self, app.config, config_key)

        self.setWindowTitle("Find Package")
        self.package = None

        self.widget = BrowsePackageWidget(context_model, self)

        self.ok_btn = QtGui.QPushButton("Ok")
        cancel_btn = QtGui.QPushButton("Cancel")
        btn_pane = create_pane([None, cancel_btn, self.ok_btn], True)
        self.ok_btn.setEnabled(False)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.widget)
        layout.addWidget(btn_pane)
        self.setLayout(layout)

        cancel_btn.clicked.connect(self.close)
        self.ok_btn.clicked.connect(self._ok)
        self.widget.packageSelected.connect(self._set_package)

        if package_text:
            self.widget.set_package_text(package_text)

    def _set_package(self):
        package = self.widget.current_package()
        if package is None:
            self.setWindowTitle("Find Package")
            self.ok_btn.setEnabled(False)
        else:
            self.setWindowTitle("Find Package - %s" % package.qualified_name)
            self.ok_btn.setEnabled(True)

    def _ok(self):
        self.package = self.widget.current_package()
        self.close()
