from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane, get_icon, add_menu_action
from rezgui.widgets.ContextToolsWidget import ContextToolsWidget
from rezgui.widgets.ContextDetailsWidget import ContextDetailsWidget
from rezgui.widgets.ConfiguredSplitter import ConfiguredSplitter
from rezgui.widgets.ContextTableWidget import ContextTableWidget
from rezgui.widgets.PackageTabWidget import PackageTabWidget
from rezgui.widgets.ContextSettingsWidget import ContextSettingsWidget
from rezgui.widgets.ContextResolveTimeLabel import ContextResolveTimeLabel
from rezgui.widgets.FindPopup import FindPopup
from rezgui.dialogs.ResolveDialog import ResolveDialog
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.models.ContextModel import ContextModel
from rezgui.objects.App import app
from rez.resolved_context import PatchLock
from rez.utils.formatting import readable_time_duration
from functools import partial
import time


class ContextManagerWidget(QtGui.QWidget, ContextViewMixin):

    diffModeChanged = QtCore.Signal()

    def __init__(self, context_model=None, parent=None):
        super(ContextManagerWidget, self).__init__(parent)
        ContextViewMixin.__init__(self, context_model)

        # widgets
        self.popup = None
        self.context_table = ContextTableWidget(self.context_model)
        self.show_effective_request_checkbox = QtGui.QCheckBox("show effective request")

        resolve_time_label = ContextResolveTimeLabel(self.context_model)

        self.time_lock_tbtn = QtGui.QToolButton()
        icon = get_icon("time_lock", as_qicon=True)
        self.time_lock_tbtn.setIcon(icon)

        self.find_tbtn = QtGui.QToolButton()
        self.find_tbtn.setToolTip("find resolved package")
        icon = get_icon("find", as_qicon=True)
        self.find_tbtn.setIcon(icon)

        self.shell_tbtn = QtGui.QToolButton()
        self.shell_tbtn.setToolTip("open shell")
        icon = get_icon("terminal", as_qicon=True)
        self.shell_tbtn.setIcon(icon)

        self.diff_tbtn = QtGui.QToolButton()
        self.diff_tbtn.setToolTip("enter diff mode")
        self.diff_tbtn.setPopupMode(QtGui.QToolButton.MenuButtonPopup)
        self.diff_menu = QtGui.QMenu()
        self.diff_action = add_menu_action(
            self.diff_menu, "Diff Against Current",
            self._diff_with_last_resolve, "diff")
        self.diff_to_disk_action = add_menu_action(
            self.diff_menu, "Diff Against Disk",
            self._diff_with_disk, "diff_to_disk")
        self.diff_to_other_action = add_menu_action(
            self.diff_menu, "Diff Against Other...",
            self._diff_with_other, "diff_to_other")
        self.diff_tbtn.setMenu(self.diff_menu)
        self.diff_tbtn.setDefaultAction(self.diff_action)

        self.undiff_tbtn = QtGui.QToolButton()
        self.undiff_tbtn.setToolTip("leave diff mode")
        icon = get_icon("diff", as_qicon=True)
        self.undiff_tbtn.setIcon(icon)
        self.undiff_tbtn.setCheckable(True)

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

        self.revert_menu = QtGui.QMenu()
        self.revert_action = add_menu_action(
            self.revert_menu, "Revert To Last Resolve...",
            self._revert_to_last_resolve, "revert")
        self.revert_diff_action = add_menu_action(
            self.revert_menu, "Revert To Reference...",
            self._revert_to_diff, "revert_to_diff")
        self.revert_disk_action = add_menu_action(
            self.revert_menu, "Revert To Disk...",
            self._revert_to_disk, "revert_to_disk")
        self.revert_tbtn.setMenu(self.revert_menu)

        resolve_tbtn = QtGui.QToolButton()
        resolve_tbtn.setPopupMode(QtGui.QToolButton.MenuButtonPopup)
        menu = QtGui.QMenu()
        default_resolve_action = add_menu_action(menu, "Resolve", self._resolve, "resolve")
        add_menu_action(menu, "Advanced Resolve...",
                        partial(self._resolve, advanced=True), "advanced_resolve")
        resolve_tbtn.setDefaultAction(default_resolve_action)
        resolve_tbtn.setMenu(menu)

        toolbar = QtGui.QToolBar()
        toolbar.addWidget(resolve_time_label)
        self.time_lock_tbtn_action = toolbar.addWidget(self.time_lock_tbtn)
        toolbar.addSeparator()
        toolbar.addWidget(self.find_tbtn)
        toolbar.addWidget(self.shell_tbtn)
        self.diff_tbtn_action = toolbar.addWidget(self.diff_tbtn)
        self.undiff_tbtn_action = toolbar.addWidget(self.undiff_tbtn)
        toolbar.addWidget(self.lock_tbtn)
        toolbar.addWidget(self.revert_tbtn)
        toolbar.addWidget(resolve_tbtn)
        self.time_lock_tbtn_action.setVisible(False)
        self.undiff_tbtn_action.setVisible(False)

        self.time_lock_tbtn.setCursor(QtCore.Qt.PointingHandCursor)
        self.find_tbtn.setCursor(QtCore.Qt.PointingHandCursor)
        self.shell_tbtn.setCursor(QtCore.Qt.PointingHandCursor)
        self.diff_tbtn.setCursor(QtCore.Qt.PointingHandCursor)
        self.lock_tbtn.setCursor(QtCore.Qt.PointingHandCursor)
        self.revert_tbtn.setCursor(QtCore.Qt.PointingHandCursor)
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

        self.settings = ContextSettingsWidget(self.context_model)
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

        # shortcuts
        find_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+F"), self)
        find_shortcut.activated.connect(self._search)

        # widget signals
        self.context_table.variantSelected.connect(self._variantSelected)
        self.find_tbtn.clicked.connect(self._search_variant)
        self.shell_tbtn.clicked.connect(self._open_shell)
        self.undiff_tbtn.clicked.connect(self._leave_diff_mode)
        self.time_lock_tbtn.clicked.connect(self._timelockClicked)
        self.tools_list.toolsChanged.connect(self._updateToolsCount)
        self.diff_menu.aboutToShow.connect(self._aboutToShowDiffMenu)
        self.revert_menu.aboutToShow.connect(self._aboutToShowRevertMenu)
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

    def _revert_to_disk(self):
        if self._changes_prompt():
            self.context_table.revert_to_disk()

    def _open_shell(self):
        assert self.context()
        app.execute_shell(context=self.context(), terminal=True)

    def _leave_diff_mode(self):
        self.context_table.leave_diff_mode()
        self._change_diff_mode(False)

    def _diff_with_last_resolve(self):
        self.context_table.enter_diff_mode()
        self._change_diff_mode(True)

    def _diff_with_disk(self):
        filepath = self.context_model.filepath()
        self._diff_with_file(filepath)

    def _diff_with_other(self):
        filepath = QtGui.QFileDialog.getOpenFileName(
            self, "Open Context", filter="Context files (*.rxt)")
        if filepath:
            self._diff_with_file(str(filepath))

    def _diff_with_file(self, filepath):
        assert filepath
        disk_context = app.load_context(filepath)
        model = ContextModel(disk_context)
        self.context_table.enter_diff_mode(model)
        self._change_diff_mode(True)

    def _change_diff_mode(self, enabled):
        self.undiff_tbtn.setChecked(enabled)
        self.diff_tbtn_action.setVisible(not enabled)
        self.undiff_tbtn_action.setVisible(enabled)
        self.diffModeChanged.emit()

    def _aboutToShowDiffMenu(self):
        stale = self.context_model.is_stale()
        self.diff_action.setEnabled(not stale)
        self.diff_to_other_action.setEnabled(not stale)
        self.diff_to_disk_action.setEnabled(bool(self.context_model.filepath())
                                            and not stale)

    def _aboutToShowRevertMenu(self):
        model = self.context_model
        self.revert_action.setEnabled(model.can_revert())
        self.revert_disk_action.setEnabled(bool(model.filepath())
                                           and model.is_modified())
        self.revert_diff_action.setEnabled(self.context_table.diff_mode
                                           and self.context_table.diff_from_source
                                           and not model.is_stale())

    def _contextChanged(self, flags=0):
        stale = self.context_model.is_stale()
        context = self.context()
        is_context = bool(context)

        self.diff_action.setEnabled(not stale)
        self.diff_tbtn.setEnabled(not stale)
        self.undiff_tbtn.setEnabled(not stale)
        self.shell_tbtn.setEnabled(not stale)
        self.lock_tbtn.setEnabled(is_context)
        self.find_tbtn.setEnabled(is_context)

        self.tab.setTabEnabled(2, is_context)
        self.tab.setTabEnabled(3, is_context)
        tab_text = "context*" if stale else "context"
        self.tab.setTabText(0, tab_text)

        context_changed = (flags & ContextModel.CONTEXT_CHANGED)

        if context_changed:
            if is_context and context.requested_timestamp:
                t = time.localtime(context.requested_timestamp)
                t_str = time.strftime("%a %b %d %H:%M:%S %Y", t)
                txt = "packages released after %s were ignored" % t_str
                self.time_lock_tbtn.setToolTip(txt)
                self.time_lock_tbtn_action.setVisible(True)
            else:
                self.time_lock_tbtn_action.setVisible(False)

        settings_modified = ((flags & ContextModel.PACKAGES_PATH_CHANGED)
                             and not context_changed)
        label = "settings*" if settings_modified else "settings"
        self.tab.setTabText(1, label)

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

    def _search(self):
        tab_index = self.tab.currentIndex()
        if tab_index == 0:
            self._search_variant()
        elif tab_index == 3:
            self.resolve_details.search()

    def _search_variant(self):
        context = self.context()
        if not context:
            return

        words = [x.name for x in context.resolved_packages]
        self.popup = FindPopup(self.find_tbtn, "bottomLeft", words, parent=self)
        self.popup.find.connect(self.context_table.select_variant)
        self.popup.show()


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
