from rezgui.qt import QtCore, QtGui
from rezgui.widgets.VariantSummaryWidget import VariantSummaryWidget
from rezgui.widgets.VariantVersionsWidget import VariantVersionsWidget
from rezgui.widgets.VariantToolsList import VariantToolsList
from rezgui.widgets.VariantDetailsWidget import VariantDetailsWidget


class PackageTabWidget(QtGui.QTabWidget):
    def __init__(self, settings=None, versions_tab=False, parent=None):
        super(PackageTabWidget, self).__init__(parent)
        self.tools_index = 2 if versions_tab else 1
        self.settings = settings

        self.summary_widget = VariantSummaryWidget()
        self.tools_widget = VariantToolsList()
        self.details_widget = VariantDetailsWidget()
        self.versions_widget = VariantVersionsWidget(self.settings) \
            if versions_tab else None

        self.addTab(self.summary_widget, "package summary")
        if self.versions_widget:
            self.addTab(self.versions_widget, "versions")
        self.addTab(self.tools_widget, "tools")
        self.addTab(self.details_widget, "details")
        self.setEnabled(False)

    def refresh(self):
        self._update_package_tabs("refresh")

    def set_context(self, context):
        self._update_package_tabs("set_context", context)

    def set_package(self, package):
        self._set_packagebase(package)

    def set_variant(self, variant):
        self._set_packagebase(variant)

    def _set_packagebase(self, variant):
        self.setEnabled(variant is not None)
        self._update_package_tabs("set_variant", variant)

        if variant and variant.tools:
            tool_label = "tools (%d)" % len(variant.tools)
            self.setTabEnabled(self.tools_index, True)
        else:
            tool_label = "tools"
            current = (self.currentIndex() == self.tools_index)
            self.setTabEnabled(self.tools_index, False)
            if current:
                self.setCurrentIndex(0)
        self.setTabText(self.tools_index, tool_label)

    def _update_package_tabs(self, attr, *nargs, **kwargs):
        for i in range(self.count()):
            widget = self.widget(i)
            if hasattr(widget, attr):
                getattr(widget, attr)(*nargs, **kwargs)
