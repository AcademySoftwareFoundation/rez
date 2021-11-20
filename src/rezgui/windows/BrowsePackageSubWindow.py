# Copyright Contributors to the Rez project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


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
