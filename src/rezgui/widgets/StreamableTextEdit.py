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


from Qt import QtCore, QtGui
from rezgui.widgets.SearchableTextEdit import SearchableTextEdit
import threading


class StreamableTextEdit(SearchableTextEdit):
    """A QTextEdit that also acts like a write-only file object.

    The object is threadsafe and can be written to from any thread.
    """
    written = QtCore.Signal()

    def __init__(self, parent=None):
        super(StreamableTextEdit, self).__init__(parent)
        self.setReadOnly(True)
        self.buffer = []
        self.lock = threading.Lock()

        self.written.connect(self._consume)

    # -- file-like methods

    def isatty(self):
        return False

    def write(self, txt):
        emit = False
        try:
            self.lock.acquire()
            emit = not bool(self.buffer)
            self.buffer.append(str(txt))
        finally:
            self.lock.release()
        if emit:
            self.written.emit()

    def _consume(self):
        try:
            self.lock.acquire()
            buffer_ = self.buffer
            self.buffer = []
        finally:
            self.lock.release()

        if buffer_:
            txt = ''.join(buffer_)
            self._write(txt)

    def _write(self, txt):
        self.moveCursor(QtGui.QTextCursor.End)
        self.insertPlainText(txt)
        self.moveCursor(QtGui.QTextCursor.End)
