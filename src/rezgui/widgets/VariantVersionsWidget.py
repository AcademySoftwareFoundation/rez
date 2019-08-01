from Qt import QtCore, QtWidgets
from rezgui.util import create_pane
from rezgui.widgets.VariantVersionsTable import VariantVersionsTable
from rezgui.widgets.PackageLoadingWidget import PackageLoadingWidget
from rezgui.widgets.ChangelogEdit import ChangelogEdit
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rez.utils.formatting import positional_number_string
from rez.vendor.version.version import VersionRange


class VariantVersionsWidget(PackageLoadingWidget, ContextViewMixin):

    closeWindow = QtCore.Signal()

    def __init__(self, context_model=None, reference_variant=None,
                 in_window=False, parent=None):
        """
        Args:
            reference_variant (`Variant`): Used to show the difference between
                two variants.
            in_window (bool): If True, the 'view changelogs' option turns
                into a checkbox, dropping the 'View in window' option.
        """
        super(VariantVersionsWidget, self).__init__(parent)
        ContextViewMixin.__init__(self, context_model)

        self.in_window = in_window
        self.variant = None
        self.reference_variant = reference_variant
        self.pending_changelog_packages = None

        self.label = QtWidgets.QLabel()
        self.changelog_edit = ChangelogEdit()
        self.table = VariantVersionsTable(self.context_model,
                                          reference_variant=reference_variant)

        self.tab = QtWidgets.QTabWidget()
        self.tab.addTab(self.table, "list view")
        self.tab.addTab(self.changelog_edit, "changelogs")
        self.tab.currentChanged.connect(self._tabIndexChanged)

        buttons = [None]
        if self.in_window:
            close_btn = QtWidgets.QPushButton("Close")
            buttons.append(close_btn)
            close_btn.clicked.connect(self._close_window)
        else:
            browse_versions_btn = QtWidgets.QPushButton("Browse Versions...")
            browse_versions_btn.clicked.connect(self._browseVersions)
            buttons.append(browse_versions_btn)

            window_btn = QtWidgets.QPushButton("View In Window...")
            window_btn.clicked.connect(self._view_changelogs_window)
            buttons.append(window_btn)

        btn_pane = create_pane(buttons, True, compact=not self.in_window)
        pane = create_pane([self.label, self.tab, btn_pane], False, compact=True)

        self.set_main_widget(pane)
        self.set_loader_swap_delay(300)
        self.clear()

    def clear(self):
        self.label.setText("no package selected")
        self.table.clear()
        self.pending_changelog_packages = None
        self.setEnabled(False)

    def refresh(self):
        variant = self.variant
        self.variant = None
        self.set_variant(variant)

    def set_variant(self, variant):
        self.tab.setCurrentIndex(0)
        self.stop_loading_packages()
        self.clear()

        self.variant = variant
        if self.variant is None:
            return

        package_paths = self.context_model.packages_path
        if self.variant.wrapped.location not in package_paths:
            txt = "not on the package search path"
            self.label.setText(txt)
            return

        self.setEnabled(True)

        range_ = None
        if self.reference_variant and self.reference_variant.name == variant.name:
            versions = sorted([variant.version, self.reference_variant.version])
            range_ = VersionRange.as_span(*versions)

        self.load_packages(package_paths=package_paths,
                           package_name=variant.name,
                           range_=range_,
                           package_attributes=("timestamp",))

    def set_packages(self, packages):
        self.table._set_variant(self.variant, packages)
        self._update_label()
        self._update_changelogs(packages)
        self.setEnabled(True)

    def _update_label(self):
        diff_num = self.table.get_reference_difference()
        if diff_num is None:
            # normal mode
            if self.table.version_index == 0:
                if self.table.num_versions == 1:
                    txt = "the only package"
                else:
                    txt = "the latest package"
            else:
                nth = positional_number_string(self.table.version_index + 1)
                txt = "the %s latest package" % nth
            if self.table.num_versions > 1:
                txt += " of %d packages" % self.table.num_versions
            txt = "%s is %s" % (self.variant.qualified_package_name, txt)
        else:
            # reference mode - showing difference between two versions
            adj = "ahead" if diff_num > 0 else "behind"
            diff_num = abs(diff_num)
            unit = "version" if diff_num == 1 else "versions"
            txt = "Package is %d %s %s" % (diff_num, unit, adj)

        self.label.setText(txt)

    def _update_changelogs(self, packages):
        # don't actually update until tab is selected - changelogs may get big,
        # we don't want to block up the gui thread unless necessary
        self.pending_changelog_packages = packages
        if self.tab.currentIndex() == 1:
            self._apply_changelogs()

    def _tabIndexChanged(self, index):
        if index == 1:
            self._apply_changelogs()

    def _apply_changelogs(self):
        if self.pending_changelog_packages:
            self.changelog_edit.set_packages(self.pending_changelog_packages)
            self.pending_changelog_packages = None

    def _changelogStateChanged(self, state):
        self._view_changelogs(state == QtCore.Qt.Checked)
        self.refresh()

    def _view_or_hide_changelogs(self):
        enable = (not self.table.view_changelog)
        self._view_changelogs(enable)
        self.refresh()

    def _view_changelogs_window(self):
        from rezgui.dialogs.VariantVersionsDialog import VariantVersionsDialog
        dlg = VariantVersionsDialog(self.context_model, self.variant,
                                    parent=self)
        dlg.exec_()

    def _browseVersions(self):
        from rezgui.dialogs.BrowsePackageDialog import BrowsePackageDialog
        dlg = BrowsePackageDialog(context_model=self.context_model,
                                  package_text=self.variant.qualified_package_name,
                                  close_only=True,
                                  lock_package=True,
                                  parent=self.parentWidget())

        dlg.setWindowTitle("Versions - %s" % self.variant.name)
        dlg.exec_()

    def _close_window(self):
        self.closeWindow.emit()


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
