from rezgui.qt import QtCore, QtGui
from rezgui.windows.ContextSubWindow import ContextSubWindow
from rez.exceptions import ResolvedContextError
from rez.resolved_context import ResolvedContext
from contextlib import contextmanager
import time


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
        file_menu.addSeparator()
        self.quit_action = _action(file_menu, "Quit", self.close)

        file_menu.aboutToShow.connect(self._update_file_menu)

    def closeEvent(self, event):
        # attempt to close modified contexts first
        subwindows = [x for x in self.mdi.subWindowList() if x.isWindowModified()]
        subwindows += [x for x in self.mdi.subWindowList() if not x.isWindowModified()]

        for subwindow in subwindows:
            if not subwindow.close():
                event.ignore()
                return

        if self.mdi.subWindowList():
            event.ignore()

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
