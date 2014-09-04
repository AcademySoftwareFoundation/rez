from rezgui.qt import QtCore, QtGui
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.widgets.VariantSummaryWidget import VariantSummaryWidget
from rezgui.widgets.VariantVersionsWidget import VariantVersionsWidget
from rezgui.widgets.VariantToolsList import VariantToolsList
from rezgui.widgets.VariantDetailsWidget import VariantDetailsWidget


class PackageTabWidget(QtGui.QTabWidget, ContextViewMixin):
    def __init__(self, context_model=None, versions_tab=False, parent=None):
        super(PackageTabWidget, self).__init__(parent)
        ContextViewMixin.__init__(self, context_model)
        self.tools_index = 2 if versions_tab else 1

        self.summary_widget = VariantSummaryWidget()
        self.tools_widget = VariantToolsList(self.context_model)
        self.details_widget = VariantDetailsWidget(self.context_model)
        if versions_tab:
            self.versions_widget = VariantVersionsWidget(self.context_model)
        else:
            self.versions_widget = None

        self.addTab(self.summary_widget, "package summary")
        if self.versions_widget:
            self.addTab(self.versions_widget, "versions")
        self.addTab(self.tools_widget, "tools")
        self.addTab(self.details_widget, "details")
        self.setEnabled(False)

    def set_package(self, package):
        self._set_packagebase(package)

    def set_variant(self, variant):
        self._set_packagebase(variant)

    def _set_packagebase(self, variant):
        self.setEnabled(variant is not None)
        for i in range(self.count()):
            self.widget(i).set_variant(variant)

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
