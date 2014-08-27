from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane
from rezgui.dialogs.WriteGraphDialog import view_graph
from rezgui.widgets.ContextEnvironWidget import ContextEnvironWidget
from rezgui.widgets.StreamableTextEdit import StreamableTextEdit
from rez.shells import get_shell_types
from rez.system import system
import pprint


class ContextDetailsWidget(QtGui.QTabWidget):
    def __init__(self, settings=None, parent=None):
        super(ContextDetailsWidget, self).__init__(parent)
        self.settings = settings
        self.code_pending = True
        self.context = None

        self.overview_edit = StreamableTextEdit()
        self.overview_edit.setStyleSheet("font: 9pt 'Courier'")

        self.graph_btn = QtGui.QPushButton("View Graph...")
        self.graph_btn.setEnabled(False)
        btn_pane = create_pane([None, self.graph_btn], True)
        overview_pane = create_pane([self.overview_edit, btn_pane], False)

        self.code_edit = QtGui.QTextEdit()
        self.code_edit.setStyleSheet("font: 9pt 'Courier'")

        self.code_combo = QtGui.QComboBox()
        # strip out 'sh' and 'csh', they only differ from bash and tcsh in shell
        # startup behaviour, which is irrelevant here
        code_types = set(get_shell_types()) - set([system.shell, "sh", "csh"])
        code_types = [system.shell] + sorted(code_types) + ["python dict"]
        for code_type in code_types:
            self.code_combo.addItem(code_type)

        label = QtGui.QLabel("Format:")
        btn_pane = create_pane([None, label, self.code_combo], True)
        code_pane = create_pane([self.code_edit, btn_pane], False)

        self.environ_widget = ContextEnvironWidget()

        self.addTab(overview_pane, "overview")
        self.addTab(code_pane, "shell code")
        self.addTab(self.environ_widget, "environment")

        self.graph_btn.clicked.connect(self._view_graph)
        self.code_combo.currentIndexChanged.connect(self._update_code)
        self.currentChanged.connect(self._currentTabChanged)

    def clear(self):
        self.overview_edit.clear()
        self.code_edit.clear()
        self.graph_btn.setEnabled(False)
        self.setCurrentIndex(0)
        self.code_pending = True

    def set_context(self, context):
        self.clear()
        self.context = context
        if context is None:
            return

        self.context.print_info(buf=self.overview_edit, verbosity=1)
        self.environ_widget.set_context(self.context)
        self.graph_btn.setEnabled(True)

    def _currentTabChanged(self, index):
        if index == 1 and self.code_pending:
            self._update_code()

    def _view_graph(self):
        assert self.context
        graph_str = self.context.graph(as_dot=True)
        view_graph(graph_str, self)

    def _update_code(self):
        assert self.context
        shell = str(self.code_combo.currentText())
        if shell == "python dict":
            environ = self.context.get_environ()
            code = pprint.pformat(environ)
        else:
            code = self.context.get_shell_code(shell=shell)

        self.code_edit.clear()
        self.code_edit.insertPlainText(code)
        self.code_edit.moveCursor(QtGui.QTextCursor.Start)
        self.code_pending = False
