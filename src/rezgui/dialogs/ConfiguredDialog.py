from rezgui.qt import QtCore, QtGui


class ConfiguredDialog(QtGui.QDialog):
    """A QDialog that remembers its dimensions, and position relative to parent.
    """
    def __init__(self, config, config_key, *nargs, **kwargs):
        super(ConfiguredDialog, self).__init__(*nargs, **kwargs)
        self.config = config
        self.config_key = config_key

        parent_window = self.parent_window()
        if parent_window:
            pos_x = self.config.get(self.config_key + "/pos_x", int)
            pos_y = self.config.get(self.config_key + "/pos_y", int)
            if pos_x is not None and pos_y is not None:
                pos = QtCore.QPoint(pos_x, pos_y)
                pos += parent_window.pos()
                self.move(pos)

    def sizeHint(self):
        width = self.config.get(self.config_key + "/width")
        height = self.config.get(self.config_key + "/height")
        return QtCore.QSize(width, height)

    def closeEvent(self, event):
        size = self.size()
        self.config.setValue(self.config_key + "/width", size.width())
        self.config.setValue(self.config_key + "/height", size.height())

        parent_window = self.parent_window()
        if parent_window:
            pos = self.pos() - parent_window.pos()
            self.config.setValue(self.config_key + "/pos_x", pos.x())
            self.config.setValue(self.config_key + "/pos_y", pos.y())

        event.accept()

    def parent_window(self):
        parent = self.parentWidget()
        if parent:
            return parent.window()
        return None
