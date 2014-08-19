from rezgui.qt import QtCore, QtGui
from rezgui.widgets.StreamableTextEdit import StreamableTextEdit
from rezgui.util import create_pane
from rez.util import readable_time_duration
import time


class VariantSummaryWidget(QtGui.QWidget):
    def __init__(self, parent=None):
        super(VariantSummaryWidget, self).__init__(parent)
        self.variant = None

        self.label = QtGui.QLabel()

        self.table = QtGui.QTableWidget(0, 1)
        self.table.setGridStyle(QtCore.Qt.DotLine)
        self.table.setFocusPolicy(QtCore.Qt.NoFocus)
        self.table.setSelectionMode(QtGui.QAbstractItemView.NoSelection)
        self.table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        hh = self.table.horizontalHeader()
        hh.setStretchLastSection(True)
        hh.setVisible(False)
        vh = self.table.verticalHeader()
        vh.setResizeMode(QtGui.QHeaderView.Fixed)
        vh.setDefaultSectionSize(3 * self.table.fontMetrics().height() / 2)

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
            self.label.setText(str(variant))
            self.table.clear()
            rows = []

            if variant.timestamp:
                now = int(time.time())
                release_time = time.localtime(variant.timestamp)
                release_time_str = time.strftime('%m %b %Y %H:%M', release_time)
                ago = readable_time_duration(now - variant.timestamp)
                rows.append(("released: ", "%s (%s ago)" % (release_time_str, ago)))
            if variant.description:
                rows.append(("description: ", variant.description))
            if variant.authors:
                txt = "; ".join(variant.authors)
                rows.append(("authors: ", txt))
            if variant.requires:
                txt = "; ".join(str(x) for x in variant.requires)
                rows.append(("requires: ", txt))

            self.table.setRowCount(len(rows))
            for i, row in enumerate(rows):
                item = QtGui.QTableWidgetItem(row[0])
                item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                self.table.setVerticalHeaderItem(i, item)
                item = QtGui.QTableWidgetItem(row[1])
                self.table.setItem(i, 0, item)

            vh = self.table.verticalHeader()
            vh.setVisible(True)
            self.table.resizeRowsToContents()

        self.variant = variant
