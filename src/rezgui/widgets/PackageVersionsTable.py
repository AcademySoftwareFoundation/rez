from rezgui.qt import QtCore, QtGui
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.models.ContextModel import ContextModel
from rezgui.util import get_timestamp_str
from rez.packages_ import iter_packages
from rez.exceptions import RezError


class PackageVersionsTable(QtGui.QTableWidget, ContextViewMixin):
    def __init__(self, context_model=None, parent=None, callback=None):
        """
        Args:
            callback (callable): If supplied, this will be called and passed
            a `Package` for each package in the versions list. If the callable
            returns False, that package will be disabled for selection.
        """
        super(PackageVersionsTable, self).__init__(0, 2, parent)
        ContextViewMixin.__init__(self, context_model)

        self.package_name = None
        self.callback = callback
        self.packages = {}

        self.setGridStyle(QtCore.Qt.DotLine)
        self.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.setVerticalScrollMode(QtGui.QAbstractItemView.ScrollPerPixel)

        hh = self.horizontalHeader()
        hh.setStretchLastSection(True)
        vh = self.verticalHeader()
        vh.setResizeMode(QtGui.QHeaderView.ResizeToContents)
        self.clear()

    def clear(self):
        super(PackageVersionsTable, self).clear()
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setVisible(False)

    def refresh(self):
        self.set_package_name(self.package_name)

    def current_package(self):
        return self.packages.get(self.currentRow())

    def select_version(self, version_range):
        """Select the latest versioned package in the given range.

        If there are no packages in the range, the selection is cleared.
        """
        row = -1
        version = None
        for i, package in self.packages.iteritems():
            if package.version in version_range \
                    and (version is None or version < package.version):
                version = package.version
                row = i

        self.clearSelection()
        if row != -1:
            self.selectRow(row)
        return version

    def set_package_name(self, package_name):
        package_paths = self.context_model.packages_path
        self.packages = {}
        self.clear()
        rows = []

        busy_cursor = QtGui.QCursor(QtCore.Qt.WaitCursor)
        QtGui.QApplication.setOverrideCursor(busy_cursor)
        try:
            packages = list(iter_packages(name=str(package_name),
                            paths=package_paths))
        except RezError:
            packages = []

        if not packages:
            self.setEnabled(False)
            self.package_name = None
            QtGui.QApplication.restoreOverrideCursor()
            return

        for i, package in enumerate(sorted(packages, key=lambda x: x.version,
                                           reverse=True)):
            version_str = str(package.version) + ' '
            path_str = package.uri + "  "
            release_str = get_timestamp_str(package.timestamp) \
                if package.timestamp else '-'
            enabled = self.callback(package) if self.callback else True
            rows.append((enabled, version_str, path_str, release_str))
            self.packages[i] = package

        QtGui.QApplication.restoreOverrideCursor()
        self.setRowCount(len(rows))
        first_selectable_row = -1

        for i, row in enumerate(rows):
            enabled, version_str = row[:2]
            row = row[2:]
            item = QtGui.QTableWidgetItem(version_str)
            item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.setVerticalHeaderItem(i, item)

            for j in range(len(row)):
                item = QtGui.QTableWidgetItem(row[j])
                if enabled:
                    if first_selectable_row == -1:
                        first_selectable_row = i
                else:
                    item.setFlags(QtCore.Qt.NoItemFlags)
                self.setItem(i, j, item)

        self.setHorizontalHeaderLabels(["path", "released"])
        self.resizeRowsToContents()
        self.resizeColumnsToContents()
        vh = self.verticalHeader()
        vh.setVisible(True)
        hh = self.horizontalHeader()
        hh.setStretchLastSection(True)
        hh.setVisible(True)

        self.package_name = package_name
        self.setEnabled(True)

        if first_selectable_row != -1:
            self.selectRow(first_selectable_row)

    def _contextChanged(self, flags=0):
        if flags & ContextModel.PACKAGES_PATH_CHANGED:
            self.refresh()


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
