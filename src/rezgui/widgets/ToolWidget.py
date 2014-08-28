from rezgui.qt import QtCore, QtGui
from rezgui.widgets.IconButton import IconButton
from rezgui.objects.App import app
from rezgui.util import get_icon_widget


class ToolWidget(QtGui.QWidget):

    clicked = QtCore.Signal()

    def __init__(self, context, tool_name, process_tracker=None, parent=None):
        super(ToolWidget, self).__init__(parent)
        self.context = context
        self.tool_name = tool_name
        self.process_tracker = process_tracker

        self.tool_icon = get_icon_widget("spanner")
        self.label = QtGui.QLabel(tool_name)
        self.instances_label = QtGui.QLabel("")
        self.instances_label.setEnabled(False)
        font = self.instances_label.font()
        font.setItalic(True)
        self.instances_label.setFont(font)

        if self.context:
            self.setCursor(QtCore.Qt.PointingHandCursor)
            if self.process_tracker:
                nprocs = self.process_tracker.num_instances(self.context, self.tool_name)
                self.set_instance_count(nprocs)

        layout = QtGui.QHBoxLayout()
        layout.setSpacing(2)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(self.tool_icon)
        layout.addWidget(self.label, 1)
        layout.addWidget(self.instances_label)
        self.setLayout(layout)

    def contextMenuEvent(self, event):
        if not self.context:
            return

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
        if not self.context:
            return

        self.clicked.emit()
        if event.button() == QtCore.Qt.LeftButton:
            self._launch_tool()

    def _launch_tool(self, terminal=False):
        if terminal:
            term_cmd = app.config.get("terminal_command") or ""
            command = term_cmd.strip().split() + [self.tool_name]
        else:
            command = [self.tool_name]

        proc = self.context.execute_shell(command=command,
                                          block=False,
                                          start_new_session=True)
        if self.process_tracker:
            self.process_tracker.add_instance(self.context, self.tool_name, proc)

    def set_instance_count(self, nprocs):
        if nprocs:
            txt = "%d instances running..." % nprocs
        else:
            txt = ""
        self.instances_label.setText(txt)
