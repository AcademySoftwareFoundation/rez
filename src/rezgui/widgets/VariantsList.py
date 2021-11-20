# Copyright Contributors to the Rez project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


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
