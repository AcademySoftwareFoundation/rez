from rezgui.qt import QtCore, QtGui
from rezgui.dialogs.ConfiguredDialog import ConfiguredDialog
from rezgui.widgets.PackageLineEdit import PackageLineEdit
from rezgui.widgets.PackageVersionsTable import PackageVersionsTable
from rezgui.objects.App import app
from rez.packages import iter_packages


class BrowsePackageDialog(ConfiguredDialog):
    def __init__(self, settings, parent=None):
        super(BrowsePackageDialog, self).__init__(app.config,
                                                  "layout/window/browse_package",
                                                  parent)
        self.setWindowTitle("Find Package")
        self.settings = settings

        self.edit = PackageLineEdit(self.settings, family_only=True)

        self.versions_table = PackageVersionsTable(settings)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.edit)
        layout.addWidget(self.versions_table)
        self.setLayout(layout)

        self.edit.focusOutViaKeyPress.connect(self._set_package_name)

    def _set_package_name(self, package_name):
        self.versions_table.set_package_name(package_name)
        self.versions_table.setFocus()
