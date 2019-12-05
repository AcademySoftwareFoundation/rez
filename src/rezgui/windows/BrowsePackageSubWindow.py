from Qt import QtCore, QtWidgets
from rezgui.objects.App import app
from rezgui.widgets.BrowsePackagePane import BrowsePackagePane
from rezgui.mixins.StoreSizeMixin import StoreSizeMixin


class BrowsePackageSubWindow(QtWidgets.QMdiSubWindow, StoreSizeMixin):
    def __init__(self, parent=None):
        super(BrowsePackageSubWindow, self).__init__(parent)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        config_key = "layout/window/package_browser"
        StoreSizeMixin.__init__(self, app.config, config_key)
        self.setWindowTitle("Browse Packages")

        widget = BrowsePackagePane()
        self.setWidget(widget)

    def closeEvent(self, event):
        super(BrowsePackageSubWindow, self).closeEvent(event)
        StoreSizeMixin.closeEvent(self, event)


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
