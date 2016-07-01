from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane


class GraphicsView(QtGui.QGraphicsView):
    def __init__(self, parent=None, max_scale=None):
        super(GraphicsView, self).__init__(parent)
        self.interactive = True
        self.press_pos = None
        self.max_scale = max_scale

    def mousePressEvent(self, event):
        if self.interactive:
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            self.press_pos = QtGui.QCursor.pos()
            self.press_scroll_pos = self._scroll_pos()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event):
        if self.interactive:
            self.unsetCursor()
        else:
            event.ignore()

    def mouseMoveEvent(self, event):
        if self.interactive:
            pos = QtGui.QCursor.pos()
            pos_delta = pos - self.press_pos
            scroll_pos = self.press_scroll_pos - pos_delta
            self._set_scroll_pos(scroll_pos)
        else:
            event.ignore()

    def wheelEvent(self, event):
        if self.interactive:
            scale = 1.0 + (event.delta() * 0.001)
            if scale < 1.0:
                rect = self.mapToScene(self.rect()).boundingRect()
                if rect.width() > self.scene().width() \
                        and rect.height() > self.scene().height():
                    # all of image visible in viewport
                    event.ignore()
                    return
            elif self.max_scale and self.transform().m11() > self.max_scale:
                # we're zoomed in really close
                event.ignore()
                return

            self.scale(scale, scale)
        else:
            event.ignore()

    def _scroll_pos(self):
        hs = self.horizontalScrollBar()
        vs = self.verticalScrollBar()
        return QtCore.QPoint(hs.value(), vs.value())

    def _set_scroll_pos(self, pos):
        hs = self.horizontalScrollBar()
        vs = self.verticalScrollBar()
        hs.setValue(pos.x())
        vs.setValue(pos.y())


class ImageViewerWidget(QtGui.QWidget):
    def __init__(self, image_file, parent=None):
        super(ImageViewerWidget, self).__init__(parent)
        self.fit = False
        self.prev_scale = 1.0

        self.scene = QtGui.QGraphicsScene()
        image = QtGui.QPixmap(image_file)
        self.image_item = self.scene.addPixmap(image)
        self.image_item.setTransformationMode(QtCore.Qt.SmoothTransformation)
        npix = max(image.width(), image.height())
        max_scale = npix / 200.0
        self.view = GraphicsView(self.scene, max_scale=max_scale)

        create_pane([self.view], False, parent_widget=self)
        self.view.setRenderHints(QtGui.QPainter.Antialiasing
                                 | QtGui.QPainter.SmoothPixmapTransform)
        self.view.show()
        self._fit_in_view()

    def resizeEvent(self, event):
        if self.fit:
            self._fit_in_view()
        event.accept()

    def fit_to_window(self, enabled):
        if enabled != self.fit:
            self.fit = enabled
            self.view.interactive = not enabled
            current_scale = self.view.transform().m11()

            if self.fit:
                self.prev_scale = current_scale
                self._fit_in_view()
            else:
                factor = self.prev_scale / current_scale
                self.view.scale(factor, factor)

    def _fit_in_view(self):
        self.view.fitInView(self.image_item, QtCore.Qt.KeepAspectRatio)


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
