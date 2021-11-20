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


from Qt import QtWidgets
from rezgui.mixins.StoreSizeMixin import StoreSizeMixin
from rezgui.widgets.ImageViewerWidget import ImageViewerWidget
from rezgui.util import create_pane
from rezgui.objects.App import app


class ImageViewerDialog(QtWidgets.QDialog, StoreSizeMixin):
    def __init__(self, image_file, parent=None):
        config_key = "layout/window/resolve_graph"
        super(ImageViewerDialog, self).__init__(parent)
        StoreSizeMixin.__init__(self, app.config, config_key)
        self.setWindowTitle("Resolve Graph")

        self.image_viewer = ImageViewerWidget(image_file)
        close_btn = QtWidgets.QPushButton("Close")
        fit_checkbox = QtWidgets.QCheckBox("Fit to window")

        btn_pane = create_pane([None, fit_checkbox, 10, close_btn], True)
        create_pane([(self.image_viewer, 1), btn_pane], False, parent_widget=self)

        close_btn.clicked.connect(self.close)
        fit_checkbox.stateChanged.connect(self.image_viewer.fit_to_window)
        app.config.attach(fit_checkbox, "resolve/fit_graph")
