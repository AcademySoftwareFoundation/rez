from Qt import QtCompat, QtCore, QtWidgets
from rez.packages import Package


class VariantsList(QtWidgets.QTableWidget):
    def __init__(self, parent=None):
        super(VariantsList, self).__init__(0, 1, parent)

        self.variant = None
        self.package = None
        self.allow_selection = False

        self.setGridStyle(QtCore.Qt.DotLine)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)

        hh = self.horizontalHeader()
        hh.setStretchLastSection(True)
        hh.setVisible(False)
        vh = self.verticalHeader()
        QtCompat.QHeaderView.setSectionResizeMode(
            vh, QtWidgets.QHeaderView.ResizeToContents)
        vh.setVisible(False)

    def set_package(self, package):
        self.clear()
        if package is not None:
            self.setRowCount(package.num_variants)
            for i, variant_ in enumerate(package.iter_variants()):
                txt = "; ".join(str(x) for x in variant_.requires)
                item = QtWidgets.QTableWidgetItem(txt)
                self.setItem(i, 0, item)

        self.package = package
        self.variant = None

    def set_variant(self, variant):
        self.clear()
        if variant is not None:
            if isinstance(variant, Package):
                self.set_package(variant)
                return

            self.set_package(variant.parent)
            if variant.index is not None:
                self.allow_selection = True
                self.selectRow(variant.index)
                self.allow_selection = False

        self.variant = variant

    def selectionCommand(self, index, event=None):
        return QtCore.QItemSelectionModel.ClearAndSelect if self.allow_selection \
            else QtCore.QItemSelectionModel.NoUpdate


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
