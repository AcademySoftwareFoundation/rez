# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from Qt import QtCompat, QtCore, QtWidgets, QtGui
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rez.package_filter import PackageFilterList
from rezgui.util import get_timestamp_str, update_font, get_icon_widget, create_pane
from rez.packages import iter_packages
from rez.vendor.version.version import VersionRange


class VariantVersionsTable(QtWidgets.QTableWidget, ContextViewMixin):
    def __init__(self, context_model=None, reference_variant=None, parent=None):
        super(VariantVersionsTable, self).__init__(0, 2, parent)
        ContextViewMixin.__init__(self, context_model)

        self.variant = None
        self.reference_variant = reference_variant
        self.allow_selection = False
        self.num_versions = -1
        self.version_index = -1
        self.reference_version_index = -1

        self.setWordWrap(False)
        self.setGridStyle(QtCore.Qt.DotLine)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)

        hh = self.horizontalHeader()
        hh.setVisible(False)
        vh = self.verticalHeader()
        QtCompat.QHeaderView.setSectionResizeMode(
            vh, QtWidgets.QHeaderView.ResizeToContents)

        self.clear()

    def selectionCommand(self, index, event=None):
        return QtCore.QItemSelectionModel.ClearAndSelect if self.allow_selection \
            else QtCore.QItemSelectionModel.NoUpdate

    def clear(self):
        super(VariantVersionsTable, self).clear()
        self.version_index = -1
        self.setRowCount(0)
        vh = self.verticalHeader()
        vh.setVisible(False)
        hh = self.horizontalHeader()
        hh.setVisible(False)
        self.variant = None

    def get_reference_difference(self):
        if self.version_index == -1 or self.reference_version_index == -1:
            return None
        return (self.reference_version_index - self.version_index)

    def refresh(self):
        variant = self.variant
        self.variant = None
        self.set_variant(variant)

    def set_variant(self, variant):
        self._set_variant(variant)

    def _set_variant(self, variant, preloaded_packages=None):
        self.clear()

        hh = self.horizontalHeader()
        self.setHorizontalHeaderLabels(["path", "released"])
        QtCompat.QHeaderView.setSectionResizeMode(
            hh, 0, QtWidgets.QHeaderView.Interactive)
        hh.setStretchLastSection(True)
        hh.setVisible(True)

        package_paths = self.context_model.packages_path
        package_filter = PackageFilterList.from_pod(self.context_model.package_filter)

        if variant and variant.wrapped.location in package_paths:
            self.version_index = -1
            self.reference_version_index = -1
            reference_version = None
            range_ = None

            if self.reference_variant and self.reference_variant.name == variant.name:
                reference_version = self.reference_variant.version
                versions = sorted([reference_version, variant.version])
                range_ = VersionRange.as_span(*versions)

            timestamp = self.context().timestamp

            if preloaded_packages is not None:
                if range_ is None:
                    packages = preloaded_packages
                else:
                    packages = [x for x in preloaded_packages if x.version in range_]
            else:
                it = iter_packages(name=variant.name, paths=package_paths, range_=range_)
                packages = sorted(it, key=lambda x: x.version, reverse=True)

            self.setRowCount(len(packages))
            brush = self.palette().brush(QtGui.QPalette.Active, QtGui.QPalette.Base)

            for row, package in enumerate(packages):
                version_str = str(package.version) + ' '
                item = QtWidgets.QTableWidgetItem(version_str)
                item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self.setVerticalHeaderItem(row, item)

                if package.version == variant.version:
                    self.version_index = row
                    update_font(item, bold=True)

                if reference_version is not None \
                        and package.version == reference_version:
                    self.reference_version_index = row
                    update_font(item, bold=True, italic=True)

                def _item():
                    item_ = QtWidgets.QTableWidgetItem()
                    item_.setBackground(brush)  # get rid of mouse-hover coloring
                    return item_

                if package.timestamp:
                    release_str = get_timestamp_str(package.timestamp)
                    in_future = (package.timestamp > timestamp)
                else:
                    release_str = '-'
                    in_future = False

                item = _item()
                txt = package.uri + "  "

                icons = []
                if in_future:
                    icon = get_icon_widget(
                        "clock_warning", "package did not exist at time of resolve")
                    icons.append(icon)

                rule = package_filter.excludes(package)
                if rule:
                    icon = get_icon_widget(
                        "excluded", "package was excluded by rule %s" % str(rule))
                    icons.append(icon)

                if icons:
                    label = QtWidgets.QLabel(txt)
                    pane = create_pane(icons + [label, None], True, compact=True)
                    self.setCellWidget(row, 0, pane)
                else:
                    item.setText(txt)

                self.setItem(row, 0, item)

                item = _item()
                item.setText(release_str)
                self.setItem(row, 1, item)

            vh = self.verticalHeader()
            vh.setVisible(True)
            self.resizeColumnsToContents()
            hh.setStretchLastSection(True)
            self.update()

            self.allow_selection = True
            self.selectRow(self.version_index)
            self.allow_selection = False

        self.variant = variant
