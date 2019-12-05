from __future__ import print_function

from Qt import QtCore, QtWidgets
from rezgui.util import create_pane
from rezgui.mixins.StoreSizeMixin import StoreSizeMixin
from rezgui.widgets.StreamableTextEdit import StreamableTextEdit
from rezgui.objects.App import app
from threading import Thread, Lock


class ProcessDialog(QtWidgets.QDialog, StoreSizeMixin):
    """A dialog that monitors a process and captures its output.

    Note that in order to capture the process's output, you need to have piped
    its stdout and stderr to subprocess.PIPE.
    """
    def __init__(self, process, command_string, parent=None):
        config_key = "layout/window/process"
        super(ProcessDialog, self).__init__(parent)
        StoreSizeMixin.__init__(self, app.config, config_key)
        self.setWindowTitle("Running: %s" % command_string)

        self.proc = process
        self.ended = False
        self.output_ended = False
        self.capture_output = True
        self.buffer = []

        self.bar = QtWidgets.QProgressBar()
        self.bar.setRange(0, 0)
        self.edit = StreamableTextEdit()
        close_btn = QtWidgets.QPushButton("Close")
        btn_pane = create_pane([None, close_btn], True)
        create_pane([self.bar, self.edit, btn_pane], False, parent_widget=self)

        self.lock = Lock()
        self.stdout_thread = Thread(target=self._read_output, args=(self.proc.stdout,))
        self.stderr_thread = Thread(target=self._read_output, args=(self.proc.stderr,))

        self.timer = QtCore.QTimer()
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._update)
        self.timer.start()

        self.stdout_thread.start()
        self.stderr_thread.start()

        close_btn.clicked.connect(self.close)

    def closeEvent(self, event):
        self.capture_output = False

    def _read_output(self, buf):
        for line in buf:
            try:
                self.lock.acquire()
                self.buffer.append(line)
            finally:
                self.lock.release()
            if not self.capture_output:
                break

    def _update(self):
        if not self.output_ended \
                and not self.stdout_thread.is_alive() \
                and not self.stderr_thread.is_alive() \
                and self.proc.poll() is not None:
            self.output_ended = True
            self.buffer.append("\nProcess ended with returncode %d\n"
                               % self.proc.returncode)

        if self.buffer:
            try:
                self.lock.acquire()
                buf = self.buffer
                self.buffer = []
            finally:
                self.lock.release()

            txt = ''.join(buf)
            print(txt, file=self.edit)

        if not self.ended and self.proc.poll() is not None:
            self.bar.setMaximum(10)
            self.bar.setValue(10)
            self.ended = True

        if self.ended and self.output_ended:
            self.timer.stop()


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
