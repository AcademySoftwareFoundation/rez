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


from Qt import QtCore, QtWidgets
from rezgui.util import create_pane
from rezgui.widgets.IconButton import IconButton
from rezgui.widgets.TimeSelecterPopup import TimeSelecterPopup
from rezgui.dialogs.BrowsePackageDialog import BrowsePackageDialog
import time


class TimestampWidget(QtWidgets.QFrame):

    timeChanged = QtCore.Signal(int)  # epoch time

    def __init__(self, context_model, parent=None):
        super(TimestampWidget, self).__init__(parent)
        self.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Sunken)
        self.context_model = context_model

        self.popup = None
        self.package_btn = IconButton("package", "select package release date")
        self.clock_btn = IconButton("clock", "select time in the past")
        self.checkbox = QtWidgets.QCheckBox("ignore packages released after:")
        pane = create_pane([None,
                           self.checkbox,
                           self.package_btn,
                           self.clock_btn], True, compact=True)

        self.edit = QtWidgets.QDateTimeEdit()
        self.edit.setCalendarPopup(True)
        self.edit.setDateTime(QtCore.QDateTime.currentDateTime())

        create_pane([pane, self.edit], False, compact=True, parent_widget=self)
        self.checkbox.stateChanged.connect(self._stateChanged)
        self.package_btn.clicked.connect(self._selectPackage)
        self.clock_btn.clicked.connect(self._selectTime)

        self.refresh()

    def datetime(self):
        """Returns the selected datetime, or None if not set."""
        if self.checkbox.isChecked():
            return self.edit.dateTime()
        else:
            return None

    def set_time(self, epoch):
        dt = QtCore.QDateTime()
        dt.setTime_t(epoch)
        self.edit.setDateTime(dt)
        self.checkbox.setChecked(True)
        self.timeChanged.emit(epoch)

    def refresh(self):
        b = self.checkbox.isChecked()
        self.package_btn.setEnabled(b)
        self.clock_btn.setEnabled(b)
        self.edit.setEnabled(b)

    def _stateChanged(self, state):
        self.refresh()

    def _selectPackage(self):
        fn = lambda x: bool(x.timestamp)
        dlg = BrowsePackageDialog(context_model=self.context_model,
                                  parent=self.parentWidget(),
                                  package_selectable_callback=fn)
        dlg.exec_()
        if dlg.package:
            self.set_time(dlg.package.timestamp)

    def _selectTime(self):
        self.popup = TimeSelecterPopup(self.clock_btn, parent=self)
        self.popup.secondsClicked.connect(self._secondsClicked)
        self.popup.show()

    def _secondsClicked(self, seconds):
        now = int(time.time())
        self.set_time(now - seconds)
