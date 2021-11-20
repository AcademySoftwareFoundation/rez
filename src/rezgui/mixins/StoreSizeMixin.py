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
