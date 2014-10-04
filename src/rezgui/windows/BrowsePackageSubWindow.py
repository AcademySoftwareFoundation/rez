from rezgui.qt import QtCore, QtGui
from rezgui.objects.App import app
from rezgui.widgets.BrowsePackagePane import BrowsePackagePane
from rezgui.mixins.StoreSizeMixin import StoreSizeMixin


class BrowsePackageSubWindow(QtGui.QMdiSubWindow, StoreSizeMixin):
    def __init__(self, parent=None):
        super(BrowsePackageSubWindow, self).__init__(parent)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        config_key = "layout/window/package_browser"
        StoreSizeMixin.__init__(self, app.config, config_key)

        widget = BrowsePackagePane()
        self.setWidget(widget)

    def closeEvent(self, event):
        super(BrowsePackageSubWindow, self).closeEvent(event)
        StoreSizeMixin.closeEvent(self, event)
