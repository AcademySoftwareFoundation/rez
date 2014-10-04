from rezgui.qt import QtCore, QtGui
from rezgui.objects.App import app
from rezgui.widgets.ContextManagerWidget import ContextManagerWidget
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.mixins.StoreSizeMixin import StoreSizeMixin
from rezgui.models.ContextModel import ContextModel
import os.path


class ContextSubWindow(QtGui.QMdiSubWindow, ContextViewMixin, StoreSizeMixin):
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
            ret = QtGui.QMessageBox.warning(
                self,
                title,
                "%s is pending a resolve.\n"
                "Close and discard changes?\n"
                "If you close, your changes will be lost."
                % id_str.capitalize(),
                QtGui.QMessageBox.Discard,
                QtGui.QMessageBox.Cancel)
            return (ret == QtGui.QMessageBox.Discard)
        else:
            ret = QtGui.QMessageBox.warning(
                self,
                title,
                "Save the changes to %s before closing?\n"
                "If you don't save the context, your changes will be lost."
                % id_str,
                QtGui.QMessageBox.Save,
                QtGui.QMessageBox.Discard,
                QtGui.QMessageBox.Cancel)
            if ret == QtGui.QMessageBox.Save:
                if self.is_saveable():
                    self._save_context()
                    return True
                else:
                    assert self.is_save_as_able()
                    return self._save_context_as()
            else:
                return (ret == QtGui.QMessageBox.Discard)

        # should never get here
        assert False
        return False

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

    def _save_context(self):
        assert self.filepath()
        with self.window()._status("Saving %s..." % self.filepath()):
            self.context_model.save(self.filepath())
        return True

    def _save_context_as(self):
        dir_ = os.path.dirname(self.filepath()) if self.filepath() else ""
        filepath = QtGui.QFileDialog.getSaveFileName(
            self, "Save Context", dir_, "Context files (*.rxt)")

        if filepath:
            filepath = str(filepath)
            with self.window()._status("Saving %s..." % filepath):
                self.context_model.save(filepath)

        return bool(filepath)

    def _contextChanged(self, flags=0):
        self._update_window_title()

    def _diffModeChanged(self):
        self._update_window_title()

    def _update_window_title(self):
        title = self.widget().get_title()
        self.setWindowTitle(title)
