from Qt import QtCore, QtWidgets, QtGui
from rezgui.util import update_font, create_pane
from rez.utils.formatting import readable_time_duration
import math


class Canvas(QtWidgets.QWidget):

    secondsHover = QtCore.Signal(int)
    secondsClicked = QtCore.Signal(int)

    def __init__(self, width, height, parent=None):
        super(Canvas, self).__init__(parent)
        self.setCursor(QtCore.Qt.CrossCursor)
        self.setMouseTracking(True)
        self._width = width
        self._height = height

    def paintEvent(self, event):
        rect = self.rect()
        w = rect.width()
        h = rect.height()
        margin = 5
        j = h / 4

        p = QtGui.QPainter(self)
        update_font(p, italic=True)

        pal = QtGui.QPalette()
        bg_brush = pal.brush(QtGui.QPalette.Active, QtGui.QPalette.Light)
        p.fillRect(rect, bg_brush)

        p.setPen(QtCore.Qt.DotLine)
        p.drawLine(0, j, w, j)
        p.drawLine(0, j * 2, w, j * 2)
        p.drawLine(0, j * 3, w, j * 3)

        p.setPen(pal.color(QtGui.QPalette.Disabled, QtGui.QPalette.WindowText))
        p.drawText(margin, j - margin, "days")
        p.drawText(margin, j * 2 - margin, "hours")
        p.drawText(margin, j * 3 - margin, "minutes")
        p.drawText(margin, j * 4 - margin, "seconds")

    def leaveEvent(self, event):
        self.secondsHover.emit(-1)

    def mousePressEvent(self, event):
        secs = self._get_seconds(event.pos())
        self.secondsClicked.emit(secs)

    def mouseMoveEvent(self, event):
        secs = self._get_seconds(event.pos())
        self.secondsHover.emit(secs)

    def sizeHint(self):
        return QtCore.QSize(self._width, self._height)

    def _get_seconds(self, pos):
        rect = self.rect()
        x_norm = pos.x() / float(rect.width())
        y_norm = min(1.0 - (pos.y() / float(rect.height())), 0.99)
        unit = int(y_norm / 0.25)
        y_norm -= unit * 0.25
        y_norm *= 4.0
        x_norm = max(min(x_norm, 0.99), 0.0)
        y_norm = max(min(y_norm, 0.99), 0.0)

        j = 2.5 * (1.0 - y_norm)
        x_pow = 0.5 + (j * j / 2.5)
        f = math.pow(x_norm, x_pow)

        if unit == 0:  # seconds
            j = int(1.0 + f * 59)
            secs = min(j, 59)
        elif unit == 1:  # minutes
            j = int((1.0 + f * 60) * 60)
            secs = min(j, 3600)
        elif unit == 2:  # hours
            j = int((1.0 + f * 24) * 3600)
            secs = min(j, 3600 * 24)
        else:  # days
            j = int((1.0 + f * 7) * 3600 * 24)
            secs = min(j, 3600 * 24 * 7)
        return secs


class TimeSelecterPopup(QtWidgets.QFrame):

    secondsClicked = QtCore.Signal(int)

    def __init__(self, pivot_widget, width=240, height=160, parent=None):
        super(TimeSelecterPopup, self).__init__(parent)
        self.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Raised)
        self.setWindowFlags(QtCore.Qt.Popup)
        self.seconds = None

        self.label = QtWidgets.QLabel("")

        canvas_frame = QtWidgets.QFrame()
        canvas_frame.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Sunken)
        canvas = Canvas(width, height)
        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(2)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(canvas)
        canvas_frame.setLayout(layout)

        create_pane([self.label, canvas_frame], False, compact=True,
                    parent_widget=self)
        self.adjustSize()

        pt = pivot_widget.rect().topLeft()
        global_pt = pivot_widget.mapToGlobal(pt)
        self.move(global_pt - QtCore.QPoint(0, self.height()))

        canvas.secondsHover.connect(self._secondsHover)
        canvas.secondsClicked.connect(self._secondsClicked)

    def _secondsHover(self, seconds):
        if seconds == -1:
            self.label.setText("")
        else:
            secs_txt = readable_time_duration(seconds)
            self.label.setText("%s ago" % secs_txt)

    def _secondsClicked(self, seconds):
        self.secondsClicked.emit(seconds)
        self.close()


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
