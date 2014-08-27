from rezgui.qt import QtCore, QtGui
from rezgui.widgets.ConfiguredSplitter import ConfiguredSplitter
from rezgui.widgets.PackageLineEdit import PackageLineEdit
from rezgui.widgets.PackageVersionsTable import PackageVersionsTable
from rezgui.widgets.PackageTabWidget import PackageTabWidget
from rezgui.objects.App import app


class BrowsePackageWidget(QtGui.QWidget):

    packageSelected = QtCore.Signal()

    def __init__(self, settings, parent=None):
        super(BrowsePackageWidget, self).__init__(parent)
        self.settings = settings

        self.edit = PackageLineEdit(self.settings, family_only=True)
        self.versions_table = PackageVersionsTable(settings)
        self.package_tab = PackageTabWidget(settings=self.settings,
                                            versions_tab=False)

        splitter = ConfiguredSplitter(app.config, "layout/splitter/browse_package")
        splitter.setOrientation(QtCore.Qt.Vertical)
        splitter.addWidget(self.versions_table)
        splitter.addWidget(self.package_tab)
        if not splitter.apply_saved_layout():
            splitter.setStretchFactor(0, 2)
            splitter.setStretchFactor(1, 1)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.edit)
        layout.addWidget(splitter)
        self.setLayout(layout)

        self.edit.focusOutViaKeyPress.connect(self._set_package_name)
        self.versions_table.itemSelectionChanged.connect(self._set_package)

    def current_package(self):
        return self.versions_table.current_package()

    def _set_package_name(self, package_name):
        self.versions_table.set_package_name(package_name)
        self.versions_table.setFocus()

    def _set_package(self):
        package = self.versions_table.current_package()
        self.package_tab.set_package(package)
        self.packageSelected.emit()
