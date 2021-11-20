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
