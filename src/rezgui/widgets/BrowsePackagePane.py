from rezgui.qt import QtGui
from rezgui.widgets.BrowsePackageWidget import BrowsePackageWidget
from rezgui.widgets.ContextSettingsWidget import ContextSettingsWidget
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.util import get_icon


class BrowsePackagePane(QtGui.QTabWidget, ContextViewMixin):
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
