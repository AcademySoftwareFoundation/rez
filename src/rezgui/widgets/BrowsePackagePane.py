# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from Qt import QtWidgets
from rezgui.widgets.BrowsePackageWidget import BrowsePackageWidget
from rezgui.widgets.ContextSettingsWidget import ContextSettingsWidget
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.util import get_icon


class BrowsePackagePane(QtWidgets.QTabWidget, ContextViewMixin):
    """A widget for browsing rez packages.

    Unlike `BrowsePackageWidget`, this class has its own settings tab, so that
    packages path can be changed. In contrast, `BrowsePackageWidget` does not,
    because it is intended to allow browsing of packages within an existing
    context.
    """
    def __init__(self, context_model=None, parent=None):
        super(BrowsePackagePane, self).__init__(parent)
        ContextViewMixin.__init__(self, context_model)

        self.browse = BrowsePackageWidget(self.context_model)
        self.settings = ContextSettingsWidget(self.context_model,
                                              attributes=("packages_path",))

        icon = get_icon("package", as_qicon=True)
        self.addTab(self.browse, icon, "packages")
        icon = get_icon("cog", as_qicon=True)
        self.addTab(self.settings, icon, "settings")
