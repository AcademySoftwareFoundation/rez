# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


from Qt import QtCore, QtWidgets
from rezgui.objects.App import app
from rezgui.widgets.ContextManagerWidget import ContextManagerWidget
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.mixins.StoreSizeMixin import StoreSizeMixin
from rezgui.models.ContextModel import ContextModel
import os.path


class ContextSubWindow(QtWidgets.QMdiSubWindow, ContextViewMixin, StoreSizeMixin):
    def __init__(self, context=None, parent=None):
        super(ContextSubWindow, self).__init__(parent)
        context_model = ContextModel(context)
        ContextViewMixin.__init__(self, context_model)
        config_key = "layout/window/context_manager"
        StoreSizeMixin.__init__(self, app.config, config_key)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)

        widget = ContextManagerWidget(context_model)
        widget.diffModeChanged.connect(self._diffModeChanged)
        self.setWidget(widget)
        self._update_window_title()

    def filepath(self):
        return self.context_model.filepath()

    def closeEvent(self, event):
        if self.can_close():
            super(ContextSubWindow, self).closeEvent(event)
            StoreSizeMixin.closeEvent(self, event)
        else:
            event.ignore()

    def diff_with_file(self, filepath):
        """Turn on diff mode and diff against given context.
        """
        self.widget()._diff_with_file(filepath)

    def can_close(self):
        if not self.context_model.is_modified():
            return True

        if self.filepath():
            filename = os.path.basename(self.filepath())
            id_str = "context %r" % filename
            title = "Close %s" % filename
        else:
            id_str = "the context"
            title = "Close context"

        if self.context_model.is_stale():
            ret = QtWidgets.QMessageBox.warning(
                self,
                title,
                "%s is pending a resolve.\n"
                "Close and discard changes?\n"
                "If you close, your changes will be lost."
                % id_str.capitalize(),
                QtWidgets.QMessageBox.Discard,
                QtWidgets.QMessageBox.Cancel)
            return (ret == QtWidgets.QMessageBox.Discard)
        else:
            ret = QtWidgets.QMessageBox.warning(
                self,
                title,
                "Save the changes to %s before closing?\n"
                "If you don't save the context, your changes will be lost."
                % id_str,
                buttons=(
                    QtWidgets.QMessageBox.Save
                    | QtWidgets.QMessageBox.Discard
                    | QtWidgets.QMessageBox.Cancel
                )
            )

            if ret == QtWidgets.QMessageBox.Save:
                if self.is_saveable():
                    self._save_context()
                    return True
                else:
                    assert self.is_save_as_able()
                    return self._save_context_as()
            else:
                return (ret == QtWidgets.QMessageBox.Discard)

        raise RuntimeError("Should never get here")  # NOSONAR

    def is_save_as_able(self):
        return not self.context_model.is_stale()

    def is_saveable(self):
        return bool(self.is_save_as_able() and self.filepath())

    def save_context(self):
        if self.mdiArea().activeSubWindow() != self:
            return
        self._save_context()

    def save_context_as(self):
        if self.mdiArea().activeSubWindow() != self:
            return
        self._save_context_as()

    def copy_request_to_clipboard(self):
        txt = " ".join(self.context_model.request)
        clipboard = app.clipboard()
        clipboard.setText(txt)
        with app.status("Copied request to clipboard"):
            pass

    def copy_resolve_to_clipboard(self):
        context = self.context()
        assert context
        strs = (x.qualified_package_name for x in context.resolved_packages)
        txt = " ".join(strs)
        clipboard = app.clipboard()
        clipboard.setText(txt)
        with app.status("Copied resolve to clipboard"):
            pass

    def _save_context(self):
        assert self.filepath()
        with app.status("Saving %s..." % self.filepath()):
            self.context_model.save(self.filepath())
        return True

    def _save_context_as(self):
        dir_ = os.path.dirname(self.filepath()) if self.filepath() else ""
        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Context", dir_, "Context files (*.rxt)")

        if filepath:
            filepath = str(filepath)
            with app.status("Saving %s..." % filepath):
                self.context_model.save(filepath)

        return bool(filepath)

    def _contextChanged(self, flags=0):
        self._update_window_title()

    def _diffModeChanged(self):
        self._update_window_title()

    def _update_window_title(self):
        title = self.widget().get_title()
        self.setWindowTitle(title)
