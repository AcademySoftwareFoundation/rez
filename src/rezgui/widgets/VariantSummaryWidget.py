from rezgui.qt import QtCore, QtGui
from rezgui.widgets.StreamableTextEdit import StreamableTextEdit
from rezgui.util import create_pane, get_timestamp_str
from rez.packages import Package, Variant
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

        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.table)
        self.setLayout(layout)

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
                label = str(variant)
            else:
                label = "%s@%s" % (variant.qualified_package_name, variant.search_path)
            self.label.setText(label)
            self.table.clear()
            rows = []

            if variant.description:
                rows.append(("description: ", variant.description))
            if variant.path:
                rows.append(("location: ", variant.path))
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
                    var_reqs = variant.variant_requires()
                    if var_reqs:
                        index = find_last_sublist(variant.requires, var_reqs)
                        if index is not None:
                            var_strs[index] = "[%s" % var_strs[index]
                            index2 = index + len(var_reqs) - 1
                            var_strs[index2] = "%s]" % var_strs[index2]
                txt = "; ".join(var_strs)
                rows.append(("requires: ", txt))

            # if a package, show changelog.
            if isinstance(variant, Package) and variant.changelog:
                rows.append(("changelog: ", variant.changelog))

            self.table.setRowCount(len(rows))
            for i, row in enumerate(rows):
                label, value = row
                item = QtGui.QTableWidgetItem(label)
                item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self.table.setVerticalHeaderItem(i, item)
                item = QtGui.QTableWidgetItem(value)
                self.table.setItem(i, 0, item)

            vh = self.table.verticalHeader()
            vh.setVisible(True)
            self.table.resizeRowsToContents()

        self.variant = variant
