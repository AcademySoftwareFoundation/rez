from rezgui.qt import QtCore, QtGui
from rezgui.util import get_icon
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.widgets.VariantHelpWidget import VariantHelpWidget
from rezgui.widgets.VariantSummaryWidget import VariantSummaryWidget
from rezgui.widgets.VariantVersionsWidget import VariantVersionsWidget
from rezgui.widgets.VariantToolsList import VariantToolsList
from rezgui.widgets.VariantDetailsWidget import VariantDetailsWidget
from rezgui.widgets.VariantsList import VariantsList
from rez.packages import Package, Variant


class PackageTabWidget(QtGui.QTabWidget, ContextViewMixin):
    def __init__(self, context_model=None, versions_tab=False, parent=None):
        super(PackageTabWidget, self).__init__(parent)
        ContextViewMixin.__init__(self, context_model)
        self.tabs = {}

        self.summary_widget = VariantSummaryWidget()
        self.tools_widget = VariantToolsList(self.context_model)
        self.variants_widget = VariantsList()
        self.details_widget = VariantDetailsWidget(self.context_model)
        self.help_widget = VariantHelpWidget(self.context_model)
        if versions_tab:
            self.versions_widget = VariantVersionsWidget(self.context_model)
        else:
            self.versions_widget = None

        n = 0
        icon = get_icon("package", as_qicon=True)
        self.addTab(self.summary_widget, icon, "package summary")
        self.tabs["summary"] = n
        n += 1

        if self.versions_widget:
            icon = get_icon("versions", as_qicon=True)
            self.addTab(self.versions_widget, icon, "versions")
            self.tabs["versions"] = n
            n += 1

        icon = get_icon("variant", as_qicon=True)
        self.addTab(self.variants_widget, icon, "variants")
        self.tabs["variants"] = n
        n += 1

        icon = get_icon("tools", as_qicon=True)
        self.addTab(self.tools_widget, icon, "tools")
        self.tabs["tools"] = n
        n += 1

        icon = get_icon("info", as_qicon=True)
        self.addTab(self.details_widget, icon, "details")
        self.tabs["info"] = n
        n += 1

        #icon = get_icon("help", as_qicon=True)
        #self.addTab(self.help_widget, icon, "help")
        #self.tabs["help"] = n

        self.setEnabled(False)

    def set_package(self, package):
        self._set_packagebase(package)

    def set_variant(self, variant):
        self._set_packagebase(variant)

    def _set_packagebase(self, variant):
        self.setEnabled(variant is not None)
        is_package = isinstance(variant, Package)
        prev_index = self.currentIndex()
        disabled_tabs = set()

        for i in range(self.count()):
            self.widget(i).set_variant(variant)

        tab_index = self.tabs["variants"]
        if (isinstance(variant, Variant) and variant.index is not None) \
                or (is_package and variant.num_variants):
            n = variant.num_variants if is_package else variant.parent.num_variants
            label = "variants (%d)" % n
            self.setTabEnabled(tab_index, True)
        else:
            label = "variants"
            self.setTabEnabled(tab_index, False)
            disabled_tabs.add(tab_index)
        self.setTabText(tab_index, label)

        tab_index = self.tabs["tools"]
        if variant and variant.tools:
            label = "tools (%d)" % len(variant.tools)
            self.setTabEnabled(tab_index, True)
        else:
            label = "tools"
            self.setTabEnabled(tab_index, False)
            disabled_tabs.add(tab_index)
        self.setTabText(tab_index, label)

        """
        tab_index = self.tabs["help"]
        if self.help_widget.success:
            self.setTabEnabled(tab_index, True)
        else:
            self.setTabEnabled(tab_index, False)
            disabled_tabs.add(tab_index)
        """

        if prev_index in disabled_tabs:
            self.setCurrentIndex(0)
