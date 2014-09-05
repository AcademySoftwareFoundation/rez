from rezgui.qt import QtCore, QtGui
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.util import get_timestamp_str, update_font
from rez.packages import iter_packages


class VariantVersionsTable(QtGui.QTableWidget, ContextViewMixin):
    def __init__(self, context_model=None, parent=None):
        super(VariantVersionsTable, self).__init__(0, 1, parent)
        ContextViewMixin.__init__(self, context_model)

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
        hh.setVisible(False)
        vh = self.verticalHeader()
        vh.setResizeMode(QtGui.QHeaderView.ResizeToContents)

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
        hh = self.horizontalHeader()
        hh.setVisible(False)

    def refresh(self):
        variant = self.variant
        self.variant = None
        self.set_variant(variant)

    def set_variant(self, variant):
        if variant == self.variant:
            return

        self.clear()

        hh = self.horizontalHeader()
        if self.view_changelog:
            self.setColumnCount(1)
            hh.setResizeMode(0, QtGui.QHeaderView.Stretch)
            hh.setVisible(False)
        else:
            self.setColumnCount(2)
            self.setHorizontalHeaderLabels(["path", "released"])
            hh.setResizeMode(0, QtGui.QHeaderView.Interactive)
            hh.setVisible(True)

        package_paths = self.context_model.packages_path

        if variant and variant.search_path in package_paths:
            rows = []
            self.num_versions = 0
            self.version_index = -1
            row_index = -1
            it = iter_packages(name=variant.name, paths=package_paths)

            for i, package in enumerate(sorted(it, key=lambda x: x.version,
                                               reverse=True)):
                self.num_versions += 1
                if package.version == variant.version:
                    self.version_index = i
                    row_index = len(rows)
                version_str = str(package.version) + ' '
                path_str = package.path
                release_str = get_timestamp_str(package.timestamp) \
                    if package.timestamp else '-'

                if self.view_changelog:
                    if package.timestamp:
                        path_str += " - %s" % release_str
                    if package.changelog:
                        changelog = package.changelog.rstrip() + '\n'
                    else:
                        changelog = "-"

                    rows.append((version_str, path_str))
                    rows.append(("", changelog))
                else:
                    rows.append((version_str, path_str, release_str))

            self.setRowCount(len(rows))
            for i, row in enumerate(rows):
                item = QtGui.QTableWidgetItem(row[0])
                item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self.setVerticalHeaderItem(i, item)
                if i == row_index:
                    update_font(item, bold=True)

                for j in range(len(row) - 1):
                    item = QtGui.QTableWidgetItem(row[j + 1])
                    if self.view_changelog and not (i % 2):
                        brush = QtGui.QPalette().brush(QtGui.QPalette.Active,
                                                       QtGui.QPalette.Button)
                        item.setBackground(brush)
                        brush = QtGui.QPalette().brush(QtGui.QPalette.Active,
                                                       QtGui.QPalette.ButtonText)
                        item.setForeground(brush)
                        update_font(item, bold=True)
                    else:
                        # gets rid of mouse-hover row highlighting
                        brush = QtGui.QPalette().brush(QtGui.QPalette.Active,
                                                       QtGui.QPalette.Base)
                        item.setBackground(brush)

                    self.setItem(i, j, item)

            vh = self.verticalHeader()
            vh.setVisible(True)
            self.resizeRowsToContents()
            self.resizeColumnsToContents()
            hh.setStretchLastSection(True)

            self.allow_selection = True
            self.selectRow(row_index)
            self.allow_selection = False

        self.variant = variant
