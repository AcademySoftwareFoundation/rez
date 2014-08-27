from rezgui.qt import QtCore, QtGui
from rezgui.util import get_timestamp_str
from rez.packages import iter_packages
from rez.exceptions import RezError


class PackageVersionsTable(QtGui.QTableWidget):
    def __init__(self, settings, parent=None):
        super(PackageVersionsTable, self).__init__(0, 2, parent)
        self.settings = settings
        self.package_name = None
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
        if package_name == self.package_name:
            return

        package_paths = self.settings.get("packages_path")
        self.packages = {}
        rows = []

        busy_cursor = QtGui.QCursor(QtCore.Qt.WaitCursor)
        QtGui.QApplication.setOverrideCursor(busy_cursor)
        try:
            packages = list(iter_packages(name=package_name,
                            paths=package_paths))
        except RezError:
            packages = []

        if not packages:
            self.clear()
            self.setEnabled(False)
            self.package_name = None
            QtGui.QApplication.restoreOverrideCursor()
            return

        for i, package in enumerate(sorted(packages, key=lambda x: x.version,
                                           reverse=True)):
            version_str = str(package.version) + ' '
            path_str = package.path
            release_str = get_timestamp_str(package.timestamp) \
                if package.timestamp else '-'
            rows.append((version_str, path_str, release_str))
            self.packages[i] = package

        QtGui.QApplication.restoreOverrideCursor()

        self.setRowCount(len(rows))
        for i, row in enumerate(rows):
            item = QtGui.QTableWidgetItem(row[0])
            item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.setVerticalHeaderItem(i, item)

            for j in range(len(row) - 1):
                item = QtGui.QTableWidgetItem(row[j + 1])
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

        self.clearSelection()  # ensure an itemSelectionChanged signal
        self.selectRow(0)
