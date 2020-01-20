from Qt import QtWidgets
from rezgui.util import get_icon
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.widgets.VariantHelpWidget import VariantHelpWidget
from rezgui.widgets.VariantSummaryWidget import VariantSummaryWidget
from rezgui.widgets.VariantVersionsWidget import VariantVersionsWidget
from rezgui.widgets.VariantToolsList import VariantToolsList
from rezgui.widgets.ChangelogEdit import VariantChangelogEdit
from rezgui.widgets.VariantDetailsWidget import VariantDetailsWidget

from rezgui.widgets.VariantsList import VariantsList
from rez.packages import Package, Variant


class PackageTabWidget(QtWidgets.QTabWidget, ContextViewMixin):
    def __init__(self, context_model=None, versions_tab=False, parent=None):
        super(PackageTabWidget, self).__init__(parent)
        ContextViewMixin.__init__(self, context_model)
        self.variant = None
        self.tabs = {}

        self.summary_widget = VariantSummaryWidget()
        self.tools_widget = VariantToolsList(self.context_model)
        self.variants_widget = VariantsList()
        self.changelog_edit = VariantChangelogEdit()
        self.details_widget = VariantDetailsWidget(self.context_model)
        self.help_widget = VariantHelpWidget(self.context_model)

        if versions_tab:
            self.versions_widget = VariantVersionsWidget(self.context_model)
        else:
            self.versions_widget = None

        n = 0
        icon = get_icon("package", as_qicon=True)
        self.addTab(self.summary_widget, icon, "package summary")
        self.tabs["summary"] = dict(index=n, lazy=False)
        n += 1

        if self.versions_widget:
            icon = get_icon("versions", as_qicon=True)
            self.addTab(self.versions_widget, icon, "versions")
            self.tabs["versions"] = dict(index=n, lazy=True)
            n += 1

        icon = get_icon("variant", as_qicon=True)
        self.addTab(self.variants_widget, icon, "variants")
        self.tabs["variants"] = dict(index=n, lazy=False)
        n += 1

        icon = get_icon("tools", as_qicon=True)
        self.addTab(self.tools_widget, icon, "tools")
        self.tabs["tools"] = dict(index=n, lazy=False)
        n += 1

        icon = get_icon("changelog", as_qicon=True)
        self.addTab(self.changelog_edit, icon, "changelog")
        self.tabs["changelog"] = dict(index=n, lazy=True)
        n += 1

        icon = get_icon("help", as_qicon=True)
        self.addTab(self.help_widget, icon, "help")
        self.tabs["help"] = dict(index=n, lazy=True)
        n += 1

        icon = get_icon("info", as_qicon=True)
        self.addTab(self.details_widget, icon, "details")
        self.tabs["info"] = dict(index=n, lazy=False)

        self.currentChanged.connect(self._tabChanged)
        self.setEnabled(False)

    def set_package(self, package):
        self._set_packagebase(package)

    def set_variant(self, variant):
        self._set_packagebase(variant)

    def _set_packagebase(self, variant):
        self.setEnabled(variant is not None)
        self.variant = variant
        is_package = isinstance(variant, Package)
        prev_index = self.currentIndex()
        disabled_tabs = set()

        for d in self.tabs.values():
            index = d["index"]
            if (not d["lazy"]) or (self.currentIndex() == index):
                self.widget(index).set_variant(variant)

        tab_index = self.tabs["variants"]["index"]
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

        tab_index = self.tabs["tools"]["index"]
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

    # some widgets lazily load the variant when tab is selected
    def _tabChanged(self, index):
        widget = self.widget(index)
        if widget.variant != self.variant:
            widget.set_variant(self.variant)


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
