from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane
from rezgui.widgets.ContextTableWidget import ContextTableWidget
from rezgui.widgets.SettingsWidget import SettingsWidget
from rezgui.dialogs.ResolveDialog import ResolveDialog
from rez.vendor.version.requirement import Requirement
from rez.vendor.schema.schema import Schema
from rez.config import config
from functools import partial


class ContextManagerWidget(QtGui.QWidget):

    settings_schema = Schema({
        "packages_path":        [basestring],
        "implicit_packages":    [basestring]
    })

    def __init__(self, parent=None):
        super(ContextManagerWidget, self).__init__(parent)
        self.load_context = None
        self.current_context = None

        # context settings
        settings = {
            "packages_path":        config.packages_path,
            "implicit_packages":    config.implicit_packages
        }
        self.settings = SettingsWidget(data=settings,
                                       schema=self.settings_schema)

        # widgets
        self.context_table = ContextTableWidget(self.settings)

        menu = QtGui.QMenu()
        a1 = QtGui.QAction("Resolve", self)
        a1.triggered.connect(self._resolve)
        menu.addAction(a1)
        a2 = QtGui.QAction("Advanced...", self)
        a2.triggered.connect(partial(self._resolve, advanced=True))
        menu.addAction(a2)

        resolve_btn = QtGui.QToolButton()
        resolve_btn.setPopupMode(QtGui.QToolButton.MenuButtonPopup)
        resolve_btn.setDefaultAction(a1)
        resolve_btn.setMenu(menu)

        diff_btn = QtGui.QPushButton("Diff Mode")
        btn_pane = create_pane([None, diff_btn, resolve_btn], True)
        context_pane = create_pane([(self.context_table, 1), btn_pane], False)

        self.tab = QtGui.QTabWidget()
        self.tab.addTab(context_pane, "context")
        self.tab.addTab(self.settings, "settings")

        # layout
        layout = QtGui.QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tab)
        self.setLayout(layout)

        # signals
        self.settings.changes_applied.connect(self.context_table.refresh)

    def _resolve(self, advanced=False):
        # get and validate request from context table
        request = []
        for req_str in self.context_table.get_request():
            try:
                req = Requirement(req_str)
                request.append(req)
            except Exception as e:
                title = "Invalid package request - %r" % req_str
                QtGui.QMessageBox.warning(self, title, str(e))
                return None

        # do the resolve, set as current if successful
        dlg = ResolveDialog(self.settings, parent=self, advanced=advanced)
        if dlg.resolve(request):
            self.current_context = dlg.get_context()
            self.context_table.set_context(self.current_context)
