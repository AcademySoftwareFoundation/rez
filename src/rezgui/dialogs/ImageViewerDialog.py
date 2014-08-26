from rezgui.qt import QtCore, QtGui
from rezgui.widgets.ImageViewerWidget import ImageViewerWidget
from rezgui.dialogs.ConfiguredDialog import ConfiguredDialog
from rezgui.util import create_pane
from rezgui.objects.App import app


class ImageViewerDialog(ConfiguredDialog):
    def __init__(self, image_file, parent=None):
        super(ImageViewerDialog, self).__init__(app.config,
                                                "layout/window/resolve_graph",
                                                parent)
        self.setWindowTitle("Resolve Graph")

        self.image_viewer = ImageViewerWidget(image_file)
        close_btn = QtGui.QPushButton("Close")
        fit_checkbox = QtGui.QCheckBox("Fit to window")

        btn_pane = create_pane([None, fit_checkbox, 10, close_btn], True)
        create_pane([(self.image_viewer, 1), btn_pane], False, parent_widget=self)

        close_btn.clicked.connect(self.close)
        fit_checkbox.stateChanged.connect(self.image_viewer.fit_to_window)
        app.config.attach(fit_checkbox, "resolve/fit_graph")
