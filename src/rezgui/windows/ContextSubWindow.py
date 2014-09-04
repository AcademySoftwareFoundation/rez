from rezgui.qt import QtCore, QtGui
from rezgui.widgets.ContextManagerWidget import ContextManagerWidget
from rezgui.mixins.ContextViewMixin import ContextViewMixin
from rezgui.models.ContextModel import ContextModel
import os.path


class ContextSubWindow(QtGui.QMdiSubWindow, ContextViewMixin):
    def __init__(self, context=None, parent=None):
        super(ContextSubWindow, self).__init__(parent)
        context_model = ContextModel(context)
        ContextViewMixin.__init__(self, context_model)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.filepath = None

        if context:
            self._set_filepath(context.load_path)
            title = context.load_path
        else:
            self.setWindowTitle("new context[*]")
            self.setWindowModified(True)

        widget = ContextManagerWidget(context_model)
        self.setWidget(widget)

    def closeEvent(self, event):
        if self.can_close():
            super(ContextSubWindow, self).closeEvent(event)
        else:
            event.ignore()

    def can_close(self):
        if self.isWindowModified():
            if self.filepath:
                filename = os.path.basename(self.filepath)
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
                if ret == QtGui.QMessageBox.Cancel:
                    return False
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
                        return self._save_context()
                    else:
                        assert self.is_save_as_able()
                        return self._save_context_as()
                elif ret == QtGui.QMessageBox.Discard:
                    return True
                else:
                    return False
        return True

    def is_save_as_able(self):
        return not self.context_model.is_stale()

    def is_saveable(self):
        return bool(self.is_save_as_able() and self.filepath)

    def save_context(self):
        if self.mdiArea().activeSubWindow() != self:
            return
        self._save_context()

    def save_context_as(self):
        if self.mdiArea().activeSubWindow() != self:
            return
        self._save_context_as()

    def _save_context(self):
        assert self.filepath
        with self.window()._status("Saving %s..." % self.filepath):
            self.context().save(self.filepath)
        self._set_filepath(self.filepath)
        return True

    def _save_context_as(self):
        dir_ = os.path.dirname(self.filepath) if self.filepath else ""
        filepath = QtGui.QFileDialog.getSaveFileName(
            self, "Save Context", dir_, "Context files (*.rxt)")

        if filepath:
            filepath = str(filepath)
            with self.window()._status("Saving %s..." % filepath):
                self.context().save(filepath)
            self._set_filepath(filepath)

        return bool(filepath)

    def _set_filepath(self, filepath):
        self.filepath = filepath
        self.setWindowTitle(os.path.basename(filepath) + "[*]")
        self.setWindowModified(False)

    def _contextChanged(self, flags=0):
        self.setWindowModified(True)

        if flags & ContextModel.CONTEXT_CHANGED:
            # for some reason the subwindow occasionally loses focus after a resolve
            self.mdiArea().setActiveSubWindow(self)
