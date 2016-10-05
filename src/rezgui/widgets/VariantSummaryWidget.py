from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane, get_timestamp_str
from rez.packages_ import Package, Variant
from rez.util import find_last_sublist


class VariantSummaryWidget(QtGui.QWidget):
    def __init__(self, parent=None):
        super(VariantSummaryWidget, self).__init__(parent)
        self.variant = None

        self.label = QtGui.QLabel()

        self.table = QtGui.QTableWidget(0, 1)
        self.table.setGridStyle(QtCore.Qt.DotLine)
        self.table.setFocusPolicy(QtCore.Qt.NoFocus)
        self.table.setSelectionMode(QtGui.QAbstractItemView.NoSelection)
        self.table.setAlternatingRowColors(True)

        hh = self.table.horizontalHeader()
        hh.setStretchLastSection(True)
        hh.setVisible(False)
        vh = self.table.verticalHeader()
        vh.setResizeMode(QtGui.QHeaderView.ResizeToContents)

        create_pane([self.label, self.table], False, compact=True,
                    parent_widget=self)

        self.clear()

    def clear(self):
        self.label.setText("no package selected")
        self.table.clear()
        self.table.setRowCount(0)
        vh = self.table.verticalHeader()
        vh.setVisible(False)
        self.setEnabled(False)

    def set_variant(self, variant):
        if variant == self.variant:
            return

        if variant is None:
            self.clear()
        else:
            self.setEnabled(True)
            if isinstance(variant, Package):
                label_name = variant.qualified_name
                location = variant.uri
            else:
                label_name = variant.qualified_package_name
                location = variant.parent.uri

            label = "%s@%s" % (label_name, variant.wrapped.location)

            self.label.setText(label)
            self.table.clear()
            rows = []

            if variant.description:
                desc = variant.description
                max_chars = 1000
                if len(desc) > max_chars:
                    desc = desc[:max_chars] + "..."
                rows.append(("description: ", desc))
            if variant.uri:
                rows.append(("location: ", location))
            if variant.timestamp:
                release_time_str = get_timestamp_str(variant.timestamp)
                rows.append(("released: ", release_time_str))
            if variant.authors:
                txt = "; ".join(variant.authors)
                rows.append(("authors: ", txt))
            if variant.requires:
                var_strs = [str(x) for x in variant.requires]
                if isinstance(variant, Variant):
                    # put variant-specific requires in square brackets
                    if variant.requires:
                        index = find_last_sublist(variant.requires, variant.requires)
                        if index is not None:
                            var_strs[index] = "[%s" % var_strs[index]
                            index2 = index + len(variant.requires) - 1
                            var_strs[index2] = "%s]" % var_strs[index2]
                txt = "; ".join(var_strs)
                rows.append(("requires: ", txt))

            self.table.setRowCount(len(rows))
            for i, row in enumerate(rows):
                label, value = row
                item = QtGui.QTableWidgetItem(label)
                item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTop)
                self.table.setVerticalHeaderItem(i, item)
                item = QtGui.QTableWidgetItem(value)
                self.table.setItem(i, 0, item)

            vh = self.table.verticalHeader()
            vh.setVisible(True)
            self.table.resizeRowsToContents()

        self.variant = variant


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
