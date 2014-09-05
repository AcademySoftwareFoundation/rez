from rezgui.qt import QtCore, QtGui
from rezgui.util import get_icon


class IconButton(QtGui.QLabel):

    clicked = QtCore.Signal(int)

    def __init__(self, icon_name, parent=None):
        super(IconButton, self).__init__(parent)
        icon = get_icon(icon_name)
        self.setPixmap(icon)
        self.setCursor(QtCore.Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        self.clicked.emit(event.button())
