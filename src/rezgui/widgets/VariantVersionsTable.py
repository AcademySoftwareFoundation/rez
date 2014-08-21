from rezgui.qt import QtCore, QtGui
from rez.packages import iter_packages


class VariantVersionsTable(QtGui.QTableWidget):
    def __init__(self, settings, parent=None):
        super(VariantVersionsTable, self).__init__(0, 1, parent)
        self.settings = settings
        self.variant = None
        self.allow_selection = False
        self.num_versions = -1
        self.version_index = -1
        self.view_changelog = False

        self.setGridStyle(QtCore.Qt.DotLine)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.setVerticalScrollMode(QtGui.QAbstractItemView.ScrollPerPixel)

        hh = self.horizontalHeader()
        hh.setStretchLastSection(True)
        hh.setVisible(False)
        vh = self.verticalHeader()
        vh.setResizeMode(QtGui.QHeaderView.Fixed)
        vh.setDefaultSectionSize(3 * self.fontMetrics().height() / 2)

        self.clear()

    def set_view_changelog(self, enable):
        """Enable changelog view.

        Note that you still need to call refresh() after this call, to update
        the view.
        """
        self.view_changelog = enable

    def selectionCommand(self, index, event=None):
        return QtGui.QItemSelectionModel.ClearAndSelect if self.allow_selection \
            else QtGui.QItemSelectionModel.NoUpdate

    def clear(self):
        super(VariantVersionsTable, self).clear()
        self.version_index = -1
        self.setRowCount(0)
        vh = self.verticalHeader()
        vh.setVisible(False)

    def refresh(self):
        variant = self.variant
        self.variant = None
        self.set_variant(variant)

    def set_variant(self, variant):
        if variant == self.variant:
            return

        package_paths = self.settings.get("packages_path")

        if variant is None or variant.search_path not in package_paths:
            self.clear()
        else:
            rows = []
            self.num_versions = 0
            self.version_index = -1
            it = iter_packages(name=variant.name, paths=package_paths)

            for i, package in enumerate(sorted(it, key=lambda x: x.version,
                                               reverse=True)):
                self.num_versions += 1
                if package.version == variant.version:
                    self.version_index = i
                rows.append((str(package.version) + ' ', package.path))
                if self.view_changelog:
                    changelog = package.changelog or "-"
                    rows.append(("", changelog))

            self.setRowCount(len(rows))
            for i, row in enumerate(rows):
                item = QtGui.QTableWidgetItem(row[0])
                item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self.setVerticalHeaderItem(i, item)

                item = QtGui.QTableWidgetItem(row[1])
                if self.view_changelog and not (i % 2):
                    brush = QtGui.QPalette().brush(QtGui.QPalette.Active,
                                                   QtGui.QPalette.Button)
                    item.setBackground(brush)
                    brush = QtGui.QPalette().brush(QtGui.QPalette.Active,
                                                   QtGui.QPalette.ButtonText)
                    item.setForeground(brush)

                    font = item.font()
                    font.setWeight(QtGui.QFont.Bold)
                    item.setFont(font)
                else:
                    # gets rid of passive row highlighting
                    brush = QtGui.QPalette().brush(QtGui.QPalette.Active,
                                                   QtGui.QPalette.Base)
                    item.setBackground(brush)

                self.setItem(i, 0, item)

            vh = self.verticalHeader()
            vh.setVisible(True)
            self.resizeRowsToContents()

            self.allow_selection = True
            index = self.version_index
            if self.view_changelog:
                index *= 2
            self.selectRow(self.version_index)
            self.allow_selection = False

        self.variant = variant
