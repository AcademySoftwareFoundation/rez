from rezgui.qt import QtCore, QtGui
from rezgui.models.ContextModel import ContextModel
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rez.utils.formatting import readable_time_duration
import time


class ContextResolveTimeLabel(QtGui.QLabel, ContextViewMixin):
    def __init__(self, context_model=None, parent=None):
        super(ContextResolveTimeLabel, self).__init__(parent)
        ContextViewMixin.__init__(self, context_model)

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(60 * 1000)
        self.timer.timeout.connect(self.refresh)
        self.refresh()

    def refresh(self):
        context = self.context()
        if not context:
            self.timer.stop()
            self.setText("")
            return

        minutes = (int(time.time()) - context.created) / 60

        if minutes:
            time_txt = readable_time_duration(minutes * 60)
        else:
            time_txt = "moments"
        self.setText("resolved %s ago" % time_txt)
        self.timer.start()

    def _contextChanged(self, flags=0):
        if flags & ContextModel.CONTEXT_CHANGED:
            self.refresh()


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
