from rezgui.qt import QtCore, QtGui
from rezgui.dialogs.ProcessDialog import ProcessDialog
from rezgui.widgets.IconButton import IconButton
from rezgui.objects.App import app
from rezgui.util import get_icon_widget
import subprocess


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
                nprocs = self.process_tracker.num_instances(self.context,
                                                            self.tool_name)
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
        run_moniter_action = menu.addAction("Run And Moniter")

        action = menu.exec_(self.mapToGlobal(event.pos()))
        self.clicked.emit()
        if action == run_action:
            self._launch_tool()
        elif action == run_term_action:
            self._launch_tool(terminal=True)
        elif action == run_moniter_action:
            self._launch_tool(moniter=True)

    def mouseReleaseEvent(self, event):
        super(ToolWidget, self).mouseReleaseEvent(event)
        if not self.context:
            return

        self.clicked.emit()
        if event.button() == QtCore.Qt.LeftButton:
            self._launch_tool()

    def _launch_tool(self, terminal=False, moniter=False):
        buf = subprocess.PIPE if moniter else None
        proc = app.execute_shell(context=self.context,
                                 command=self.tool_name,
                                 terminal=terminal,
                                 stdout=buf,
                                 stderr=buf)

        if self.process_tracker:
            self.process_tracker.add_instance(self.context, self.tool_name, proc)
        if moniter:
            dlg = ProcessDialog(proc, self.tool_name)
            dlg.exec_()

    def set_instance_count(self, nprocs):
        if nprocs:
            txt = "%d instances running..." % nprocs
        else:
            txt = ""
        self.instances_label.setText(txt)
