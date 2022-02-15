# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from Qt import QtCore, QtWidgets
from rezgui.models.ContextModel import ContextModel
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rez.utils.formatting import readable_time_duration
import time


class ContextResolveTimeLabel(QtWidgets.QLabel, ContextViewMixin):
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
