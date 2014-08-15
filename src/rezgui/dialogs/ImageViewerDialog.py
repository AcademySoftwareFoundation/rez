from rezgui.qt import QtCore, QtGui
from rezgui.widgets.ImageViewerWidget import ImageViewerWidget
from rezgui.util import create_pane


class ImageViewerDialog(QtGui.QDialog):
    def __init__(self, image_file, parent=None):
        super(ImageViewerDialog, self).__init__(parent)
        self.setWindowTitle("Resolve Graph")

        self.image_viewer = ImageViewerWidget(image_file)
        ok_btn = QtGui.QPushButton("Ok")
        fit_checkbox = QtGui.QCheckBox("Fit to window")
        btn_pane = create_pane([None, fit_checkbox, 10, ok_btn], True)
        create_pane([(self.image_viewer, 1), btn_pane], False, parent_widget=self)

        ok_btn.clicked.connect(self.close)
        fit_checkbox.stateChanged.connect(self.image_viewer.fit_to_window)
