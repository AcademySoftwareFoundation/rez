from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane


class GraphicsView(QtGui.QGraphicsView):
    def __init__(self, parent=None):
        super(GraphicsView, self).__init__(parent)
        self.interactive = True
        self.press_pos = None
        self.press_transform = None

    def mousePressEvent(self, event):
        if self.interactive:
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            self.press_pos = QtGui.QCursor.pos()
            self.press_transform = self.transform()

    def mouseReleaseEvent(self, event):
        if self.interactive:
            self.unsetCursor()

    def mouseMoveEvent(self, event):
        if self.interactive:
            pos = QtGui.QCursor.pos()
            diff = pos - self.press_pos
            transform = QtGui.QTransform(self.press_transform)
            scale = transform.m11()
            diff *= 1
            transform.translate(diff.x(), diff.y())
            self.setTransform(transform)
            print transform.m31(), transform.m32()

    def viewportEvent(self, event):
        print ">>>", self.transform().m31(), self.transform().m32()
        return super(GraphicsView, self).viewportEvent(event)


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
            current_scale = self.view.transform().m11()

            if enabled:
                self.prev_scale = current_scale
                self._fit_in_view()
            else:
                factor = self.prev_scale / current_scale
                self.view.scale(factor, factor)

    def _fit_in_view(self):
        if self.fit:
            self.view.fitInView(self.image_item, QtCore.Qt.KeepAspectRatio)
