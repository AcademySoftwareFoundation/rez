from rezgui.qt import QtCore, QtGui
from rezgui.widgets.IconButton import IconButton
from rezgui.config import config
from rezgui.util import get_icon_widget


class ToolWidget(QtGui.QWidget):

    clicked = QtCore.Signal()

    def __init__(self, context, tool_name, parent=None):
        super(ToolWidget, self).__init__(parent)
        self.context = context
        self.tool_name = tool_name
        self.procs = []

        self.tool_icon = get_icon_widget("spanner")
        self.label = QtGui.QLabel(tool_name)
        self.instances_label = QtGui.QLabel("")
        self.instances_label.setEnabled(False)
        font = self.instances_label.font()
        font.setItalic(True)
        self.instances_label.setFont(font)

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._update_procs)

        self.setCursor(QtCore.Qt.PointingHandCursor)

        layout = QtGui.QHBoxLayout()
        layout.setSpacing(2)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(self.tool_icon)
        layout.addWidget(self.label, 1)
        layout.addWidget(self.instances_label)
        self.setLayout(layout)

    def contextMenuEvent(self, event):
        menu = QtGui.QMenu(self)
        run_action = menu.addAction("Run")
        run_term_action = menu.addAction("Run In Terminal")
        action = menu.exec_(self.mapToGlobal(event.pos()))
        self.clicked.emit()
        if action == run_action:
            self._launch_tool()
        elif action == run_term_action:
            self._launch_tool(terminal=True)

    def mouseReleaseEvent(self, event):
        super(ToolWidget, self).mouseReleaseEvent(event)
        self.clicked.emit()
        if event.button() == QtCore.Qt.LeftButton:
            self._launch_tool()

    def _launch_tool(self, terminal=False):
        if terminal:
            term_cmd = config.get("launch/terminal_command")
            if not term_cmd:
                title = "Cannot launch tool from separate terminal"
                body = "The command is not configured"
                QtGui.QMessageBox.warning(self, title, body)
                return
            command = term_cmd.strip().split() + [self.tool_name]
        else:
            command = [self.tool_name]

        proc = self.context.execute_shell(command=command,
                                          block=False,
                                          start_new_session=True)
        self.procs.append(proc)
        self._update_procs()

    def _update_procs(self):
        # remove terminated processes
        procs = []
        for proc in self.procs:
            if proc.poll() is None:
                procs.append(proc)
        self.procs = procs

        # update label
        if procs:
            txt = "%d instances running..." % len(procs)
            if not self.timer.isActive():
                self.timer.start()
        else:
            txt = ""
            self.timer.stop()

        self.instances_label.setText(txt)
