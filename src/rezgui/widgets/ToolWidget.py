from Qt import QtCore, QtWidgets
from rezgui.dialogs.ProcessDialog import ProcessDialog
from rezgui.objects.App import app
from rezgui.util import get_icon_widget, update_font, add_menu_action
from rez.utils.formatting import readable_time_duration
from functools import partial
import subprocess
import time


class ToolWidget(QtWidgets.QWidget):

    clicked = QtCore.Signal()

    def __init__(self, context, tool_name, process_tracker=None, parent=None):
        super(ToolWidget, self).__init__(parent)
        self.context = context
        self.tool_name = tool_name
        self.process_tracker = process_tracker

        tool_icon = get_icon_widget("spanner")
        self.label = QtWidgets.QLabel(tool_name)
        self.instances_label = QtWidgets.QLabel("")
        self.instances_label.setEnabled(False)
        update_font(self.instances_label, italic=True)

        if self.context:
            self.setCursor(QtCore.Qt.PointingHandCursor)
            if self.process_tracker:
                entries = self.get_processes()
                self.set_instance_count(len(entries))

        layout = QtWidgets.QHBoxLayout()
        layout.setSpacing(2)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(tool_icon)
        layout.addWidget(self.label, 1)
        layout.addWidget(self.instances_label)
        self.setLayout(layout)

    def get_processes(self):
        if not self.process_tracker:
            return []

        return self.process_tracker.running_instances(self.context, self.tool_name)

    def mouseReleaseEvent(self, event):
        super(ToolWidget, self).mouseReleaseEvent(event)
        if not self.context:
            return

        menu = QtWidgets.QMenu(self)
        add_menu_action(menu, "Run", self._launch_tool)
        fn = partial(self._launch_tool, terminal=True)
        add_menu_action(menu, "Run In Terminal", fn)
        fn = partial(self._launch_tool, moniter=True)
        add_menu_action(menu, "Run And Moniter", fn)

        entries = self.get_processes()
        if entries:
            menu.addSeparator()
            add_menu_action(menu, "Running Processes...", self._list_processes)

        menu.addSeparator()
        add_menu_action(menu, "Cancel")

        menu.exec_(self.mapToGlobal(event.pos()))
        self.clicked.emit()

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

    def _list_processes(self):
        entries = self.get_processes()
        now = int(time.time())
        items = []
        for proc, start_time in entries:
            age = now - start_time
            items.append((age, proc.pid))

        if items:
            items = sorted(items)
            lines = []
            for age, pid in items:
                t_str = readable_time_duration(age)
                line = "Process #%d has been running for %s" % (pid, t_str)
                lines.append(line)
            txt = "\n".join(lines)
        else:
            txt = "There are no running processes."

        QtWidgets.QMessageBox.information(self, "Processes", txt)

    def set_instance_count(self, nprocs):
        if nprocs:
            txt = "%d instances running..." % nprocs
        else:
            txt = ""
        self.instances_label.setText(txt)


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
