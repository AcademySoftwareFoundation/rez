from rezgui.qt import QtCore, QtGui


class PackageVersionsList(QtGui.QListWidget):
    def __init__(self, settings=None, parent=None):
        super(PackageVersionsList, self).__init__(parent)
