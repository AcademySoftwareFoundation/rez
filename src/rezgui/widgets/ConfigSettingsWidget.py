from rezgui.qt import QtCore, QtGui
from rezgui.widgets.SettingsWidget import SettingsWidget


class ConfigSettingsWidget(SettingsWidget):
    def __init__(self, config, keys, schema=None, parent=None):
        self.config = config
        self.keys = keys

        data = {}
        titles = {}
        for key in keys:
            data[key] = config.get(key)
            title = config.get("%s_title" % key)
            if title:
                titles[key] = title

        super(ConfigSettingsWidget, self).__init__(parent=parent, schema=schema,
                                                   data=data, titles=titles)
