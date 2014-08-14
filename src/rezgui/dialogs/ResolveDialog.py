from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane
from rezgui.dialogs.ImageViewerDialog import ImageViewerDialog
from rez.resolved_context import ResolvedContext
from functools import partial
import threading
import StringIO


class Resolver(QtCore.QObject):

    finished = QtCore.Signal()
    update = QtCore.Signal(str)

    def __init__(self, settings):
        super(Resolver, self).__init__()
        self.settings = settings
        self.context = None
        self.keep_going = True
        self.abort_reason = None

    def __call__(self, solver_state):
        self.update.emit(str(solver_state) + '\n')
        return self.keep_going, self.abort_reason

    def resolve(self, request):
        context = ResolvedContext(request, callback=self)
        self.context = context
        self.finished.emit()

    def cancel(self):
        self.keep_going = False
        self.abort_reason = "Cancelled by user."

    def success(self):
        return self.context and self.context.success


class ResolveDialog(QtGui.QDialog):
    def __init__(self, settings, parent=None, advanced=False):
        super(ResolveDialog, self).__init__(parent)
        self.setWindowTitle("Resolve")
        self.setContentsMargins(0, 0, 0, 0)

        self.settings = settings
        self.advanced = advanced
        self.request = None
        self.resolver = None
        self.thread = None
        self.started = False
        self.finished = False

        self.edit = QtGui.QTextEdit()
        self.edit.setReadOnly(True)
        self.edit.setStyleSheet("font: 10pt 'Courier'")

        self.bar = QtGui.QProgressBar()
        self.bar.setRange(0, 10)

        self.ok_btn = QtGui.QPushButton("Ok")
        self.cancel_btn = QtGui.QPushButton("Cancel")
        self.resolve_btn = QtGui.QPushButton("Resolve")
        self.graph_btn = QtGui.QPushButton("View Graph...")
        self.ok_btn.hide()
        self.graph_btn.hide()
        btn_pane = create_pane([None,
                               self.graph_btn,
                               self.ok_btn,
                               self.cancel_btn,
                               self.resolve_btn],
                               not self.advanced)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.bar)
        layout.addWidget(self.edit, 1)

        if self.advanced:
            group = QtGui.QGroupBox("resolve settings")

            label = QtGui.QLabel("maximum fails:")
            max_fails_combo = QtGui.QComboBox()
            max_fails_combo.setEditable(True)
            max_fails_combo.addItem("None")
            max_fails_combo.addItem("0")
            max_fails_combo.addItem("1")
            max_fails_combo.addItem("2")
            max_fails_pane = create_pane([label, 10, max_fails_combo], True)

            label = QtGui.QLabel("verbosity:")
            verbosity_combo = QtGui.QComboBox()
            verbosity_combo.addItem("0")
            verbosity_combo.addItem("1")
            verbosity_combo.addItem("2")
            verbosity_pane = create_pane([label, 10, verbosity_combo], True)

            create_pane([max_fails_pane,
                        verbosity_pane,
                        None],
                        False, parent_widget=group, spacing=5, margin=10)

            pane = create_pane([group, None, btn_pane], True)
            self.cancel_btn.hide()
            layout.addWidget(pane)
        else:
            self.resolve_btn.hide()
            layout.addWidget(btn_pane)

        self.setLayout(layout)

        self.cancel_btn.clicked.connect(self._cancel_resolve)
        self.resolve_btn.clicked.connect(self._start_resolve)
        self.graph_btn.clicked.connect(self._view_graph)
        self.ok_btn.clicked.connect(partial(self.done, 0))

    def resolve(self, request):
        self.request = request
        request_str = " ".join(str(x) for x in self.request)
        self._log("Resolving: %s...\n" % request_str)

        if not self.advanced:
            self._start_resolve()

        self.exec_()
        if self.started:
            self.resolver.cancel()
            self.thread.join()
            return self.resolver.success()
        return False

    def get_context(self):
        if self.resolver:
            return self.resolver.context
        return None

    def sizeHint(self):
        return QtCore.QSize(500, 200)

    def reject(self):
        if self.finished or not self.started:
            super(ResolveDialog, self).reject()
        else:
            self._cancel_resolve()

    def closeEvent(self, event):
        if self.finished:
            super(ResolveDialog, self).closeEvent(event)
        else:
            self._cancel_resolve()
            event.ignore()

    def _log(self, msg):
        self.edit.append(msg)
        self.edit.moveCursor(QtGui.QTextCursor.End)

    def _start_resolve(self):
        self.setWindowTitle("Resolving...")
        self.resolve_btn.hide()
        self.cancel_btn.show()
        self.bar.setRange(0, 0)
        self.started = True

        self.resolver = Resolver(self.settings)
        self.resolver.finished.connect(self._resolve_finished)
        self.resolver.update.connect(self._resolve_update)
        self.thread = threading.Thread(target=self.resolver.resolve,
                                       args=(self.request,))
        self.thread.start()

    def _cancel_resolve(self):
        if self.started:
            self.cancel_btn.setText("Cancelling...")
            self.resolver.cancel()

    def _resolve_update(self, msg):
        self._log(msg)

    def _resolve_finished(self):
        self.finished = True
        self.cancel_btn.setEnabled(False)
        self.bar.setMaximum(10)
        self.bar.setValue(10)

        self.graph_btn.setEnabled(self.resolver.context.has_graph)
        self.graph_btn.show()

        if self.resolver.success():
            if self.advanced:
                self.cancel_btn.hide()
                self.ok_btn.show()

                sbuf = StringIO.StringIO()
                self.resolver.context.print_info(buf=sbuf)
                msg = "\nTHE RESOLVE SUCCEEDED:\n\n"
                msg += sbuf.getvalue()
                self.edit.setTextColor(QtGui.QColor("green"))
                self._log(msg)
            else:
                self.done(0)
            return

        self.edit.setTextColor(QtGui.QColor("red"))
        msg = "\nTHE RESOLVE FAILED"
        desc = self.resolver.context.failure_description
        if desc:
            msg += ":\n%s" % desc
        self._log(msg)

        self.cancel_btn.hide()
        self.ok_btn.show()

    def _view_graph(self):
        self._log("\nRendering graph...")

        dlg = ImageViewerDialog("/home/ajohns/tmp/foo.png")
        dlg.exec_()
