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
from rezgui.util import get_icon


class IconButton(QtWidgets.QLabel):

    clicked = QtCore.Signal(int)

    def __init__(self, icon_name, tooltip=None, parent=None):
        super(IconButton, self).__init__(parent)
        icon = get_icon(icon_name)
        self.setPixmap(icon)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)

    def mousePressEvent(self, event):
        self.clicked.emit(event.button())
