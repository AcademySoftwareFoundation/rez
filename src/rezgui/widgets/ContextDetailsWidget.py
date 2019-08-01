from Qt import QtWidgets, QtGui
from rezgui.util import create_pane
from rezgui.widgets.ContextEnvironWidget import ContextEnvironWidget
from rezgui.widgets.SearchableTextEdit import SearchableTextEdit
from rezgui.widgets.StreamableTextEdit import StreamableTextEdit
from rezgui.widgets.ViewGraphButton import ViewGraphButton
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.models.ContextModel import ContextModel
from rez.shells import get_shell_types
from rez.system import system
import pprint


class ContextDetailsWidget(QtWidgets.QTabWidget, ContextViewMixin):
    def __init__(self, context_model=None, parent=None):
        super(ContextDetailsWidget, self).__init__(parent)
        ContextViewMixin.__init__(self, context_model)
        self.code_pending = True

        self.overview_edit = StreamableTextEdit()
        self.overview_edit.setStyleSheet("font: 12pt 'Courier'")

        self.graph_btn = ViewGraphButton(context_model)
        btn_pane = create_pane([None, self.graph_btn], True)
        overview_pane = create_pane([self.overview_edit, btn_pane], False)

        self.code_edit = SearchableTextEdit()
        self.code_edit.setStyleSheet("font: 12pt 'Courier'")

        self.code_combo = QtWidgets.QComboBox()
        # strip out 'sh' and 'csh', they only differ from bash and tcsh in shell
        # startup behaviour, which is irrelevant here
        code_types = set(get_shell_types()) - set([system.shell, "sh", "csh"])
        code_types = [system.shell] + sorted(code_types) + ["python dict"]
        for code_type in code_types:
            self.code_combo.addItem(code_type)

        label = QtWidgets.QLabel("Format:")
        btn_pane = create_pane([None, label, self.code_combo], True)
        code_pane = create_pane([self.code_edit, btn_pane], False)

        self.environ_widget = ContextEnvironWidget()

        self.addTab(overview_pane, "overview")
        self.addTab(code_pane, "shell code")
        self.addTab(self.environ_widget, "environment")

        self.code_combo.currentIndexChanged.connect(self._update_code)
        self.currentChanged.connect(self._currentTabChanged)

        self.refresh()

    def refresh(self):
        self.overview_edit.clear()
        self.setCurrentIndex(0)

        context = self.context()
        if not context:
            self.setEnabled(False)
            return

        self.code_pending = True
        context.print_info(buf=self.overview_edit, verbosity=1)
        self.overview_edit.moveCursor(QtGui.QTextCursor.Start)
        self.environ_widget.set_context(context)

    def search(self):
        tab_index = self.currentIndex()
        if tab_index == 0:
            self.overview_edit.search()
        elif tab_index == 1:
            self.code_edit.search()

    def _contextChanged(self, flags=0):
        if not (flags & ContextModel.CONTEXT_CHANGED):
            return
        self.refresh()

    def _currentTabChanged(self, index):
        if index == 1 and self.code_pending:
            self._update_code()

    def _update_code(self):
        self.code_edit.clear()
        context = self.context()
        if not context:
            return

        shell = str(self.code_combo.currentText())
        if shell == "python dict":
            environ = context.get_environ()
            code = pprint.pformat(environ)
        else:
            code = context.get_shell_code(shell=shell)

        self.code_edit.insertPlainText(code)
        self.code_edit.moveCursor(QtGui.QTextCursor.Start)
        self.code_pending = False


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
