from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane, get_icon_widget
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rez.package_help import PackageHelp
from rez.vendor.version.version import VersionRange
from functools import partial


class HelpEntryWidget(QtGui.QWidget):

    clicked = QtCore.Signal()

    def __init__(self, help_, index, parent=None):
        super(HelpEntryWidget, self).__init__(parent)
        self.help_ = help_
        self.index = index

        icon = get_icon_widget("help")
        label = self.help_.sections[self.index][0]
        label_widget = QtGui.QLabel(label)
        self.setCursor(QtCore.Qt.PointingHandCursor)

        create_pane([icon, label_widget, None], True, compact=True,
                    parent_widget=self)

    def mouseReleaseEvent(self, event):
        super(HelpEntryWidget, self).mouseReleaseEvent(event)
        self.clicked.emit()
        if event.button() == QtCore.Qt.LeftButton:
            self.help_.open(self.index)


class VariantHelpWidget(QtGui.QWidget, ContextViewMixin):
    def __init__(self, context_model=None, parent=None):
        super(VariantHelpWidget, self).__init__(parent)
        ContextViewMixin.__init__(self, context_model)
        self.variant = None
        self.help_1 = None
        self.help_2 = None

        self.table_1 = self._create_table()
        self.table_2 = self._create_table()

        self.tab = QtGui.QTabWidget()
        self.tab.addTab(self.table_1, "latest help")
        self.tab.addTab(self.table_2, "help")

        create_pane([self.tab], False, compact=True, parent_widget=self)

    @property
    def success(self):
        return self.help_1 and self.help_1.success

    def set_variant(self, variant):
        self.table_1.clear()
        self.table_2.clear()
        self.tab.setTabText(0, "latest help")
        self.tab.setTabText(1, "help")

        self.variant = variant
        if self.variant is None:
            self.tab.setTabEnabled(0, False)
            self.tab.setTabEnabled(1, False)
            return

        package_paths = self.context_model.packages_path
        self.help_1 = PackageHelp(variant.name, paths=package_paths)
        self.tab.setTabEnabled(0, self.help_1.success)
        if self.help_1.success:
            self._apply_help(self.help_1, 0)
            label = "latest help (%s)" % self.help_1.package.qualified_name
            self.tab.setTabText(0, label)

        exact_range = VersionRange.from_version(variant.version, "==")
        self.help_2 = PackageHelp(variant.name, exact_range, paths=package_paths)
        self.tab.setTabEnabled(1, self.help_2.success)
        label = None
        if self.help_2.success:
            self._apply_help(self.help_2, 1)
            label = "help for %s"
        elif self.help_1.success:
            label = "no help for %s"
        if label:
            self.tab.setTabText(1, label % self.variant.qualified_package_name)

    def _create_table(self):
        table = QtGui.QTableWidget(0, 1)
        table.setGridStyle(QtCore.Qt.DotLine)
        table.setFocusPolicy(QtCore.Qt.NoFocus)
        table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)

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
