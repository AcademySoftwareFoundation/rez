from rezgui.qt import QtCore, QtGui
import threading


class StreamableTextEdit(QtGui.QTextEdit):
    """A QTextEdit that also acts like a write-only file object.

    The object is threadsafe - write() etc can be called from any thread.
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
        try:
            self.lock.acquire()
            self.buffer.append(str(txt))
        finally:
            self.lock.release()
        self.written.emit()

    def _consume(self):
        try:
            self.lock.acquire()
            buffer_ = self.buffer
            self.buffer = []
        finally:
            self.lock.release()
        for txt in buffer_:
            self._write(txt)

    def _write(self, txt):
        self.moveCursor(QtGui.QTextCursor.End)
        self.insertPlainText(txt)
        self.moveCursor(QtGui.QTextCursor.End)
