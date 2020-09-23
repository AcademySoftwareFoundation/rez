from Qt import QtWidgets
from rezgui.objects.App import app
from rezgui.util import add_menu_action
from rezgui.windows.BrowsePackageSubWindow import BrowsePackageSubWindow
from rezgui.windows.ContextSubWindow import ContextSubWindow
from rezgui.dialogs.AboutDialog import AboutDialog
from contextlib import contextmanager
from functools import partial
import time


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setWindowTitle("Rez GUI")

        self.mdi = QtWidgets.QMdiArea(self)
        self.mdi.show()
        self.setCentralWidget(self.mdi)
        self.statusBar().showMessage("")

        # -- file menu
        file_menu = self.menuBar().addMenu('File')

        add_menu_action(file_menu, "Open Package Browser...",
                        self._open_package_browser)
        file_menu.addSeparator()

        add_menu_action(file_menu, "New Context", self.new_context)
        add_menu_action(file_menu, "Open Context...", self._open_context)
        self.recent_contexts_menu = file_menu.addMenu("Open Recent Context")

        self.save_context_action = add_menu_action(file_menu, "Save Context")
        self.save_context_as_action = add_menu_action(file_menu, "Save Context As...")
        file_menu.addSeparator()
        self.quit_action = add_menu_action(file_menu, "Quit", self.close)

        # -- edit menu
        edit_menu = self.menuBar().addMenu('Edit')
        menu = edit_menu.addMenu("Copy To Clipboard")
        self.copy_request_action = add_menu_action(menu, "Request")
        self.copy_resolve_action = add_menu_action(menu, "Resolve")

        # -- help menu
        help_menu = self.menuBar().addMenu('Help')
        add_menu_action(help_menu, "About", self.about)

        file_menu.aboutToShow.connect(self._update_file_menu)
        edit_menu.aboutToShow.connect(self._update_edit_menu)

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

    def about(self):
        dlg = AboutDialog(self)
        dlg.exec_()

    def _open_package_browser(self):
        subwindow = BrowsePackageSubWindow()
        self.mdi.addSubWindow(subwindow)
        subwindow.show()

    def new_context(self):
        self._add_context_subwindow()

    def open_context(self, filepath):
        context = app.load_context(filepath)
        if context:
            return self._add_context_subwindow(context)
        else:
            return None

    def open_context_and_diff_with_file(self, filepath1, filepath2):
        context = app.load_context(filepath1)
        if not context:
            return None

        subwindow = self._add_context_subwindow(context)
        subwindow.diff_with_file(filepath2)
        return subwindow

    @contextmanager
    def status(self, txt):
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

    def _open_context(self):
        filepath, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open Context", filter="Context files (*.rxt)")
        if filepath:
            self.open_context(str(filepath))

    def _add_context_subwindow(self, context=None):
        subwindow = ContextSubWindow(context)
        self.mdi.addSubWindow(subwindow)
        self.save_context_action.triggered.connect(subwindow.save_context)
        self.save_context_as_action.triggered.connect(subwindow.save_context_as)
        self.copy_request_action.triggered.connect(subwindow.copy_request_to_clipboard)
        self.copy_resolve_action.triggered.connect(subwindow.copy_resolve_to_clipboard)
        subwindow.show()
        return subwindow

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

    def _update_edit_menu(self):
        copy_request = False
        copy_resolve = False

        subwindow = self.mdi.activeSubWindow()
        if subwindow:
            if isinstance(subwindow, ContextSubWindow):
                copy_request = True
                copy_resolve = bool(subwindow.context())

        self.copy_request_action.setEnabled(copy_request)
        self.copy_resolve_action.setEnabled(copy_resolve)


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
