from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane, get_icon, add_locking_submenu, add_menu_action
from rezgui.widgets.ContextToolsWidget import ContextToolsWidget
from rezgui.widgets.ContextDetailsWidget import ContextDetailsWidget
from rezgui.widgets.ConfiguredSplitter import ConfiguredSplitter
from rezgui.widgets.ContextTableWidget import ContextTableWidget
from rezgui.widgets.PackageTabWidget import PackageTabWidget
from rezgui.widgets.SettingsWidget import SettingsWidget
from rezgui.widgets.ContextResolveTimeLabel import ContextResolveTimeLabel
from rezgui.dialogs.ResolveDialog import ResolveDialog
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.models.ContextModel import ContextModel
from rezgui.objects.App import app
from rez.vendor.schema.schema import Schema, Or
from rez.config import config
from rez.resolved_context import PatchLock
from functools import partial


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

    # see ContextSubWindow._resolve, it is the reason for this signal
    resolved = QtCore.Signal()

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
        self.diff_btn = QtGui.QPushButton("Diff Mode")
        self.shell_btn = QtGui.QPushButton("Open Shell")

        self.resolve_btn = QtGui.QToolButton()

        menu = QtGui.QMenu()
        default_action = add_menu_action(menu, "Resolve", self._resolve)
        add_menu_action(menu, "Advanced Resolve...", partial(self._resolve, advanced=True))
        self.reset_action = add_menu_action(menu, "Reset To Last Resolve...", self._reset)
        menu.addSeparator()

        self.lock_menu, self.lock_actions = add_locking_submenu(menu, self._set_lock_type)

        self.resolve_btn.setPopupMode(QtGui.QToolButton.MenuButtonPopup)
        self.resolve_btn.setDefaultAction(default_action)
        self.resolve_btn.setMenu(menu)
        self.resolve_btn.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)

        btn_pane = create_pane([self.show_effective_request_checkbox,
                                None,
                                resolve_time_label,
                                self.shell_btn,
                                self.diff_btn,
                                self.resolve_btn],
                               True, compact=True, compact_spacing=0)

        context_pane = create_pane([self.context_table, btn_pane], False,
                                   compact=True, compact_spacing=0)

        self.package_tab = PackageTabWidget(self.context_model, versions_tab=True)

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
        self.context_table.variantSelected.connect(self._variantSelected)
        self.shell_btn.clicked.connect(self._open_shell)
        self.lock_menu.aboutToShow.connect(self._update_lock_menu)
        self.show_effective_request_checkbox.stateChanged.connect(
            self._effectiveRequestStateChanged)

        self.refresh()

    def sizeHint(self):
        return QtCore.QSize(800, 500)

    def refresh(self):
        self._contextChanged(ContextModel.CONTEXT_CHANGED)

    def _resolve(self, advanced=False):
        dlg = ResolveDialog(self.context_model, parent=self, advanced=advanced)
        dlg.resolve()  # this updates the model on successful solve
        self.resolved.emit()

    def _reset(self):
        assert self.context_model.can_revert()
        ret = QtGui.QMessageBox.warning(
            self,
            "The context has been modified.",
            "Your changes will be lost. Are you sure?",
            QtGui.QMessageBox.Ok,
            QtGui.QMessageBox.Cancel)
        if ret == QtGui.QMessageBox.Ok:
            self.context_model.revert()

    def _open_shell(self):
        assert self.context()
        app.execute_shell(context=self.context(), terminal=True)

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
        is_context = bool(self.context())

        self.diff_btn.setEnabled(not stale)
        self.shell_btn.setEnabled(not stale)
        self.reset_action.setEnabled(self.context_model.can_revert())
        self.lock_menu.setEnabled(is_context)

        self.tab.setTabEnabled(2, is_context)
        self.tab.setTabEnabled(3, is_context)
        tab_text = "context*" if stale else "context"
        self.tab.setTabText(0, tab_text)

        if flags & (ContextModel.LOCKS_CHANGED | ContextModel.CONTEXT_CHANGED):
            lock_type = self.context_model.default_patch_lock
            icon = get_icon(lock_type.name, as_qicon=True)
            self.resolve_btn.setIcon(icon)

    def _variantSelected(self, variant):
        self.package_tab.set_variant(variant)

    def _effectiveRequestStateChanged(self, state):
        self.context_table.show_effective_request(state == QtCore.Qt.Checked)

    def _set_lock_type(self, lock_type):
        self.context_model.set_default_patch_lock(lock_type)

    def _update_lock_menu(self):
        action = self.lock_actions[self.context_model.default_patch_lock]
        action.setChecked(True)
