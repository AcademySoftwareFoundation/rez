from rezgui.qt import QtCore, QtGui
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.util import get_timestamp_str, update_font, get_icon_widget, create_pane
from rez.packages import iter_packages
from rez.vendor.version.version import VersionRange


class VariantVersionsTable(QtGui.QTableWidget, ContextViewMixin):
    def __init__(self, context_model=None, reference_variant=None, parent=None):
        super(VariantVersionsTable, self).__init__(0, 1, parent)
        ContextViewMixin.__init__(self, context_model)

        self.variant = None
        self.reference_variant = reference_variant
        self.allow_selection = False
        self.num_versions = -1
        self.version_index = -1
        self.reference_version_index = -1
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

    def get_reference_difference(self):
        if self.version_index == -1 or self.reference_version_index == -1:
            return None
        return (self.reference_version_index - self.version_index)

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
            self.reference_version_index = -1
            row_index = -1
            reference_row_index = -1
            reference_version = None
            range_ = None

            if self.reference_variant and self.reference_variant.name == variant.name:
                reference_version = self.reference_variant.version
                versions = sorted([reference_version, variant.version])
                range_ = VersionRange.as_span(*versions)

            it = iter_packages(name=variant.name, paths=package_paths, range=range_)
            packages = sorted(it, key=lambda x: x.version, reverse=True)
            timestamp = self.context().timestamp

            for i, package in enumerate(packages):
                self.num_versions += 1
                if package.version == variant.version:
                    self.version_index = i
                    row_index = len(rows)

                if reference_version is not None \
                        and package.version == reference_version:
                    self.reference_version_index = i
                    reference_row_index = len(rows)

                version_str = str(package.version) + ' '
                path_str = package.path
                release_str = get_timestamp_str(package.timestamp) \
                    if package.timestamp else '-'

                if self.view_changelog:
                    if package.timestamp:
                        path_str += " - %s" % release_str
                        if package.timestamp > timestamp:
                            path_str = ("clock_warning", path_str)

                    rows.append((version_str, path_str))
                    if reference_version is not None and i == len(packages) - 1:
                        # don't include the last changelog when in reference mode,
                        # we are only interested in what is inbetween the versions.
                        continue

                    if package.changelog:
                        changelog = package.changelog.rstrip() + '\n'
                    else:
                        changelog = "-"
                    rows.append(("", changelog))
                else:
                    if package.timestamp and package.timestamp > timestamp:
                        path_str = ("clock_warning", path_str)
                    rows.append((version_str, path_str, release_str))

            pal = self.palette()
            self.setRowCount(len(rows))

            for i, row in enumerate(rows):
                item = QtGui.QTableWidgetItem(row[0])
                item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self.setVerticalHeaderItem(i, item)
                if i == row_index:
                    update_font(item, bold=True)
                elif i == reference_row_index:
                    update_font(item, bold=True, italic=True)

                for j in range(len(row) - 1):
                    value = row[j + 1]
                    icon_name = None
                    if isinstance(value, tuple):
                        icon_name, value = value

                    item = QtGui.QTableWidgetItem()
                    label = QtGui.QLabel(value)

                    if self.view_changelog and not (i % 2):
                        brush = pal.brush(QtGui.QPalette.Active,
                                          QtGui.QPalette.Button)
                        item.setBackground(brush)
                        update_font(label, bold=True)
                    else:
                        # gets rid of mouse-hover row highlighting
                        brush = pal.brush(QtGui.QPalette.Active,
                                          QtGui.QPalette.Base)
                        item.setBackground(brush)

                    if icon_name:
                        icon = get_icon_widget(
                            icon_name, "package did not exist at time of resolve")
                        widgets = [icon, label, None, 5]
                    else:
                        widgets = [label, None, 5]

                    widget = create_pane(widgets, True, compact=True)
                    self.setItem(i, j, item)
                    self.setCellWidget(i, j, widget)

            vh = self.verticalHeader()
            vh.setVisible(True)
            self.resizeRowsToContents()
            self.resizeColumnsToContents()
            hh.setStretchLastSection(True)

            self.allow_selection = True
            self.selectRow(row_index)
            self.allow_selection = False

        self.variant = variant
