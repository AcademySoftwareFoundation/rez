from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane, get_icon, add_locking_submenu, \
    add_menu_action, get_icon_widget
from rezgui.widgets.ContextToolsWidget import ContextToolsWidget
from rezgui.widgets.ContextDetailsWidget import ContextDetailsWidget
from rezgui.widgets.ConfiguredSplitter import ConfiguredSplitter
from rezgui.widgets.ContextTableWidget import ContextTableWidget
from rezgui.widgets.PackageTabWidget import PackageTabWidget
from rezgui.widgets.SettingsWidget import SettingsWidget
from rezgui.widgets.IconButton import IconButton
from rezgui.widgets.ContextResolveTimeLabel import ContextResolveTimeLabel
from rezgui.dialogs.ResolveDialog import ResolveDialog
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.models.ContextModel import ContextModel
from rezgui.objects.App import app
from rez.vendor.schema.schema import Schema, Or
from rez.config import config
from rez.resolved_context import PatchLock
from rez.util import readable_time_duration
from functools import partial
import time


class ContextManagerWidget(QtGui.QWidget, ContextViewMixin):

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

    resolved = QtCore.Signal()
    diffModeChanged = QtCore.Signal()

    def __init__(self, context_model=None, parent=None):
        super(ContextManagerWidget, self).__init__(parent)
        ContextViewMixin.__init__(self, context_model)

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
        self.context_table = ContextTableWidget(self.context_model)
        self.show_effective_request_checkbox = QtGui.QCheckBox("show effective request")

        resolve_time_label = ContextResolveTimeLabel(self.context_model)

        self.time_lock_tbtn = QtGui.QToolButton()
        icon = get_icon("time_lock", as_qicon=True)
        self.time_lock_tbtn.setIcon(icon)

        self.shell_tbtn = QtGui.QToolButton()
        self.shell_tbtn.setToolTip("open shell")
        icon = get_icon("terminal", as_qicon=True)
        self.shell_tbtn.setIcon(icon)

        self.diff_tbtn = QtGui.QToolButton()
        self.diff_tbtn.setToolTip("diff mode")
        icon = get_icon("diff", as_qicon=True)
        self.diff_tbtn.setIcon(icon)
        self.diff_tbtn.setCheckable(True)

        self.lock_tbtn = QtGui.QToolButton()
        self.lock_tbtn.setToolTip("locking")
        icon = get_icon("no_lock", as_qicon=True)
        self.lock_tbtn.setIcon(icon)
        self.lock_tbtn.setPopupMode(QtGui.QToolButton.InstantPopup)
        menu = QtGui.QMenu()
        for lock_type in PatchLock:
            fn = partial(self._set_lock_type, lock_type)
            add_menu_action(menu, lock_type.description, fn, lock_type.name)
        menu.addSeparator()
        add_menu_action(menu, "Remove Explicit Locks", self._removeExplicitLocks)
        self.lock_tbtn.setMenu(menu)

        self.revert_tbtn = QtGui.QToolButton()
        self.revert_tbtn.setToolTip("revert")
        icon = get_icon("revert", as_qicon=True)
        self.revert_tbtn.setIcon(icon)
        self.revert_tbtn.setPopupMode(QtGui.QToolButton.InstantPopup)
        menu = QtGui.QMenu()
        self.revert_action = add_menu_action(menu, "Revert To Last Resolve...",
                                             self._revert_to_last_resolve, "revert")
        self.revert_diff_action = add_menu_action(menu, "Revert To Reference...",
                                                  self._revert_to_diff, "revert_to_diff")
        self.revert_diff_action.setEnabled(False)
        self.revert_tbtn.setMenu(menu)

        resolve_tbtn = QtGui.QToolButton()
        icon = get_icon("resolve", as_qicon=True)
        resolve_tbtn.setIcon(icon)
        resolve_tbtn.setPopupMode(QtGui.QToolButton.MenuButtonPopup)
        menu = QtGui.QMenu()
        default_action = add_menu_action(menu, "Resolve", self._resolve, "resolve")
        add_menu_action(menu, "Advanced Resolve...",
                        partial(self._resolve, advanced=True), "advanced_resolve")
        resolve_tbtn.setDefaultAction(default_action)
        resolve_tbtn.setMenu(menu)

        toolbar = QtGui.QToolBar()
        toolbar.addWidget(resolve_time_label)
        self.time_lock_action = toolbar.addWidget(self.time_lock_tbtn)
        toolbar.addSeparator()
        toolbar.addWidget(self.shell_tbtn)
        toolbar.addWidget(self.diff_tbtn)
        toolbar.addWidget(self.lock_tbtn)
        toolbar.addWidget(self.revert_tbtn)
        toolbar.addWidget(resolve_tbtn)
        self.time_lock_action.setVisible(False)

        self.time_lock_tbtn.setCursor(QtCore.Qt.PointingHandCursor)
        self.shell_tbtn.setCursor(QtCore.Qt.PointingHandCursor)
        self.diff_tbtn.setCursor(QtCore.Qt.PointingHandCursor)
        self.lock_tbtn.setCursor(QtCore.Qt.PointingHandCursor)
        resolve_tbtn.setCursor(QtCore.Qt.PointingHandCursor)

        btn_pane = create_pane([self.show_effective_request_checkbox,
                                None, toolbar],
                               True, compact=True, compact_spacing=0)

        context_pane = create_pane([btn_pane, self.context_table], False,
                                   compact=True, compact_spacing=0)

        self.package_tab = PackageTabWidget(
            self.context_model, versions_tab=True)

        context_splitter = ConfiguredSplitter(app.config, "layout/splitter/main")
        context_splitter.setOrientation(QtCore.Qt.Vertical)
        context_splitter.addWidget(context_pane)
        context_splitter.addWidget(self.package_tab)
        if not context_splitter.apply_saved_layout():
            context_splitter.setStretchFactor(0, 2)
            context_splitter.setStretchFactor(1, 1)

        self.tools_list = ContextToolsWidget(self.context_model)
        self.resolve_details = ContextDetailsWidget(self.context_model)

        self.tab = QtGui.QTabWidget()
        icon = get_icon("context", as_qicon=True)
        self.tab.addTab(context_splitter, icon, "context")
        icon = get_icon("context_settings", as_qicon=True)
        self.tab.addTab(self.settings, icon, "settings")
        icon = get_icon("tools", as_qicon=True)
        self.tab.addTab(self.tools_list, icon, "tools")
        icon = get_icon("info", as_qicon=True)
        self.tab.addTab(self.resolve_details, icon, "resolve details")
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
        self.context_table.variantSelected.connect(self._variantSelected)
        self.shell_tbtn.clicked.connect(self._open_shell)
        self.diff_tbtn.clicked.connect(self._change_diff_mode)
        self.time_lock_tbtn.clicked.connect(self._timelockClicked)
        self.tools_list.toolsChanged.connect(self._updateToolsCount)
        self.show_effective_request_checkbox.stateChanged.connect(
            self._effectiveRequestStateChanged)

        self.refresh()
        self._updateToolsCount()

    def sizeHint(self):
        return QtCore.QSize(800, 500)

    def get_title(self):
        """Returns a string suitable for titling a window containing this widget."""
        return self.context_table.get_title()

    def refresh(self):
        self._contextChanged(ContextModel.CONTEXT_CHANGED)

    def _resolve(self, advanced=False):
        dlg = ResolveDialog(self.context_model, parent=self, advanced=advanced)
        dlg.resolve()  # this updates the model on successful solve
        self.resolved.emit()

    def _changes_prompt(self):
        ret = QtGui.QMessageBox.warning(
            self,
            "The context has been modified.",
            "Your changes will be lost. Are you sure?",
            QtGui.QMessageBox.Ok,
            QtGui.QMessageBox.Cancel)
        return (ret == QtGui.QMessageBox.Ok)

    def _revert_to_last_resolve(self):
        assert self.context_model.can_revert()
        if self._changes_prompt():
            self.context_model.revert()

    def _revert_to_diff(self):
        if self._changes_prompt():
            self.context_table.revert_to_diff()

    def _open_shell(self):
        assert self.context()
        app.execute_shell(context=self.context(), terminal=True)

    def _change_diff_mode(self):
        b = self.diff_tbtn.isChecked()
        self.context_table.set_diff_mode(b)
        self.revert_diff_action.setEnabled(b)
        #self.diff_tbtn.setEnabled(not self.context_model.is_stale())
        self._enable_revert(diff=(not self.context_model.is_stale()))
        self.diffModeChanged.emit()

    def _enable_revert(self, last_resolve=None, diff=None):
        if last_resolve is not None:
            self.revert_action.setEnabled(last_resolve)
        if diff is not None:
            self.revert_diff_action.setEnabled(diff)
        self.revert_tbtn.setEnabled(self.revert_action.isEnabled()
                                    or self.revert_diff_action.isEnabled())

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
        pass
        #self.tab.setTabText(1, "settings*")
        #self.context_table.refresh()
        #self.package_tab.refresh()

    def _settingsChanged(self):
        pass
        #self.tab.setTabText(1, "settings**")
        #self._set_resolved(False)

    def _settingsChangesDiscarded(self):
        pass
        #self.tab.setTabText(1, "settings*")

    def _contextChanged(self, flags=0):
        stale = self.context_model.is_stale()
        context = self.context()
        is_context = bool(context)

        self._enable_revert(last_resolve=self.context_model.can_revert())
        self.diff_tbtn.setEnabled(self.diff_tbtn.isChecked() or not stale)
        self.shell_tbtn.setEnabled(not stale)
        self.lock_tbtn.setEnabled(is_context)

        self.tab.setTabEnabled(2, is_context)
        self.tab.setTabEnabled(3, is_context)
        tab_text = "context*" if stale else "context"
        self.tab.setTabText(0, tab_text)

        if flags & ContextModel.CONTEXT_CHANGED:
            if is_context and context.requested_timestamp:
                t = time.localtime(context.requested_timestamp)
                t_str = time.strftime("%a %b %d %H:%M:%S %Y", t)
                txt = "packages released after %s were ignored" % t_str
                self.time_lock_tbtn.setToolTip(txt)
                self.time_lock_action.setVisible(True)
            else:
                self.time_lock_action.setVisible(False)

        if flags & (ContextModel.LOCKS_CHANGED | ContextModel.CONTEXT_CHANGED):
            lock_type = self.context_model.default_patch_lock
            icon = get_icon(lock_type.name, as_qicon=True)
            self.lock_tbtn.setIcon(icon)

    def _variantSelected(self, variant):
        self.package_tab.set_variant(variant)

    def _effectiveRequestStateChanged(self, state):
        self.context_table.show_effective_request(state == QtCore.Qt.Checked)

    def _timelockClicked(self):
        title = "The resolve is timelocked"
        body = str(self.time_lock_tbtn.toolTip()).capitalize()
        secs = int(time.time()) - self.context().requested_timestamp
        t_str = readable_time_duration(secs)
        body += "\n(%s ago)" % t_str
        QtGui.QMessageBox.information(self, title, body)

    def _set_lock_type(self, lock_type):
        self.context_model.set_default_patch_lock(lock_type)

    def _updateToolsCount(self):
        label = "tools (%d)" % self.tools_list.num_tools()
        self.tab.setTabText(2, label)

    def _removeExplicitLocks(self):
        self.context_model.remove_all_patch_locks()
