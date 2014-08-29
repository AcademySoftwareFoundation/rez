from rezgui.qt import QtCore, QtGui
from rezgui.widgets.ContextManagerWidget import ContextManagerWidget
from rez.exceptions import ResolvedContextError
from rez.resolved_context import ResolvedContext
from contextlib import contextmanager
import os.path
import time


class ContextSubWindow(QtGui.QMdiSubWindow):
    def __init__(self, context=None, parent=None):
        super(ContextSubWindow, self).__init__(parent)
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

    def is_save_as_able(self):
        widget = self.widget()
        return bool(widget.is_resolved and widget.context)

    def is_saveable(self):
        return bool(self.is_save_as_able() and self.filepath)

    def save_context(self):
        if self.mdiArea().activeSubWindow() != self:
            return

        assert self.filepath
        widget = self.widget()
        assert widget.context
        with self.window()._status("Saving %s..." % self.filepath):
            widget.context.save(self.filepath)
        self._set_filepath(self.filepath)

    def save_context_as(self):
        if self.mdiArea().activeSubWindow() != self:
            return

        dir_ = os.path.dirname(self.filepath) if self.filepath else ""
        filepath = QtGui.QFileDialog.getSaveFileName(
            self, "Save Context", dir_, "Context files (*.rxt)")

        if filepath:
            widget = self.widget()
            filepath = str(filepath)
            with self.window()._status("Saving %s..." % filepath):
                widget.context.save(filepath)
            self._set_filepath(filepath)

    def _set_filepath(self, filepath):
        self.filepath = filepath
        self.setWindowTitle(os.path.basename(filepath) + "[*]")
        self.setWindowModified(False)

    def _modified(self):
        self.setWindowModified(True)

    def _resolved(self, success):
        # for some reason the subwindow occasionally loses focus after a resolve
        self.mdiArea().setActiveSubWindow(self)


class MainWindow(QtGui.QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setWindowTitle("Rez GUI")

        self.mdi = QtGui.QMdiArea(self)
        self.mdi.show()
        self.setCentralWidget(self.mdi)

        def _action(menu, label, slot=None):
            action = QtGui.QAction(label, self)
            menu.addAction(action)
            if slot:
                action.triggered.connect(slot)
            return action

        file_menu = self.menuBar().addMenu('&File')
        self.new_context_action = _action(file_menu, "&New Context",
                                          self.new_context)
        file_menu.addSeparator()
        self.open_context_action = _action(file_menu, "Open &Context...",
                                           self._open_context)
        self.save_context_action = _action(file_menu, "&Save Context")
        self.save_context_as_action = _action(file_menu, "Save Context As...")

        file_menu.aboutToShow.connect(self._update_file_menu)

    def cascade(self):
        self.mdi.cascadeSubWindows()

    def new_context(self):
        self._add_context_subwindow()

    def load_context(self, filepath):
        with self._status("Loading %s..." % filepath):
            try:
                context = ResolvedContext.load(filepath)
            except ResolvedContextError as e:
                QtGui.QMessageBox.critical(self, "Failed to load context", str(e))
                return

        self._add_context_subwindow(context)

    def _open_context(self):
        filepath = QtGui.QFileDialog.getOpenFileName(
            self, "Open Context", filter="Context files (*.rxt)")
        if filepath:
            self.load_context(str(filepath))

    def _add_context_subwindow(self, context=None):
        subwindow = ContextSubWindow(context)
        self.mdi.addSubWindow(subwindow)
        self.save_context_action.triggered.connect(subwindow.save_context)
        self.save_context_as_action.triggered.connect(subwindow.save_context_as)
        subwindow.show()

    def _update_file_menu(self):
        context_save = False
        context_save_as = False

        subwindow = self.mdi.activeSubWindow()
        if subwindow:
            if isinstance(subwindow, ContextSubWindow):
                context_save = subwindow.is_saveable()
                context_save_as = subwindow.is_save_as_able()

        self.save_context_action.setEnabled(context_save)
        self.save_context_as_action.setEnabled(context_save_as)

    @contextmanager
    def _status(self, txt):
        t = time.time()
        bar = self.statusBar()
        bar.showMessage(txt)
        yield

        if bar.currentMessage() == txt:
            bar.clearMessage()
            milisecs = int(1000 * (time.time() - t))
            min_display_time = 1000
            if milisecs < min_display_time:
                bar.showMessage(txt, min_display_time - milisecs)
