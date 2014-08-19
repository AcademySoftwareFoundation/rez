from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane
from rezgui.widgets.StreamableTextEdit import StreamableTextEdit
from rezgui.dialogs.ConfiguredDialog import ConfiguredDialog
from rezgui.dialogs.ImageViewerDialog import ImageViewerDialog
from rezgui.config import config
from rez.exceptions import RezError
from rez.resolved_context import ResolvedContext
from rez.dot import save_graph
import tempfile
import threading
import StringIO
import os


class Resolver(QtCore.QObject):

    finished = QtCore.Signal()
    graph_written = QtCore.Signal(str, str)

    def __init__(self, settings, verbosity=0, buf=None):
        super(Resolver, self).__init__()
        self.settings = settings
        self.verbosity = verbosity
        self.buf = buf
        self.context = None
        self.keep_going = True
        self.abort_reason = None
        self.error_message = None

    def resolve(self, request):
        if config.get("resolve/show_package_loads"):
            package_load_callback = self._package_load_callback
        else:
            package_load_callback = None

        try:
            self.context = ResolvedContext(
                request,
                package_paths=self.settings.get("packages_path"),
                verbosity=self.verbosity,
                buf=self.buf,
                callback=self._callback,
                package_load_callback=package_load_callback)
        except RezError as e:
            self.error_message = str(e)

        self.finished.emit()

    def save_graph(self, filepath):
        try:
            graph_str = self.context.graph(as_dot=True)
            save_graph(graph_str, filepath)
            self.graph_written.emit(filepath, "")
        except Exception as e:
            self.graph_written.emit("", str(e))

    def cancel(self):
        self.keep_going = False
        self.abort_reason = "Cancelled by user."

    def success(self):
        return self.context and self.context.success

    def _callback(self, solver_state):
        if self.buf and self.verbosity == 0:
            print >> self.buf, "solve step %d..." % solver_state.num_solves
        return self.keep_going, self.abort_reason

    def _package_load_callback(self, package):
        if self.buf:
            print >> self.buf, "loading %s..." % str(package)


class ResolveDialog(ConfiguredDialog):
    def __init__(self, settings, parent=None, advanced=False):
        config_key = ("layout/window/advanced_resolve" if advanced
                      else "layout/window/resolve")
        super(ResolveDialog, self).__init__(config, config_key, parent)
        self.setWindowTitle("Resolve")
        self.setContentsMargins(0, 0, 0, 0)

        self.settings = settings
        self.advanced = advanced
        self.request = None
        self.resolver = None
        self.thread = None
        self.started = False
        self._finished = False

        self.busy_cursor = QtGui.QCursor(QtCore.Qt.WaitCursor)

        self.edit = StreamableTextEdit()
        self.edit.setStyleSheet("font: 9pt 'Courier'")

        self.bar = QtGui.QProgressBar()
        self.bar.setRange(0, 10)

        self.save_context_btn = QtGui.QPushButton("Save Context As...")
        self.graph_btn = QtGui.QPushButton("View Graph...")
        self.ok_btn = QtGui.QPushButton("Ok")
        self.cancel_btn = QtGui.QPushButton("Cancel")
        self.resolve_btn = QtGui.QPushButton("Resolve")
        self.ok_btn.hide()
        self.graph_btn.hide()
        self.save_context_btn.hide()

        btn_pane = create_pane([None,
                               self.save_context_btn,
                               self.graph_btn,
                               self.ok_btn,
                               self.cancel_btn,
                               self.resolve_btn],
                               not self.advanced)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.bar)
        layout.addWidget(self.edit, 1)

        self.resolve_group = None
        self.max_fails_combo = None
        self.verbosity_combo = None
        self.show_package_loads_checkbox = None

        if self.advanced:
            self.resolve_group = QtGui.QGroupBox("resolve settings")

            label = QtGui.QLabel("maximum fails:")
            self.max_fails_combo = QtGui.QComboBox()
            self.max_fails_combo.setEditable(True)
            self.max_fails_combo.addItem("None")
            self.max_fails_combo.addItem("0")
            self.max_fails_combo.addItem("1")
            self.max_fails_combo.addItem("2")
            config.attach(self.max_fails_combo, "resolve/max_fails")
            max_fails_pane = create_pane([None, label, self.max_fails_combo], True)

            label = QtGui.QLabel("verbosity:")
            self.verbosity_combo = QtGui.QComboBox()
            self.verbosity_combo.addItem("0")
            self.verbosity_combo.addItem("1")
            self.verbosity_combo.addItem("2")
            config.attach(self.verbosity_combo, "resolve/verbosity")
            verbosity_pane = create_pane([None, label, self.verbosity_combo], True)

            self.show_package_loads_checkbox = QtGui.QCheckBox("show package loads")
            self.show_package_loads_checkbox.setLayoutDirection(QtCore.Qt.RightToLeft)
            config.attach(self.show_package_loads_checkbox, "resolve/show_package_loads")
            show_loads_pane = create_pane([None, self.show_package_loads_checkbox], True)

            create_pane([max_fails_pane,
                         verbosity_pane,
                         show_loads_pane,
                         None],
                        False,
                        parent_widget=self.resolve_group)

            pane = create_pane([self.resolve_group, None, btn_pane], True)
            self.cancel_btn.hide()
            layout.addWidget(pane)
        else:
            self.resolve_btn.hide()
            layout.addWidget(btn_pane)

        self.setLayout(layout)

        self.cancel_btn.clicked.connect(self._cancel_resolve)
        self.resolve_btn.clicked.connect(self._start_resolve)
        self.graph_btn.clicked.connect(self._view_graph)
        self.save_context_btn.clicked.connect(self._save_context)
        self.ok_btn.clicked.connect(self.close)

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

    def reject(self):
        if self._finished or not self.started:
            super(ResolveDialog, self).reject()
        else:
            self._cancel_resolve()

    def closeEvent(self, event):
        if self._finished or not self.started:
            super(ResolveDialog, self).closeEvent(event)
        else:
            self._cancel_resolve()
            event.ignore()

    def _log(self, msg, color=None):
        if color:
            old_color = self.edit.textColor()
            self.edit.setTextColor(QtGui.QColor(color))
        self.edit.append(msg)
        self.edit.moveCursor(QtGui.QTextCursor.End)
        if color:
            self.edit.setTextColor(old_color)

    def _start_resolve(self):
        self.setWindowTitle("Resolving...")
        self.resolve_btn.hide()
        self.cancel_btn.show()
        self._set_progress(False)
        self.started = True

        verbosity = 0
        if self.advanced:
            verbosity = config.get("resolve/verbosity")

        self.resolver = Resolver(self.settings,
                                 verbosity=verbosity,
                                 buf=self.edit)

        self.resolver.finished.connect(self._resolve_finished)
        self.resolver.graph_written.connect(self._graph_written)

        self.thread = threading.Thread(target=self.resolver.resolve,
                                       args=(self.request,))
        self.thread.start()

    def _cancel_resolve(self):
        if self.started:
            self.cancel_btn.setText("Cancelling...")
            self.cancel_btn.setEnabled(False)
            self.resolver.cancel()

    def _resolve_finished(self):
        self._finished = True
        self.cancel_btn.hide()
        self.ok_btn.show()
        self._set_progress(True)

        if self.advanced:
            self.resolve_group.setEnabled(False)

        if self.resolver.error_message:
            msg = "\nTHE RESOLVE FAILED:\n%s" % self.resolver.error_message
            self._log(msg, "red")
            return

        if self.resolver.context.has_graph:
            self.graph_btn.setEnabled(True)

        self.save_context_btn.setEnabled(True)
        self.graph_btn.show()
        self.save_context_btn.show()

        if self.resolver.success():
            if self.advanced:
                sbuf = StringIO.StringIO()
                self.resolver.context.print_info(buf=sbuf)
                msg = "\nTHE RESOLVE SUCCEEDED:\n\n"
                msg += sbuf.getvalue()
                self._log(msg, "green")
            else:
                self.close()
        else:
            msg = "\nTHE RESOLVE FAILED"
            desc = self.resolver.context.failure_description
            if desc:
                msg += ":\n%s" % desc
            self._log(msg, "red")

    def _save_context(self):
        filepath = QtGui.QFileDialog.getSaveFileName(
            self, "Save Context", filter="Context files (*.rxt)")
        if filepath:
            self.resolver.context.save(filepath)
            self._log("\nSaved context to: %s" % filepath)

    def _view_graph(self):
        self._log("\nRendering graph...")
        self.graph_btn.setEnabled(False)
        fd, filepath = tempfile.mkstemp(suffix=".png", prefix="rez-graph-")
        os.close(fd)

        self._finished = False
        self._set_progress(False)
        QtGui.QApplication.setOverrideCursor(self.busy_cursor)

        self.thread = threading.Thread(target=self.resolver.save_graph,
                                       args=(filepath,))
        self.thread.start()

    def _graph_written(self, filepath, error_message):
        QtGui.QApplication.restoreOverrideCursor()
        self.graph_btn.setEnabled(True)
        self._set_progress(True)
        self._finished = True

        if filepath:
            dlg = ImageViewerDialog(filepath)
            dlg.exec_()
        else:
            self.log('\n' + error_message, "red")

    def _set_progress(self, done=True):
        if done:
            self.bar.setMaximum(10)
            self.bar.setValue(10)
        else:
            self.bar.setRange(0, 0)
