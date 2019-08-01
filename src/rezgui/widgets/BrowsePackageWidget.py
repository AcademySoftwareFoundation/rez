from Qt import QtCore, QtWidgets
from rezgui.widgets.ConfiguredSplitter import ConfiguredSplitter
from rezgui.widgets.PackageLineEdit import PackageLineEdit
from rezgui.widgets.PackageVersionsTable import PackageVersionsTable
from rezgui.widgets.PackageTabWidget import PackageTabWidget
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.objects.App import app
from rez.vendor.version.requirement import Requirement


class BrowsePackageWidget(QtWidgets.QWidget, ContextViewMixin):
    """A widget for browsing rez packages.
    """
    packageSelected = QtCore.Signal()

    def __init__(self, context_model=None, parent=None, lock_package=False,
                 package_selectable_callback=None):
        super(BrowsePackageWidget, self).__init__(parent)
        ContextViewMixin.__init__(self, context_model)

        self.edit = PackageLineEdit(context_model, family_only=True)
        if lock_package:
            self.edit.hide()

        self.versions_table = PackageVersionsTable(context_model,
                                                   callback=package_selectable_callback)
        self.package_tab = PackageTabWidget(versions_tab=False)

        splitter = ConfiguredSplitter(app.config, "layout/splitter/browse_package")
        splitter.setOrientation(QtCore.Qt.Vertical)
        splitter.addWidget(self.versions_table)
        splitter.addWidget(self.package_tab)
        if not splitter.apply_saved_layout():
            splitter.setStretchFactor(0, 2)
            splitter.setStretchFactor(1, 1)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.edit)
        layout.addWidget(splitter)
        self.setLayout(layout)

        self.edit.focusOutViaKeyPress.connect(self._set_package_name)
        self.versions_table.itemSelectionChanged.connect(self._set_package)

    def set_package_text(self, txt):
        try:
            req = Requirement(str(txt))
            package_name = req.name
            version_range = req.range
        except:
            package_name = str(txt)
            version_range = None

        self.edit.setText(package_name)
        self._set_package_name(package_name)

        if version_range is not None:
            self.versions_table.select_version(version_range)

    def current_package(self):
        return self.versions_table.current_package()

    def _set_package_name(self, package_name):
        self.versions_table.set_package_name(package_name)
        self.versions_table.setFocus()

    def _set_package(self):
        package = self.versions_table.current_package()
        self.package_tab.set_package(package)
        self.packageSelected.emit()


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
