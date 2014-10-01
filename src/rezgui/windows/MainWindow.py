from rezgui.qt import QtCore, QtGui
from rezgui.objects.App import app
from rezgui.util import add_menu_action
from rezgui.windows.ContextSubWindow import ContextSubWindow
from rez.exceptions import ResolvedContextError
from rez.resolved_context import ResolvedContext
from rez.status import status
from contextlib import contextmanager
from functools import partial
import os.path
import time


class MainWindow(QtGui.QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setWindowTitle("Rez GUI")

        self.mdi = QtGui.QMdiArea(self)
        self.mdi.show()
        self.setCentralWidget(self.mdi)
        self.statusBar().showMessage("")

        file_menu = self.menuBar().addMenu('&File')
        add_menu_action(file_menu, "&New Context", self.new_context)
        add_menu_action(file_menu, "Open &Context...", self._open_context)
        self.recent_contexts_menu = file_menu.addMenu("Open Recent Context")

        if status.context and status.context.load_path:
            menu = file_menu.addMenu("Open Active Context")
            filepath = status.context.load_path
            fn = partial(self.open_context, filepath)
            add_menu_action(file_menu, filepath, fn)

        suites = status.suites
        if suites:
            menu = file_menu.addMenu("Open Context From Active Suite")
            for suite in suites:
                menu2 = menu.addMenu(suite.load_path)
                for context_name in suite.context_names:
                    context = suite.context(context_name)
                    filepath = context.load_path
                    filename = os.path.basename(filepath)
                    label = "%s (%s)" % (context_name, filename)
                    fn = partial(self.open_context, filepath)
                    add_menu_action(menu2, label, fn)

        self.save_context_action = add_menu_action(file_menu, "&Save Context")
        self.save_context_as_action = add_menu_action(file_menu, "Save Context As...")
        file_menu.addSeparator()
        self.quit_action = add_menu_action(file_menu, "Quit", self.close)

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

    def load_context(self, filepath):
        context = None
        busy_cursor = QtGui.QCursor(QtCore.Qt.WaitCursor)

        with self._status("Loading %s..." % filepath):
            QtGui.QApplication.setOverrideCursor(busy_cursor)
            try:
                context = ResolvedContext.load(filepath)
            except ResolvedContextError as e:
                QtGui.QMessageBox.critical(self, "Failed to load context", str(e))
            finally:
                QtGui.QApplication.restoreOverrideCursor()

        if context:
            with self._status("Validating %s..." % filepath):
                QtGui.QApplication.setOverrideCursor(busy_cursor)
                try:
                    context.validate()
                except ResolvedContextError as e:
                    QtGui.QMessageBox.critical(self, "Context validation failure", str(e))
                    context = None
                finally:
                    QtGui.QApplication.restoreOverrideCursor()

        if context:
            app.config.prepend_string_list("most_recent_contexts", filepath,
                                           "max_most_recent_contexts")
        return context

    def new_context(self):
        self._add_context_subwindow()

    def open_context(self, filepath):
        context = self.load_context(filepath)
        if context:
            self._add_context_subwindow(context)

    def _open_context(self):
        filepath = QtGui.QFileDialog.getOpenFileName(
            self, "Open Context", filter="Context files (*.rxt)")
        if filepath:
            self.open_context(str(filepath))

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

        menu = self.recent_contexts_menu
        app.config.sync()
        most_recent = app.config.get_string_list("most_recent_contexts")
        menu.setEnabled(bool(most_recent))
        if most_recent:
            menu.clear()
            for filepath in most_recent:
                fn = partial(self.open_context, filepath)
                add_menu_action(menu, filepath, fn)

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
