from rezgui.qt import QtCore, QtGui
from rezgui.widgets.ContextManagerWidget import ContextManagerWidget
import os.path


class ContextSubWindow(QtGui.QMdiSubWindow):
    def __init__(self, context=None, parent=None):
        super(ContextSubWindow, self).__init__(parent)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.filepath = None

        widget = ContextManagerWidget()
        if context:
            widget.set_context(context)
            self._set_filepath(context.load_path)
            title = context.load_path
        else:
            self.setWindowTitle("new context[*]")
            self.setWindowModified(True)

        self.setWidget(widget)
        widget.modified.connect(self._modified)
        widget.resolved.connect(self._resolved)

    def closeEvent(self, event):
        if self.can_close():
            super(ContextSubWindow, self).closeEvent(event)
        else:
            event.ignore()

    def can_close(self):
        if self.isWindowModified():
            widget = self.widget()
            if self.filepath:
                filename = os.path.basename(self.filepath)
                id_str = "context %r" % filename
                title = "Close %s" % filename
            else:
                id_str = "the context"
                title = "Close context"

            if widget.is_resolved:
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
            else:
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
        return True

    def is_save_as_able(self):
        widget = self.widget()
        return bool(widget.is_resolved and widget.context)

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
        widget = self.widget()
        assert widget.context
        with self.window()._status("Saving %s..." % self.filepath):
            widget.context.save(self.filepath)
        self._set_filepath(self.filepath)
        return True

    def _save_context_as(self):
        dir_ = os.path.dirname(self.filepath) if self.filepath else ""
        filepath = QtGui.QFileDialog.getSaveFileName(
            self, "Save Context", dir_, "Context files (*.rxt)")

        if filepath:
            widget = self.widget()
            filepath = str(filepath)
            with self.window()._status("Saving %s..." % filepath):
                widget.context.save(filepath)
            self._set_filepath(filepath)

        return bool(filepath)

    def _set_filepath(self, filepath):
        self.filepath = filepath
        self.setWindowTitle(os.path.basename(filepath) + "[*]")
        self.setWindowModified(False)

    def _modified(self):
        self.setWindowModified(True)

    def _resolved(self, success):
        # for some reason the subwindow occasionally loses focus after a resolve
        self.mdiArea().setActiveSubWindow(self)
