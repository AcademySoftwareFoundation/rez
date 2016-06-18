from rezgui.qt import QtGui
from rezgui.mixins.StoreSizeMixin import StoreSizeMixin
from rezgui.widgets.ImageViewerWidget import ImageViewerWidget
from rezgui.util import create_pane
from rezgui.objects.App import app


class ImageViewerDialog(QtGui.QDialog, StoreSizeMixin):
    def __init__(self, image_file, parent=None):
        config_key = "layout/window/resolve_graph"
        super(ImageViewerDialog, self).__init__(parent)
        StoreSizeMixin.__init__(self, app.config, config_key)
        self.setWindowTitle("Resolve Graph")

        self.image_viewer = ImageViewerWidget(image_file)
        close_btn = QtGui.QPushButton("Close")
        fit_checkbox = QtGui.QCheckBox("Fit to window")

        btn_pane = create_pane([None, fit_checkbox, 10, close_btn], True)
        create_pane([(self.image_viewer, 1), btn_pane], False, parent_widget=self)

        close_btn.clicked.connect(self.close)
        fit_checkbox.stateChanged.connect(self.image_viewer.fit_to_window)
        app.config.attach(fit_checkbox, "resolve/fit_graph")


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
