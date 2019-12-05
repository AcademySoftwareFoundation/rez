from Qt import QtCore, QtWidgets


class StoreSizeMixin(object):
    """A mixing for persisting a top-level widget's dimensions.
    """
    def __init__(self, config, config_key):
        assert isinstance(self, QtWidgets.QWidget)
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
