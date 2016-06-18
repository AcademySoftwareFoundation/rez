from rezgui.qt import QtCore, QtGui
from rezgui.util import get_icon


class IconButton(QtGui.QLabel):

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
