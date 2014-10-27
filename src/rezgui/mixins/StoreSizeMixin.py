from rezgui.qt import QtCore, QtGui


class StoreSizeMixin(object):
    """A mixing for persisting a top-level widget's dimensions.
    """
    def __init__(self, config, config_key):
        assert isinstance(self, QtGui.QWidget)
        self.config = config
        self.config_key = config_key

    def sizeHint(self):
        width = self.config.get(self.config_key + "/width")
        height = self.config.get(self.config_key + "/height")
        return QtCore.QSize(width, height)

    def closeEvent(self, event):
        size = self.size()
        self.config.setValue(self.config_key + "/width", size.width())
        self.config.setValue(self.config_key + "/height", size.height())
        self.config.sync()
