from rezgui.qt import QtCore, QtGui
from rezgui.util import create_pane, create_toolbutton
from rezgui.widgets.VariantVersionsTable import VariantVersionsTable
from rez.util import positional_number_string


class VariantVersionsWidget(QtGui.QWidget):

    closeWindow = QtCore.Signal()

    def __init__(self, settings, in_window=False, parent=None):
        """
        Args:
            in_window (bool): If True, the 'view changelogs' option turns
                into a checkbox, dropping the 'View in window' option.
        """
        super(VariantVersionsWidget, self).__init__(parent)
        self.settings = settings
        self.in_window = in_window
        self.variant = None

        self.label = QtGui.QLabel()
        self.table = VariantVersionsTable(settings)
        buttons = [None]

        if self.in_window:
            self.changelog_btn = QtGui.QCheckBox("view changelogs")
            self.changelog_btn.stateChanged.connect(self._changelogStateChanged)
            self.changelog_btn.setCheckState(QtCore.Qt.Checked)
            close_btn = QtGui.QPushButton("Close")
            buttons.append(self.changelog_btn)
            buttons.append(close_btn)
            close_btn.clicked.connect(self._close_window)
        else:
            self.changelog_btn, _ = create_toolbutton(
                [("View Changelogs", self._view_or_hide_changelogs),
                 ("View In Window...", self._view_changelogs_window)],
                self)
            buttons.append(self.changelog_btn)

        btn_pane = create_pane(buttons, True, compact=not self.in_window)
        create_pane([self.label, self.table, btn_pane], False, compact=True,
                    parent_widget=self)
        self.clear()

    def clear(self):
        self.label.setText("no package selected")
        self.table.clear()
        self.setEnabled(False)

    def refresh(self):
        variant = self.variant
        self.variant = None
        self.set_variant(variant)
        self.table.refresh()

    def set_variant(self, variant):
        self.table.set_variant(variant)
        if variant == self.variant:
            return

        package_paths = self.settings.get("packages_path")

        if variant is None:
            self.clear()
        else:
            if variant.search_path not in package_paths:
                self.clear()
                txt = "not on the package search path"
                self.label.setText(txt)
            else:
                self.setEnabled(True)
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

            txt = "%s is %s" % (variant.qualified_package_name, txt)
            self.label.setText(txt)

        self.variant = variant

    def _view_changelogs(self, enable):
        self.table.set_view_changelog(enable)
        self.refresh()

    def _changelogStateChanged(self, state):
        self._view_changelogs(state == QtCore.Qt.Checked)

    def _view_or_hide_changelogs(self):
        view_changelogs = False
        label = "View Changelogs"
        if self.changelog_btn.text() == label:
            view_changelogs = True
            label = "Hide Changelogs"

        self.changelog_btn.setText(label)
        self.changelog_btn.defaultAction().setText(label)
        self._view_changelogs(view_changelogs)

    def _view_changelogs_window(self):
        from rezgui.dialogs.VariantVersionsDialog import VariantVersionsDialog
        dlg = VariantVersionsDialog(self.settings, self.variant, self)
        dlg.exec_()

    def _close_window(self):
        self.closeWindow.emit()
