from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane, create_toolbutton, get_icon, lock_types
from rezgui.widgets.ContextToolsWidget import ContextToolsWidget
from rezgui.widgets.ContextDetailsWidget import ContextDetailsWidget
from rezgui.widgets.ConfiguredSplitter import ConfiguredSplitter
from rezgui.widgets.ContextTableWidget import ContextTableWidget
from rezgui.widgets.PackageTabWidget import PackageTabWidget
from rezgui.widgets.SettingsWidget import SettingsWidget
from rezgui.dialogs.ResolveDialog import ResolveDialog
from rezgui.objects.App import app
from rez.vendor.version.requirement import Requirement
from rez.vendor.schema.schema import Schema, Or
from rez.config import config
from rez.resolved_context import PatchLock
from functools import partial


class ContextManagerWidget(QtGui.QWidget):

    modified = QtCore.Signal(bool)
    resolved = QtCore.Signal(bool)  # True if resolve was successful

    settings_titles = {
        "packages_path":        "Search path for Rez packages",
        "implicit_packages":    "Packages that are implicitly added to the request",
        "default_patch_lock":   "Locking to apply during a re-resolve"
    }

    settings_schema = Schema({
        "packages_path":        [basestring],
        "implicit_packages":    [basestring],
        "default_patch_lock":   Or(*[x.name for x in PatchLock])
    })

    def __init__(self, parent=None):
        super(ContextManagerWidget, self).__init__(parent)
        self.context = None
        self.is_resolved = False

        # context settings
        settings = {
            "packages_path":        config.packages_path,
            "implicit_packages":    config.implicit_packages,
            "default_patch_lock":   PatchLock.no_lock.name
        }
        self.settings = SettingsWidget(data=settings,
                                       schema=self.settings_schema,
                                       titles=self.settings_titles)

        # widgets
        self.context_table = ContextTableWidget(self.settings)
        self.show_effective_request_checkbox = QtGui.QCheckBox("show effective request")

        self.diff_btn = QtGui.QPushButton("Diff Mode")
        self.shell_btn = QtGui.QPushButton("Open Shell")

        self.resolve_btn = QtGui.QToolButton()

        def _action(menu, label, slot, icon_name=None, group=None):
            nargs = [label, self.resolve_btn]
            if icon_name:
                icon = get_icon(icon_name, as_qicon=True)
                nargs.insert(0, icon)
            action = QtGui.QAction(*nargs)
            action.triggered.connect(slot)
            if group:
                action.setCheckable(True)
                group.addAction(action)
            menu.addAction(action)
            return action

        menu = QtGui.QMenu()
        default_action = _action(menu, "Resolve", self._resolve)
        _action(menu, "Advanced Resolve...", partial(self._resolve, advanced=True))
        self.reset_action = _action(menu, "Reset To Last Resolve...", self._reset)

        menu.addSeparator()
        lock_group = QtGui.QActionGroup(menu)
        self.lock_menu = menu.addMenu("Set Locking To...")
        fn = partial(self._set_lock_type, "no_lock")
        _action(self.lock_menu, "No Locking", fn, "no_lock", lock_group)
        for k, v in lock_types.iteritems():
            fn = partial(self._set_lock_type, k)
            _action(self.lock_menu, "Lock to %s" % v, fn, k, lock_group)

        self.resolve_btn.setPopupMode(QtGui.QToolButton.MenuButtonPopup)
        self.resolve_btn.setDefaultAction(default_action)
        self.resolve_btn.setMenu(menu)
        icon = get_icon("no_lock", as_qicon=True)
        self.resolve_btn.setIcon(icon)
        self.resolve_btn.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)

        btn_pane = create_pane([self.show_effective_request_checkbox,
                                None,
                                self.shell_btn,
                                self.diff_btn,
                                self.resolve_btn],
                               True, compact=True, compact_spacing=0)

        context_pane = create_pane([self.context_table, btn_pane], False,
                                   compact=True, compact_spacing=0)

        self.package_tab = PackageTabWidget(settings=self.settings,
                                            versions_tab=True)

        context_splitter = ConfiguredSplitter(app.config, "layout/splitter/main")
        context_splitter.setOrientation(QtCore.Qt.Vertical)
        context_splitter.addWidget(context_pane)
        context_splitter.addWidget(self.package_tab)
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
        self.show_effective_request_checkbox.stateChanged.connect(
            self._effectiveRequestStateChanged)

        self._set_resolved(False)

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
        success = dlg.resolve(request)
        if success:
            context = dlg.get_context()
            self.set_context(context)
        self.resolved.emit(success)

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
            "implicit_packages":    implicit_strs,
            "default_patch_lock":   context.default_patch_lock.name
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
        self.reset_action.setEnabled(not resolved and bool(self.context))
        self.lock_menu.setEnabled(bool(self.context))
        self.modified.emit(not resolved)

    def _effectiveRequestStateChanged(self, state):
        self.context_table.show_effective_request(state == QtCore.Qt.Checked)

    def _set_lock_type(self, lock_type):
        icon = get_icon(lock_type, as_qicon=True)
        self.resolve_btn.setIcon(icon)
        #self.context_table.set_default_patch_lock(lock_type)
