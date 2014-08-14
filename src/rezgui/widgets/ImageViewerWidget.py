from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane


class GraphicsView(QtGui.QGraphicsView):
    def __init__(self, parent=None):
        super(GraphicsView, self).__init__(parent)
        self.interactive = True

    def mousePressEvent(self, event):
        if self.interactive:
            self.setCursor(QtCore.Qt.ClosedHandCursor)

    def mouseReleaseEvent(self, event):
        if self.interactive:
            self.unsetCursor()

    def mouseMoveEvent(self, event):
        if self.interactive:
            pos = event.pos()
            print pos.x(), pos.y()


class ImageViewerWidget(QtGui.QWidget):
    def __init__(self, image_file, parent=None):
        super(ImageViewerWidget, self).__init__(parent)
        self.fit = False
        self.prev_scale = 1.0

        self.scene = QtGui.QGraphicsScene()
        image = QtGui.QPixmap(image_file)
        self.image_item = self.scene.addPixmap(image)
        self.image_item.setTransformationMode(QtCore.Qt.SmoothTransformation)
        self.view = GraphicsView(self.scene)

        create_pane([self.view], False, parent_widget=self)
        self.view.setRenderHints(QtGui.QPainter.Antialiasing
                                 | QtGui.QPainter.SmoothPixmapTransform)
        self.view.show()

    def resizeEvent(self, event):
        super(ImageViewerWidget, self).resizeEvent(event)
        self._fit_in_view()

    def fit_to_window(self, enabled):
        if enabled != self.fit:
            self.fit = enabled
            self.view.interactive = not enabled
            current_scale = self._get_scale()

            if enabled:
                self.prev_scale = current_scale
                self._fit_in_view()
            else:
                factor = self.prev_scale / current_scale
                self.view.scale(factor, factor)

    def _fit_in_view(self):
        if self.fit:
            self.view.fitInView(self.image_item, QtCore.Qt.KeepAspectRatio)

    def _get_scale(self):
        return self.view.transform().m11()
