from Qt import QtCore, QtWidgets, QtGui
from rezgui.util import create_pane


class FindPopup(QtWidgets.QFrame):

    find = QtCore.Signal(str)

    def __init__(self, pivot_widget, pivot_position=None, words=None,
                 initial_word=None, close_on_find=True, parent=None):
        super(FindPopup, self).__init__(parent)
        self.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Raised)
        self.setWindowFlags(QtCore.Qt.Popup)
        self.close_on_find = close_on_find

        self.edit = QtWidgets.QLineEdit()
        self.btn = QtWidgets.QPushButton("Find")
        create_pane([self.edit, self.btn], True, compact=True,
                    compact_spacing=0, parent_widget=self)
        self.edit.setFocus()

        if initial_word:
            self.edit.setText(initial_word)
            self.edit.selectAll()

        self.completer = None
        if words:
            self.completer = QtWidgets.QCompleter(self)
            self.completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
            self.completions = QtCore.QStringListModel(words, self.completer)
            self.completer.setModel(self.completions)
            self.edit.setCompleter(self.completer)

        pt = getattr(pivot_widget.rect(), pivot_position)()
        global_pt = pivot_widget.mapToGlobal(pt)
        self.move(global_pt)

        self.btn.clicked.connect(self._find)
        self.edit.returnPressed.connect(self._find)

        find_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+F"), self)
        find_shortcut.activated.connect(self._find_again)

    def _find(self):
        word = self.edit.text()
        self.find.emit(word)
        if self.close_on_find:
            self.close()

    def _find_again(self):
        self.edit.selectAll()


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
