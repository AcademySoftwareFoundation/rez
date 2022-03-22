# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


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
