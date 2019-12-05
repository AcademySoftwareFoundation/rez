from Qt import QtCore, QtWidgets
from rezgui.util import create_pane, get_icon_widget
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.widgets.PackageLoadingWidget import PackageLoadingWidget
from rez.vendor.version.version import VersionRange
from rez.package_help import PackageHelp
from functools import partial


class HelpEntryWidget(QtWidgets.QWidget):

    clicked = QtCore.Signal()

    def __init__(self, help_, index, parent=None):
        super(HelpEntryWidget, self).__init__(parent)
        self.help_ = help_
        self.index = index

        icon = get_icon_widget("help")
        label = self.help_.sections[self.index][0]
        label_widget = QtWidgets.QLabel(label)
        self.setCursor(QtCore.Qt.PointingHandCursor)

        create_pane([icon, label_widget, None], True, compact=True,
                    parent_widget=self)

    def mouseReleaseEvent(self, event):
        super(HelpEntryWidget, self).mouseReleaseEvent(event)
        self.clicked.emit()
        if event.button() == QtCore.Qt.LeftButton:
            self.help_.open(self.index)


class VariantHelpWidget(PackageLoadingWidget, ContextViewMixin):
    def __init__(self, context_model=None, parent=None):
        super(VariantHelpWidget, self).__init__(parent)
        ContextViewMixin.__init__(self, context_model)
        self.variant = None
        self.help_1 = None
        self.help_2 = None

        self.table_1 = self._create_table()
        self.table_2 = self._create_table()

        self.tab = QtWidgets.QTabWidget()
        self.tab.addTab(self.table_1, "latest help")
        self.tab.addTab(self.table_2, "help")

        self.no_help_label = QtWidgets.QLabel("No help found.")
        self.no_help_label.setAlignment(QtCore.Qt.AlignCenter)
        pane = create_pane([self.no_help_label, self.tab], False, compact=True)

        self.set_main_widget(pane)
        self.set_loader_swap_delay(300)
        self.clear()

    def clear(self):
        self.no_help_label.hide()
        self.tab.hide()
        self.table_1.setRowCount(0)
        self.table_2.setRowCount(0)
        self.tab.setTabText(0, "latest help")
        self.tab.setTabText(1, "help")
        self.tab.setTabEnabled(0, False)
        self.tab.setTabEnabled(1, False)

    def set_variant(self, variant):
        self.clear()
        self.variant = variant
        if self.variant is None:
            self.tab.setTabEnabled(0, False)
            self.tab.setTabEnabled(1, False)
            return

        package_paths = self.context_model.packages_path
        self.load_packages(package_paths=package_paths,
                           package_name=variant.name,
                           callback=self._load_packages_callback,
                           package_attributes=("help",))

    def set_packages(self, packages):
        package_paths = self.context_model.packages_path

        self.help_1 = PackageHelp(self.variant.name, paths=package_paths)
        self.tab.setTabEnabled(0, self.help_1.success)
        if self.help_1.success:
            self._apply_help(self.help_1, 0)
            label = "latest help (%s)" % self.help_1.package.qualified_name
            self.tab.setTabText(0, label)

        exact_range = VersionRange.from_version(self.variant.version, "==")
        self.help_2 = PackageHelp(self.variant.name, exact_range, paths=package_paths)
        self.tab.setTabEnabled(1, self.help_2.success)
        label = None
        if self.help_2.success:
            self._apply_help(self.help_2, 1)
            label = "help for %s"
        if label:
            self.tab.setTabText(1, label % self.help_2.package.qualified_name)

        if self.help_1.success or self.help_2.success:
            self.tab.show()
        else:
            self.no_help_label.show()

    def _create_table(self):
        table = QtWidgets.QTableWidget(0, 1)
        table.setGridStyle(QtCore.Qt.DotLine)
        table.setFocusPolicy(QtCore.Qt.NoFocus)
        table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        hh = table.horizontalHeader()
        hh.setStretchLastSection(True)
        hh.setVisible(False)
        vh = table.verticalHeader()
        vh.setVisible(False)
        return table

    def _apply_help(self, help_, tab_index):
        table = self.table_2 if tab_index else self.table_1
        table.clear()
        sections = help_.sections
        table.setRowCount(len(sections))

        for row, (label, _) in enumerate(sections):
            widget = HelpEntryWidget(help_, row)
            widget.clicked.connect(partial(self._helpClicked, tab_index))
            table.setCellWidget(row, 0, widget)

    def _helpClicked(self, tab_index):
        table = self.table_2 if tab_index else self.table_1
        table.clearSelection()

    @classmethod
    def _load_packages_callback(cls, package):
        return (not package.help)


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
