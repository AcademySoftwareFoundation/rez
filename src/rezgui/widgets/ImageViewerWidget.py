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


from Qt import QtCore, QtWidgets, QtGui
from rezgui.util import create_pane


class GraphicsView(QtWidgets.QGraphicsView):
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


class ImageViewerWidget(QtWidgets.QWidget):
    def __init__(self, image_file, parent=None):
        super(ImageViewerWidget, self).__init__(parent)
        self.fit = False
        self.prev_scale = 1.0

        self.scene = QtWidgets.QGraphicsScene()
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
