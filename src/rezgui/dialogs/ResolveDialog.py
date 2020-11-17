from Qt import QtCore, QtWidgets, QtGui
from rezgui.util import create_pane
from rezgui.mixins.StoreSizeMixin import StoreSizeMixin
from rezgui.widgets.StreamableTextEdit import StreamableTextEdit
from rezgui.widgets.TimestampWidget import TimestampWidget
from rezgui.dialogs.WriteGraphDialog import view_graph
from rezgui.objects.ResolveThread import ResolveThread
from rezgui.objects.App import app
from rez.vendor.six.six import StringIO
from rez.vendor.version.requirement import Requirement
from rez.config import config


class ResolveDialog(QtWidgets.QDialog, StoreSizeMixin):
    def __init__(self, context_model, parent=None, advanced=False):
        config_key = ("layout/window/advanced_resolve" if advanced
                      else "layout/window/resolve")
        super(ResolveDialog, self).__init__(parent)
        StoreSizeMixin.__init__(self, app.config, config_key)

        self.setWindowTitle("Resolve")
        self.setContentsMargins(0, 0, 0, 0)

        self.context_model = context_model
        self.advanced = advanced
        self.resolver = None
        self.thread = None
        self.started = False
        self._finished = False

        #self.busy_cursor = QtGui.QCursor(QtCore.Qt.WaitCursor)

        self.edit = StreamableTextEdit()
        self.edit.setStyleSheet("font: 9pt 'Courier'")

        self.bar = QtWidgets.QProgressBar()
        self.bar.setRange(0, 10)

        self.save_context_btn = QtWidgets.QPushButton("Save Context As...")
        self.graph_btn = QtWidgets.QPushButton("View Graph...")
        self.ok_btn = QtWidgets.QPushButton("Ok")
        self.start_again_btn = QtWidgets.QPushButton("Start Again")
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.resolve_btn = QtWidgets.QPushButton("Resolve")
        self.ok_btn.hide()
        self.graph_btn.hide()
        self.start_again_btn.hide()
        self.save_context_btn.hide()

        btn_pane = create_pane([None,
                               self.save_context_btn,
                               self.graph_btn,
                               self.start_again_btn,
                               self.ok_btn,
                               self.cancel_btn,
                               self.resolve_btn],
                               not self.advanced)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.bar)
        layout.addWidget(self.edit, 1)

        self.resolve_group = None
        self.max_fails_combo = None
        self.verbosity_combo = None
        self.show_package_loads_checkbox = None

        # this is solely to execute _start_resolve() as soon as the dialog opens
        self.timer = QtCore.QTimer()
        self.timer.setInterval(1)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._on_dialog_open)

        if self.advanced:
            self.resolve_group = QtWidgets.QGroupBox("resolve settings")

            label = QtWidgets.QLabel("maximum fails:")
            self.max_fails_combo = QtWidgets.QComboBox()
            self.max_fails_combo.setEditable(True)
            self.max_fails_combo.addItem("-")
            self.max_fails_combo.addItem("1")
            self.max_fails_combo.addItem("2")
            self.max_fails_combo.addItem("3")
            app.config.attach(self.max_fails_combo, "resolve/max_fails")
            max_fails_pane = create_pane([None, label, self.max_fails_combo], True)

            label = QtWidgets.QLabel("verbosity:")
            self.verbosity_combo = QtWidgets.QComboBox()
            self.verbosity_combo.addItem("0")
            self.verbosity_combo.addItem("1")
            self.verbosity_combo.addItem("2")
            app.config.attach(self.verbosity_combo, "resolve/verbosity")
            verbosity_pane = create_pane([None, label, self.verbosity_combo], True)

            self.show_package_loads_checkbox = QtWidgets.QCheckBox("show package loads")
            self.show_package_loads_checkbox.setLayoutDirection(QtCore.Qt.RightToLeft)
            app.config.attach(self.show_package_loads_checkbox, "resolve/show_package_loads")
            show_loads_pane = create_pane([None, self.show_package_loads_checkbox], True)

            self.timestamp_widget = TimestampWidget(self.context_model)
            context = self.context_model.context()
            if context and context.requested_timestamp:
                self.timestamp_widget.set_time(context.requested_timestamp)

            left_pane = create_pane([self.timestamp_widget, None], False,
                                    compact=True)

            right_pane = create_pane([max_fails_pane,
                                      verbosity_pane,
                                      show_loads_pane,
                                      None],
                                     False, compact=True)

            create_pane([left_pane, right_pane], True,
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
        self.start_again_btn.clicked.connect(self._reset)
        self.ok_btn.clicked.connect(self.close)

    def resolve(self):
        # validate the request before opening dialog
        for req_str in self.context_model.request:
            try:
                Requirement(req_str)
            except Exception as e:
                title = "Invalid package request - %r" % req_str
                QtWidgets.QMessageBox.critical(self, title, str(e))
                return

        self._reset()
        self.timer.start()
        self.exec_()

        if self.started:
            self.resolver.stop()

            if self.thread:
                self.thread.quit()
                self.thread.wait()
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
            StoreSizeMixin.closeEvent(self, event)
        else:
            self._cancel_resolve()
            event.ignore()

    def _on_dialog_open(self):
        if not self.advanced:
            self._start_resolve()

    def _reset(self):
        self.setWindowTitle("Resolve")
        self.cancel_btn.setText("Cancel")
        self.cancel_btn.hide()
        self.ok_btn.hide()
        self.start_again_btn.hide()
        self.graph_btn.hide()
        self.save_context_btn.hide()
        self.resolve_btn.show()
        self._set_progress(False)

        if self.advanced:
            self.resolve_group.setEnabled(True)

        self.edit.clear()
        request_str = " ".join(str(x) for x in self.context_model.request)
        self._log("Resolving: %s...\n" % request_str)

    def _log(self, msg, color=None):
        if color:
            old_color = self.edit.textColor()
            self.edit.setTextColor(QtGui.QColor(color))
        self.edit.append(msg)
        self.edit.moveCursor(QtGui.QTextCursor.End)
        if color:
            self.edit.setTextColor(old_color)

    def _start_resolve(self):
        max_fails = self._get_max_fails()
        if max_fails is None:
            return

        self.setWindowTitle("Resolving...")
        self.resolve_btn.hide()
        self.cancel_btn.show()
        self._set_progress(None)
        self.started = True

        verbosity = 0
        show_package_loads = True
        timestamp = None
        if self.advanced:
            verbosity = app.config.get("resolve/verbosity")
            show_package_loads = app.config.get("resolve/show_package_loads")
            timestamp = self.timestamp_widget.datetime()
            if timestamp is not None:
                timestamp = timestamp.toTime_t()

        self.resolver = ResolveThread(
            self.context_model,
            verbosity=verbosity,
            max_fails=max_fails,
            timestamp=timestamp,
            show_package_loads=show_package_loads,
            buf=self.edit)

        if config.gui_threads:
            self.resolver.finished.connect(self._resolve_finished)

            self.thread = QtCore.QThread()
            self.resolver.moveToThread(self.thread)
            self.thread.started.connect(self.resolver.run)
            self.thread.start()
        else:
            self.resolver.run()
            self._resolve_finished()

    def _cancel_resolve(self):
        if self.started:
            self.cancel_btn.setText("Cancelling...")
            self.cancel_btn.setEnabled(False)
            self.resolver.stop()

    def _resolve_finished(self):
        self._finished = True
        self.cancel_btn.hide()
        self.ok_btn.show()
        self._set_progress(True)

        if self.advanced:
            self.start_again_btn.show()
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
                sbuf = StringIO()
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

    def _get_max_fails(self):
        if self.max_fails_combo is None:
            return -1
        txt = str(self.max_fails_combo.currentText())
        if txt == "-":
            return -1
        try:
            i = int(txt)
        except:
            i = -1
        if i < 0:
            title = "Invalid max fails value"
            body = "Must be a positive integer."
            QtWidgets.QMessageBox.critical(self, title, body)
            self.max_fails_combo.setCurrentIndex(0)
            return None
        return i

    def _save_context(self):
        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Context", filter="Context files (*.rxt)")
        if filepath:
            self.resolver.context.save(filepath)
            self._log("\nSaved context to: %s" % filepath)

    def _view_graph(self):
        graph_str = self.resolver.context.graph(as_dot=True)
        view_graph(graph_str, self)

    def _set_progress(self, done=True):
        if done is True:
            self.bar.setMaximum(10)
            self.bar.setValue(10)
        elif done is False:
            self.bar.setMaximum(10)
            self.bar.setValue(0)
        elif done is None:
            self.bar.setRange(0, 0)


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
