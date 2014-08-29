from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane, create_toolbutton
from rezgui.widgets.ContextToolsWidget import ContextToolsWidget
from rezgui.widgets.ContextDetailsWidget import ContextDetailsWidget
from rezgui.widgets.ConfiguredSplitter import ConfiguredSplitter
from rezgui.widgets.ContextTableWidget import ContextTableWidget
from rezgui.widgets.PackageTabWidget import PackageTabWidget
from rezgui.widgets.SettingsWidget import SettingsWidget
from rezgui.dialogs.ResolveDialog import ResolveDialog
from rez.vendor.version.requirement import Requirement
from rez.vendor.schema.schema import Schema
from rezgui.objects.App import app
from rez.config import config
from functools import partial


class ContextManagerWidget(QtGui.QWidget):

    modified = QtCore.Signal(bool)

    settings_titles = {
        "packages_path":        "Search path for Rez package",
        "implicit_packages":    "Packages that are implicitly added to the request"
    }

    settings_schema = Schema({
        "packages_path":        [basestring],
        "implicit_packages":    [basestring]
    })

    def __init__(self, parent=None):
        super(ContextManagerWidget, self).__init__(parent)
        self.load_context = None
        self.context = None
        self.is_resolved = False

        # context settings
        settings = {
            "packages_path":        config.packages_path,
            "implicit_packages":    config.implicit_packages
        }
        self.settings = SettingsWidget(data=settings,
                                       schema=self.settings_schema,
                                       titles=self.settings_titles)

        # widgets
        self.context_table = ContextTableWidget(self.settings)

        resolve_btn = create_toolbutton(
            [("Resolve", self._resolve),
             ("Advanced...", partial(self._resolve, advanced=True))])
        szpol = QtGui.QSizePolicy()
        szpol.setHorizontalPolicy(QtGui.QSizePolicy.Ignored)
        resolve_btn.setSizePolicy(szpol)

        self.reset_btn = QtGui.QPushButton("Reset...")
        self.diff_btn = QtGui.QPushButton("Diff Mode")
        self.shell_btn = QtGui.QPushButton("Open Shell")
        self.reset_btn.setEnabled(False)
        self.diff_btn.setEnabled(False)
        self.shell_btn.setEnabled(False)
        btn_pane = create_pane([None, self.shell_btn, self.diff_btn,
                                self.reset_btn, resolve_btn], False)

        self.package_tab = PackageTabWidget(settings=self.settings,
                                            versions_tab=True)

        bottom_pane = create_pane([(self.package_tab, 1), btn_pane], True)

        context_splitter = ConfiguredSplitter(app.config, "layout/splitter/main")
        context_splitter.setOrientation(QtCore.Qt.Vertical)
        context_splitter.addWidget(self.context_table)
        context_splitter.addWidget(bottom_pane)
        if not context_splitter.apply_saved_layout():
            context_splitter.setStretchFactor(0, 2)
            context_splitter.setStretchFactor(1, 1)

        self.tools_list = ContextToolsWidget()

        self.resolve_details = ContextDetailsWidget()

        self.tab = QtGui.QTabWidget()
        self.tab.addTab(context_splitter, "context")
        self.tab.addTab(self.settings, "settings")
        self.tab.addTab(self.tools_list, "tools")
        self.tab.addTab(self.resolve_details, "resolve details")
        self.tab.setTabEnabled(2, False)
        self.tab.setTabEnabled(3, False)

        # layout
        layout = QtGui.QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tab)
        self.setLayout(layout)

        # signals
        self.settings.settingsApplied.connect(self._settingsApplied)
        self.settings.settingsChanged.connect(self._settingsChanged)
        self.settings.settingsChangesDiscarded.connect(self._settingsChangesDiscarded)
        self.context_table.contextModified.connect(self._contextModified)
        self.context_table.variantSelected.connect(self._variantSelected)
        self.shell_btn.clicked.connect(self._open_shell)
        self.reset_btn.clicked.connect(self._reset)

    def sizeHint(self):
        return QtCore.QSize(800, 500)

    def set_context(self, context):
        self.context = context

        settings = self._current_context_settings()
        self.settings.reset(settings)

        self.context_table.set_context(self.context)
        self.tools_list.set_context(self.context)
        self.resolve_details.set_context(self.context)
        self.package_tab.set_context(self.context)

        self.tab.setTabText(0, "context")
        self.tab.setTabText(1, "settings")
        self.tab.setTabEnabled(2, True)
        self.tab.setTabEnabled(3, True)

        self._set_resolved(True)

    def _resolve(self, advanced=False):
        # check for pending settings changes
        if self.settings.pending_changes():
            title = "Context settings changes are pending."
            body = ("The context settings have been modified, and must be "
                    "applied or discarded in order to continue.")
            QtGui.QMessageBox.warning(self, title, body)
            self.tab.setCurrentIndex(1)
            return

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
            context = dlg.get_context()
            self.set_context(context)

    def _reset(self):
        assert self.context
        ret = QtGui.QMessageBox.warning(
            self,
            "The context has been modified.",
            "Your changes will be lost. Are you sure?",
            QtGui.QMessageBox.Ok,
            QtGui.QMessageBox.Cancel)
        if ret == QtGui.QMessageBox.Ok:
            self.set_context(self.context)

    def _open_shell(self):
        assert self.context
        app.execute_shell(context=self.context, terminal=True)

    def _current_context_settings(self):
        assert self.context
        context = self.context
        implicit_strs = [str(x) for x in context.implicit_packages]
        return {
            "packages_path":        context.package_paths,
            "implicit_packages":    implicit_strs
        }

    def _settingsApplied(self):
        self.tab.setTabText(1, "settings*")
        self.context_table.refresh()
        self.package_tab.refresh()

    def _settingsChanged(self):
        self.tab.setTabText(1, "settings**")
        self._set_resolved(False)

    def _settingsChangesDiscarded(self):
        self.tab.setTabText(1, "settings*")

    def _contextModified(self):
        self.tab.setTabText(0, "context*")
        self._set_resolved(False)

    def _variantSelected(self, variant):
        self.package_tab.set_variant(variant)

    def _set_resolved(self, resolved=True):
        self.is_resolved = resolved
        self.diff_btn.setEnabled(resolved)
        self.shell_btn.setEnabled(resolved)
        self.reset_btn.setEnabled(not resolved and bool(self.context))
        self.modified.emit(not resolved)
